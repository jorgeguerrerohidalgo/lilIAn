import type { Metadata } from "next";
import { TeamClient } from "@/components/team/team-client";

export const metadata: Metadata = {
  title: "Mi equipo — lilIAn",
  description:
    "Gestiona los miembros de tu organización, asigna roles, y envía o revoca invitaciones.",
};

/**
 * /dashboard/team — Phase 2a (multi-tenant team management).
 *
 * Why a Server Component that delegates immediately:
 *   - Most of the data lives behind the auth cookie, which the BFF
 *     catch-all translates into an ``Authorization: Bearer`` header.
 *     Server Components cannot read that cookie directly, so the
 *     page hands the rendering off to a Client Component that fetches
 *     over the same-origin ``/api/v1/*`` paths.
 *   - The Server Component's only job is to publish metadata and
 *     keep the route registered under the dashboard layout.
 */
export default function TeamPage() {
  return <TeamClient />;
}