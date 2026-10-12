#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
if [[ $# != 1 || ${1:-} != --apply ]]; then
    printf '%s\n' 'Usage: bash 03-add-registry.sh --apply' \
        'KH_REGISTRY_BAT must point to the original add_registry.bat from your OpenKH setup.' \
        'Close the game, launcher and OpenKH first. The prefix will be backed up.'
    exit 0
fi
load_config
[[ -n ${KH_REGISTRY_BAT:-} && -f "$KH_REGISTRY_BAT" && "$KH_REGISTRY_BAT" == /* ]] || fail 'KH_REGISTRY_BAT is missing or is not an absolute file path.'
backup_prefix
check_wine
cd -- "$(dirname -- "$KH_REGISTRY_BAT")"
batch=$("$WINE" winepath.exe -w "$KH_REGISTRY_BAT" | tr -d '\r')
[[ -n "$batch" ]] || fail 'Wine path conversion failed.'
"$WINE" cmd.exe /d /s /c "\"$batch\""
check_wine
printf 'Registry batch executed. Backup: %s/pfx\n' "$BACKUP_DIR"
