"use client";

/**
 * /dashboard/settings — Fase 2b.
 *
 * Self-service account settings page. Two independent sections:
 *
 *  1. Perfil — edit full_name and phone. Pre-filled from /auth/me and
 *     persisted via PATCH /auth/me.
 *
 *  2. Seguridad — change the account password. Uses the same 12-char +
 *     complexity rules as /auth/register (see lib/validators.passwordSchema)
 *     so client-side feedback matches the backend's UserCreate validators.
 *     Submits to POST /auth/change-password.
 *
 * The dashboard layout already gates auth (it redirects unauthenticated
 * users to /auth/login) so this page only needs to consume the cookie
 * that the BFF issued — it never builds absolute API URLs.
 *
 * Both forms live in the same component because they share header chrome
 * and a "saving" indicator, but the loading and submit states are
 * independent so a slow profile save doesn't block a password change.
 */

import { useEffect, useState } from "react";
import { Button } from "@/components/ui";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui";
import { Input } from "@/components/ui";
import { useToast } from "@/lib/toast";
import { passwordSchema } from "@/lib/validators";

interface CurrentUser {
  id: number;
  email: string;
  full_name: string;
  phone: string | null;
}

export default function SettingsPage() {
  const { show: showToast } = useToast();

  // --- profile state ---
  const [loadingMe, setLoadingMe] = useState(true);
  const [me, setMe] = useState<CurrentUser | null>(null);
  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [profileErrors, setProfileErrors] = useState<{ fullName?: string; form?: string }>({});
  const [savingProfile, setSavingProfile] = useState(false);

  // --- password state ---
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordErrors, setPasswordErrors] = useState<{
    currentPassword?: string;
    newPassword?: string;
    confirmPassword?: string;
    form?: string;
  }>({});
  const [savingPassword, setSavingPassword] = useState(false);
  const [passwordFormOpen, setPasswordFormOpen] = useState(true);

  // Pre-fill the profile form on mount.
  useEffect(() => {
    let cancelled = false;
    async function loadMe() {
      try {
        const res = await fetch("/api/v1/auth/me", { credentials: "include" });
        if (!res.ok) throw new Error("No pudimos cargar tu perfil.");
        const data = (await res.json()) as CurrentUser;
        if (cancelled) return;
        setMe(data);
        setFullName(data.full_name ?? "");
        setPhone(data.phone ?? "");
      } catch (err) {
        const message = err instanceof Error ? err.message : "No pudimos cargar tu perfil.";
        if (!cancelled) {
          showToast({ tone: "error", title: "Error al cargar tu perfil", body: message });
          setProfileErrors({ form: message });
        }
      } finally {
        if (!cancelled) setLoadingMe(false);
      }
    }
    loadMe();
    return () => {
      cancelled = true;
    };
  }, [showToast]);

  // -----------------------------------------------------------------
  // Profile submit — PATCH /auth/me
  // -----------------------------------------------------------------
  async function handleProfileSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setProfileErrors({});

    if (!fullName.trim()) {
      setProfileErrors({ fullName: "Ingresa tu nombre completo." });
      return;
    }

    setSavingProfile(true);
    try {
      // Phone is optional: send null when blank so the backend clears it.
      const trimmedPhone = phone.trim();
      const body: { full_name: string; phone: string | null } = {
        full_name: fullName.trim(),
        phone: trimmedPhone.length > 0 ? trimmedPhone : null,
      };

      const res = await fetch("/api/v1/auth/me", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        credentials: "include",
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        const detail = typeof data?.detail === "string" ? data.detail : "No pudimos guardar los cambios.";
        throw new Error(detail);
      }

      const updated = (await res.json()) as CurrentUser;
      setMe(updated);
      setPhone(updated.phone ?? "");
      showToast({ tone: "success", title: "Perfil actualizado", body: "Tus cambios se guardaron correctamente." });
    } catch (err) {
      const message = err instanceof Error ? err.message : "No pudimos guardar los cambios.";
      setProfileErrors({ form: message });
      showToast({ tone: "error", title: "Error al guardar", body: message });
    } finally {
      setSavingProfile(false);
    }
  }

  // -----------------------------------------------------------------
  // Password submit — POST /auth/change-password
  // -----------------------------------------------------------------
  async function handlePasswordSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPasswordErrors({});

    if (!currentPassword) {
      setPasswordErrors({ currentPassword: "Ingresa tu contraseña actual." });
      return;
    }
    if (newPassword !== confirmPassword) {
      setPasswordErrors({ confirmPassword: "Las contraseñas no coinciden" });
      return;
    }
    // Reuse the same Zod schema as register so error copy matches
    // exactly. ``safeParse`` returns a flat issues array; surface the
    // first message on the newPassword field (the only one we validate).
    const parsed = passwordSchema.safeParse(newPassword);
    if (!parsed.success) {
      const firstIssue = parsed.error.issues[0]?.message ?? "Contraseña inválida.";
      setPasswordErrors({ newPassword: firstIssue });
      return;
    }

    setSavingPassword(true);
    try {
      const res = await fetch("/api/v1/auth/change-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
        }),
        credentials: "include",
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        const detail = typeof data?.detail === "string" ? data.detail : "No pudimos cambiar tu contraseña.";
        throw new Error(detail);
      }

      showToast({
        tone: "success",
        title: "Contraseña actualizada",
        body: "Tu nueva contraseña ya está activa.",
      });
      // Clear sensitive fields and collapse the form so the user
      // knows the action completed and the secrets aren't lingering.
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setPasswordFormOpen(false);
    } catch (err) {
      const message = err instanceof Error ? err.message : "No pudimos cambiar tu contraseña.";
      setPasswordErrors({ form: message });
      showToast({ tone: "error", title: "Error al cambiar la contraseña", body: message });
    } finally {
      setSavingPassword(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <header>
        <h1 className="text-2xl font-heading font-bold text-ink">Configuración de cuenta</h1>
        <p className="text-ink/60 mt-1">
          Actualiza tu información personal y la seguridad de tu cuenta.
        </p>
      </header>

      {/* ----------------------------- Perfil ----------------------------- */}
      <Card padding="lg">
        <CardHeader>
          <CardTitle>Perfil</CardTitle>
        </CardHeader>
        <CardContent>
          {loadingMe ? (
            <p className="text-ink/60 text-sm">Cargando tu información…</p>
          ) : (
            <form onSubmit={handleProfileSubmit} className="space-y-5" noValidate>
              <div>
                <label
                  htmlFor="settings-email"
                  className="block text-sm font-semibold text-ink"
                >
                  Email
                </label>
                <input
                  id="settings-email"
                  type="email"
                  value={me?.email ?? ""}
                  disabled
                  className="mt-1.5 w-full px-3 py-2.5 rounded-lg text-base bg-soft border border-border text-ink/60 cursor-not-allowed"
                />
                <p className="mt-1 text-xs text-ink/50">
                  El email está vinculado a tu cuenta y no se puede cambiar aquí.
                </p>
              </div>

              <Input
                label="Nombre completo"
                id="settings-full-name"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Tu nombre completo"
                autoComplete="name"
                required
                error={profileErrors.fullName}
                aria-invalid={profileErrors.fullName ? true : undefined}
              />

              <Input
                label="Teléfono (opcional)"
                id="settings-phone"
                type="tel"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="+56 9 1234 5678"
                autoComplete="tel"
                error={profileErrors.form}
              />

              {profileErrors.form && !profileErrors.fullName && (
                <div
                  role="alert"
                  aria-live="assertive"
                  className="bg-coral-pale border border-coral/20 text-coral-dark px-4 py-3 rounded-xl text-sm"
                >
                  {profileErrors.form}
                </div>
              )}

              <div className="flex justify-end">
                <Button type="submit" variant="primary" loading={savingProfile}>
                  {savingProfile ? "Guardando..." : "Guardar cambios"}
                </Button>
              </div>
            </form>
          )}
        </CardContent>
      </Card>

      {/* ----------------------------- Seguridad ----------------------------- */}
      <Card padding="lg">
        <CardHeader>
          <CardTitle>Seguridad</CardTitle>
        </CardHeader>
        <CardContent>
          <h2 className="text-base font-semibold text-ink">Cambiar contraseña</h2>
          <p className="text-sm text-ink/60 mt-1">
            Usa al menos 12 caracteres, con mayúscula, minúscula, número y símbolo.
          </p>

          <form onSubmit={handlePasswordSubmit} className="space-y-5 mt-5" noValidate>
            <Input
              label="Contraseña actual"
              id="settings-current-password"
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              autoComplete="current-password"
              required
              error={passwordErrors.currentPassword}
              aria-invalid={passwordErrors.currentPassword ? true : undefined}
            />

            <Input
              label="Nueva contraseña"
              id="settings-new-password"
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              placeholder="Mínimo 12 caracteres, con mayúscula, número y símbolo"
              autoComplete="new-password"
              required
              error={passwordErrors.newPassword}
              aria-invalid={passwordErrors.newPassword ? true : undefined}
            />

            <Input
              label="Confirmar nueva contraseña"
              id="settings-confirm-password"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              autoComplete="new-password"
              required
              error={passwordErrors.confirmPassword}
              aria-invalid={passwordErrors.confirmPassword ? true : undefined}
            />

            {passwordErrors.form && (
              <div
                role="alert"
                aria-live="assertive"
                className="bg-coral-pale border border-coral/20 text-coral-dark px-4 py-3 rounded-xl text-sm"
              >
                {passwordErrors.form}
              </div>
            )}

            <div className="flex justify-end">
              <Button type="submit" variant="primary" loading={savingPassword}>
                {savingPassword ? "Cambiando..." : "Cambiar contraseña"}
              </Button>
            </div>
          </form>

          {!passwordFormOpen && (
            <p className="mt-4 text-sm text-ink/60">
              Contraseña actualizada. Para cambiarla de nuevo, edita los campos y vuelve a enviar.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
