#!/usr/bin/env bash
# Install or update Pendel on Debian/Ubuntu (run as root inside the unpacked release directory).
# Data lives in /var/lib/pendel, settings in /etc/pendel/pendel.env; both survive updates.
set -euo pipefail
cd "$(dirname "$0")"

DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3 python3-venv >/dev/null
id pendel >/dev/null 2>&1 || useradd --system --home-dir /var/lib/pendel --shell /usr/sbin/nologin pendel
install -d -o pendel -g pendel -m 750 /var/lib/pendel
install -d -m 755 /etc/pendel /opt/pendel

if [ ! -f /etc/pendel/pendel.env ]; then
	cat > /etc/pendel/pendel.env <<'ENV'
PENDEL_DATA_DIR=/var/lib/pendel
PENDEL_STATIC_DIR=/opt/pendel/static
# Keep true behind an HTTPS reverse proxy
PENDEL_SECURE_COOKIES=true
# Addresses of trusted reverse proxies / cloudflared (for real client IPs), comma separated
PENDEL_FORWARDED_ALLOW_IPS=127.0.0.1
# Optional default for the public address; can also be set in the UI (Admin → Instance)
#PENDEL_PUBLIC_URL=https://pendel.example.com
PENDEL_PORT=8000
ENV
	chmod 640 /etc/pendel/pendel.env
	chgrp pendel /etc/pendel/pendel.env
fi

[ -d /opt/pendel/venv ] || python3 -m venv /opt/pendel/venv
/opt/pendel/venv/bin/pip install --quiet --upgrade pip
/opt/pendel/venv/bin/pip install --quiet --upgrade --force-reinstall --no-deps wheels/*.whl
/opt/pendel/venv/bin/pip install --quiet wheels/*.whl  # dependencies

rm -rf /opt/pendel/static.new && cp -r static /opt/pendel/static.new
rm -rf /opt/pendel/static && mv /opt/pendel/static.new /opt/pendel/static
cp VERSION /opt/pendel/VERSION

install -m 644 pendel.service /etc/systemd/system/pendel.service
systemctl daemon-reload
systemctl enable --quiet pendel
systemctl restart pendel

port="$(sed -n 's/^PENDEL_PORT=//p' /etc/pendel/pendel.env)"
for _ in $(seq 20); do
	if python3 -c 'import sys, urllib.request; urllib.request.urlopen(sys.argv[1], timeout=2)' \
		"http://127.0.0.1:${port:-8000}/api/health" 2>/dev/null; then
		echo "Pendel $(cat VERSION) installed and running"
		if python3 -c 'import json, sys, urllib.request; sys.exit(not json.load(urllib.request.urlopen(sys.argv[1]))["needed"])' \
			"http://127.0.0.1:${port:-8000}/api/setup" 2>/dev/null; then
			echo "First start: open Pendel in the browser and enter the setup code from the log:"
			journalctl -u pendel --no-pager | grep -o 'setup code: .*' | tail -1
		fi
		exit 0
	fi
	sleep 1
done
echo "Pendel did not become healthy, see: journalctl -u pendel" >&2
exit 1
