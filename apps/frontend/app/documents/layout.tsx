import type { Metadata } from "next";
import DashboardLayout from "@/components/layout/dashboard-layout";

export const metadata: Metadata = {
  title: "Documentos — lilIAn",
  description: "Repositorio central de documentos legales subidos para análisis.",
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return <DashboardLayout>{children}</DashboardLayout>;
}
