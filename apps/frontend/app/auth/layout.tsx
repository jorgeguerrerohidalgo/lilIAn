import type { Metadata } from "next";

export const metadata: Metadata = {
  title: {
    default: "Autenticación — lilIAn",
    template: "%s — lilIAn",
  },
  description: "Inicia sesión o regístrate en lilIAn para acceder al revisor legal inteligente de documentos.",
};

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-background flex items-center justify-center">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="flex justify-center mb-4">
            <div className="w-16 h-16 rounded-xl bg-primary flex items-center justify-center shadow-lg">
              <span className="text-white font-bold text-2xl">LG</span>
            </div>
          </div>
          <h1 className="text-2xl font-heading font-semibold text-foreground">LilIAN</h1>
          <p className="text-muted mt-2">Plataforma legal AI chilena</p>
        </div>
        {children}
      </div>
    </div>
  );
}
