import type { Metadata } from "next";
import "./globals.css";
import { ToastProvider } from "@/lib/toast";

export const metadata: Metadata = {
  title: "lilIAn",
  description: "Plataforma legaltech chilena asistida por IA",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="es">
      <body>
        {/* S5 accessibility: skip-to-content link for keyboard users.
            Hidden by default, becomes visible on focus. */}
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:px-3 focus:py-2 focus:bg-primary focus:text-white focus:rounded-md"
        >
          Saltar al contenido principal
        </a>
        {/* S1.5: toast provider wraps the entire app so any client
            component can fire notifications (replaces ad-hoc
            setError patterns). */}
        <ToastProvider>{children}</ToastProvider>
      </body>
    </html>
  );
}
