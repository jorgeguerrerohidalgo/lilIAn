import DashboardLayout from "@/components/layout/dashboard-layout";

// Internal preview surface used to validate the responsive layout without a
// live backend. Not exposed in production navigation; visit directly via URL
// when running `next dev`.
export default function LayoutPreviewPage() {
  return (
    <DashboardLayout previewMode previewUser={{ full_name: "Camila Soto", email: "camila@bufete.cl", roles: ["PLATFORM_ADMIN"] }}>
      <div className="space-y-4">
        <div className="rounded-2xl border border-border bg-surface p-6">
          <h2 className="text-xl font-heading font-semibold text-ink">Vista previa del layout</h2>
          <p className="mt-2 text-sm text-ink/70">
            Esta ruta sólo existe en desarrollo para inspeccionar el shell del
            dashboard (sidebar, topbar, drawer móvil) sin necesidad de un
            backend levantado. No contiene datos reales.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="rounded-2xl border border-border bg-surface p-5">
              <p className="text-xs uppercase tracking-widest text-ink/50">Tarjeta {i}</p>
              <p className="mt-2 text-3xl font-heading font-bold text-ink">{i * 12}</p>
              <p className="mt-1 text-xs text-ink/60">Elementos activos</p>
            </div>
          ))}
        </div>

        <div className="rounded-2xl border border-border bg-surface overflow-hidden">
          <div className="px-5 py-4 border-b border-border flex items-center justify-between">
            <h3 className="font-semibold text-ink">Tabla de ejemplo</h3>
            <button className="rounded-lg bg-primary px-3 py-1.5 text-sm font-semibold text-white">Acción</button>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-soft text-ink/60">
                <tr>
                  <th className="px-5 py-3 text-left font-medium">Cliente</th>
                  <th className="px-5 py-3 text-left font-medium">Estado</th>
                  <th className="px-5 py-3 text-left font-medium">Riesgo</th>
                  <th className="px-5 py-3 text-left font-medium">Actualizado</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {[
                  { name: "Constructora Austral", status: "Activo", risk: "Bajo", date: "Hoy" },
                  { name: "Inmobiliaria Andina", status: "En revisión", risk: "Medio", date: "Ayer" },
                  { name: "Banco Sur", status: "Activo", risk: "Bajo", date: "Hace 3 días" },
                  { name: "Pesquera del Pacífico", status: "Bloqueado", risk: "Alto", date: "Hace 1 semana" },
                ].map((row) => (
                  <tr key={row.name}>
                    <td className="px-5 py-3 font-medium text-ink">{row.name}</td>
                    <td className="px-5 py-3 text-ink/70">{row.status}</td>
                    <td className="px-5 py-3 text-ink/70">{row.risk}</td>
                    <td className="px-5 py-3 text-ink/70">{row.date}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
