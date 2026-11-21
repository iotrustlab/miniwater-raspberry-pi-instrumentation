#!/bin/bash
set -euo pipefail

if [[ $# -lt 1 || $# -gt 2 ]]; then
    echo "Usage: $0 {win|linux|docker|rpi|neuron|custom} [ethercat]" >&2
    exit 1
fi
case "$1" in
    win|linux|docker|rpi|neuron|custom) ;;
    *) echo "Error: Unknown platform: $1" >&2; exit 1 ;;
esac
if [[ $# -eq 2 && "$2" != ethercat ]]; then
    echo "Error: The optional second argument must be ethercat" >&2
    exit 1
fi

REPO_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
cd -- "$REPO_DIR"
# pipefail preserves installer failures instead of reporting tee's status.
./background_installer.sh "$@" 2>&1 | tee install_log.txt
