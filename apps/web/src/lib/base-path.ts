/**
 * Normalization of `APP_BASE_PATH`, mirroring the api's
 * `normalize_app_base_path` — the two modules must agree on what a valid base
 * path is, or the web's assets and the api's routes end up disagreeing about
 * the mount point.
 */

const BASE_PATH_ERROR_PREFIX = "Invalid APP_BASE_PATH:";

function assertNonEmptyString(input: unknown): asserts input is string {
  if (typeof input !== "string" || input.trim().length === 0) {
    throw new Error(`${BASE_PATH_ERROR_PREFIX} provide an absolute path, such as "/caramello".`);
  }
}

export function normalizeBasePath(input: string): string {
  assertNonEmptyString(input);

  if (input !== input.trim()) {
    throw new Error(`${BASE_PATH_ERROR_PREFIX} no leading or trailing whitespace allowed.`);
  }

  if (!input.startsWith("/")) {
    throw new Error(
      `${BASE_PATH_ERROR_PREFIX} the value must start with "/". Example: "/caramello".`,
    );
  }

  if (input.includes("//")) {
    throw new Error(`${BASE_PATH_ERROR_PREFIX} no duplicated slashes allowed.`);
  }

  if (input.length > 1 && input.endsWith("/")) {
    return input.slice(0, -1);
  }

  return input;
}
