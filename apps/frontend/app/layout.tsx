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
      <body>{children}</body>
    </html>
  );
}
