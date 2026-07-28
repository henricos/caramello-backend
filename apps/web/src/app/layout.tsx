import "./globals.css";

import { locale, t } from "@/i18n";

// `lang` and the document title are user-facing, so both come from the same
// single-locale source as every other string (see @/i18n).
export const metadata = {
  title: t("app.name"),
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang={locale}>
      <body className="min-h-screen bg-bg font-sans text-ink antialiased">{children}</body>
    </html>
  );
}
