import { type NextRequest, NextResponse } from "next/server";
import { createMiddlewareClient } from "@/lib/supabase/middleware";

/**
 * Next.js middleware — runs on every matched request before any rendering.
 *
 * Responsibilities:
 * 1. In mock mode (no Supabase credentials): pass all requests through.
 * 2. In real mode:
 *    - Refresh the Supabase session on every request so tokens stay fresh.
 *    - Redirect unauthenticated users away from protected routes to /login.
 *    - Redirect authenticated users away from /login to /dashboard.
 */
export async function middleware(request: NextRequest) {
  const { supabase, response } = createMiddlewareClient(request);

  // Mock mode — no credentials configured, allow everything through.
  if (supabase === null) {
    return NextResponse.next();
  }

  // Trigger session refresh. Must be called before any response is returned so
  // that refreshed tokens are written to cookies in the response we send back.
  const {
    data: { session },
  } = await supabase.auth.getSession();

  const { pathname } = request.nextUrl;
  const isLoginPage = pathname === "/login";

  // Authenticated user hitting /login → send to dashboard.
  if (session && isLoginPage) {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }

  // Unauthenticated user hitting a protected route → send to login.
  if (!session && !isLoginPage) {
    const loginUrl = new URL("/login", request.url);
    return NextResponse.redirect(loginUrl);
  }

  // All other cases: return the response (which may carry refreshed cookies).
  return response;
}

export const config = {
  matcher: [
    /*
     * Match all request paths EXCEPT:
     * - _next/static  (Next.js static assets)
     * - _next/image   (Next.js image optimisation)
     * - favicon.ico
     * - Any file with an extension (e.g. .png, .svg, .js, .css)
     */
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico|css|js|woff2?|ttf|eot)$).*)",
  ],
};
