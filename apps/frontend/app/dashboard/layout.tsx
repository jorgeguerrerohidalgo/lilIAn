"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import Image from "next/image";

// Design System: Trust & Authority (Legal Tech)
// Colors: Navy #0F172A | Accent #0369A1 | Background #F8FAFC

interface User {
  id: number;
  email: string;
  full_name: string;
}

interface NavItem {
  href: string;
  label: string;
  icon: string;
}

const NAV_ITEMS: NavItem[] = [
  { href: "/dashboard", label: "Inicio", icon: "M3 12l2-2m0 0l-2 2m2-2 0l2 2m0 0l2-2m-2 2" },
  { href: "/matters", label: "Casos", icon: "M19 11H5a2 2 0 012-2h12a2 2 0 012 2h1a2 2 0 012-2h-2a2 2 0 012-2v-6a2 2 0 012-2h-2a2 2 0 012-2v6a2 2 0 002 2h-12z" },
  { href: "/dashboard/clients", label: "Clientes", icon: "M17 21v-2a3 3 0 00-3-3V5a2 2 0 012-2h14a2 2 0 012 2v6m-8-5v-2a3 3 0 00-3-3V5a2 2 0 012-2h14a2 2 0 012 2v6" },
  { href: "/precedents", label: "Precedentes", icon: "M12 2l.866.5-.866.5h3.464M12 22v-4m-3.464-2H7.536M12 18v-4m3.464-2H16.464M12 14v-4" },
  { href: "/documents", label: "Documentos", icon: "M9 12h6m-6-6h12m-6 6H9m6-6v12m-6-6V6" },
];

function HomeIcon() {
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12l8.96-8.96c.44-.439 1.152-.439 1.591 0L21.75 12l-8.96 8.96c-.44.439-1.152.439-1.591 0L2.25 12z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12l8.96-8.96c.44-.439 1.152-.439 1.591 0L21.75 12l-8.96 8.96c-.44.439-1.152.439-1.591 0L2.25 12z" />
    </svg>
  );
}

function DocumentIcon() {
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.25a2.25 2.25 0 00-2.25-2.25H5a2.25 2.25 0 00-2.25 2.25v10.5a2.25 2.25 0 002.25 2.25h14.5a2.25 2.25 0 002.25-2.25v-2.25" />
    </svg>
  );
}

function GavelIcon() {
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v12m-3-2.5l3.5 3.5 3.5-3.5M18.75 4.75l-15 15M3 3l18 18" />
    </svg>
  );
}

function UsersIcon() {
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 19.128a9.38 9.38 0 01.342-.121l1.731-1.731A9.37 9.37 0 0121.212 15.5H3.788a9.37 9.37 0 01.129-.371l1.731-1.731A9.38 9.38 0 0112 4.872V4.5a2.25 2.25 0 012.25-2.25h1.5a2.25 2.25 0 012.25 2.25v15.75a2.25 2.25 0 01-2.25 2.25h-1.5a2.25 2.25 0 01-2.25-2.25V8.122" />
    </svg>
  );
}

function BriefcaseIcon() {
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M20.25 7.5l-2 4.166a2.25 2.25 0 01-2.155 2.154H7.911a2.25 2.25 0 01-2.154-2.155l.917-4.166m-1.173-2.833V3.75a2.25 2.25 0 012.25-2.25h9.75a2.25 2.25 0 012.25 2.25v1.833m-1.173-2.833l-1.173 2.833m1.173 2.833l1.173 2.833M18 18H6a2.25 2.25 0 01-2.25-2.25V6.75A2.25 2.25 0 013.75 4.5h16.5A2.25 2.25 0 0122.5 6.75v8.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6" />
    </svg>
  );
}

function LogoutIcon() {
  return (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0013.5 3h-2.25a2.25 2.25 0 00-2.25 2.25v13.5a2.25 2.25 0 002.25 2.25h2.25a2.25 2.25 0 002.25-2.25V15m-6-9l-3 3m3 0l-3-3m-3 3l3 3" />
    </svg>
  );
}

function ChevronIcon() {
  return (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-9 9-9 9" />
    </svg>
  );
}

function getIcon(iconName: string) {
  switch (iconName) {
    case "M3 12l2-2m0 0l-2 2m2-2 0l2 2m0 0l2-2m-2 2":
      return <HomeIcon />;
    case "M19 11H5a2 2 0 012-2h12a2 2 0 012 2h1a2 2 0 012-2h-2a2 2 0 012-2v-6a2 2 0 012-2h-2a2 2 0 012-2v6a2 2 0 002 2h-12z":
      return <BriefcaseIcon />;
    case "M17 21v-2a3 3 0 00-3-3V5a2 2 0 012-2h14a2 2 0 012 2v6m-8-5v-2a3 3 0 00-3-3V5a2 2 0 012-2h14a2 2 0 012 2v6":
      return <UsersIcon />;
    case "M12 2l.866.5-.866.5h3.464M12 22v-4m-3.464-2H7.536M12 18v-4m3.464-2H16.464M12 14v-4":
      return <GavelIcon />;
    case "M9 12h6m-6-6h12m-6 6H9m6-6v12m-6-6V6":
      return <DocumentIcon />;
    default:
      return <HomeIcon />;
  }
}

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [userMenuOpen, setUserMenuOpen] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      router.push("/auth/login");
      return;
    }

    fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/v1/auth/me`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    })
      .then((res) => {
        if (!res.ok) throw new Error("No autorizado");
        return res.json();
      })
      .then((data) => {
        setUser(data);
        setLoading(false);
      })
      .catch(() => {
        localStorage.removeItem("token");
        router.push("/auth/login");
      });
  }, [router]);

  const handleLogout = () => {
    localStorage.removeItem("token");
    router.push("/");
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="text-center">
          <div className="w-10 h-10 border-4 border-slate-200 border-t-slate-700 rounded-full animate-spin mx-auto mb-4" />
          <p className="text-slate-600 text-sm">Cargando...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header - Trust & Authority Style */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            {/* Logo & Brand */}
            <div className="flex items-center gap-3">
              <Link href="/dashboard" className="flex items-center gap-3 group">
                <div className="w-9 h-9 rounded-lg bg-slate-900 flex items-center justify-center transition-transform group-hover:scale-105">
                  <Image
                    src="/images/logo.png"
                    alt="lilIAn"
                    width={24}
                    height={24}
                    className="invert"
                  />
                </div>
                <span className="text-xl font-semibold text-slate-900 tracking-tight">
                  lil<span className="text-sky-600">I</span>An
                </span>
              </Link>
              <div className="hidden sm:block h-6 w-px bg-slate-200 mx-2" />
            </div>

            {/* Navigation - Desktop */}
            <nav className="hidden md:flex items-center gap-1">
              {NAV_ITEMS.map((item) => {
                const isActive = pathname === item.href || (item.href !== "/dashboard" && pathname.startsWith(item.href));
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`
                      flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium
                      transition-all duration-200
                      ${isActive
                        ? "bg-slate-900 text-white"
                        : "text-slate-600 hover:text-slate-900 hover:bg-slate-100"
                      }
                    `}
                  >
                    {getIcon(item.icon)}
                    {item.label}
                  </Link>
                );
              })}
            </nav>

            {/* User Menu */}
            <div className="relative">
              <button
                onClick={() => setUserMenuOpen(!userMenuOpen)}
                className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-slate-100 transition-colors duration-200"
              >
                <div className="hidden sm:block text-right">
                  <p className="text-sm font-medium text-slate-900">{user?.full_name}</p>
                  <p className="text-xs text-slate-500">{user?.email}</p>
                </div>
                <div className="w-9 h-9 rounded-full bg-slate-200 flex items-center justify-center text-slate-600 font-medium text-sm">
                  {user?.full_name?.charAt(0).toUpperCase() || "U"}
                </div>
                <ChevronIcon />
              </button>

              {/* Dropdown Menu */}
              {userMenuOpen && (
                <>
                  <div
                    className="fixed inset-0 z-40"
                    onClick={() => setUserMenuOpen(false)}
                  />
                  <div className="absolute right-0 mt-2 w-56 bg-white rounded-xl shadow-lg border border-slate-200 py-2 z-50">
                    <div className="px-4 py-3 border-b border-slate-100">
                      <p className="text-sm font-medium text-slate-900">{user?.full_name}</p>
                      <p className="text-xs text-slate-500 mt-0.5">{user?.email}</p>
                    </div>
                    <div className="py-2">
                      <button
                        onClick={handleLogout}
                        className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-red-600 hover:bg-red-50 transition-colors"
                      >
                        <LogoutIcon />
                        Cerrar sesión
                      </button>
                    </div>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>

        {/* Mobile Navigation */}
        <div className="md:hidden border-t border-slate-200 bg-white">
          <nav className="flex overflow-x-auto px-4 py-2 gap-2">
            {NAV_ITEMS.map((item) => {
              const isActive = pathname === item.href || (item.href !== "/dashboard" && pathname.startsWith(item.href));
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`
                    flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium whitespace-nowrap
                    transition-all duration-200
                    ${isActive
                      ? "bg-slate-900 text-white"
                      : "text-slate-600 bg-slate-100"
                    }
                  `}
                >
                  {getIcon(item.icon)}
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {children}
      </main>
    </div>
  );
}
