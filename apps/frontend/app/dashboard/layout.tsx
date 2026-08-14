import type { Metadata } from "next";
import DashboardLayout from "@/components/layout/dashboard-layout";

export const metadata: Metadata = {
  title: "Centro ejecutivo — lilIAn",
  description: "Panel principal con métricas de casos, clientes, documentos y vencimientos legales.",
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return <DashboardLayout>{children}</DashboardLayout>;
}
