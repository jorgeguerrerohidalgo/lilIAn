"use client";

import { useEffect, useRef, useState } from "react";
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
  // S4.6: list of role names pulled from the backend /me endpoint.
  // Used to gate the Admin nav section.
  roles?: string[];
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
  // S2e: team management (own / invited members). Visible to every
  // authenticated role with a membership — action gating is per-row.
  { href: "/dashboard/team", label: "Mi equipo", icon: <TeamIcon /> },
  // S2e: self-service profile + password.
  { href: "/dashboard/settings", label: "Configuración", icon: <SettingsIcon /> },
];

// S4.6: admin section shown only for PLATFORM_ADMIN. The endpoint
// itself enforces the role server-side; this is purely a UI gate so
// non-admins don't see the link.
const ADMIN_NAV_ITEMS: NavItem[] = [
  { href: "/dashboard/admin/audit-logs", label: "Auditoría", icon: <ShieldIcon /> },
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

function TeamIcon({ className = "w-5 h-5" }: { className?: string }) {
  // Two-people glyph for the "Mi equipo" nav item.
  return (
    <svg aria-hidden="true" className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z" />
    </svg>
  );
}

function SettingsIcon({ className = "w-5 h-5" }: { className?: string }) {
  // Cog/gear glyph for the "Configuración" nav item.
  return (
    <svg aria-hidden="true" className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.325.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.241-.438.613-.43.992a7.723 7.723 0 010 .255c-.008.378.137.75.43.991l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.47 6.47 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.991a6.932 6.932 0 010-.255c.007-.38-.138-.751-.43-.992l-1.004-.827a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.086.22-.128.332-.183.582-.495.644-.869l.214-1.281z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
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

function UserIcon({ className = "w-4 h-4" }: { className?: string }) {
  // Single-person glyph for the "Mi perfil" menu item.
  return (
    <svg aria-hidden="true" className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" />
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

function ShieldIcon({ className = "w-5 h-5" }: { className?: string }) {
  // Shield glyph for the admin section.
  return (
    <svg aria-hidden="true" className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12c0 1.268-.063 2.522-.187 3.757a48.32 48.32 0 01-3.387 13.094c-.18.452-.665.74-1.146.74H7.72c-.48 0-.965-.288-1.146-.74A48.32 48.32 0 013.187 15.757 48.696 48.696 0 013 12c0-2.357.24-4.66.69-6.879.132-.65.612-1.187 1.243-1.392A48.146 48.146 0 0112 3a48.146 48.146 0 017.067.729c.63.205 1.11.742 1.243 1.392C20.76 7.34 21 9.643 21 12z" />
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

function MenuIcon({ className = "w-6 h-6" }: { className?: string }) {
  return (
    <svg aria-hidden="true" className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
    </svg>
  );
}

function CloseIcon({ className = "w-6 h-6" }: { className?: string }) {
  return (
    <svg aria-hidden="true" className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
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

// SidebarBody: el árbol de navegación compartido entre el drawer móvil y el
// sidebar fijo de desktop. Cuando el drawer está abierto en móvil, ocultar el
// contenido duplicado provocaría scroll innecesario, así que reutilizamos el
// mismo JSX con un callback que cierra el drawer al hacer tap en un enlace.
function SidebarBody({
  pathname,
  user,
  onNavigate,
}: {
  pathname: string;
  user: User | null;
  onNavigate?: () => void;
}) {
  return (
    <>
      {/* Logo */}
      <div className="p-4 border-b border-border flex items-center justify-between">
        <Link href="/dashboard" onClick={onNavigate} className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-primary flex items-center justify-center shadow-md">
            <span className="text-white font-bold text-sm">LG</span>
          </div>
          <div>
            <span className="text-lg font-heading font-semibold text-foreground tracking-tight">LilIAN</span>
            <p className="text-[10px] font-bold uppercase tracking-widest text-muted">Legal AI</p>
          </div>
        </Link>
        {/* Close button only renders inside the mobile drawer */}
        {onNavigate && (
          <button
            type="button"
            onClick={onNavigate}
            aria-label="Cerrar menú"
            className="md:hidden -mr-1 p-2 rounded-lg text-ink/60 hover:bg-soft hover:text-ink transition-colors"
          >
            <CloseIcon />
          </button>
        )}
      </div>

      {/* Navigation */}
      <nav aria-label="Navegación principal" className="flex-1 p-3 overflow-auto">
        <div className="nav-label">Navegación</div>
        {NAV_ITEMS.map((item) => {
          const isActive = pathname === item.href || (item.href !== "/dashboard" && pathname.startsWith(item.href));
          // S1.2: tour step 2 anchors to the Casos nav item.
          const tourProps = item.href === "/matters" ? { "data-tour-target": "matters-list" } : {};
          // S6.2: contextual tooltip per nav item. Hidden inside the mobile
          // drawer to avoid hover/tap conflicts on touch devices.
          const navTooltip = onNavigate
            ? null
            : item.href === "/dashboard/billing"
            ? TOOLTIPS.currentPlan
            : item.href === "/matters"
            ? TOOLTIPS.newCase
            : null;
          const link = (
            <Link
              key={item.href}
              href={item.href}
              onClick={onNavigate}
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

        {/* S4.6: Admin section. Only visible for PLATFORM_ADMIN. The
            underlying endpoints enforce the same gate server-side, so
            this is purely a UI gatekeeper. */}
        {user?.roles?.includes("PLATFORM_ADMIN") && (
          <>
            <div className="nav-label mt-4">Administración</div>
            {ADMIN_NAV_ITEMS.map((item) => {
              const isActive = pathname === item.href || pathname.startsWith(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={onNavigate}
                  aria-current={isActive ? "page" : undefined}
                  aria-label={item.label}
                  className={`nav-btn ${isActive ? 'nav-btn-active' : ''}`}
                >
                  <span aria-hidden="true" className="text-ink/50">{item.icon}</span>
                  {item.label}
                </Link>
              );
            })}
          </>
        )}
      </nav>
    </>
  );
}

export default function DashboardLayout({
  children,
  // Preview mode bypasses the auth check and renders a mock user. Intended
  // for visual QA of the responsive layout without standing up the backend.
  // Never set this from user-controlled code paths.
  previewMode = false,
  previewUser,
}: {
  children: React.ReactNode;
  previewMode?: boolean;
  previewUser?: Partial<User>;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<User | null>(
    previewMode
      ? {
          id: 0,
          email: previewUser?.email ?? "preview@lilian.mx",
          full_name: previewUser?.full_name ?? "Usuario Preview",
          roles: previewUser?.roles ?? ["PLATFORM_ADMIN"],
        }
      : null
  );
  const [loading, setLoading] = useState(!previewMode);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  // S6.3: invite-team modal state.
  const [inviteOpen, setInviteOpen] = useState(false);
  // Mobile drawer state.
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  // S1.2: 3-step first-run overlay. localStorage-backed so it never
  // reappears once dismissed.
  const tour = useWelcomeTour();

  useEffect(() => {
    if (previewMode) return;
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
  }, [router, previewMode]);

  // Close the mobile drawer automatically whenever the route changes —
  // otherwise navigating through the drawer keeps it mounted over the
  // destination page, which feels broken on touch devices.
  useEffect(() => {
    setMobileMenuOpen(false);
  }, [pathname]);

  // Lock body scroll while the mobile drawer is open so background tap
  // doesn't bleed through the overlay.
  useEffect(() => {
    if (typeof document === "undefined") return;
    if (mobileMenuOpen) {
      const previousOverflow = document.body.style.overflow;
      document.body.style.overflow = "hidden";
      return () => {
        document.body.style.overflow = previousOverflow;
      };
    }
  }, [mobileMenuOpen]);

  // S2e: click-outside closes the user dropdown. We bind/unbind on the
  // document on every render the menu is open so we never leave a stale
  // listener attached after the menu closes.
  const userMenuRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    if (!userMenuOpen) return;
    function handleDocClick(event: MouseEvent) {
      if (userMenuRef.current && !userMenuRef.current.contains(event.target as Node)) {
        setUserMenuOpen(false);
      }
    }
    function handleEsc(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setUserMenuOpen(false);
        setMobileMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", handleDocClick);
    document.addEventListener("keydown", handleEsc);
    return () => {
      document.removeEventListener("mousedown", handleDocClick);
      document.removeEventListener("keydown", handleEsc);
    };
  }, [userMenuOpen]);

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

  const currentNavLabel =
    NAV_ITEMS.find(n => pathname === n.href || (n.href !== "/dashboard" && pathname.startsWith(n.href)))?.label ||
    "Dashboard";

  return (
    <div className="min-h-screen bg-soft flex">
      {/* Sidebar - desktop only. Hidden on mobile; the mobile drawer below
          renders the same navigation tree with a tap-to-close behavior. */}
      <aside className="hidden md:flex w-[260px] xl:w-[275px] bg-surface border-r border-border flex-col">
        <SidebarBody pathname={pathname} user={user} />
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

      {/* Mobile drawer. Off-canvas by default; slides in when the hamburger
          button is tapped. The overlay catches taps outside the panel so
          the user has a clear way to dismiss it. */}
      {mobileMenuOpen && (
        <div
          className="md:hidden fixed inset-0 z-50"
          role="dialog"
          aria-modal="true"
          aria-label="Menú de navegación"
        >
          <button
            type="button"
            aria-label="Cerrar menú"
            onClick={() => setMobileMenuOpen(false)}
            className="absolute inset-0 bg-ink/40 backdrop-blur-sm animate-slide-in"
          />
          <aside className="absolute inset-y-0 left-0 w-[280px] max-w-[85vw] h-full bg-surface border-r border-border flex flex-col shadow-xl animate-slide-in z-10">
            <SidebarBody
              pathname={pathname}
              user={user}
              onNavigate={() => setMobileMenuOpen(false)}
            />
            <div className="p-4 border-t border-border space-y-1">
              <button
                type="button"
                onClick={() => {
                  setInviteOpen(true);
                  setMobileMenuOpen(false);
                }}
                className="flex items-center gap-3 w-full px-4 py-3 rounded-xl text-sm font-semibold text-primary bg-primary/5 hover:bg-primary/10 transition-colors"
              >
                <PlusUserIcon />
                Invitar a tu equipo
              </button>
              <button
                onClick={handleLogout}
                className="flex items-center gap-3 w-full px-4 py-3 rounded-xl text-sm font-semibold text-ink/60 hover:bg-soft hover:text-ink transition-colors"
              >
                <LogoutIcon />
                Cerrar sesión
              </button>
            </div>
          </aside>
        </div>
      )}

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Topbar */}
        <header className="sticky top-0 z-30 bg-surface/95 backdrop-blur-xl border-b border-border px-4 md:px-6 py-3 md:py-4">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2 md:gap-4 min-w-0">
              {/* Hamburger: only on mobile */}
              <button
                type="button"
                onClick={() => setMobileMenuOpen(true)}
                aria-label="Abrir menú de navegación"
                aria-expanded={mobileMenuOpen}
                className="md:hidden -ml-1 p-2 rounded-lg text-ink/70 hover:bg-soft hover:text-ink transition-colors"
              >
                <MenuIcon />
              </button>
              <h1 className="text-base md:text-xl font-heading font-bold text-ink truncate">
                {currentNavLabel}
              </h1>
            </div>
            <div className="flex items-center gap-2 md:gap-4">
              <div ref={userMenuRef} className="relative">
                {/* S2e: user dropdown trigger. On mobile we collapse the
                    visible identity to just the avatar so the header
                    keeps a single row of tappable controls. */}
                <button
                  type="button"
                  onClick={() => setUserMenuOpen((open) => !open)}
                  aria-haspopup="menu"
                  aria-expanded={userMenuOpen}
                  aria-label="Abrir menú de usuario"
                  className="flex items-center gap-2 md:gap-3 rounded-xl px-2 py-1 hover:bg-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 transition-colors"
                >
                  <div className="hidden sm:block text-right">
                    <p className="text-sm font-semibold text-ink">{user?.full_name}</p>
                    <p className="text-xs text-ink/50">{user?.email}</p>
                  </div>
                  <div className="w-9 h-9 rounded-full bg-primary flex items-center justify-center text-white font-bold text-sm shrink-0">
                    {user?.full_name?.charAt(0).toUpperCase() || "U"}
                  </div>
                  <ChevronIcon className={`hidden md:block w-4 h-4 text-ink/40 transition-transform ${userMenuOpen ? "rotate-180" : ""}`} />
                </button>

                {userMenuOpen && (
                  <div
                    role="menu"
                    aria-label="Menú de usuario"
                    className="absolute right-0 top-full mt-2 w-56 rounded-xl border border-border bg-surface shadow-lg py-1 z-50"
                  >
                    <div className="sm:hidden px-4 py-2 border-b border-border">
                      <p className="text-sm font-semibold text-ink truncate">{user?.full_name}</p>
                      <p className="text-xs text-ink/50 truncate">{user?.email}</p>
                    </div>
                    <Link
                      href="/dashboard/settings"
                      role="menuitem"
                      onClick={() => setUserMenuOpen(false)}
                      className="flex items-center gap-2 px-4 py-2 text-sm text-ink hover:bg-soft transition-colors"
                    >
                      <UserIcon />
                      Mi perfil
                    </Link>
                    <Link
                      href="/dashboard/billing"
                      role="menuitem"
                      onClick={() => setUserMenuOpen(false)}
                      className="flex items-center gap-2 px-4 py-2 text-sm text-ink hover:bg-soft transition-colors"
                    >
                      <BillingIcon className="w-4 h-4" />
                      Mi plan
                    </Link>
                    <div role="separator" className="my-1 border-t border-border" />
                    <button
                      type="button"
                      role="menuitem"
                      onClick={handleLogout}
                      className="flex w-full items-center gap-2 px-4 py-2 text-sm text-ink hover:bg-soft transition-colors"
                    >
                      <LogoutIcon />
                      Cerrar sesión
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>
        </header>

        {/* Page Content */}
        <main id="main-content" className="flex-1 p-4 md:p-6">
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
