# Four stages on a SINGLE base image (node:22-bookworm-slim), plus the
# PUID/PGID runtime adjustment in entrypoint.sh — same pattern as apps/api,
# rationale in the root docs/architecture.md ("PUID/PGID adjustable at
# runtime"). One base image for every stage means builder and runtime share the
# same libc, so a native dependency compiled in the builder never breaks only in
# production.
FROM node:22-bookworm-slim AS base

FROM base AS deps
WORKDIR /app
# Only the manifests, so a source-only change reuses this layer.
COPY package.json package-lock.json ./
RUN npm ci

FROM base AS builder
WORKDIR /app
# basePath is baked into the assets at BUILD time (see next.config.ts), so it
# cannot be deferred to runtime — an empty value would silently produce an image
# serving the root, with every asset 404ing behind the proxy.
ARG APP_BASE_PATH
RUN test -n "${APP_BASE_PATH}" || (echo "ERROR: APP_BASE_PATH is required at build time (e.g. --build-arg APP_BASE_PATH=/caramello)" && exit 1)
ENV APP_BASE_PATH=${APP_BASE_PATH}
# Throwaway values, only so module evaluation succeeds while Next collects the
# routes (src/lib/env.ts validates the environment at module load). They never
# leave this stage: the runner below does not inherit them, and the real values
# arrive at runtime from the orchestrator.
ENV AUTH_SECRET=build-secret-build-secret-build-secret-1234
ENV AUTH_OIDC_ISSUER=http://127.0.0.1:8790
ENV AUTH_OIDC_CLIENT_ID=build-client
ENV AUTH_OIDC_CLIENT_SECRET=build-secret
ENV API_URL=http://127.0.0.1:8000
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM base AS runner
WORKDIR /app

ARG APP_BASE_PATH
ENV NODE_ENV=production
ENV PORT=3000
ENV HOSTNAME=0.0.0.0
# Auth.js reads the base path at RUNTIME (src/auth.ts, src/proxy.ts) — the value
# baked at build time must also exist as an env var of the final container.
ENV APP_BASE_PATH=${APP_BASE_PATH}

# gosu drops privilege in entrypoint.sh. Version pinned to bookworm's current
# candidate for build reproducibility — same pin as apps/api's Dockerfile.
RUN apt-get update \
  && apt-get install -y --no-install-recommends gosu=1.14-1+b10 \
  && rm -rf /var/lib/apt/lists/*

# Placeholder "app" user (UID/GID 1000 baked at build time only as the default —
# entrypoint.sh adjusts it at runtime). The node base image already ships a
# "node" user owning 1000:1000, so it is RENAMED instead of created (unlike
# apps/api's python base, where 1000 is free).
RUN usermod --login app --shell /usr/sbin/nologin node \
  && groupmod --new-name app node

# `output: "standalone"` produces a self-contained server plus a pruned
# node_modules; the static assets are copied separately because the standalone
# tracer deliberately leaves them out.
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# /data is the external volume mounted at runtime, READ-ONLY for the web (see
# compose.example.yaml). The directory exists in the image so the mount never
# depends on implicit creation, and it is never chown'd: it is read-only here.
RUN mkdir -p /data

EXPOSE 3000

# No fixed USER (same as apps/api) — root at ENTRYPOINT, privilege dropped via
# gosu before the server starts.
ENTRYPOINT ["/entrypoint.sh"]
CMD ["node", "server.js"]
