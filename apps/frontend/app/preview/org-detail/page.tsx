import DashboardLayout from "@/components/layout/dashboard-layout";

// Internal preview for the PLATFORM_ADMIN cross-tenant organization
// detail view. Renders the layout shell with a mock user and an
// inline mock of the API response shape, so the page chrome can be
// inspected without a live backend.
export default function OrgDetailPreview() {
  const mockOrg = {
    id: 1,
    name: "Bufete Guerrero & Asociados",
    type: "law_firm",
    status: "active",
    plan_id: "pro",
    rut: "76.123.456-7",
    billing_email: "billing@guerrero.cl",
    stripe_customer_id: "cus_Qwerty123",
    created_at: "2026-07-14T18:09:30.496993",
    updated_at: "2026-08-20T11:32:11.000000",
    user_count: 5,
    matter_count: 47,
    document_count: 312,
    members: [
      { user_id: 1, email: "madneo710@gmail.com", full_name: "Jorge Guerrero", role: "PLATFORM_ADMIN", created_at: "2026-07-14T18:09:30" },
      { user_id: 2, email: "camila.soto@bufete.cl", full_name: "Camila Soto", role: "OWNER", created_at: "2026-07-14T18:09:30" },
      { user_id: 3, email: "matias.lopez@bufete.cl", full_name: "Matías López", role: "ADMIN", created_at: "2026-07-20T10:14:00" },
      { user_id: 4, email: "valentina.ruiz@bufete.cl", full_name: "Valentina Ruiz", role: "LAWYER", created_at: "2026-07-25T09:00:00" },
      { user_id: 5, email: "diego.morales@bufete.cl", full_name: "Diego Morales", role: "VIEWER", created_at: "2026-08-01T16:45:00" },
    ],
  };

  // Inline shell that mirrors the actual page structure so the preview
  // looks right without bringing in the real fetch flow.
  return (
    <DashboardLayout
      previewMode
      previewUser={{ full_name: "Jorge Guerrero", email: "madneo710@gmail.com", roles: ["PLATFORM_ADMIN"] }}
    >
      <div className="mx-auto max-w-5xl px-4 md:px-6 py-6 md:py-8 space-y-6">
        <a
          href="/dashboard/admin/organizations"
          className="inline-flex items-center gap-2 text-sm text-slate-600 hover:text-slate-900"
        >
          <span aria-hidden="true">←</span> Volver a Organizaciones
        </a>

        <header className="flex flex-wrap items-start justify-between gap-3 sm:gap-4">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2 sm:gap-3">
              <h1 className="text-xl md:text-2xl font-semibold text-slate-900 truncate">{mockOrg.name}</h1>
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                Activa
              </span>
            </div>
            <p className="mt-1 text-sm text-slate-500">
              Bufete de abogados · creada el 14 jul 2026 · actualizada el 20 ago 2026
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button className="px-3 py-2 text-sm font-medium rounded-md border border-amber-300 text-amber-800 bg-amber-50">
              Suspender
            </button>
          </div>
        </header>

        <section className="grid grid-cols-1 sm:grid-cols-3 gap-3 md:gap-4">
          <Kpi label="Usuarios" value={5} hint="Miembros activos" />
          <Kpi label="Casos" value={47} hint="Asuntos legales" />
          <Kpi label="Documentos" value={312} hint="Archivos cargados" />
        </section>

        <section className="rounded-lg border border-slate-200 bg-white overflow-hidden">
          <div className="px-5 py-4 border-b border-slate-200">
            <h2 className="text-sm font-semibold text-slate-700">Perfil de la organización</h2>
          </div>
          <dl className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-4 px-5 py-4">
            <Field label="ID interno" value="#1" />
            <Field label="Tipo" value="Bufete de abogados" />
            <Field label="Plan" value="pro" />
            <Field label="RUT" value="76.123.456-7" />
            <Field label="Email de facturación" value="billing@guerrero.cl" mono />
            <Field label="Cliente Stripe" value="cus_Qwerty123" mono />
          </dl>
        </section>

        <section className="rounded-lg border border-slate-200 bg-white overflow-hidden">
          <div className="px-5 py-4 border-b border-slate-200">
            <h2 className="text-sm font-semibold text-slate-700">Miembros ({mockOrg.members.length})</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm" aria-label={`Miembros de ${mockOrg.name}`}>
              <thead className="bg-slate-50 text-slate-600">
                <tr>
                  <th className="px-5 py-3 text-left font-medium">Usuario</th>
                  <th className="px-5 py-3 text-left font-medium">Email</th>
                  <th className="px-5 py-3 text-left font-medium">Rol</th>
                  <th className="px-5 py-3 text-left font-medium">Desde</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {mockOrg.members.map((m) => (
                  <tr key={m.user_id} className="hover:bg-slate-50">
                    <td className="px-5 py-3">
                      <a href={`/dashboard/admin/users/${m.user_id}`} className="font-medium text-slate-900 hover:text-primary">
                        {m.full_name}
                      </a>
                    </td>
                    <td className="px-5 py-3 text-slate-600 font-mono text-xs">{m.email}</td>
                    <td className="px-5 py-3">
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-700">
                        {m.role}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-slate-600">{m.created_at.split("T")[0]}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </DashboardLayout>
  );
}

function Kpi({ label, value, hint }: { label: string; value: number; hint: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-5 py-4">
      <p className="text-[11px] font-bold uppercase tracking-widest text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-slate-900">{value}</p>
      <p className="mt-1 text-xs text-slate-500">{hint}</p>
    </div>
  );
}

function Field({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs font-medium text-slate-500">{label}</dt>
      <dd className={`mt-1 text-sm text-slate-900 break-words ${mono ? "font-mono" : ""}`}>{value}</dd>
    </div>
  );
}
