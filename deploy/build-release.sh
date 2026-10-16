#!/usr/bin/env bash
# Build a release tarball (backend wheel + built frontend + installer) into dist/.
# Usage: deploy/build-release.sh
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
version="$(sed -n 's/^__version__ = "\(.*\)"/\1/p' "$root/backend/pendel/__init__.py")"
rev="$(git -C "$root" rev-parse --short HEAD 2>/dev/null || echo unknown)"
out="$root/dist/pendel-$version"

rm -rf "$out" && mkdir -p "$out"
(cd "$root/frontend" && npm ci --silent && npm run build >/dev/null)
cp -r "$root/frontend/build" "$out/static"
buildenv="$root/dist/.buildenv"
[ -x "$buildenv/bin/pip" ] || python3 -m venv "$buildenv"
"$buildenv/bin/pip" wheel --quiet --no-deps --wheel-dir "$out/wheels" "$root/backend"
cp "$root/deploy/install.sh" "$root/deploy/pendel.service" "$out/"
echo "$version+$rev" > "$out/VERSION"
tar -C "$root/dist" -czf "$root/dist/pendel-$version.tar.gz" "pendel-$version"
echo "$root/dist/pendel-$version.tar.gz"
