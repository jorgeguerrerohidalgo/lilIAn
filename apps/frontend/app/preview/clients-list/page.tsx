"use client";

import DashboardLayout from "@/components/layout/dashboard-layout";

// Internal preview of the /dashboard/clients page chrome. Renders the
// DashboardLayout with a mock user and an inline clone of the client list
// HTML so we can verify that no second sidebar/nav sneaks in on desktop.
export default function ClientsListPreview() {
  return (
    <DashboardLayout
      previewMode
      previewUser={{ full_name: "Camila Soto", email: "camila@bufete.cl", roles: ["PLATFORM_ADMIN"] }}
    >
      <div className="p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Clientes</h1>
            <p className="text-gray-600 mt-1">Gestiona tus clientes y sus datos</p>
          </div>
          <button className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 flex items-center gap-2">
            <span aria-hidden="true">+</span>
            Nuevo Cliente
          </button>
        </div>

        <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full" aria-label="Lista de clientes">
              <thead className="bg-gray-50 border-b">
                <tr>
                  <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">Nombre</th>
                  <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">Empresa</th>
                  <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">RUT</th>
                  <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">Contacto</th>
                  <th className="px-4 py-3 text-right text-sm font-medium text-gray-500">Acciones</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {[
                  { id: 1, name: "Constructora Austral", company: "Austral SpA", rut: "76.123.456-7", phone: "+56 2 2234 5678", email: "contacto@austral.cl" },
                  { id: 2, name: "Inmobiliaria Andina", company: "Andina Ltda", rut: "77.234.567-8", phone: "+56 2 2245 6789", email: "info@andina.cl" },
                  { id: 3, name: "Banco Sur", company: "Banco Sur S.A.", rut: "97.345.678-9", phone: "+56 2 2789 0123", email: "legal@bancosur.cl" },
                ].map((c) => (
                  <tr key={c.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full bg-primary-100 text-primary-700 flex items-center justify-center font-semibold">
                          {c.name.charAt(0)}
                        </div>
                        <div>
                          <p className="font-medium text-gray-900">{c.name}</p>
                          <p className="text-sm text-gray-500">{c.email}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-gray-700">{c.company}</td>
                    <td className="px-4 py-3 text-gray-700">{c.rut}</td>
                    <td className="px-4 py-3 text-gray-700">
                      <p>{c.phone}</p>
                      <p className="text-sm text-gray-500">{c.email}</p>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <span className="text-sm text-gray-400">—</span>
                    </td>
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
