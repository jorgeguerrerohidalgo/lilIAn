"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import Image from "next/image";
import { ChatWidget } from "@/components/chat";
import { clearLegacyTokens } from "@/lib/auth-cookie";
import { WelcomeTourOverlay, useWelcomeTour } from "@/components/onboarding/welcome-tour";
import { Tooltip } from "@/components/ui";
import { TOOLTIPS } from "@/lib/tooltips";
import { InviteTeamModal } from "@/components/modals/invite-team-modal";
import { SupportWidget } from "@/components/support-widget";

interface User {
  id: number;
  email: string;
  full_name: string;
}

interface NavItem {
  href: string;
  label: string;
  icon: React.ReactNode;
  count?: number;
}

const NAV_ITEMS: NavItem[] = [
  { href: "/dashboard", label: "Centro ejecutivo", icon: <DashboardIcon /> },
  { href: "/matters", label: "Casos", icon: <FolderIcon />, count: 0 },
  { href: "/dashboard/clients", label: "Clientes", icon: <UsersIcon /> },
  { href: "/precedents", label: "Precedentes", icon: <GavelIcon /> },
  { href: "/documents", label: "Documentos", icon: <DocumentIcon /> },
  // S2-05: billing surface — self-service plan / payment management.
  { href: "/dashboard/billing", label: "Facturación", icon: <BillingIcon /> },
];

// Icons
function DashboardIcon({ className = "w-5 h-5" }: { className?: string }) {
  return (
    <svg aria-hidden="true" className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z" />
    </svg>
  );
}

function FolderIcon({ className = "w-5 h-5" }: { className?: string }) {
  return (
    <svg aria-hidden="true" className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z" />
    </svg>
  );
}

function UsersIcon({ className = "w-5 h-5" }: { className?: string }) {
  return (
    <svg aria-hidden="true" className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 19.128a9.38 9.38 0 002.342-.121l1.731-1.731A9.37 9.37 0 0021.212 15.5H3.788a9.37 9.37 0 00.129-.371l1.731-1.731A9.38 9.38 0 0012 4.872V4.5a2.25 2.25 0 012.25-2.25h1.5a2.25 2.25 0 012.25 2.25v15.75a2.25 2.25 0 01-2.25 2.25h-1.5a2.25 2.25 0 01-2.25-2.25V8.122" />
    </svg>
  );
}

function GavelIcon({ className = "w-5 h-5" }: { className?: string }) {
  return (
    <svg aria-hidden="true" className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v12m-3-2.5l3.5 3.5 3.5-3.5M18.75 4.75l-15 15M3 3l18 18" />
    </svg>
  );
}

function DocumentIcon({ className = "w-5 h-5" }: { className?: string }) {
  return (
    <svg aria-hidden="true" className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.25a2.25 2.25 0 00-2.25-2.25H5a2.25 2.25 0 00-2.25 2.25v10.5a2.25 2.25 0 002.25 2.25h14.5a2.25 2.25 0 002.25-2.25v-2.25" />
    </svg>
  );
}

function BillingIcon({ className = "w-5 h-5" }: { className?: string }) {
  // Credit-card / billing glyph.
  return (
    <svg aria-hidden="true" className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 8.25h19.5M2.25 9V18a2.25 2.25 0 002.25 2.25h15a2.25 2.25 0 002.25-2.25V9m-19.5 0V6.75A2.25 2.25 0 016 4.5h12a2.25 2.25 0 012.25 2.25V9m-9 6h.008v.008H12V15z" />
    </svg>
  );
}

function LogoutIcon({ className = "w-4 h-4" }: { className?: string }) {
  return (
    <svg aria-hidden="true" className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0013.5 3h-2.25a2.25 2.25 0 00-2.25 2.25v13.5a2.25 2.25 0 002.25 2.25h2.25a2.25 2.25 0 002.25-2.25V15m-6-9l-3 3m3 0l-3-3m-3 3l3 3" />
    </svg>
  );
}

function PlusUserIcon({ className = "w-4 h-4" }: { className?: string }) {
  // "Person with +" glyph for the invite CTA.
  return (
    <svg aria-hidden="true" className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M18 7.5v3m0 0v3m0-3h3m-3 0h-3m-2.25-4.125a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zM3 19.235v-.11a6.375 6.375 0 0112.75 0v.109A12.318 12.318 0 019.374 21c-2.331 0-4.512-.645-6.374-1.766z" />
    </svg>
  );
}

function ChevronIcon({ className = "w-4 h-4" }: { className?: string }) {
  return (
    <svg aria-hidden="true" className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
    </svg>
  );
}

function CountBadge({ count }: { count: number }) {
  return (
    <span className="ml-auto min-w-[23px] h-5 rounded-full border border-border bg-surface flex items-center justify-center font-mono text-[10px] font-bold text-ink/60">
      {count}
    </span>
  );
}

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  // S6.3: invite-team modal state.
  const [inviteOpen, setInviteOpen] = useState(false);
  // S1.2: 3-step first-run overlay. localStorage-backed so it never
  // reappears once dismissed.
  const tour = useWelcomeTour();

  useEffect(() => {
    // La cookie `lilian_auth_token` es HttpOnly, así que no se puede leer
    // desde aquí: el BFF la convierte en `Authorization: Bearer` y este
    // fetch es la única forma de saber si la sesión sigue viva.
    //
    // Importante: el navegador a veces no adjunta la cookie recién emitida
    // en la primera petición inmediata (race Set-Cookie → siguiente fetch).
    // Si caemos en ese caso y deslogueamos al usuario en seco, entra en
    // un loop landing↔login. Reintentamos UNA vez con un backoff corto
    // antes de considerarlo un fallo real.
    let cancelled = false;

    async function checkAuth() {
      for (let attempt = 0; attempt < 2; attempt++) {
        if (cancelled) return;
        try {
          const res = await fetch("/api/v1/auth/me");
          if (res.ok) {
            const data = await res.json();
            if (!cancelled) {
              setUser(data);
              setLoading(false);
            }
            return;
          }
        } catch {
          // network error: try again
        }
        if (attempt === 0) {
          await new Promise((r) => setTimeout(r, 400));
        }
      }
      // Ambos intentos fallaron → sesión realmente inválida
      if (!cancelled) {
        await fetch("/api/auth/logout", { method: "POST" }).catch(() => {});
        clearLegacyTokens();
        router.push("/auth/login");
      }
    }

    checkAuth();
    return () => {
      cancelled = true;
    };
  }, [router]);

  const handleLogout = async () => {
    await fetch("/api/auth/logout", { method: "POST" }).catch(() => {});
    clearLegacyTokens();
    router.push("/");
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-soft">
        <div className="text-center">
          <div className="w-10 h-10 border-4 border-border border-t-primary rounded-full animate-spin mx-auto mb-4" />
          <p className="text-ink/60 text-sm">Cargando...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-soft flex">
      {/* Sidebar - Warm Professional */}
      <aside className="w-[275px] bg-surface border-r border-border flex flex-col">
        {/* Logo */}
        <div className="p-4 border-b border-border">
          <Link href="/dashboard" className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-primary flex items-center justify-center shadow-md">
              <span className="text-white font-bold text-sm">LG</span>
            </div>
            <div>
              <span className="text-lg font-heading font-semibold text-foreground tracking-tight">LilIAN</span>
              <p className="text-[10px] font-bold uppercase tracking-widest text-muted">Legal AI</p>
            </div>
          </Link>
        </div>

        {/* Navigation */}
        <nav aria-label="Navegación principal" className="flex-1 p-3 overflow-auto">
          <div className="nav-label">Navegación</div>
          {NAV_ITEMS.map((item) => {
            const isActive = pathname === item.href || (item.href !== "/dashboard" && pathname.startsWith(item.href));
            // S1.2: tour step 2 anchors to the Casos nav item.
            const tourProps = item.href === "/matters" ? { "data-tour-target": "matters-list" } : {};
            // S6.2: contextual tooltip per nav item.
            const navTooltip =
              item.href === "/dashboard/billing"
                ? TOOLTIPS.currentPlan
                : item.href === "/matters"
                ? TOOLTIPS.newCase
                : null;
            const link = (
              <Link
                key={item.href}
                href={item.href}
                aria-current={isActive ? "page" : undefined}
                {...tourProps}
                aria-label={
                  item.count !== undefined
                    ? `${item.label}, ${item.count} ${item.count === 1 ? "elemento" : "elementos"}`
                    : item.label
                }
                className={`nav-btn ${isActive ? 'nav-btn-active' : ''}`}
              >
                <span aria-hidden="true" className="text-ink/50">{item.icon}</span>
                {item.label}
                {item.count !== undefined && <CountBadge count={item.count} />}
              </Link>
            );
            return navTooltip ? (
              <Tooltip key={item.href} label={navTooltip} side="right">
                {link}
              </Tooltip>
            ) : (
              link
            );
          })}
        </nav>

        {/* Footer */}
        <div className="p-4 border-t border-border space-y-1">
          {/* S6.3: invite-CTA. Pinned above logout so it stays visible even
              on short viewports without competing with the primary nav. */}
          <Tooltip label={TOOLTIPS.inviteTeam} side="right">
            <button
              type="button"
              onClick={() => setInviteOpen(true)}
              className="flex items-center gap-3 w-full px-4 py-3 rounded-xl text-sm font-semibold text-primary bg-primary/5 hover:bg-primary/10 transition-colors"
            >
              <PlusUserIcon />
              Invitar a tu equipo
            </button>
          </Tooltip>
          <button
            onClick={handleLogout}
            className="flex items-center gap-3 w-full px-4 py-3 rounded-xl text-sm font-semibold text-ink/60 hover:bg-soft hover:text-ink transition-colors"
          >
            <LogoutIcon />
            Cerrar sesión
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Topbar */}
        <header className="sticky top-0 z-40 bg-surface/95 backdrop-blur-xl border-b border-border px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <h1 className="text-xl font-heading font-bold text-ink">
                {NAV_ITEMS.find(n => pathname === n.href || (n.href !== "/dashboard" && pathname.startsWith(n.href)))?.label || "Dashboard"}
              </h1>
            </div>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-3">
                <div className="text-right">
                  <p className="text-sm font-semibold text-ink">{user?.full_name}</p>
                  <p className="text-xs text-ink/50">{user?.email}</p>
                </div>
                <div className="w-9 h-9 rounded-full bg-primary flex items-center justify-center text-white font-bold text-sm">
                  {user?.full_name?.charAt(0).toUpperCase() || "U"}
                </div>
              </div>
            </div>
          </div>
        </header>

        {/* Page Content */}
        <main id="main-content" className="flex-1 p-6">
          {children}
        </main>
      </div>

      {/* Chat Widget */}
      <ChatWidget />

      {/* S6.5: support widget (bottom-right). Floats above content and
          renders inside the dashboard so it survives navigation. */}
      <SupportWidget defaultEmail={user?.email ?? ""} />

      {/* S6.3: invite-team modal. Controlled from the sidebar button. */}
      <InviteTeamModal
        open={inviteOpen}
        onClose={() => setInviteOpen(false)}
        inviterName={user?.full_name}
      />

      {/* S1.2 welcome tour — must be the last sibling so its portal
          renders on top of any other fixed-positioned element. */}
      <WelcomeTourOverlay state={tour} />
    </div>
  );
}
