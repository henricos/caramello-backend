import { describe, expect, it } from "vitest";

import { normalizeBasePath } from "../lib/base-path";

describe("normalizeBasePath", () => {
  it("keeps a valid path", () => {
    expect(normalizeBasePath("/caramello")).toBe("/caramello");
  });

  it("strips the trailing slash", () => {
    expect(normalizeBasePath("/caramello/")).toBe("/caramello");
  });

  it("accepts the root as a path", () => {
    expect(normalizeBasePath("/")).toBe("/");
  });

  it("keeps nested segments", () => {
    expect(normalizeBasePath("/familia/caramello")).toBe("/familia/caramello");
  });

  it.each(["caramello", " /caramello", "/caramello ", "//caramello", ""])(
    "rejects invalid value %j",
    (value) => {
      expect(() => normalizeBasePath(value)).toThrow("Invalid APP_BASE_PATH");
    },
  );
});
