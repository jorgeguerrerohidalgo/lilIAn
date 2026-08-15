"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui";
import { Input } from "@/components/ui";
import { Card } from "@/components/ui";
import { getApiUrl } from "@/lib/api";


const API_URL = getApiUrl();

export default function RegisterPage() {
  const router = useRouter();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [errors, setErrors] = useState<{
    fullName?: string;
    email?: string;
    password?: string;
    confirmPassword?: string;
    form?: string;
  }>({});
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrors({});

    if (password !== confirmPassword) {
      setErrors({ confirmPassword: "Las contraseñas no coinciden" });
      return;
    }

    if (password.length < 6) {
      setErrors({ password: "La contraseña debe tener al menos 6 caracteres" });
      return;
    }

    setLoading(true);

    try {
      const res = await fetch(`${API_URL}/api/v1/auth/register`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          email,
          password,
          full_name: fullName,
        }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Error al registrar");
      }

      router.push("/auth/login?registered=true");
    } catch (err: any) {
      setErrors({ form: err.message || "Error al registrar" });
    } finally {
      setLoading(false);
    }
  };

  return (
    <main id="main-content" className="min-h-screen bg-soft flex items-center justify-center p-4">
      <Card className="w-full max-w-md p-8">
        <div className="text-center mb-8">
          {/* Logo */}
          <div className="flex items-center justify-center gap-3 mb-6">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-ink to-blue flex items-center justify-center shadow-md">
              <span className="text-2xl font-heading font-bold text-white">L</span>
            </div>
            <div className="text-left">
              <h1 className="text-2xl font-heading font-bold text-ink tracking-tight">
                lil<span className="text-coral">I</span>An
              </h1>
              <p className="text-[10px] font-bold uppercase tracking-widest text-ink/40">Legal AI</p>
            </div>
          </div>
          <h2 className="text-2xl font-heading font-bold text-ink">Crear cuenta</h2>
          <p className="text-ink/60 mt-2">Regístrate en LILIAN</p>
        </div>

        {errors.form && (
          <div
            id="register-form-error"
            role="alert"
            aria-live="assertive"
            className="bg-coral-pale border border-coral/20 text-coral-dark px-4 py-3 rounded-xl mb-6 text-sm"
          >
            {errors.form}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-5">
          <Input
            label="Nombre completo"
            type="text"
            id="fullName"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            placeholder="Tu nombre completo"
            autoComplete="name"
            required
            aria-required="true"
            aria-describedby={errors.form ? "register-form-error" : undefined}
            aria-invalid={errors.fullName ? true : undefined}
          />

          <Input
            label="Email"
            type="email"
            id="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="tu@email.com"
            autoComplete="email"
            required
            aria-required="true"
            aria-describedby={errors.form ? "register-form-error" : undefined}
            aria-invalid={errors.email ? true : undefined}
          />

          <Input
            label="Contraseña"
            type="password"
            id="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            autoComplete="new-password"
            required
            aria-required="true"
            aria-describedby={errors.form ? "register-form-error" : undefined}
            aria-invalid={errors.password ? true : undefined}
          />

          <Input
            label="Confirmar contraseña"
            type="password"
            id="confirmPassword"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            placeholder="••••••••"
            autoComplete="new-password"
            required
            aria-required="true"
            aria-describedby={errors.form ? "register-form-error" : undefined}
            aria-invalid={errors.confirmPassword ? true : undefined}
          />

          <Button type="submit" variant="primary" size="lg" loading={loading} className="w-full">
            {loading ? "Creando cuenta..." : "Crear cuenta"}
          </Button>
        </form>

        <p className="mt-6 text-center text-sm text-ink/60">
          ¿Ya tienes cuenta?{" "}
          <Link href="/auth/login" className="text-coral font-semibold hover:text-coral-dark">
            Inicia sesión
          </Link>
        </p>
      </Card>
    </main>
  );
}
