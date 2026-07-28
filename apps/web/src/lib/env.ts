/**
 * Typed, validated view of the process environment.
 *
 * Why this exists: the module's `.env.development` is auto-loaded by
 * `next dev`/`next start` (Next.js's own convention) and its loader is NOT a
 * shell, so `${VAR:-default}` is unavailable there — defaults must live in
 * code (see "Configuration and environment variables" in the root
 * `AGENTS.md`). This is that place, and it doubles as the fail-loudly gate the
 * api gets from its `Settings`: a missing or malformed variable throws with the
 * variable's NAME, instead of surfacing later as a broken login.
 *
 * Hand-rolled on purpose: six variables and three checks do not justify adding
 * a runtime dependency (zod) to a module whose only other dependencies are the
 * framework itself. `readEnv` takes its source as an argument and is pure, so
 * it is unit-tested without touching the real `process.env`.
 *
 * Messages are in English: they are operator-facing runtime output, not
 * product strings (language policy in the root `AGENTS.md`).
 */
import { normalizeBasePath } from "./base-path";

export interface WebEnv {
  /**
   * Normalized public prefix: `""` (mounted at the origin root) or an absolute
   * path such as `/caramello`. Baked at build time into the assets, and read
   * again at runtime by Auth.js — see `src/auth.ts`.
   */
  appBasePath: string;
  /** Base URL of `apps/api`, without a trailing slash and with no version prefix. */
  apiUrl: string;
  /** OIDC issuer (realm URL), without a trailing slash. */
  oidcIssuer: string;
  oidcClientId: string;
  oidcClientSecret: string;
  authSecret: string;
}

/**
 * Dev-friendly default for the one variable whose local value is always the
 * same. Everything else must be provided: guessing an issuer or a cookie
 * secret would trade a loud failure for a subtly broken session.
 */
const DEFAULT_API_URL = "http://localhost:8000";

/** Minimum length for `AUTH_SECRET` — `openssl rand -base64 33` yields 44. */
const AUTH_SECRET_MIN_LENGTH = 32;

type EnvSource = Record<string, string | undefined>;

function read(source: EnvSource, name: string): string | undefined {
  const value = source[name];
  if (value === undefined) {
    return undefined;
  }
  const trimmed = value.trim();
  return trimmed.length === 0 ? undefined : trimmed;
}

function readRequired(source: EnvSource, name: string): string {
  const value = read(source, name);
  if (value === undefined) {
    throw new Error(
      `Missing required environment variable ${name} (see apps/web/docs/dev-setup.md for development and apps/web/docs/release.md for production).`,
    );
  }
  return value;
}

/** Absolute http(s) URL, trailing slashes stripped so path concatenation is safe. */
function readUrl(source: EnvSource, name: string, fallback?: string): string {
  const value = fallback === undefined ? readRequired(source, name) : (read(source, name) ?? fallback);
  let parsed: URL;
  try {
    parsed = new URL(value);
  } catch {
    throw new Error(
      `Invalid environment variable ${name}: expected an absolute URL, got ${JSON.stringify(value)}.`,
    );
  }
  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    throw new Error(
      `Invalid environment variable ${name}: expected an http(s) URL, got ${JSON.stringify(value)}.`,
    );
  }
  return value.replace(/\/+$/, "");
}

/**
 * Validates and normalizes the environment. Throws on the first problem, always
 * naming the offending variable.
 */
export function readEnv(source: EnvSource): WebEnv {
  const rawBasePath = read(source, "APP_BASE_PATH");
  let appBasePath = "";
  if (rawBasePath !== undefined) {
    const normalized = normalizeBasePath(rawBasePath);
    appBasePath = normalized === "/" ? "" : normalized;
  }

  const authSecret = readRequired(source, "AUTH_SECRET");
  if (authSecret.length < AUTH_SECRET_MIN_LENGTH) {
    throw new Error(
      `Invalid environment variable AUTH_SECRET: at least ${AUTH_SECRET_MIN_LENGTH} characters required. Generate one with "openssl rand -base64 33".`,
    );
  }

  return {
    appBasePath,
    apiUrl: readUrl(source, "API_URL", DEFAULT_API_URL),
    // The issuer loses its trailing slash here, once: it would otherwise break
    // both the discovery URL and the issuer equality check the OIDC client
    // performs against the discovery document (the api normalizes it too).
    oidcIssuer: readUrl(source, "AUTH_OIDC_ISSUER"),
    oidcClientId: readRequired(source, "AUTH_OIDC_CLIENT_ID"),
    oidcClientSecret: readRequired(source, "AUTH_OIDC_CLIENT_SECRET"),
    authSecret,
  };
}

let cached: WebEnv | undefined;

/**
 * Memoized environment for the running server. Deliberately lazy (a function,
 * not a top-level constant) so importing this module — in a unit test, or from
 * a tool that only needs `readEnv` — never validates by side effect. The first
 * caller at server boot is `src/auth.ts`, so a misconfigured deployment fails
 * immediately and visibly.
 */
export function env(): WebEnv {
  cached ??= readEnv(process.env);
  return cached;
}
