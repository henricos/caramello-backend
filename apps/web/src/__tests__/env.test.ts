import { describe, expect, it } from "vitest";

import { readEnv } from "../lib/env";

/**
 * `readEnv` takes its source as an argument, so these tests never touch the
 * real `process.env` and never trigger the memoized `env()`.
 */
const VALID = {
  APP_BASE_PATH: "/caramello",
  API_URL: "http://localhost:8000",
  AUTH_OIDC_ISSUER: "http://localhost:8790",
  AUTH_OIDC_CLIENT_ID: "caramello-web",
  AUTH_OIDC_CLIENT_SECRET: "segredo-de-dev",
  AUTH_SECRET: "0123456789012345678901234567890123456789",
};

describe("readEnv", () => {
  it("normalizes a complete environment", () => {
    expect(readEnv(VALID)).toEqual({
      appBasePath: "/caramello",
      apiUrl: "http://localhost:8000",
      oidcIssuer: "http://localhost:8790",
      oidcClientId: "caramello-web",
      oidcClientSecret: "segredo-de-dev",
      authSecret: VALID.AUTH_SECRET,
    });
  });

  it("treats an absent base path as no prefix", () => {
    expect(readEnv({ ...VALID, APP_BASE_PATH: undefined }).appBasePath).toBe("");
  });

  it("treats the root base path as no prefix", () => {
    expect(readEnv({ ...VALID, APP_BASE_PATH: "/" }).appBasePath).toBe("");
  });

  it("strips trailing slashes from the api url and the issuer", () => {
    const parsed = readEnv({
      ...VALID,
      API_URL: "https://exemplo.com/caramello-api/",
      AUTH_OIDC_ISSUER: "https://keycloak.exemplo.com/realms/caramello/",
    });
    expect(parsed.apiUrl).toBe("https://exemplo.com/caramello-api");
    expect(parsed.oidcIssuer).toBe("https://keycloak.exemplo.com/realms/caramello");
  });

  it("defaults the api url to localhost", () => {
    expect(readEnv({ ...VALID, API_URL: undefined }).apiUrl).toBe("http://localhost:8000");
  });

  it.each([
    ["AUTH_OIDC_ISSUER", { AUTH_OIDC_ISSUER: undefined }],
    ["AUTH_OIDC_CLIENT_ID", { AUTH_OIDC_CLIENT_ID: undefined }],
    ["AUTH_OIDC_CLIENT_SECRET", { AUTH_OIDC_CLIENT_SECRET: "   " }],
    ["AUTH_SECRET", { AUTH_SECRET: undefined }],
  ])("fails loudly naming the missing variable %s", (name, override) => {
    expect(() => readEnv({ ...VALID, ...override })).toThrow(name);
  });

  it("rejects a secret that is too short", () => {
    expect(() => readEnv({ ...VALID, AUTH_SECRET: "curto" })).toThrow("AUTH_SECRET");
  });

  it("rejects a non-absolute url", () => {
    expect(() => readEnv({ ...VALID, API_URL: "localhost:8000" })).toThrow("API_URL");
  });

  it("rejects a non-http url scheme", () => {
    expect(() => readEnv({ ...VALID, AUTH_OIDC_ISSUER: "ftp://exemplo.com" })).toThrow(
      "AUTH_OIDC_ISSUER",
    );
  });

  it("rejects an invalid base path naming APP_BASE_PATH", () => {
    expect(() => readEnv({ ...VALID, APP_BASE_PATH: "caramello" })).toThrow("APP_BASE_PATH");
  });
});
