#!/bin/sh
# Container start: make /data writable for the app user, then run Pendel without root.
# PUID/PGID choose that user (default 1000:1000); when the container already runs as a
# non-root user (--user, rootless setups), it starts directly.
set -e
PUID="${PUID:-1000}"
PGID="${PGID:-1000}"
run() {
	exec uvicorn pendel.main:app --host 0.0.0.0 --port "${PENDEL_PORT:-8000}" \
		--proxy-headers --forwarded-allow-ips "${PENDEL_FORWARDED_ALLOW_IPS:-127.0.0.1}" "$@"
}
if [ "$(id -u)" = "0" ]; then
	mkdir -p "${PENDEL_DATA_DIR:-/data}"
	if [ "$(stat -c %u:%g "${PENDEL_DATA_DIR:-/data}")" != "$PUID:$PGID" ]; then
		chown -R "$PUID:$PGID" "${PENDEL_DATA_DIR:-/data}"
	fi
	exec setpriv --reuid="$PUID" --regid="$PGID" --clear-groups "$0" "$@"
fi
run "$@"
