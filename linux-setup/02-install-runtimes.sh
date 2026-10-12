#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
if [[ ${1:-} != --install || $# -lt 2 ]]; then
    printf '%s\n' 'Usage: bash 02-install-runtimes.sh --install COMPONENT [...]' \
        'Allowed: dotnet8 dotnetdesktop8 vcrun6 xaudio29' \
        'Example: bash 02-install-runtimes.sh --install dotnet8 dotnetdesktop8 vcrun6 xaudio29' \
        'Close the game, launcher and OpenKH first. The prefix will be backed up.' \
        'Reproduces the recorded Winetricks verbs (.NET 8.0.12), not an update to the newest .NET version.'
    exit 0
fi
shift
for verb in "$@"; do
    case "$verb" in dotnet8|dotnetdesktop8|vcrun6|xaudio29) ;; *) fail "Component not allowed: $verb";; esac
done
load_config
for cmd in curl cabextract unzip sha256sum; do need "$cmd"; done
winetricks_path
backup_prefix
check_wine
for verb in "$@"; do
    printf '\nInstalling %s ...\n' "$verb"
    # Deliberately no --force and no ucrtbase2019 or broad vcrun bundles.
    bash "$WINETRICKS" -q "$verb" || fail "Installation of $verb failed. Backup: $BACKUP_DIR/pfx"
    check_wine
done
printf '\nDone. Backup: %s/pfx\nNext: bash 01-check.sh --wine\n' "$BACKUP_DIR"
