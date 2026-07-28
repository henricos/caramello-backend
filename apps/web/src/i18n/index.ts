/**
 * Minimal i18n layer — the structural guarantee of the project's language
 * policy (see the root `AGENTS.md`): the repository is English-only, and every
 * string rendered to the END USER lives in the message catalog, never
 * hardcoded in a component.
 *
 * The product implements a single locale (pt-BR), so this is a dependency-free
 * catalog plus accessor instead of a full i18n framework. The catalog file
 * follows the `messages/<locale>.json` convention, so swapping in a library
 * like next-intl later (locale negotiation, routing, plurals) means reusing the
 * same file, not rewriting the strings.
 */
import messages from "../../messages/pt-BR.json";

/** The single locale the product ships today. */
export const locale = "pt-BR";

export type MessageKey = keyof typeof messages;

/**
 * Resolves a catalog message, interpolating `{placeholder}` values. Keys are
 * checked at compile time (`MessageKey`), so a typo or a missing catalog entry
 * fails `tsc`, not the user.
 */
export function t(key: MessageKey, values?: Record<string, string>): string {
  const template: string = messages[key];
  if (!values) {
    return template;
  }
  return template.replace(/\{(\w+)\}/g, (match, name: string) => values[name] ?? match);
}
