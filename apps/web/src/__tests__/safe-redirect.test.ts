import { describe, expect, it } from "vitest";

import { resolveAuthRedirect } from "../lib/safe-redirect";

const BASE_URL = "https://exemplo.com";
const BASE_PATH = "/caramello";
const HOME = `${BASE_URL}${BASE_PATH}`;

describe("resolveAuthRedirect", () => {
  it("keeps a relative url inside the base path", () => {
    expect(resolveAuthRedirect("/caramello/agenda", BASE_URL, BASE_PATH)).toBe(
      `${BASE_URL}/caramello/agenda`,
    );
  });

  it("keeps an absolute url on the app origin inside the base path", () => {
    expect(resolveAuthRedirect(`${HOME}/financas`, BASE_URL, BASE_PATH)).toBe(`${HOME}/financas`);
  });

  it("falls back to home for a relative url outside the base path", () => {
    expect(resolveAuthRedirect("/outra-app", BASE_URL, BASE_PATH)).toBe(HOME);
  });

  it("falls back to home for another origin", () => {
    expect(resolveAuthRedirect("https://malicioso.com/caramello", BASE_URL, BASE_PATH)).toBe(HOME);
  });

  it("rejects an origin that merely starts with the app origin (open redirect)", () => {
    // "https://exemplo.com.evil.com" passes a naive startsWith(baseUrl) check —
    // the exact bug this helper exists to prevent.
    expect(resolveAuthRedirect("https://exemplo.com.evil.com/caramello", BASE_URL, BASE_PATH)).toBe(
      HOME,
    );
  });

  it("rejects a path that merely starts with the base path string", () => {
    expect(resolveAuthRedirect("/caramello-evil", BASE_URL, BASE_PATH)).toBe(HOME);
  });

  it("rejects a protocol-relative url pointing elsewhere", () => {
    expect(resolveAuthRedirect("//exemplo.com.evil.com/caramello", BASE_URL, BASE_PATH)).toBe(HOME);
  });

  it("falls back to home for an unparseable url", () => {
    expect(resolveAuthRedirect("https://", BASE_URL, BASE_PATH)).toBe(HOME);
  });

  it("accepts any path on the app origin when there is no base path", () => {
    expect(resolveAuthRedirect("/agenda", BASE_URL, "")).toBe(`${BASE_URL}/agenda`);
    expect(resolveAuthRedirect("https://malicioso.com/", BASE_URL, "")).toBe(BASE_URL);
  });
});
