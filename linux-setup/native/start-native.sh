#!/usr/bin/env bash
set -euo pipefail
KIT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
state="${XDG_STATE_HOME:-$HOME/.local/state}/panacea-arm"
mkdir -p -- "$state"
exec >"$state/native-start.log" 2>&1
fail() {
    printf '%s\n' "$1"
    if command -v kdialog >/dev/null; then kdialog --error "$1"; fi
    exit 1
}
case "$(uname -m)" in aarch64|arm64) ;; *) fail 'This package requires DroidDeck Linux ARM64.';; esac
export PATH="$HOME/.local/bin:$PATH"
# Android shared storage is commonly noexec and cannot preserve symbolic links.
# Extract the bundled runtime into the Linux home, never into /tmp or Downloads.
base="$HOME/.local/share/panacea-arm/native"
mkdir -p -- "$base"
work=$(mktemp -d "$base/session.XXXXXXXX")
trap 'rm -rf -- "$work"' EXIT
(cd -- "$KIT" && sha256sum -c runtime.sha256) || fail 'The setup package is damaged. Download it again.'
tar -xzf "$KIT/runtime.tar.gz" -C "$work" || fail 'Could not extract the setup interface.'
export PANACEA_SETUP_KIT="$KIT"
"$work/Panacea-Setup/Panacea-Setup" "$@" || fail "The setup interface did not finish successfully. Details: $state/native-start.log"
