"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function RegisterPage() {
  const router = useRouter();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (password !== confirmPassword) {
      setError("Las contraseñas no coinciden");
      return;
    }

    if (password.length < 6) {
      setError("La contraseña debe tener al menos 6 caracteres");
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
      setError(err.message || "Error al registrar");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-white rounded-xl shadow-sm border p-8">
      <h2 className="text-2xl font-bold mb-6 text-center">Crear cuenta</h2>

      {error && (
        <div className="bg-red-50 text-red-600 p-3 rounded-lg mb-4 text-sm">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="fullName" className="block text-sm font-medium text-gray-700 mb-1">
            Nombre completo
          </label>
          <input
            type="text"
            id="fullName"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
            required
          />
        </div>

        <div>
          <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">
            Email
          </label>
          <input
            type="email"
            id="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
            required
          />
        </div>

        <div>
          <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">
            Contraseña
          </label>
          <input
            type="password"
            id="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
            required
          />
        </div>

        <div>
          <label htmlFor="confirmPassword" className="block text-sm font-medium text-gray-700 mb-1">
            Confirmar contraseña
          </label>
          <input
            type="password"
            id="confirmPassword"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
            required
          />
        </div>

        <button
          type="submit"
          disabled={loading}
          className="w-full py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
        >
          {loading ? "Creando cuenta..." : "Crear cuenta"}
        </button>
      </form>

      <p className="mt-4 text-center text-sm text-gray-600">
        ¿Ya tienes cuenta?{" "}
        <Link href="/auth/login" className="text-primary-600 hover:text-primary-700">
          Inicia sesión
        </Link>
      </p>
    </div>
  );
}
