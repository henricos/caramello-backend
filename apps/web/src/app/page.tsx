import { signOut } from "@/auth";
import { locale, t } from "@/i18n";
import { getMe, listMyFamilies, type FamilyRead, type UserRead } from "@/lib/api-client";

/**
 * Home page. Proves the login → web → api → database path end to end: who is
 * logged in (`GET /api/v1/users/me`) and which families that person belongs to
 * (`GET /api/v1/families/families`, scoped by family membership in the api).
 *
 * An async Server Component: both calls happen in the Node process, with the
 * access token read from the encrypted cookie — nothing authenticated is
 * fetched from the browser.
 *
 * Every user-facing string comes from the message catalog (`@/i18n`); see the
 * language policy in the root `AGENTS.md`.
 */

function formatDate(value: string): string {
  return new Date(value).toLocaleDateString(locale);
}

export default async function HomePage() {
  let me: UserRead | null = null;
  let families: FamilyRead[] | null = null;
  let apiError: string | null = null;

  try {
    [me, families] = await Promise.all([getMe(), listMyFamilies()]);
  } catch (error) {
    // The api being down must degrade the page, never crash it: the sign-out
    // form below is the user's way out of a session the api cannot serve.
    apiError = error instanceof Error ? error.message : t("home.apiUnavailable.unknownError");
  }

  return (
    <main className="mx-auto max-w-2xl px-6 py-16">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{t("app.name")}</h1>
          <p className="mt-1 text-sm text-muted">{t("home.tagline")}</p>
        </div>
        <form
          action={async () => {
            "use server";
            await signOut();
          }}
        >
          <button
            type="submit"
            className="rounded-lg border border-border bg-surface px-3 py-1.5 text-sm text-muted transition-colors hover:text-ink"
          >
            {t("home.signOut")}
          </button>
        </form>
      </header>

      {apiError ? (
        <section className="mt-10 rounded-lg border border-border bg-surface p-6">
          <h2 className="text-base font-medium">{t("home.apiUnavailable.title")}</h2>
          <p className="mt-2 text-sm text-muted">
            {t("home.apiUnavailable.body", { detail: apiError })}
          </p>
        </section>
      ) : (
        <>
          <section className="mt-10 rounded-lg border border-border bg-surface p-6">
            <h2 className="text-base font-medium">{t("home.loggedIn.title")}</h2>
            <p className="mt-2 text-sm text-muted">
              {me?.name ? `${me.name} (${me.email})` : me?.email}
            </p>
            {me ? (
              <p className="mt-1 text-xs text-muted">
                {t("home.loggedIn.memberSince", { date: formatDate(me.created_at) })}
              </p>
            ) : null}
          </section>

          <section className="mt-6 rounded-lg border border-border bg-surface p-6">
            <h2 className="text-base font-medium">{t("home.families.title")}</h2>
            <p className="mt-1 text-xs text-muted">
              {/* The endpoint is a code identifier, not prose: it stays a
                  literal on purpose, and every word around it comes from the
                  catalog (which is why the sentence ends in a colon). */}
              {t("home.families.source")} <code>GET /api/v1/families/families</code>
            </p>
            {families && families.length > 0 ? (
              <ul className="mt-4 divide-y divide-border">
                {families.map((family) => (
                  <li key={family.uuid} className="py-2">
                    <p className="text-sm">{family.name}</p>
                    <p className="text-xs text-muted">
                      {family.description ?? t("home.families.noDescription")}
                    </p>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-4 text-sm text-muted">{t("home.families.empty")}</p>
            )}
          </section>
        </>
      )}
    </main>
  );
}
