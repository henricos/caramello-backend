/**
 * Typed HTTP client for `apps/api`, implemented as a Server Actions module
 * (`"use server"`).
 *
 * The types mirror the api's Pydantic schemas field by field, in snake_case, so
 * the mapping to the backend is obvious and a contract change is a visible
 * diff. Public identifiers are UUIDs — the api never exposes integer ids (see
 * "Public identifiers are UUIDs" in the root `docs/architecture.md`).
 *
 * The api's business routes are versioned: it mounts `/users`, `/families` and
 * `/finances` under `/api/v1`, so every path below carries that prefix through
 * `API_V1`. The exception is `POST /auth/verify`, which stays unversioned — same
 * as `GET /health` and the `.well-known` documents — because it is the URL the
 * OIDC callback hits and it must not move with an api version bump.
 *
 * `APP_BASE_PATH` (when set) is applied by the api itself through `root_path`,
 * so it is already part of `API_URL` and never appears here.
 *
 * Every exported function runs in `apps/web`'s Node process, never in the
 * browser: the access token is read server-side by `getAccessToken` and never
 * reaches browser JavaScript — protection against token theft via XSS.
 */
"use server";

import { getToken } from "next-auth/jwt";
import type { JWT } from "next-auth/jwt";
import { headers } from "next/headers";

import { env } from "./env";

/**
 * The api is reached through its public URL (tunnel) by default — a hung hop
 * must surface as an "API unavailable" section on the page, never hold the
 * request for the runtime's multi-minute default.
 */
const API_TIMEOUT_MS = 10_000;

/** Version prefix of the api's business surface (see the module docstring). */
const API_V1 = "/api/v1";

/** Local `JWT` extension with only the field read here (see `src/auth.ts`). */
interface OidcJWT extends JWT {
  accessToken?: string;
}

/**
 * Reads the access token DIRECTLY from the session cookie's encrypted JWT
 * (`httpOnly`), never via `auth()`/`session()` — which deliberately do not
 * expose this field. Only callable from a Server Action / Server Component
 * context.
 */
async function getAccessToken(): Promise<string | null> {
  const token = (await getToken({
    req: { headers: await headers() },
    secret: env().authSecret,
  })) as OidcJWT | null;
  return token?.accessToken ?? null;
}

/** Mirrors `UserRead` in the api (`users/schemas.py`). */
export interface UserRead {
  uuid: string;
  idp_sub: string;
  email: string;
  name: string;
  created_at: string;
  updated_at: string;
}

/** Mirrors `FamilyRead` in the api (`families/schemas.py`). */
export interface FamilyRead {
  uuid: string;
  name: string;
  description: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

/**
 * Single outbound path to the api. Private on purpose: callers use the thin
 * typed wrappers below, so every request shares the same timeout, the same
 * cache policy and the same error unwrapping.
 */
async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  // If the access token is absent (expired or revoked session), the call
  // proceeds without `Authorization` and the api answers 401 — defense in
  // depth, since `proxy.ts` should already have blocked the navigation.
  const accessToken = await getAccessToken();
  const response = await fetch(`${env().apiUrl}${path}`, {
    // Never cache an authenticated, per-user response.
    cache: "no-store",
    signal: AbortSignal.timeout(API_TIMEOUT_MS),
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      ...init?.headers,
    },
  });

  if (!response.ok) {
    throw new Error((await readErrorDetail(response)) ?? response.statusText);
  }

  return response.json() as Promise<T>;
}

/**
 * Unwraps the api's error body. FastAPI puts everything under `detail`, and
 * this api's `detail` is often an OBJECT (`{"reason": ..., "message": "<pt-BR>"}`),
 * so `message` is preferred when present; `reason` is the machine-readable
 * fallback and a validation error's list is stringified as a last resort.
 */
async function readErrorDetail(response: Response): Promise<string | undefined> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    const detail = body.detail;
    if (typeof detail === "string") {
      return detail;
    }
    if (detail && typeof detail === "object") {
      const structured = detail as { message?: unknown; reason?: unknown };
      if (typeof structured.message === "string") {
        return structured.message;
      }
      if (typeof structured.reason === "string") {
        return structured.reason;
      }
      return JSON.stringify(detail);
    }
    return undefined;
  } catch {
    return undefined;
  }
}

/** `GET /api/v1/users/me` — the authenticated user's own profile. */
export async function getMe(): Promise<UserRead> {
  return await apiFetch<UserRead>(`${API_V1}/users/me`);
}

/** `GET /api/v1/families/families` — the families the caller belongs to. */
export async function listMyFamilies(): Promise<FamilyRead[]> {
  return await apiFetch<FamilyRead[]>(`${API_V1}/families/families`);
}
