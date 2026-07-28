import type { NextConfig } from "next";

import { normalizeBasePath } from "./src/lib/base-path";

// basePath is baked at BUILD time (unlike the api's runtime root_path): static
// assets embed the prefix, so the production image is built with
// APP_BASE_PATH set (see Dockerfile, which hard-fails when the build arg is
// empty). In dev the value comes from the committed .env.development; absent
// means "no base path", which is only useful for a throwaway experiment —
// dev and production deliberately use the same /caramello prefix.
//
// This file reads APP_BASE_PATH directly instead of going through
// src/lib/env.ts on purpose: loading the config must not require the auth
// credentials, which only the running server needs.
const configuredBasePath = process.env.APP_BASE_PATH
  ? normalizeBasePath(process.env.APP_BASE_PATH)
  : undefined;

const nextBasePath =
  configuredBasePath && configuredBasePath !== "/" ? configuredBasePath : undefined;

const nextConfig: NextConfig = {
  basePath: nextBasePath,
  devIndicators: false,
  output: "standalone",
  // data/ is the shared external volume (a symlink in dev, a read-only mount
  // in production) — the bundler must never scan or trace it.
  outputFileTracingExcludes: {
    "*": ["data/**"],
  },
};

export default nextConfig;
