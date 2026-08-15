import { NextResponse, type NextRequest } from "next/server";

/**
 * BFF logout (S5-fix): clears the frontend's HttpOnly auth cookie so
 * the middleware sees the user as logged out.
 */
export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const AUTH_COOKIE = "lilian_auth_token";

export async function POST(_request: NextRequest) {
  const cookie = `${AUTH_COOKIE}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0`;
  const headers = new Headers();
  headers.append("set-cookie", cookie);
  return NextResponse.json({ ok: true }, { headers });
}
