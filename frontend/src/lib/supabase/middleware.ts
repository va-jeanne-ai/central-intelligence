import { createServerClient } from "@supabase/ssr";
import { type NextRequest, NextResponse } from "next/server";

/**
 * Creates a Supabase client suitable for use inside Next.js middleware.
 *
 * Uses getAll/setAll cookie methods (the non-deprecated API) to ensure the
 * session is correctly refreshed and written back to response cookies on every
 * request.
 *
 * Returns `{ supabase: null, response }` when env vars are absent (mock mode)
 * so the caller can skip all auth checks.
 */
export function createMiddlewareClient(request: NextRequest): {
  supabase: ReturnType<typeof createServerClient> | null;
  response: NextResponse;
} {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

  if (!url || !key) {
    return { supabase: null, response: NextResponse.next() };
  }

  // Start with a base response that will be modified to carry refreshed
  // session cookies back to the browser.
  let response = NextResponse.next({
    request: {
      headers: request.headers,
    },
  });

  const supabase = createServerClient(url, key, {
    cookies: {
      getAll() {
        return request.cookies.getAll();
      },
      setAll(cookiesToSet) {
        // First write cookies onto the outgoing request object so that any
        // subsequent server-side reads within this request see the updated
        // values.
        cookiesToSet.forEach(({ name, value }) => {
          request.cookies.set(name, value);
        });

        // Re-create the response so it carries the new cookie headers, then
        // write the cookies onto the response as well so the browser receives
        // them.
        response = NextResponse.next({
          request: {
            headers: request.headers,
          },
        });

        cookiesToSet.forEach(({ name, value, options }) => {
          response.cookies.set(name, value, options);
        });
      },
    },
  });

  return { supabase, response };
}
