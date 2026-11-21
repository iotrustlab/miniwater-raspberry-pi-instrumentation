#!/bin/bash
set -euo pipefail

REPO_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
WEBSERVER_DIR="$REPO_DIR/webserver"

# Docker's default files are created by the Dockerfile. Native installations
# use their local configuration without requiring /workdir or /persistent.
if [[ -f "$WEBSERVER_DIR/openplc_default.db" ]]; then
    mkdir -p /persistent/st_files
    cp -n "$WEBSERVER_DIR/dnp3_default.cfg" /persistent/dnp3.cfg
    cp -n "$WEBSERVER_DIR/openplc_default.db" /persistent/openplc.db
    cp -n "$WEBSERVER_DIR/st_files_default/"* /persistent/st_files/
    cp -n /dev/null /persistent/persistent.file
    cp -n /dev/null /persistent/mbconfig.cfg
fi

PYTHON="${OPENPLC_PYTHON:-$REPO_DIR/.venv/bin/python3}"
if [[ ! -x "$PYTHON" ]]; then
    echo "Error: Python executable not found: $PYTHON. Run the installer or set OPENPLC_PYTHON to an absolute executable path." >&2
    exit 1
fi
cd -- "$WEBSERVER_DIR"
exec "$PYTHON" webserver.py
