import { describe, expect, it } from "vitest";

import { locale, t } from "../i18n";

describe("i18n catalog", () => {
  it("ships pt-BR as the implemented locale", () => {
    expect(locale).toBe("pt-BR");
  });

  it("resolves a plain message", () => {
    expect(t("home.signOut")).toBe("Sair");
  });

  it("resolves the product name from the catalog", () => {
    expect(t("app.name")).toBe("Caramello");
  });

  it("interpolates placeholder values", () => {
    expect(t("home.loggedIn.memberSince", { date: "01/01/2026" })).toContain("01/01/2026");
  });

  it("keeps the placeholder literal when no value is provided", () => {
    expect(t("home.loggedIn.memberSince")).toContain("{date}");
  });

  it("keeps an unknown placeholder literal instead of printing undefined", () => {
    expect(t("home.apiUnavailable.body", { outro: "x" })).toContain("{detail}");
  });
});
