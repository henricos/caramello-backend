import Link from "next/link";

import { t, type MessageKey } from "@/i18n";

/**
 * Post-callback error page for Auth.js (`pages.error` in `src/auth.ts`). It is
 * the only UI surface for a denial: the product has no dedicated login screen,
 * so "try again" goes straight back to the OIDC provider.
 *
 * `reason` arrives in a public query string (anyone can type an arbitrary
 * value), so the page only DISPLAYS static text resolved from a fixed map of
 * catalog keys and NEVER renders `reason` itself. The map's values are typed
 * `MessageKey`, so an entry pointing at a missing catalog key fails `tsc`.
 *
 * The keys mirror the reasons the api's `POST /auth/verify` returns (401:
 * `missing_token`, `invalid_token`, `expired_token`; 403: `email_not_verified`,
 * `not_allowlisted`) — machine-readable codes on the wire, pt-BR text resolved
 * here, as the language policy in the root `AGENTS.md` requires.
 */

const ERROR_MESSAGES: Record<string, { title: MessageKey; body: MessageKey }> = {
  not_allowlisted: {
    title: "authError.notAllowlisted.title",
    body: "authError.notAllowlisted.body",
  },
  email_not_verified: {
    title: "authError.emailNotVerified.title",
    body: "authError.emailNotVerified.body",
  },
  missing_token: {
    title: "authError.invalidToken.title",
    body: "authError.invalidToken.body",
  },
  invalid_token: {
    title: "authError.invalidToken.title",
    body: "authError.invalidToken.body",
  },
  expired_token: {
    title: "authError.expiredToken.title",
    body: "authError.expiredToken.body",
  },
};

const FALLBACK_MESSAGE: { title: MessageKey; body: MessageKey } = {
  title: "authError.fallback.title",
  body: "authError.fallback.body",
};

export default async function AuthErrorPage({
  searchParams,
}: {
  searchParams: Promise<{ reason?: string }>;
}) {
  const { reason } = await searchParams;
  // `Object.hasOwn` restricts the lookup to the map's OWN keys — a forged
  // `?reason=constructor` must fall back, never resolve through the prototype.
  const message =
    reason && Object.hasOwn(ERROR_MESSAGES, reason) ? ERROR_MESSAGES[reason] : FALLBACK_MESSAGE;

  return (
    <main className="mx-auto max-w-md px-6 py-20 text-center">
      <h1 className="text-2xl font-semibold tracking-tight">{t(message.title)}</h1>
      <p className="mt-3 text-sm text-muted">{t(message.body)}</p>
      <Link
        href="/api/auth/signin"
        className="mt-8 inline-flex items-center justify-center rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-primary-hover"
      >
        {t("authError.tryAgain")}
      </Link>
    </main>
  );
}
