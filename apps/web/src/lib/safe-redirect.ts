/**
 * Post-auth redirect resolution, extracted from the Auth.js `redirect`
 * callback (src/auth.ts) so the security-sensitive logic is unit-testable.
 *
 * Rules: the target must be on the app's own origin (compared as PARSED
 * origins, never string prefixes — "https://exemplo.com.evil.com" starts with
 * "https://exemplo.com" textually) and must equal the base path or sit under
 * it ("/caramello-evil" is not inside "/caramello"). Anything else falls back
 * to the app home.
 */
export function resolveAuthRedirect(url: string, baseUrl: string, appBasePath: string): string {
  const fallback = `${baseUrl}${appBasePath}`;
  const target = url.startsWith("/") ? `${baseUrl}${url}` : url;

  let parsed: URL;
  try {
    parsed = new URL(target);
  } catch {
    return fallback;
  }

  if (parsed.origin !== new URL(baseUrl).origin) {
    return fallback;
  }

  if (appBasePath) {
    const pathname = parsed.pathname;
    if (pathname !== appBasePath && !pathname.startsWith(`${appBasePath}/`)) {
      return fallback;
    }
  }

  return target;
}
