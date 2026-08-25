"use client";

/**
 * MembersTab — Phase 2a.
 *
 * Lists the rows from ``/api/v1/organizations/me/members``. The
 * backend already gates email visibility by role (only OWNER/ADMIN/
 * PLATFORM_ADMIN see other members' emails); we mirror that here so a
 * non-privileged caller doesn't accidentally render sensitive fields.
 *
 * Privileged callers see:
 *   - a role dropdown (LAWYER / ADMIN / COMPANY_USER / VIEWER) per row
 *     with a PATCH on selection,
 *   - a "Remover" button with a confirm() guard before issuing the
 *     DELETE.
 *
 * Non-privileged callers (LAWYER, COMPANY_USER, VIEWER, CLIENT) see
 * the same table but without the action column. They can still see
 * themselves + their own role badge (the backend caps non-privileged
 * responses to just the caller).
 */

import { useMemo, useState } from "react";
import { useToast } from "@/lib/toast";
import { Button, Badge, Card, EmptyState } from "@/components/ui";

export interface Member {
  id: number;
  user_id: number;
  role: string;
  user: {
    id: number;
    full_name: string | null;
    email?: string | null;
  };
}

const ROLE_OPTIONS: { value: string; label: string }[] = [
  { value: "LAWYER", label: "Abogado/a" },
  { value: "ADMIN", label: "Administrador/a" },
  { value: "COMPANY_USER", label: "Usuario/a de empresa" },
  { value: "VIEWER", label: "Solo lectura" },
];

const ROLE_LABEL: Record<string, string> = {
  OWNER: "OWNER",
  ADMIN: "Administrador/a",
  LAWYER: "Abogado/a",
  COMPANY_USER: "Usuario/a de empresa",
  VIEWER: "Solo lectura",
  CLIENT: "Cliente",
  PLATFORM_ADMIN: "PLATFORM_ADMIN",
};

const ROLE_VARIANT: Record<string, "default" | "coral" | "blue" | "amber" | "green" | "neutral"> = {
  OWNER: "coral",
  ADMIN: "blue",
  LAWYER: "default",
  COMPANY_USER: "amber",
  VIEWER: "neutral",
  CLIENT: "neutral",
  PLATFORM_ADMIN: "coral",
};

interface MembersTabProps {
  members: Member[] | null;
  error: string | null;
  currentUserId: number | null;
  canManage: boolean;
  onChange: () => Promise<unknown> | void;
  onRetry: () => Promise<unknown> | void;
}

export function MembersTab({
  members,
  error,
  currentUserId,
  canManage,
  onChange,
  onRetry,
}: MembersTabProps) {
  if (error) {
    return (
      <Card padding="md">
        <EmptyState
          title="No pudimos cargar los miembros"
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

  if (members === null) {
    return <MembersSkeleton canManage={canManage} />;
  }

  if (members.length === 0) {
    return (
      <Card padding="lg">
        <EmptyState
          title="Aún no hay otros miembros"
          description="Cuando alguien se una a tu organización aparecerá aquí."
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
                Nombre
              </th>
              <th className="px-4 py-3 text-xs font-bold uppercase tracking-wider">
                Rol
              </th>
              <th className="px-4 py-3 text-xs font-bold uppercase tracking-wider text-right">
                Acciones
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {members.map((m) => (
              <MemberRow
                key={m.id}
                member={m}
                currentUserId={currentUserId}
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

function MemberRow({
  member,
  currentUserId,
  canManage,
  onChange,
}: {
  member: Member;
  currentUserId: number | null;
  canManage: boolean;
  onChange: () => Promise<unknown> | void;
}) {
  const { show } = useToast();
  const [savingRole, setSavingRole] = useState(false);
  const [removing, setRemoving] = useState(false);
  const isCaller = member.user_id === currentUserId;

  const canEditRole = canManage && !isCaller && member.role !== "OWNER";
  const canRemove =
    canManage && !isCaller && member.role !== "OWNER" && member.role !== "PLATFORM_ADMIN";

  const handleRoleChange = async (newRole: string) => {
    if (newRole === member.role) return;
    setSavingRole(true);
    try {
      const res = await fetch(
        `/api/v1/organizations/me/members/${member.user_id}`,
        {
          method: "PATCH",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ role: newRole }),
        },
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
        title: "Rol actualizado",
        body: `${member.user.full_name ?? member.user.email ?? "Miembro"} ahora es ${ROLE_LABEL[newRole] ?? newRole}.`,
      });
      await onChange();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Error desconocido";
      show({ tone: "error", title: "No pudimos cambiar el rol", body: message });
    } finally {
      setSavingRole(false);
    }
  };

  const handleRemove = async () => {
    const label = member.user.full_name ?? member.user.email ?? "este miembro";
    if (typeof window !== "undefined") {
      const ok = window.confirm(
        `¿Remover a ${label} de tu organización? La persona perderá acceso de inmediato.`,
      );
      if (!ok) return;
    }
    setRemoving(true);
    try {
      const res = await fetch(
        `/api/v1/organizations/me/members/${member.user_id}`,
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
        title: "Miembro removido",
        body: `${label} ya no tiene acceso a tu organización.`,
      });
      await onChange();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Error desconocido";
      show({ tone: "error", title: "No pudimos remover", body: message });
    } finally {
      setRemoving(false);
    }
  };

  return (
    <tr className="hover:bg-soft/50 transition-colors">
      <td className="px-4 py-3 text-ink">
        {member.user.email ? (
          <span>{member.user.email}</span>
        ) : (
          <span className="text-ink/40">—</span>
        )}
      </td>
      <td className="px-4 py-3 text-ink">
        <div className="flex items-center gap-2">
          <span>{member.user.full_name ?? "—"}</span>
          {isCaller && (
            <Badge variant="coral" size="sm">
              Tú
            </Badge>
          )}
        </div>
      </td>
      <td className="px-4 py-3">
        {canEditRole ? (
          <select
            value={member.role}
            onChange={(e) => void handleRoleChange(e.target.value)}
            disabled={savingRole || removing}
            aria-label="Cambiar rol"
            className="rounded-md border border-border bg-white px-2 py-1 text-xs font-semibold text-ink focus:border-coral focus:ring-1 focus:ring-coral/20 focus:outline-none disabled:opacity-60"
          >
            {ROLE_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        ) : (
          <Badge variant={ROLE_VARIANT[member.role] ?? "default"} size="sm">
            {ROLE_LABEL[member.role] ?? member.role}
          </Badge>
        )}
      </td>
      <td className="px-4 py-3 text-right">
        {canRemove ? (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => void handleRemove()}
            loading={removing}
            disabled={savingRole}
            aria-label={`Remover a ${member.user.full_name ?? member.user.email ?? "este miembro"}`}
            className="text-coral-dark hover:text-coral-dark hover:bg-coral-pale"
          >
            Remover
          </Button>
        ) : (
          <span className="text-ink/30">—</span>
        )}
      </td>
    </tr>
  );
}

function MembersSkeleton({ canManage }: { canManage: boolean }) {
  const cols = canManage ? 4 : 3;
  return (
    <div className="rounded-lg border border-border bg-cream overflow-hidden" aria-busy="true">
      <table className="w-full text-sm text-left">
        <thead className="bg-soft text-ink/60 border-b-2 border-border">
          <tr>
            <th className="px-4 py-3 text-xs font-bold uppercase tracking-wider">Email</th>
            <th className="px-4 py-3 text-xs font-bold uppercase tracking-wider">Nombre</th>
            <th className="px-4 py-3 text-xs font-bold uppercase tracking-wider">Rol</th>
            {canManage && (
              <th className="px-4 py-3 text-xs font-bold uppercase tracking-wider text-right">
                Acciones
              </th>
            )}
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {Array.from({ length: 3 }).map((_, i) => (
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