"""Transactional email service for Lilian.

Why this exists as a thin wrapper instead of calling Resend directly from
endpoints:

- Centralises the API key read (fail-fast if missing) and the transport
  selection (real HTTP vs. log-stub for local dev).
- Endpoints only know about ``send_email(to, template, data)`` — they do
  not import HTTP clients or know about Resend's payload shape.
- Makes it trivial to swap Resend for Sendgrid, SES, Postmark, etc. by
  changing one file.

Templates are stored as plain functions returning ``(subject, html, text)``
tuples. We do not use a templating engine — the templates are small enough
that string formatting is clearer and avoids an extra dependency.

If ``RESEND_API_KEY`` is unset, the service logs the rendered email and
returns ``{"status": "stub"}`` so local development and CI never need a
real key.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Callable

import httpx

logger = logging.getLogger("lilian.email")


# ---------------------------------------------------------------------------
# Template registry
# ---------------------------------------------------------------------------

TemplateFn = Callable[[dict[str, Any]], tuple[str, str, str]]


@dataclass(frozen=True)
class _Template:
    name: str
    render: TemplateFn


def _welcome(data: dict[str, Any]) -> tuple[str, str, str]:
    name = data.get("full_name") or "abogado/a"
    login_url = data.get("login_url", "https://lil-i-5tz56uhov-jorgeguerrerohidalgo710.vercel.app/auth/login")
    subject = "Bienvenido/a a Lilian"
    html = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 560px; margin: 0 auto; padding: 24px;">
      <h1 style="color: #0f172a; font-size: 24px; margin-bottom: 16px;">¡Hola, {name}!</h1>
      <p style="color: #334155; font-size: 16px; line-height: 1.5;">
        Te damos la bienvenida a <strong>Lilian</strong>, tu copiloto legal con IA para documentos jurídicos chilenos.
      </p>
      <p style="color: #334155; font-size: 16px; line-height: 1.5;">
        Con Lilian puedes revisar contratos, detectar riesgos y generar análisis en segundos.
      </p>
      <p style="margin: 24px 0;">
        <a href="{login_url}" style="background: #0f172a; color: #fff; padding: 12px 20px; border-radius: 8px; text-decoration: none; font-weight: 600;">
          Iniciar sesión
        </a>
      </p>
      <p style="color: #64748b; font-size: 14px;">Si tienes preguntas, responde este correo.</p>
    </div>
    """.strip()
    text = (
        f"¡Hola, {name}!\n\n"
        f"Bienvenido/a a Lilian. Empieza a revisar contratos con IA en minutos:\n"
        f"{login_url}\n"
    )
    return subject, html, text


def _email_verification(data: dict[str, Any]) -> tuple[str, str, str]:
    """S1.1 — confirm the user owns the email they signed up with.

    The ``verify_url`` is the link rendered into the email. The frontend
    route ``/auth/verify-email?token=…`` immediately calls
    ``POST /api/v1/auth/verify-email`` to mark the user verified and then
    redirects to /auth/login.
    """
    name = data.get("full_name") or "abogado/a"
    verify_url = data.get(
        "verify_url",
        "https://lil-i-5tz56uhov-jorgeguerrerohidalgo710.vercel.app/auth/login",
    )
    subject = "Confirma tu correo en Lilian"
    html = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 560px; margin: 0 auto; padding: 24px;">
      <h1 style="color: #0f172a; font-size: 24px; margin-bottom: 16px;">Confirma tu correo</h1>
      <p style="color: #334155; font-size: 16px; line-height: 1.5;">Hola {name},</p>
      <p style="color: #334155; font-size: 16px; line-height: 1.5;">
        Para activar tu cuenta en Lilian, confirma tu correo haciendo clic en el botón:
      </p>
      <p style="margin: 24px 0;">
        <a href="{verify_url}" style="background: #0f172a; color: #fff; padding: 12px 20px; border-radius: 8px; text-decoration: none; font-weight: 600;">
          Confirmar correo
        </a>
      </p>
      <p style="color: #64748b; font-size: 14px;">
        Si no creaste esta cuenta, puedes ignorar este mensaje.
      </p>
    </div>
    """.strip()
    text = (
        f"Hola {name},\n\n"
        f"Confirma tu correo en Lilian para activar tu cuenta:\n{verify_url}\n"
    )
    return subject, html, text


def _payment_received(data: dict[str, Any]) -> tuple[str, str, str]:
    name = data.get("full_name") or "abogado/a"
    plan = data.get("plan_name", "tu plan")
    amount = data.get("amount", "")
    currency = data.get("currency", "CLP")
    invoice_url = data.get("invoice_url", "")
    subject = f"Confirmación de pago — Plan {plan}"
    amount_str = f"{amount} {currency}" if amount else ""
    html = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 560px; margin: 0 auto; padding: 24px;">
      <h1 style="color: #0f172a; font-size: 24px; margin-bottom: 16px;">Pago confirmado</h1>
      <p style="color: #334155; font-size: 16px; line-height: 1.5;">Hola {name},</p>
      <p style="color: #334155; font-size: 16px; line-height: 1.5;">
        Recibimos tu pago por el plan <strong>{plan}</strong>{(' por ' + amount_str) if amount_str else ''}.
        Tu suscripción está activa.
      </p>
      {f'<p style="margin: 24px 0;"><a href="{invoice_url}" style="background: #0f172a; color: #fff; padding: 10px 18px; border-radius: 8px; text-decoration: none;">Descargar boleta</a></p>' if invoice_url else ''}
      <p style="color: #64748b; font-size: 14px;">Gracias por confiar en Lilian.</p>
    </div>
    """.strip()
    text = (
        f"Hola {name},\n\n"
        f"Pago confirmado del plan {plan}"
        + (f" por {amount_str}" if amount_str else "")
        + ".\n"
        + (f"Descarga tu boleta: {invoice_url}\n" if invoice_url else "")
    )
    return subject, html, text


def _payment_failed(data: dict[str, Any]) -> tuple[str, str, str]:
    name = data.get("full_name") or "abogado/a"
    update_url = data.get("update_payment_url", "https://lil-i-5tz56uhov-jorgeguerrerohidalgo710.vercel.app/dashboard/billing")
    subject = "No pudimos procesar tu pago"
    html = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 560px; margin: 0 auto; padding: 24px;">
      <h1 style="color: #b91c1c; font-size: 24px; margin-bottom: 16px;">Problema con tu pago</h1>
      <p style="color: #334155; font-size: 16px; line-height: 1.5;">Hola {name},</p>
      <p style="color: #334155; font-size: 16px; line-height: 1.5;">
        No pudimos procesar el cobro de tu suscripción. Tu tarjeta fue rechazada o el cargo falló.
      </p>
      <p style="color: #334155; font-size: 16px; line-height: 1.5;">
        Para evitar que tu cuenta sea suspendida, actualiza tu método de pago.
      </p>
      <p style="margin: 24px 0;">
        <a href="{update_url}" style="background: #b91c1c; color: #fff; padding: 12px 20px; border-radius: 8px; text-decoration: none; font-weight: 600;">
          Actualizar método de pago
        </a>
      </p>
    </div>
    """.strip()
    text = (
        f"Hola {name},\n\n"
        f"No pudimos procesar tu pago. Actualízalo aquí:\n{update_url}\n"
    )
    return subject, html, text


def _trial_expiring(data: dict[str, Any]) -> tuple[str, str, str]:
    name = data.get("full_name") or "abogado/a"
    days_left = data.get("days_left", 3)
    upgrade_url = data.get("upgrade_url", "https://lil-i-5tz56uhov-jorgeguerrerohidalgo710.vercel.app/pricing")
    subject = f"Tu prueba termina en {days_left} días"
    html = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 560px; margin: 0 auto; padding: 24px;">
      <h1 style="color: #0f172a; font-size: 24px; margin-bottom: 16px;">Quedan {days_left} días</h1>
      <p style="color: #334155; font-size: 16px; line-height: 1.5;">Hola {name},</p>
      <p style="color: #334155; font-size: 16px; line-height: 1.5;">
        Tu periodo de prueba en Lilian termina en {days_left} días.
        Para mantener tu acceso, elige un plan.
      </p>
      <p style="margin: 24px 0;">
        <a href="{upgrade_url}" style="background: #0f172a; color: #fff; padding: 12px 20px; border-radius: 8px; text-decoration: none; font-weight: 600;">
          Ver planes
        </a>
      </p>
    </div>
    """.strip()
    text = (
        f"Hola {name},\n\n"
        f"Tu prueba termina en {days_left} días. Elige un plan:\n{upgrade_url}\n"
    )
    return subject, html, text


def _plan_limit_reached(data: dict[str, Any]) -> tuple[str, str, str]:
    name = data.get("full_name") or "abogado/a"
    resource = data.get("resource", "documentos")
    limit = data.get("limit", "")
    upgrade_url = data.get("upgrade_url", "https://lil-i-5tz56uhov-jorgeguerrerohidalgo710.vercel.app/pricing")
    subject = f"Alcanzaste el límite de {resource} de tu plan"
    html = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 560px; margin: 0 auto; padding: 24px;">
      <h1 style="color: #b45309; font-size: 24px; margin-bottom: 16px;">Límite del plan alcanzado</h1>
      <p style="color: #334155; font-size: 16px; line-height: 1.5;">Hola {name},</p>
      <p style="color: #334155; font-size: 16px; line-height: 1.5;">
        Alcanzaste el límite de {resource}{(' (' + str(limit) + ')') if limit else ''} de tu plan actual.
        Sube de plan para seguir trabajando sin interrupciones.
      </p>
      <p style="margin: 24px 0;">
        <a href="{upgrade_url}" style="background: #b45309; color: #fff; padding: 12px 20px; border-radius: 8px; text-decoration: none; font-weight: 600;">
          Subir de plan
        </a>
      </p>
    </div>
    """.strip()
    text = (
        f"Hola {name},\n\n"
        f"Alcanzaste el límite de {resource} de tu plan"
        + (f" ({limit})" if limit else "")
        + f". Sube de plan aquí: {upgrade_url}\n"
    )
    return subject, html, text


def _drip_no_upload(data: dict[str, Any]) -> tuple[str, str, str]:
    """S6.1 — sent 24h after signup if the user hasn't uploaded a document."""
    name = data.get("full_name") or "abogado/a"
    upload_url = data.get(
        "upload_url",
        "https://lil-i-5tz56uhov-jorgeguerrerohidalgo710.vercel.app/matters/new",
    )
    subject = "¿Aún no subes tu primer contrato?"
    html = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 560px; margin: 0 auto; padding: 24px;">
      <h1 style="color: #0f172a; font-size: 24px; margin-bottom: 16px;">Hola, {name}</h1>
      <p style="color: #334155; font-size: 16px; line-height: 1.5;">
        Ayer te uniste a Lilian, pero todavía no hemos visto tu primer contrato. Sabemos lo
        difícil que es empezar — aquí va el paso más corto al valor real:
      </p>
      <ol style="color: #334155; font-size: 16px; line-height: 1.6;">
        <li>Sube un PDF, DOCX o TXT.</li>
        <li>Espera ~30 segundos mientras Lilian lo analiza.</li>
        <li>Recibe riesgos, plazos y referencias legales listos para compartir.</li>
      </ol>
      <p style="margin: 24px 0;">
        <a href="{upload_url}" style="background: #0f172a; color: #fff; padding: 12px 20px; border-radius: 8px; text-decoration: none; font-weight: 600;">
          Subir mi primer contrato
        </a>
      </p>
      <p style="color: #64748b; font-size: 14px;">
        ¿Tienes dudas? Responde este correo y te ayudamos.
      </p>
    </div>
    """.strip()
    text = (
        f"Hola, {name}\n\n"
        f"Ayer te uniste a Lilian. Sube tu primer contrato y mira el análisis:\n{upload_url}\n"
    )
    return subject, html, text


def _drip_no_analysis(data: dict[str, Any]) -> tuple[str, str, str]:
    """S6.1 — sent 3 days after the first upload if no analysis has run yet."""
    name = data.get("full_name") or "abogado/a"
    matter_url = data.get(
        "matter_url",
        "https://lil-i-5tz56uhov-jorgeguerrerohidalgo710.vercel.app/matters",
    )
    subject = "Ya subiste un contrato — falta un clic"
    html = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 560px; margin: 0 auto; padding: 24px;">
      <h1 style="color: #0f172a; font-size: 24px; margin-bottom: 16px;">Ya casi, {name}</h1>
      <p style="color: #334155; font-size: 16px; line-height: 1.5;">
        Detectamos que subiste documentos pero todavía no lanzas el análisis. Es un solo clic
        y en 30–60 segundos tienes el informe ejecutivo:
      </p>
      <p style="margin: 24px 0;">
        <a href="{matter_url}" style="background: #0f172a; color: #fff; padding: 12px 20px; border-radius: 8px; text-decoration: none; font-weight: 600;">
          Iniciar análisis ahora
        </a>
      </p>
      <p style="color: #64748b; font-size: 14px;">
        El análisis extrae cláusulas, riesgos, plazos y citas legales chilenas.
      </p>
    </div>
    """.strip()
    text = (
        f"Hola, {name}\n\n"
        f"Subiste documentos pero falta el clic para analizar. Hazlo aquí:\n{matter_url}\n"
    )
    return subject, html, text


def _drip_success_story(data: dict[str, Any]) -> tuple[str, str, str]:
    """S6.1 — sent 7 days after signup: light social proof / success story."""
    name = data.get("full_name") or "abogado/a"
    login_url = data.get(
        "login_url",
        "https://lil-i-5tz56uhov-jorgeguerrerohidalgo710.vercel.app/auth/login",
    )
    subject = "Cómo otros equipos usan Lilian"
    html = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 560px; margin: 0 auto; padding: 24px;">
      <h1 style="color: #0f172a; font-size: 24px; margin-bottom: 16px;">Una semana con Lilian</h1>
      <p style="color: #334155; font-size: 16px; line-height: 1.5;">Hola {name},</p>
      <p style="color: #334155; font-size: 16px; line-height: 1.5;">
        Equipos legales como el tuyo están usando Lilian para revisar contratos de
        arriendo, laborales y comerciales — y han reducido el tiempo de revisión de
        horas a minutos.
      </p>
      <p style="color: #334155; font-size: 16px; line-height: 1.5;">
        ¿Ya probaste generar un informe con citas legales? Es lo que más valor entrega
        a tus clientes.
      </p>
      <p style="margin: 24px 0;">
        <a href="{login_url}" style="background: #0f172a; color: #fff; padding: 12px 20px; border-radius: 8px; text-decoration: none; font-weight: 600;">
          Volver a Lilian
        </a>
      </p>
    </div>
    """.strip()
    text = (
        f"Hola, {name}\n\n"
        f"Ya llevas una semana en Lilian. Sigue explorando:\n{login_url}\n"
    )
    return subject, html, text


def _drip_trial_expiring_30d(data: dict[str, Any]) -> tuple[str, str, str]:
    """S6.1 — sent 30 days after signup to users still on the free plan.

    This is a long-window upgrade nudge that complements the short
    ``trial_expiring`` template (which fires near a real trial end).
    """
    name = data.get("full_name") or "abogado/a"
    upgrade_url = data.get(
        "upgrade_url",
        "https://lil-i-5tz56uhov-jorgeguerrerohidalgo710.vercel.app/pricing",
    )
    subject = "30 días con Lilian — listo para más"
    html = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 560px; margin: 0 auto; padding: 24px;">
      <h1 style="color: #0f172a; font-size: 24px; margin-bottom: 16px;">¡30 días!</h1>
      <p style="color: #334155; font-size: 16px; line-height: 1.5;">Hola {name},</p>
      <p style="color: #334155; font-size: 16px; line-height: 1.5;">
        llevas un mes con Lilian y ya conoces el flujo básico. Si lo estás usando
        a diario, un plan de pago te da más documentos, más análisis y la
        posibilidad de invitar a tu equipo.
      </p>
      <p style="margin: 24px 0;">
        <a href="{upgrade_url}" style="background: #0f172a; color: #fff; padding: 12px 20px; border-radius: 8px; text-decoration: none; font-weight: 600;">
          Ver planes
        </a>
      </p>
    </div>
    """.strip()
    text = (
        f"Hola, {name}\n\n"
        f"Llevas 30 días con Lilian. Conoce los planes:\n{upgrade_url}\n"
    )
    return subject, html, text


def _invitation_received(data: dict[str, Any]) -> tuple[str, str, str]:
    """S6.3 — sent when an owner/admin invites a colleague."""
    name = data.get("full_name") or "colega"
    inviter = data.get("inviter_name") or "Un miembro"
    org_name = data.get("organization_name") or "tu organización"
    role = (data.get("role") or "LAWYER").lower()
    accept_url = data.get("accept_url") or "https://lil-i-5tz56uhov-jorgeguerrerohidalgo710.vercel.app/auth/login"
    subject = f"{inviter} te invitó a {org_name} en Lilian"
    html = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 560px; margin: 0 auto; padding: 24px;">
      <h1 style="color: #0f172a; font-size: 24px; margin-bottom: 16px;">Te invitaron a Lilian</h1>
      <p style="color: #334155; font-size: 16px; line-height: 1.5;">Hola {name},</p>
      <p style="color: #334155; font-size: 16px; line-height: 1.5;">
        {inviter} te invitó a unirte a <strong>{org_name}</strong> en Lilian con el rol de <strong>{role}</strong>.
      </p>
      <p style="margin: 24px 0;">
        <a href="{accept_url}" style="background: #0f172a; color: #fff; padding: 12px 20px; border-radius: 8px; text-decoration: none; font-weight: 600;">
          Aceptar invitación
        </a>
      </p>
      <p style="color: #64748b; font-size: 14px;">
        El enlace vence en 14 días. Si no esperabas este correo, puedes ignorarlo.
      </p>
    </div>
    """.strip()
    text = (
        f"Hola {name},\n\n"
        f"{inviter} te invitó a {org_name} en Lilian.\n"
        f"Acepta aquí: {accept_url}\n"
    )
    return subject, html, text


def _support_ticket_received(data: dict[str, Any]) -> tuple[str, str, str]:
    """S6.5 — internal notification sent to the support inbox when a user
    files a ticket from the floating widget."""
    ticket_id = data.get("ticket_id", "—")
    subject = data.get("subject") or "(sin asunto)"
    body = data.get("body") or ""
    user_email = data.get("user_email") or "(no email)"
    user_id = data.get("user_id") or "(invitado)"
    subject_line = f"[Soporte #{ticket_id}] {subject}"
    html = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 560px; margin: 0 auto; padding: 24px;">
      <h1 style="color: #0f172a; font-size: 22px; margin-bottom: 12px;">Nuevo ticket de soporte</h1>
      <p style="color: #334155; font-size: 14px; line-height: 1.5;"><strong>De:</strong> {user_email} (id={user_id})</p>
      <p style="color: #334155; font-size: 14px; line-height: 1.5;"><strong>Asunto:</strong> {subject}</p>
      <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 16px 0;" />
      <pre style="white-space: pre-wrap; font-family: inherit; color: #334155; font-size: 14px; line-height: 1.5;">{body}</pre>
    </div>
    """.strip()
    text = (
        f"Nuevo ticket #{ticket_id}\n"
        f"De: {user_email} (id={user_id})\n"
        f"Asunto: {subject}\n\n"
        f"{body}\n"
    )
    return subject_line, html, text


_TEMPLATES: dict[str, TemplateFn] = {
    "welcome": _welcome,
    "email_verification": _email_verification,
    "payment_received": _payment_received,
    "payment_failed": _payment_failed,
    "trial_expiring": _trial_expiring,
    "plan_limit_reached": _plan_limit_reached,
    "drip_no_upload": _drip_no_upload,
    "drip_no_analysis": _drip_no_analysis,
    "drip_success_story": _drip_success_story,
    "drip_trial_expiring_30d": _drip_trial_expiring_30d,
    "invitation_received": _invitation_received,
    "support_ticket_received": _support_ticket_received,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class EmailNotConfigured(RuntimeError):
    """Raised when ``RESEND_API_KEY`` is missing and the caller demanded a
    real send (i.e. did not pass ``allow_stub=True``).
    """


def send_email(
    to: str | list[str],
    template: str,
    data: dict[str, Any] | None = None,
    *,
    from_email: str | None = None,
    from_name: str | None = None,
    allow_stub: bool = True,
) -> dict[str, Any]:
    """Send a transactional email by template name.

    Args:
        to: Recipient email or list of emails.
        template: One of the keys in ``_TEMPLATES`` (e.g. ``"welcome"``).
        data: Dict passed to the template renderer.
        from_email: Override ``EMAIL_FROM_ADDRESS`` for this call only.
        from_name: Override ``EMAIL_FROM_NAME`` for this call only.
        allow_stub: If True (default) and ``RESEND_API_KEY`` is unset, the
            email is logged instead of sent and ``{"status": "stub"}`` is
            returned. If False, ``EmailNotConfigured`` is raised.

    Returns:
        A dict with at least ``status`` (``"sent"`` or ``"stub"``) and the
        Resend message id when applicable.

    Raises:
        EmailNotConfigured: when ``allow_stub=False`` and no API key is set.
        ValueError: when ``template`` is unknown.
        httpx.HTTPError: when the upstream Resend call fails.
    """
    if template not in _TEMPLATES:
        raise ValueError(f"Unknown email template: {template!r}")

    payload = data or {}
    subject, html, text = _TEMPLATES[template](payload)

    recipients = [to] if isinstance(to, str) else list(to)

    api_key = os.getenv("RESEND_API_KEY")
    from_addr = from_email or os.getenv("EMAIL_FROM_ADDRESS", "noreply@lilian.cl")
    from_label = from_name or os.getenv("EMAIL_FROM_NAME", "Lilian")

    if not api_key:
        if not allow_stub:
            raise EmailNotConfigured(
                "RESEND_API_KEY is not set; cannot send real email. "
                "Set the env var or pass allow_stub=True to log instead."
            )
        logger.info(
            "[email-stub] to=%s template=%s subject=%r",
            recipients,
            template,
            subject,
        )
        logger.debug("[email-stub] body text=\n%s", text)
        return {"status": "stub", "to": recipients, "subject": subject}

    body = {
        "from": f"{from_label} <{from_addr}>",
        "to": recipients,
        "subject": subject,
        "html": html,
        "text": text,
    }
    try:
        resp = httpx.post(
            "https://api.resend.com/emails",
            json=body,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10.0,
        )
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        logger.error(
            "Resend send failed to=%s template=%s error=%s",
            recipients,
            template,
            exc,
        )
        raise

    result = resp.json() if resp.content else {}
    message_id = result.get("id")
    logger.info(
        "email sent to=%s template=%s message_id=%s",
        recipients,
        template,
        message_id,
    )
    return {"status": "sent", "id": message_id, "to": recipients, "subject": subject}


def is_configured() -> bool:
    """Return True if a real email backend (Resend) is configured."""
    return bool(os.getenv("RESEND_API_KEY"))


# ---------------------------------------------------------------------------
# S6.1 — onboarding drip campaigns
# ---------------------------------------------------------------------------
#
# The drip logic is intentionally simple: the admin endpoint
# ``POST /admin/trigger-drip`` walks the user table, computes the
# relevant time window per event, and calls ``send_drip(user, event)``
# when the conditions match. We do not need a full scheduler because
# the plan calls for a manual / cron-equivalent trigger, not a real
# production scheduler (see plan).
#
# Each branch maps to one of the templates registered above and is
# gated on a single predicate so the admin endpoint stays auditable.

DripEvent = str  # "signup" | "no_upload_24h" | "no_analysis_3d" | "success_story_7d" | "trial_expiring_30d"


def _user_email_context(user) -> dict[str, Any]:
    """Build the ``data`` dict passed to the drip template for ``user``."""
    frontend_base = os.getenv(
        "FRONTEND_BASE_URL",
        "https://lil-i-5tz56uhov-jorgeguerrerohidalgo710.vercel.app",
    )
    return {
        "full_name": getattr(user, "full_name", None),
        "login_url": f"{frontend_base}/auth/login",
        "upload_url": f"{frontend_base}/matters/new",
        "matter_url": f"{frontend_base}/matters",
        "upgrade_url": f"{frontend_base}/pricing",
    }


def send_drip(user, event: DripEvent) -> dict[str, Any]:
    """Send an onboarding drip email to ``user`` for ``event``.

    Args:
        user: A SQLAlchemy ``User`` instance with ``email``, ``full_name``,
            ``id``, and ``created_at`` columns populated.
        event: One of ``signup``, ``no_upload_24h``, ``no_analysis_3d``,
            ``success_story_7d``, ``trial_expiring_30d``.

    Returns:
        The dict returned by ``send_email`` (status, id, …). Raises
        ``ValueError`` for unknown event names.
    """
    template_map: dict[str, str] = {
        "signup": "welcome",
        "no_upload_24h": "drip_no_upload",
        "no_analysis_3d": "drip_no_analysis",
        "success_story_7d": "drip_success_story",
        "trial_expiring_30d": "drip_trial_expiring_30d",
    }
    template = template_map.get(event)
    if template is None:
        raise ValueError(f"Unknown drip event: {event!r}")

    return send_email(
        to=user.email,
        template=template,
        data=_user_email_context(user),
    )


def known_templates() -> list[str]:
    """Return the list of supported template names. Useful for docs/tests."""
    return sorted(_TEMPLATES.keys())
