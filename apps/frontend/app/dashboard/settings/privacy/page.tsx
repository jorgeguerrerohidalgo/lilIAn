"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";

interface ConsentRecord {
  scope: string;
  version: string;
  granted_at: string | null;
  revoked_at: string | null;
}

interface RightsRequestRow {
  id: number;
  type: string;
  status: string;
  requested_at: string;
  completed_at: string | null;
  rejection_reason: string | null;
}

const TYPE_LABELS: Record<string, string> = {
  terms: "Términos de Uso",
  privacy: "Política de Privacidad",
  marketing: "Marketing promocional",
  cookies_analytics: "Cookies de analítica",
  data_processing_agreement: "Contrato de encargo (DPA)",
};

const RIGHTS_TYPE_LABELS: Record<string, string> = {
  access: "Acceso (obtener copia de mis datos)",
  rectification: "Rectificación (corregir datos)",
  suppression: "Supresión (eliminar mis datos)",
  opposition: "Oposición (rechazar un tratamiento)",
  portability: "Portabilidad (exportar mis datos)",
  blocking: "Bloqueo (suspender temporalmente)",
};

const RIGHTS_STATUS_STYLES: Record<string, string> = {
  pending: "bg-amber-100 text-amber-800",
  in_progress: "bg-blue-100 text-blue-800",
  completed: "bg-green-100 text-green-800",
  rejected: "bg-red-100 text-red-800",
  expired: "bg-slate-100 text-slate-700",
};

const RIGHTS_STATUS_LABELS: Record<string, string> = {
  pending: "Pendiente",
  in_progress: "En curso",
  completed: "Completada",
  rejected: "Rechazada",
  expired: "Vencida",
};

// /dashboard/settings/privacy — central Ley 21.719 surface for the
// logged-in user. Lets them:
//   - see which consents they've granted and when
//   - revoke or grant granular consents (except terms/privacy which
//     can only be revoked by closing the account)
//   - request their ARCO + portability rights
//   - see the status of past rights requests
export default function PrivacySettingsPage() {
  const router = useRouter();
  const [consents, setConsents] = useState<ConsentRecord[]>([]);
  const [rights, setRights] = useState<RightsRequestRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actionPending, setActionPending] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [cRes, rRes] = await Promise.all([
        fetch("/api/v1/privacy/consent"),
        fetch("/api/v1/privacy/rights/me"),
      ]);
      if (cRes.status === 401 || rRes.status === 401) {
        router.push("/auth/login");
        return;
      }
      if (cRes.ok) {
        const c = await cRes.json();
        setConsents(c.records || []);
      }
      if (rRes.ok) {
        const r = await rRes.json();
        setRights(r || []);
      }
    } catch {
      setError("No se pudieron cargar tus datos de privacidad.");
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => {
    load();
  }, [load]);

  const handleConsent = async (scope: string, granted: boolean) => {
    setActionPending(scope);
    try {
      const res = await fetch("/api/v1/privacy/consent", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scope, version: "v1-2026-08-29", granted }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        window.alert(data.detail || "No se pudo actualizar el consentimiento.");
        return;
      }
      await load();
    } finally {
      setActionPending(null);
    }
  };

  const handleExport = async () => {
    setActionPending("export");
    try {
      const res = await fetch("/api/v1/privacy/rights/me/export");
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        window.alert(data.detail || "No se pudo generar la exportación.");
        return;
      }
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const ts = new Date().toISOString().replace(/[:.]/g, "-");
      a.download = `lilian-data-export-${ts}.zip`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } finally {
      setActionPending(null);
    }
  };

  const handleRightsRequest = async (type: string) => {
    const confirmed = window.confirm(
      `Vas a solicitar el derecho de «${RIGHTS_TYPE_LABELS[type] ?? type}». ` +
        `Tienes derecho a una respuesta en un máximo de 30 días corridos (Ley 21.719 art. 27). ` +
        `¿Confirmas?`,
    );
    if (!confirmed) return;
    setActionPending(`rights:${type}`);
    try {
      const res = await fetch("/api/v1/privacy/rights/me/request", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ type }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        window.alert(data.detail || "No se pudo crear la solicitud.");
        return;
      }
      await load();
    } finally {
      setActionPending(null);
    }
  };

  if (loading) {
    return (
      <div className="mx-auto max-w-3xl px-4 md:px-6 py-8 md:py-10">
        <p className="text-sm text-ink/60">Cargando tus datos de privacidad…</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl px-4 md:px-6 py-6 md:py-8 space-y-8">
      <header>
        <h1 className="text-2xl md:text-3xl font-heading font-bold text-ink tracking-tight">
          Privacidad y datos personales
        </h1>
        <p className="mt-2 text-sm text-ink/60">
          Conforme a la Ley N° 21.719 (Chile) puedes ejercer tus derechos de Acceso,
          Rectificación, Supresión, Oposición, Portabilidad y Bloqueo. El plazo legal de
          respuesta es de 30 días corridos.
        </p>
      </header>

      {error && (
        <div role="alert" className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-800">
          {error}
        </div>
      )}

      {/* Consentimientos otorgados */}
      <section aria-labelledby="consents-heading" className="rounded-lg border border-ink/10 bg-surface overflow-hidden">
        <div className="px-5 py-4 border-b border-ink/10">
          <h2 id="consents-heading" className="text-sm font-semibold text-ink">
            Consentimientos otorgados
          </h2>
          <p className="mt-1 text-xs text-ink/60">
            Tus decisiones de consentimiento quedan registradas en una fila por versión del documento.
            Puedes revocar el consentimiento en cualquier momento.
          </p>
        </div>
        {consents.length === 0 ? (
          <p className="px-5 py-8 text-center text-sm text-ink/60">
            Aún no has otorgado consentimientos. Si tu cuenta es anterior al 29-ago-2026, contacta
            a <a href="mailto:dpo@lilian.mx" className="text-coral underline">dpo@lilian.mx</a>.
          </p>
        ) : (
          <ul className="divide-y divide-ink/10">
            {consents.map((c) => {
              const isActive = c.granted_at && !c.revoked_at;
              const isRequired = c.scope === "terms" || c.scope === "privacy";
              return (
                <li key={c.scope} className="px-5 py-3 flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-ink">
                      {TYPE_LABELS[c.scope] ?? c.scope}
                      {isRequired && (
                        <span className="ml-2 text-[10px] uppercase tracking-widest text-ink/50">
                          requerido
                        </span>
                      )}
                    </p>
                    <p className="text-xs text-ink/60">
                      Versión {c.version} ·{" "}
                      {isActive
                        ? `Otorgado el ${formatDate(c.granted_at)}`
                        : `Revocado el ${formatDate(c.revoked_at)}`}
                    </p>
                  </div>
                  {!isRequired && (
                    <button
                      type="button"
                      disabled={actionPending === c.scope}
                      onClick={() => handleConsent(c.scope, !isActive)}
                      className="px-3 py-1.5 text-xs font-medium rounded-md border border-ink/20 hover:bg-soft disabled:opacity-50"
                    >
                      {actionPending === c.scope
                        ? "…"
                        : isActive
                        ? "Revocar"
                        : "Otorgar"}
                    </button>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </section>

      {/* Derechos ARCO + portabilidad */}
      <section aria-labelledby="rights-heading" className="rounded-lg border border-ink/10 bg-surface overflow-hidden">
        <div className="px-5 py-4 border-b border-ink/10">
          <h2 id="rights-heading" className="text-sm font-semibold text-ink">
            Tus derechos (ARCO + Portabilidad + Bloqueo)
          </h2>
          <p className="mt-1 text-xs text-ink/60">
            Solicita cualquiera de los derechos garantizados por la Ley 21.719. La respuesta llega
            en un plazo máximo de 30 días corridos.
          </p>
        </div>
        <div className="px-5 py-4 grid grid-cols-1 sm:grid-cols-2 gap-3">
          <RightButton
            type="access"
            label="Acceso"
            description="Obtener copia de mis datos personales"
            onClick={() => handleRightsRequest("access")}
            loading={actionPending === "rights:access"}
          />
          <RightButton
            type="portability"
            label="Portabilidad"
            description="Descargar ZIP con mis datos en formato estructurado"
            onClick={handleExport}
            loading={actionPending === "export"}
            primary
          />
          <RightButton
            type="rectification"
            label="Rectificación"
            description="Corregir datos inexactos o incompletos"
            onClick={() => handleRightsRequest("rectification")}
            loading={actionPending === "rights:rectification"}
          />
          <RightButton
            type="suppression"
            label="Supresión"
            description="Solicitar la eliminación de mis datos (cuenta)"
            onClick={() => handleRightsRequest("suppression")}
            loading={actionPending === "rights:suppression"}
            destructive
          />
          <RightButton
            type="opposition"
            label="Oposición"
            description="Oponerme a un tratamiento específico"
            onClick={() => handleRightsRequest("opposition")}
            loading={actionPending === "rights:opposition"}
          />
          <RightButton
            type="blocking"
            label="Bloqueo"
            description="Suspender temporalmente el tratamiento"
            onClick={() => handleRightsRequest("blocking")}
            loading={actionPending === "rights:blocking"}
          />
        </div>
      </section>

      {/* Historial de solicitudes */}
      <section aria-labelledby="rights-history-heading" className="rounded-lg border border-ink/10 bg-surface overflow-hidden">
        <div className="px-5 py-4 border-b border-ink/10">
          <h2 id="rights-history-heading" className="text-sm font-semibold text-ink">
            Historial de solicitudes
          </h2>
        </div>
        {rights.length === 0 ? (
          <p className="px-5 py-8 text-center text-sm text-ink/60">
            Aún no has hecho solicitudes de derechos.
          </p>
        ) : (
          <ul className="divide-y divide-ink/10">
            {rights.map((r) => (
              <li key={r.id} className="px-5 py-3 flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-ink">
                    {RIGHTS_TYPE_LABELS[r.type] ?? r.type}
                  </p>
                  <p className="text-xs text-ink/60">
                    Solicitada el {formatDate(r.requested_at)}
                    {r.completed_at && ` · Completada el ${formatDate(r.completed_at)}`}
                  </p>
                </div>
                <span className={`px-2 py-0.5 rounded text-xs font-medium ${RIGHTS_STATUS_STYLES[r.status] ?? "bg-slate-100 text-slate-700"}`}>
                  {RIGHTS_STATUS_LABELS[r.status] ?? r.status}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <footer className="text-xs text-ink/50 pt-2">
        ¿Dudas? Escríbenos a <a href="mailto:dpo@lilian.mx" className="text-coral underline">dpo@lilian.mx</a>.
        Lee nuestra{" "}
        <a href="/legal/privacy" className="text-coral underline">
          Política de Privacidad
        </a>
        .
      </footer>
    </div>
  );
}

function RightButton({
  label,
  description,
  onClick,
  loading,
  primary,
  destructive,
}: {
  type: string;
  label: string;
  description: string;
  onClick: () => void;
  loading?: boolean;
  primary?: boolean;
  destructive?: boolean;
}) {
  const cls = destructive
    ? "border-red-200 hover:bg-red-50 text-red-800"
    : primary
    ? "border-coral hover:bg-coral-pale text-coral-dark"
    : "border-ink/20 hover:bg-soft text-ink";
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={loading}
      className={`text-left rounded-lg border bg-surface px-4 py-3 transition-colors disabled:opacity-50 ${cls}`}
    >
      <p className="text-sm font-semibold">{loading ? "Procesando…" : label}</p>
      <p className="mt-0.5 text-xs text-ink/60">{description}</p>
    </button>
  );
}

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleDateString("es-CL", { day: "numeric", month: "short", year: "numeric" });
  } catch {
    return iso;
  }
}
