import { NextResponse, type NextRequest } from "next/server";
import { getApiUrl } from "@/lib/api";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const cookie = request.cookies.get("lilian_auth_token")?.value;
  const apiUrl = getApiUrl();
  
  // Try to forward to backend
  let backendResult = null;
  try {
    const headers: Record<string, string> = {};
    if (cookie) headers["Cookie"] = `lilian_auth_token=${cookie}`;
    const res = await fetch(`${apiUrl}/api/v1/auth/me`, {
      method: "GET",
      headers,
      cache: "no-store",
    });
    backendResult = {
      status: res.status,
      body: await res.text(),
    };
  } catch (err) {
    backendResult = { error: String(err) };
  }
  
  return NextResponse.json({
    hasCookie: !!cookie,
    cookiePreview: cookie ? cookie.substring(0, 30) + "..." : null,
    apiUrl: apiUrl,
    backendResult,
  });
}
