import type { Metadata } from "next";
import "./globals.css";

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
        {children}
      </body>
    </html>
  );
}
