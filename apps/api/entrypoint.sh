#!/bin/sh
# Privilege-drop entrypoint, LinuxServer.io-style PUID/PGID pattern
# (https://docs.linuxserver.io/misc/non-root/); rationale in the root
# docs/architecture.md.
#
# Runs as root at container start, adjusts the "app" user to the PUID/PGID
# declared via environment, chowns what needs to change ownership, applies
# the database migrations and then hands off execution to the real
# application process via `exec gosu` — the container never serves traffic
# as root.
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

# /app/.venv and /app/src are image content (not the external volume) —
# chown here is always cheap, regardless of the chosen PUID.
chown -R app:app /app

# /data is the external volume (the only mount that receives writes).
# Recursive chown is a safety net that auto-corrects ownership drift on
# every restart — it does NOT replace the operator aligning the host
# directory's UID/GID (see compose.example.yaml and docs/release.md).
mkdir -p /data
chown -R app:app /data

# Schema always up to date before the app boots: `alembic upgrade head` is
# idempotent (no-op when there is nothing to apply), so a deploy is just a
# matter of swapping the image tag — there is no manual migration step. The
# accepted cost is a SINGLE replica of the api: two replicas starting
# together would race for the migration (see "Automatic migrations at boot"
# in the root docs/architecture.md).
gosu app alembic upgrade head

exec gosu app "$@"
