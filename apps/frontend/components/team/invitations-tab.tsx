"use client";

/**
 * InvitationsTab — Phase 2a.
 *
 * Lists pending + recent invitations from
 * ``/api/v1/organizations/me/invitations``. Each row offers two
 * privileged actions:
 *
 *   - "Copiar link" — copies the ``accept_url`` to the clipboard so
 *     the inviter can forward it manually (the invite email is
 *     best-effort; on systems without Resend the link is the only
 *     deliverable copy).
 *   - "Revocar" — DELETE on the invitation row. Disabled unless the
 *     invitation is still ``PENDING`` (the backend rejects revoke
 *     on other states with 409 Conflict).
 *
 * Non-privileged callers see the same list but without the actions
 * column. This is intentionally a Client Component because both
 * mutations need the auth cookie, and the clipboard API requires a
 * secure context (browser) anyway.
 */

import { useMemo, useState } from "react";
import { useToast } from "@/lib/toast";
import { Button, Badge, Card, EmptyState } from "@/components/ui";

export interface Invitation {
  id: number;
  email: string;
  role: string;
  status: string;
  created_at: string;
  expires_at: string;
  accept_url: string;
}

const ROLE_LABEL: Record<string, string> = {
  OWNER: "OWNER",
  ADMIN: "Administrador/a",
  LAWYER: "Abogado/a",
  COMPANY_USER: "Usuario/a de empresa",
  VIEWER: "Solo lectura",
};

const STATUS_VARIANT: Record<
  string,
  "default" | "coral" | "blue" | "amber" | "green" | "neutral"
> = {
  pending: "amber",
  accepted: "green",
  expired: "neutral",
  revoked: "neutral",
};

const STATUS_LABEL: Record<string, string> = {
  pending: "Pendiente",
  accepted: "Aceptada",
  expired: "Expirada",
  revoked: "Revocada",
};

interface InvitationsTabProps {
  invitations: Invitation[] | null;
  error: string | null;
  canManage: boolean;
  onChange: () => Promise<unknown> | void;
  onRetry: () => Promise<unknown> | void;
}

export function InvitationsTab({
  invitations,
  error,
  canManage,
  onChange,
  onRetry,
}: InvitationsTabProps) {
  // Sort: pending first, then by created_at desc. Done before any
  // early returns so the useMemo hook is always called.
  const sorted = useMemo(() => {
    if (!invitations) return [];
    return [...invitations].sort((a, b) => {
      if (a.status === "pending" && b.status !== "pending") return -1;
      if (b.status === "pending" && a.status !== "pending") return 1;
      return (
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      );
    });
  }, [invitations]);

  if (error) {
    return (
      <Card padding="md">
        <EmptyState
          title="No pudimos cargar las invitaciones"
          description={error}
          action={
            <Button variant="primary" size="md" onClick={() => void onRetry()}>
              Reintentar
            </Button>
          }
        />
      </Card>
    );
  }

  if (invitations === null) {
    return <InvitationsSkeleton canManage={canManage} />;
  }

  if (invitations.length === 0) {
    return (
      <Card padding="lg">
        <EmptyState
          title="No hay invitaciones pendientes"
          description="Las invitaciones que envíes desde este panel aparecerán aquí hasta que sean aceptadas o revocadas."
          action={<span />}
        />
      </Card>
    );
  }

  return (
    <div className="rounded-lg border border-border bg-cream overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm text-left">
          <thead className="bg-soft text-ink/60 border-b-2 border-border">
            <tr>
              <th className="px-4 py-3 text-xs font-bold uppercase tracking-wider">
                Email
              </th>
              <th className="px-4 py-3 text-xs font-bold uppercase tracking-wider">
                Rol invitado
              </th>
              <th className="px-4 py-3 text-xs font-bold uppercase tracking-wider">
                Estado
              </th>
              <th className="px-4 py-3 text-xs font-bold uppercase tracking-wider">
                Expira
              </th>
              <th className="px-4 py-3 text-xs font-bold uppercase tracking-wider text-right">
                Acciones
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {sorted.map((inv) => (
              <InvitationRow
                key={inv.id}
                invitation={inv}
                canManage={canManage}
                onChange={onChange}
              />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function InvitationRow({
  invitation,
  canManage,
  onChange,
}: {
  invitation: Invitation;
  canManage: boolean;
  onChange: () => Promise<unknown> | void;
}) {
  const { show } = useToast();
  const [revoking, setRevoking] = useState(false);
  const isPending = invitation.status === "pending";

  const handleCopy = async () => {
    const url = invitation.accept_url;
    try {
      if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(url);
        show({
          tone: "success",
          title: "Link copiado",
          body: "Pégalo en un correo para compartir la invitación.",
        });
      } else {
        // Fallback for very old browsers / insecure contexts.
        if (typeof window !== "undefined") {
          window.prompt("Copia este link para invitar:", url);
        }
      }
    } catch {
      show({
        tone: "error",
        title: "No pudimos copiar",
        body: "Tu navegador bloqueó el acceso al portapapeles.",
      });
    }
  };

  const handleRevoke = async () => {
    if (typeof window !== "undefined") {
      const ok = window.confirm(
        `¿Revocar la invitación enviada a ${invitation.email}? El link dejará de funcionar.`,
      );
      if (!ok) return;
    }
    setRevoking(true);
    try {
      const res = await fetch(
        `/api/v1/organizations/me/invitations/${invitation.id}`,
        { method: "DELETE", credentials: "include" },
      );
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        const detail =
          (data && (data.detail || data.message)) || `Error ${res.status}`;
        throw new Error(
          typeof detail === "string" ? detail : `Error ${res.status}`,
        );
      }
      show({
        tone: "success",
        title: "Invitación revocada",
        body: `${invitation.email} ya no podrá unirse con ese link.`,
      });
      await onChange();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Error desconocido";
      show({ tone: "error", title: "No pudimos revocar", body: message });
    } finally {
      setRevoking(false);
    }
  };

  const expiryLabel = formatExpiry(invitation.expires_at, isPending);

  return (
    <tr className="hover:bg-soft/50 transition-colors">
      <td className="px-4 py-3 text-ink">{invitation.email}</td>
      <td className="px-4 py-3">
        <Badge variant="default" size="sm">
          {ROLE_LABEL[invitation.role] ?? invitation.role}
        </Badge>
      </td>
      <td className="px-4 py-3">
        <Badge
          variant={STATUS_VARIANT[invitation.status] ?? "default"}
          size="sm"
        >
          {STATUS_LABEL[invitation.status] ?? invitation.status}
        </Badge>
      </td>
      <td className="px-4 py-3 text-ink/70 text-xs">{expiryLabel}</td>
      <td className="px-4 py-3 text-right">
        {canManage ? (
          <div className="inline-flex items-center gap-2 justify-end">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => void handleCopy()}
              disabled={revoking}
              aria-label="Copiar link de invitación"
            >
              Copiar link
            </Button>
            {isPending && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => void handleRevoke()}
                loading={revoking}
                aria-label={`Revocar invitación a ${invitation.email}`}
                className="text-coral-dark hover:text-coral-dark hover:bg-coral-pale"
              >
                Revocar
              </Button>
            )}
          </div>
        ) : (
          <span className="text-ink/30">—</span>
        )}
      </td>
    </tr>
  );
}

function formatExpiry(iso: string, isPending: boolean): string {
  const expires = new Date(iso);
  if (Number.isNaN(expires.getTime())) return "—";
  const dateLabel = expires.toLocaleDateString("es-CL", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
  if (!isPending) return dateLabel;
  const ms = expires.getTime() - Date.now();
  if (ms <= 0) return `${dateLabel} · expirada`;
  const days = Math.ceil(ms / (1000 * 60 * 60 * 24));
  if (days <= 3) return `${dateLabel} · en ${days} ${days === 1 ? "día" : "días"}`;
  return dateLabel;
}

function InvitationsSkeleton({ canManage }: { canManage: boolean }) {
  const cols = canManage ? 5 : 4;
  return (
    <div
      className="rounded-lg border border-border bg-cream overflow-hidden"
      aria-busy="true"
    >
      <table className="w-full text-sm text-left">
        <thead className="bg-soft text-ink/60 border-b-2 border-border">
          <tr>
            <th className="px-4 py-3 text-xs font-bold uppercase tracking-wider">Email</th>
            <th className="px-4 py-3 text-xs font-bold uppercase tracking-wider">Rol invitado</th>
            <th className="px-4 py-3 text-xs font-bold uppercase tracking-wider">Estado</th>
            <th className="px-4 py-3 text-xs font-bold uppercase tracking-wider">Expira</th>
            {canManage && (
              <th className="px-4 py-3 text-xs font-bold uppercase tracking-wider text-right">
                Acciones
              </th>
            )}
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {Array.from({ length: 2 }).map((_, i) => (
            <tr key={i} className="animate-pulse">
              {Array.from({ length: cols }).map((__, j) => (
                <td key={j} className="px-4 py-3">
                  <div className="h-4 bg-soft rounded w-3/4" />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}