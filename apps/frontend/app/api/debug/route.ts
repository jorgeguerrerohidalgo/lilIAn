import { NextResponse, type NextRequest } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const cookie = request.cookies.get("lilian_auth_token")?.value;
  const allCookies = request.cookies.getAll();
  return NextResponse.json({
    hasCookie: !!cookie,
    cookiePreview: cookie ? cookie.substring(0, 30) + "..." : null,
    allCookieNames: allCookies.map(c => c.name),
    url: request.url,
  });
}
