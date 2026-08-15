/**
 * Zod validators for the lilIAn frontend forms (S5-02).
 *
 * Reuses the same complexity rules the backend enforces
 * (UserCreate in ``app/schemas/user.py``) so the UI rejects bad input
 * before it hits the network.
 */
import { z } from "zod";

/**
 * Return ``next`` if it is a safe relative path on this app; otherwise
 * the provided default. Defends against open-redirect (a malicious
 * ``?next=https://evil.com/`` would otherwise bounce a freshly
 * authenticated user to an attacker-controlled page).
 */
export function safeRedirect(
  next: string | null | undefined,
  fallback = "/dashboard",
): string {
  if (!next) return fallback;
  // Must start with a single slash and not be a protocol-relative URL
  // (`//evil.com`) which the browser still treats as cross-origin.
  if (!next.startsWith("/") || next.startsWith("//")) return fallback;
  // Reject anything that contains characters we never use in app routes
  // and which are common XSS/URL-injection vectors.
  if (/[\r\n\t]/.test(next)) return fallback;
  return next;
}


export const emailSchema = z
  .string()
  .min(1, "Email requerido")
  .email("Email inválido");

export const passwordSchema = z
  .string()
  .min(12, "La contraseña debe tener al menos 12 caracteres")
  .regex(/[a-z]/, "Debe incluir al menos una letra minúscula")
  .regex(/[A-Z]/, "Debe incluir al menos una letra mayúscula")
  .regex(/\d/, "Debe incluir al menos un dígito")
  .regex(/[^A-Za-z0-9]/, "Debe incluir al menos un símbolo");

/**
 * Esquema Zod para el formulario de login.
 *
 * Reutiliza ``emailSchema`` y exige contraseña no vacía.
 */
export const loginSchema = z.object({
  email: emailSchema,
  password: z.string().min(1, "Contraseña requerida"),
});

/**
 * Esquema Zod para el formulario de registro.
 *
 * Aplica ``passwordSchema`` (12+ chars, mayúsculas, minúsculas, dígito
 * y símbolo) y refine adicional para confirmar la contraseña.
 */
export const registerSchema = z
  .object({
    email: emailSchema,
    fullName: z.string().min(2, "Nombre demasiado corto").max(120),
    password: passwordSchema,
    confirmPassword: z.string(),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: "Las contraseñas no coinciden",
    path: ["confirmPassword"],
  });

/**
 * Esquema Zod para crear un caso (matter).
 *
 * Valida título (3-200), tipo (enum cerrado), descripción opcional
 * (máx 2000), urgencia y contraparte.
 */
export const matterCreateSchema = z.object({
  title: z.string().min(3, "Título demasiado corto").max(200),
  matter_type: z.enum([
    "contract_review",
    "lease",
    "labor",
    "company",
    "data_protection",
    "consumer",
    "family",
    "debt",
    "other",
  ]),
  description: z.string().max(2_000).optional().default(""),
  urgency: z.enum(["low", "medium", "high", "urgent"]),
  counterparty_name: z.string().max(200).optional().default(""),
});

export type LoginInput = z.infer<typeof loginSchema>;
export type RegisterInput = z.infer<typeof registerSchema>;
export type MatterCreateInput = z.infer<typeof matterCreateSchema>;

/** Convert a ZodError into a flat error map usable by simple forms. */
export function fieldErrorsFromZod(error: z.ZodError): Record<string, string> {
  const map: Record<string, string> = {};
  for (const issue of error.issues) {
    const key = issue.path.join(".") || "_root";
    if (!map[key]) map[key] = issue.message;
  }
  return map;
}