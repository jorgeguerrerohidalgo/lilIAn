import type { Metadata } from "next";
import DashboardLayout from "@/components/layout/dashboard-layout";

export const metadata: Metadata = {
  title: "Casos — lilIAn",
  description: "Gestiona tus casos legales: contratos, arriendos, laboral, empresas y más.",
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return <DashboardLayout>{children}</DashboardLayout>;
}
