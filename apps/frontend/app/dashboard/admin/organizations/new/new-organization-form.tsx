"use client";

/**
 * Client form for ``/dashboard/admin/organizations/new``.
 *
 * Submits to ``POST /api/v1/admin/organizations`` (Fase 1c) and shows
 * a green confirmation card with a summary on success. The form uses
 * react-hook-form + zod so the validation copy matches the backend
 * rules (Pydantic ``min_length=1`` on org name and owner name, and
 * ``EmailStr`` on the owner email).
 *
 * Two CTAs are shown after a successful create:
 *   - "Crear otra organización" → reset the form to defaults.
 *   - "Volver al dashboard admin" → navigate to /dashboard/admin.
 *
 * Errors are surfaced in two places: a red card at the top of the
 * form (so the user keeps their input), and a toast for transient
 * feedback. The backend typically returns 4xx with a ``detail``
 * string (FastAPI default envelope) which we pass through verbatim.
 */

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import Link from "next/link";
import { Button } from "@/components/ui";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui";
import { Input } from "@/components/ui";
import { Select } from "@/components/ui";
import { toastFromError, useToast } from "@/lib/toast";

const PLANS: { value: string; label: string }[] = [
  { value: "free", label: "Gratis" },
  { value: "lawyer", label: "Abogado ($19.990/mes)" },
  { value: "law_firm", label: "Bufete ($59.990/mes)" },
  { value: "company", label: "Empresa ($149.990/mes)" },
  { value: "enterprise", label: "Corporativo (Contactar)" },
];

const schema = z.object({
  organization_name: z
    .string()
    .min(2, "El nombre debe tener al menos 2 caracteres.")
    .max(255, "El nombre es demasiado largo (máx 255 caracteres)."),
  owner_email: z
    .string()
    .min(1, "Ingresa el correo del primer OWNER.")
    .email("Ingresa un correo electrónico válido."),
  owner_full_name: z
    .string()
    .min(2, "El nombre del OWNER debe tener al menos 2 caracteres.")
    .max(255, "El nombre es demasiado largo (máx 255 caracteres)."),
  plan_name: z.enum(["free", "lawyer", "law_firm", "company", "enterprise"]),
});

type FormValues = z.infer<typeof schema>;

interface CreatedOrg {
  organization_id: number;
  name: string;
  type: string;
  status: string;
  owner_user_id: number;
  owner_email: string;
  subscription_plan: string | null;
  created_at: string;
}

const DEFAULT_VALUES: FormValues = {
  organization_name: "",
  owner_email: "",
  owner_full_name: "",
  plan_name: "free",
};

export function NewOrganizationForm() {
  const router = useRouter();
  const { show: showToast } = useToast();
  const [submitting, setSubmitting] = useState(false);
  const [created, setCreated] = useState<CreatedOrg | null>(null);
  const [serverError, setServerError] = useState<string | null>(null);
  // Bump this to fully reset the form on "Crear otra organización".
  const [resetKey, setResetKey] = useState(0);

  const {
    register,
    handleSubmit,
    formState: { errors },
    reset,
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: DEFAULT_VALUES,
  });

  async function onSubmit(values: FormValues) {
    setServerError(null);
    setSubmitting(true);
    try {
      const res = await fetch("/api/v1/admin/organizations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(values),
        credentials: "include",
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        const detail =
          (typeof data?.detail === "string" && data.detail) ||
          `Error ${res.status}`;
        throw new Error(detail);
      }
      const data = (await res.json()) as CreatedOrg;
      setCreated(data);
      showToast({
        tone: "success",
        title: "Organización creada",
        body: `${data.name} quedó asociada al OWNER ${data.owner_email}.`,
      });
    } catch (err) {
      const toastInput = toastFromError(err, "No pudimos crear la organización");
      // Use the backend's detail as the inline error so the user can
      // read it next to the form; the toast carries the same copy.
      const message =
        typeof (err as { detail?: string })?.detail === "string"
          ? (err as { detail: string }).detail
          : toastInput.body ?? "Inténtalo nuevamente en unos segundos.";
      setServerError(message);
      showToast({ tone: "error", title: toastInput.title, body: message });
    } finally {
      setSubmitting(false);
    }
  }

  function handleCreateAnother() {
    setCreated(null);
    setServerError(null);
    reset(DEFAULT_VALUES);
    setResetKey((k) => k + 1);
  }

  if (created) {
    return (
      <main
        id="main-content"
        className="mx-auto max-w-2xl px-6 py-8"
        lang="es"
      >
        <header className="mb-6">
          <h1 className="text-2xl font-semibold text-slate-900">
            Crear organización para cliente
          </h1>
        </header>

        <div
          role="status"
          className="rounded-md border border-emerald-200 bg-emerald-50 p-6"
        >
          <div className="flex items-start gap-3">
            <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-emerald-100 text-emerald-700">
              <svg
                aria-hidden="true"
                className="h-6 w-6"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
                strokeWidth={2}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M5 13l4 4L19 7"
                />
              </svg>
            </div>
            <div className="flex-1">
              <h2 className="text-lg font-semibold text-emerald-900">
                Organización creada
              </h2>
              <p className="mt-1 text-sm text-emerald-800">
                La organización quedó activa y el OWNER recibirá un correo
                de bienvenida con instrucciones para fijar su contraseña.
              </p>
            </div>
          </div>

          <dl className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-emerald-700">
                Organización
              </dt>
              <dd className="mt-1 text-sm font-semibold text-emerald-900">
                {created.name}
              </dd>
              <dd className="text-xs text-emerald-700">
                ID #{created.organization_id} · {created.type} · {created.status}
              </dd>
            </div>
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-emerald-700">
                OWNER
              </dt>
              <dd className="mt-1 text-sm font-semibold text-emerald-900">
                {created.owner_email}
              </dd>
              <dd className="text-xs text-emerald-700">
                user #{created.owner_user_id}
              </dd>
            </div>
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-emerald-700">
                Plan
              </dt>
              <dd className="mt-1 text-sm font-semibold text-emerald-900">
                {created.subscription_plan
                  ? PLANS.find((p) => p.value === created.subscription_plan)
                      ?.label ?? created.subscription_plan
                  : "Gratis"}
              </dd>
            </div>
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-emerald-700">
                Creada
              </dt>
              <dd className="mt-1 text-sm text-emerald-900">
                {(() => {
                  try {
                    return new Date(created.created_at).toLocaleString("es-CL", {
                      dateStyle: "short",
                      timeStyle: "medium",
                    });
                  } catch {
                    return created.created_at;
                  }
                })()}
              </dd>
            </div>
          </dl>

          <div className="mt-6 flex flex-wrap gap-3">
            <button
              type="button"
              onClick={handleCreateAnother}
              className="inline-flex items-center justify-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700"
            >
              Crear otra organización
            </button>
            <Link
              href="/dashboard"
              className="inline-flex items-center justify-center gap-2 rounded-lg border border-emerald-300 bg-white px-4 py-2 text-sm font-semibold text-emerald-900 hover:bg-emerald-100"
            >
              Volver al dashboard admin
            </Link>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main
      key={resetKey}
      id="main-content"
      className="mx-auto max-w-2xl px-6 py-8"
      lang="es"
    >
      <header className="mb-6">
        <h1 className="text-2xl font-semibold text-slate-900">
          Crear organización para cliente
        </h1>
        <p className="mt-1 text-sm text-slate-600">
          Onboarding manual para clientes enterprise o planes custom. El
          OWNER recibirá un correo de bienvenida y deberá fijar su
          contraseña con el flujo de recuperación.
        </p>
      </header>

      {serverError && (
        <div
          role="alert"
          aria-live="assertive"
          className="mb-6 rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-900"
        >
          <p className="font-semibold">No pudimos crear la organización</p>
          <p className="mt-1">{serverError}</p>
        </div>
      )}

      <Card padding="lg">
        <CardHeader>
          <CardTitle>Datos de la organización</CardTitle>
        </CardHeader>
        <CardContent>
          <form
            onSubmit={handleSubmit(onSubmit)}
            className="space-y-5"
            noValidate
          >
            <Input
              label="Nombre de la organización"
              id="org-name"
              placeholder="Bufete Pérez & Asoc."
              autoComplete="organization"
              required
              {...register("organization_name")}
              error={errors.organization_name?.message}
              aria-invalid={errors.organization_name ? true : undefined}
            />

            <Input
              label="Email del primer OWNER"
              id="owner-email"
              type="email"
              placeholder="perez@bufete.cl"
              autoComplete="email"
              required
              {...register("owner_email")}
              error={errors.owner_email?.message}
              aria-invalid={errors.owner_email ? true : undefined}
              hint="Le enviaremos un correo de bienvenida con instrucciones para fijar su contraseña."
            />

            <Input
              label="Nombre completo del OWNER"
              id="owner-full-name"
              placeholder="María Pérez"
              autoComplete="name"
              required
              {...register("owner_full_name")}
              error={errors.owner_full_name?.message}
              aria-invalid={errors.owner_full_name ? true : undefined}
            />

            <div>
              <Select
                label="Plan inicial"
                id="plan-name"
                options={PLANS}
                defaultValue="free"
                {...register("plan_name")}
                error={errors.plan_name?.message}
              />
              <p className="mt-1.5 text-sm text-slate-500">
                Para planes pagos recuerda coordinar el cobro por fuera del
                flujo de Stripe.
              </p>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <Link
                href="/dashboard"
                className="inline-flex items-center justify-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                Cancelar
              </Link>
              <Button
                type="submit"
                variant="primary"
                loading={submitting}
                disabled={submitting}
              >
                {submitting ? "Creando…" : "Crear organización"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      <footer className="mt-6 text-xs text-slate-500">
        Esta acción queda registrada en el log de auditoría con la
        acción <code>organization.created_for_client</code>.
      </footer>
    </main>
  );
}
