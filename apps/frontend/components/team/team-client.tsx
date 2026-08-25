"use client";

/**
 * TeamClient — Phase 2a.
 *
 * Top-level shell for ``/dashboard/team``. Fetches the caller's
 * profile (``/api/v1/auth/me``) and the two collections
 * (``/organizations/me/members`` and ``/organizations/me/invitations``)
 * in parallel, then renders a two-tab layout:
 *
 *   - Miembros (default)
 *   - Invitaciones pendientes
 *
 * Both tabs are simple tables with role-aware actions. The page is a
 * Client Component because every tab needs live mutation (PATCH /
 * DELETE), toasts, and clipboard access — all of which would
 * unnecessarily cross the Server/Client boundary if we tried to keep
 * it as a Server Component.
 *
 * Why a single shell (rather than per-tab server fetches): the data
 * is small and we want instant feedback after a mutation without a
 * round-trip. The two tabs share nothing except "both are org-scoped
 * collections", so we cache them separately and refresh only the
 * relevant one on mutation.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { MembersTab, type Member } from "./members-tab";
import { InvitationsTab, type Invitation } from "./invitations-tab";
import { Button } from "@/components/ui";
import { InviteTeamModal } from "@/components/modals/invite-team-modal";

type Tab = "members" | "invitations";

interface CurrentUser {
  id: number;
  email: string;
  full_name: string;
  roles: string[];
}

function canManageTeam(roles: string[] | undefined): boolean {
  if (!roles) return false;
  return roles.some((r) =>
    r === "OWNER" || r === "ADMIN" || r === "PLATFORM_ADMIN",
  );
}

export function TeamClient() {
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [members, setMembers] = useState<Member[] | null>(null);
  const [invitations, setInvitations] = useState<Invitation[] | null>(null);
  const [membersError, setMembersError] = useState<string | null>(null);
  const [invitationsError, setInvitationsError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("members");
  const [inviteOpen, setInviteOpen] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  const canManage = useMemo(
    () => canManageTeam(currentUser?.roles),
    [currentUser],
  );

  const refreshMembers = useCallback(() => {
    setMembersError(null);
    return fetch("/api/v1/organizations/me/members", { credentials: "include" })
      .then(async (res) => {
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          const detail =
            (data && (data.detail || data.message)) || `Error ${res.status}`;
          throw new Error(typeof detail === "string" ? detail : `Error ${res.status}`);
        }
        return res.json();
      })
      .then((data: Member[]) => setMembers(data))
      .catch((err: unknown) => {
        const msg = err instanceof Error ? err.message : "Error desconocido";
        setMembersError(msg);
      });
  }, []);

  const refreshInvitations = useCallback(() => {
    setInvitationsError(null);
    return fetch("/api/v1/organizations/me/invitations", { credentials: "include" })
      .then(async (res) => {
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          const detail =
            (data && (data.detail || data.message)) || `Error ${res.status}`;
          throw new Error(typeof detail === "string" ? detail : `Error ${res.status}`);
        }
        return res.json();
      })
      .then((data: Invitation[]) => setInvitations(data))
      .catch((err: unknown) => {
        const msg = err instanceof Error ? err.message : "Error desconocido";
        setInvitationsError(msg);
      });
  }, []);

  // Initial load: fetch user + both lists in parallel.
  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      const [meRes, _members, _invitations] = await Promise.allSettled([
        fetch("/api/v1/auth/me", { credentials: "include" }),
        // Both fetches kick off here so the response handlers below can
        // share the parallel pipeline. We don't await directly because
        // we want the user/role gating to land first.
        refreshMembers(),
        refreshInvitations(),
      ]);

      if (cancelled) return;

      if (meRes.status === "fulfilled" && meRes.value.ok) {
        const data = await meRes.value.json();
        setCurrentUser({
          id: data.id,
          email: data.email,
          full_name: data.full_name,
          roles: Array.isArray(data.roles) ? data.roles : [],
        });
      }
      // Silence unused vars — the actual state writes happen inside
      // the helpers themselves.
      void _members;
      void _invitations;
    }

    bootstrap();
    return () => {
      cancelled = true;
    };
  }, [refreshMembers, refreshInvitations, refreshKey]);

  const pendingCount = useMemo(
    () =>
      invitations
        ? invitations.filter((i) => i.status === "pending").length
        : 0,
    [invitations],
  );

  return (
    <div className="p-6 md:p-8 max-w-5xl mx-auto space-y-8">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-heading font-bold text-ink tracking-tight">
            Mi equipo
          </h1>
          <p className="text-ink/60 mt-2">
            Gestiona los miembros de tu organización y las invitaciones pendientes.
          </p>
        </div>
        {canManage && (
          <Button variant="primary" size="md" onClick={() => setInviteOpen(true)}>
            <PlusUserIcon />
            Invitar
          </Button>
        )}
      </header>

      {/* Tabs */}
      <div role="tablist" aria-label="Secciones del equipo" className="border-b border-border">
        <div className="flex gap-1">
          <TabButton
            active={tab === "members"}
            onClick={() => setTab("members")}
            label="Miembros"
            count={members ? members.length : undefined}
            tabId="members"
          />
          <TabButton
            active={tab === "invitations"}
            onClick={() => setTab("invitations")}
            label="Invitaciones pendientes"
            count={pendingCount}
            tabId="invitations"
          />
        </div>
      </div>

      {tab === "members" ? (
        <MembersTab
          members={members}
          error={membersError}
          currentUserId={currentUser?.id ?? null}
          canManage={canManage}
          onChange={refreshMembers}
          onRetry={refreshMembers}
        />
      ) : (
        <InvitationsTab
          invitations={invitations}
          error={invitationsError}
          canManage={canManage}
          onChange={refreshInvitations}
          onRetry={refreshInvitations}
        />
      )}

      <InviteTeamModal
        open={inviteOpen}
        onClose={() => {
          setInviteOpen(false);
          // Refresh both: a successful invite removes the form, and
          // the new invitation will show up in the second tab.
          setRefreshKey((k) => k + 1);
        }}
        inviterName={currentUser?.full_name}
        multipleEmails
      />
    </div>
  );
}

function TabButton({
  active,
  onClick,
  label,
  count,
  tabId,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
  count?: number;
  tabId: string;
}) {
  return (
    <button
      type="button"
      role="tab"
      id={`tab-${tabId}`}
      aria-selected={active}
      aria-controls={`panel-${tabId}`}
      onClick={onClick}
      className={`relative inline-flex items-center gap-2 px-4 py-3 text-sm font-semibold transition-colors ${
        active
          ? "text-ink"
          : "text-ink/50 hover:text-ink/80"
      }`}
    >
      {label}
      {typeof count === "number" && (
        <span
          className={`min-w-[20px] h-5 px-1.5 inline-flex items-center justify-center rounded-full text-[10px] font-bold ${
            active ? "bg-coral text-white" : "bg-soft text-ink/60"
          }`}
        >
          {count}
        </span>
      )}
      <span
        aria-hidden="true"
        className={`absolute inset-x-0 -bottom-px h-0.5 ${
          active ? "bg-coral" : "bg-transparent"
        }`}
      />
    </button>
  );
}

function PlusUserIcon({ className = "w-4 h-4" }: { className?: string }) {
  return (
    <svg
      aria-hidden="true"
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M18 7.5v3m0 0v3m0-3h3m-3 0h-3m-2.25-4.125a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zM3 19.235v-.11a6.375 6.375 0 0112.75 0v.109A12.318 12.318 0 019.374 21c-2.331 0-4.512-.645-6.374-1.766z"
      />
    </svg>
  );
}