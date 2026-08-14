import type { Metadata } from "next";
import DashboardLayout from "@/components/layout/dashboard-layout";

export const metadata: Metadata = {
  title: "Clientes — lilIAn",
  description: "Administra la cartera de clientes, sus datos de contacto y casos asociados.",
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return <DashboardLayout>{children}</DashboardLayout>;
}
