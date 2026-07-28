#!/bin/sh
# Privilege-drop entrypoint, LinuxServer.io-style PUID/PGID pattern
# (https://docs.linuxserver.io/misc/non-root/); rationale in the root
# docs/architecture.md.
#
# Runs as root at container start, adjusts the "app" user to the PUID/PGID
# declared via environment, chowns what needs to change ownership and then hands
# off execution to the real application process via `exec gosu` — the container
# never serves traffic as root.
#
# Difference from apps/api: /data is mounted READ-ONLY here (see
# compose.example.yaml) and is therefore NEVER chown'd — a recursive chown would
# fail on a read-only mount. Read access relies on the operator using the same
# PUID/PGID as the api, matching the host directory's owner.
set -eu

PUID="${PUID:-1000}"
PGID="${PGID:-1000}"

# Reject non-numeric values and 0 BEFORE touching any user/file. A PUID/PGID
# of 0 would mean "root" — never silently accepted.
case "$PUID" in
  ''|*[!0-9]*)
    echo "Invalid PUID/PGID: must be a positive integer, never 0 (root) or non-numeric" >&2
    exit 1
    ;;
esac
case "$PGID" in
  ''|*[!0-9]*)
    echo "Invalid PUID/PGID: must be a positive integer, never 0 (root) or non-numeric" >&2
    exit 1
    ;;
esac
if [ "$PUID" -eq 0 ] || [ "$PGID" -eq 0 ]; then
  echo "Invalid PUID/PGID: must be a positive integer, never 0 (root) or non-numeric" >&2
  exit 1
fi

CURRENT_UID="$(id -u app)"
CURRENT_GID="$(id -g app)"

if [ "$PGID" != "$CURRENT_GID" ]; then
  groupmod -o -g "$PGID" app
fi
if [ "$PUID" != "$CURRENT_UID" ]; then
  usermod -o -u "$PUID" app
fi

# /app is image content (the Next standalone output, including .next/cache, which
# the server writes to) — chown here is always cheap, regardless of the chosen
# PUID. /data is deliberately absent: read-only mount, see the header.
chown -R app:app /app

exec gosu app "$@"
