# Panacea ARM compatibility fixes

Windows **x64** `version.dll` for Kingdom Hearts HD 1.5+2.5 ReMIX under Proton Experimental ARM64/FEX. This is a modified OpenKH Panacea build, not a native ARM64 DLL or an official OpenKH release.

## What it does

- Adds 13 missing Windows VERSION exports, including `VerQueryValueA`, and forwards them to the system DLL. All four original exports and Panacea initialization are preserved.
- Uses permanent trampolines to call original game functions without repeatedly removing and reinstalling hooks.
- Contains no per-file or continuous performance tracing. Brief hook installation/error messages still go to `panacea_hookfix.log`; Panacea's own logging settings remain applicable.

The separate [Riku performance fix](https://github.com/BeZide93/kh2-riku-perf-fix) is optional and remains a separate mod DLL.

## Install

1. Close the game, launcher and OpenKH Mod Manager. Back up your current `version.dll` outside the game folder.
2. Download the root [version.dll](https://github.com/BeZide93/panacea-arm/raw/refs/heads/main/version.dll) and replace Panacea's `version.dll` in the game folder. Keep your existing Panacea dependencies and mods.
3. Keep your working launch options, including `version=n,b` in `WINEDLLOVERRIDES`. Do not rename this DLL to `dinput8.dll` or put it in `mod/kh2/dll`.

To roll back, close the game and restore your backup. `original/version.dll` is the unmodified input; `rollback/version-v1.dll` retains only the export fix, without the trampoline fix.

The [original package](packages/OpenKH-Panacea-Proton-x64-Paket.zip) includes the DLL, source, technical reports and rollback files. Freshly built packages are available under **Actions → Build and validate → Artifacts → Panacea-ARM-x64**. See [ANLEITUNG.txt](ANLEITUNG.txt) for German instructions.

## Linux ARM64 dependencies

The [Linux setup guide (English)](linux-setup/README.md) and [deutsche Anleitung](linux-setup/README-DE.md) cover prefix selection, runtime installation, backups, checks and Steam launch options. Download the [complete setup kit](https://github.com/BeZide93/panacea-arm/raw/refs/heads/main/packages/Panacea-ARM-Linux-Setup.zip), or use the scripts in [`linux-setup`](linux-setup).

The kit reproduces the recorded DroidDeck setup, including .NET 8.0.12. It uses your existing ARM64 Proton build and rejects `ucrtbase2019`, which broke that setup. Check `config.env` before installing anything; an already working installation does not need its dependencies reinstalled.

**OpenKH opens briefly and closes on ARM64?** Setting `PROTON_USE_WINED3D=1 %command%` in the **OpenKH shortcut's** Steam launch options resolved this in the tested DroidDeck setup. Keep Kingdom Hearts' launch options unchanged. See the [English workaround](linux-setup/README.md#openkh-opens-briefly-and-closes) / [deutschen Hinweis](linux-setup/README-DE.md#openkh-öffnet-sich-kurz-und-schließt-wieder).

## Build and compatibility

Build on Linux x86-64 with Python 3.12, GNU binutils and GCC:

```sh
python3 -m pip install -r requirements.txt
python3 src/build_hookfix.py original/version.dll
python3 tests/verify.py original/version.dll
gcc -O2 -Wall -Wextra -Werror -pthread -I build tests/abi_harness.c -o build/abi_harness
build/abi_harness version.dll
gcc -O2 -Wall -Wextra -Werror -pthread -I build tests/hook_harness.c -o build/hook_harness
build/hook_harness version.dll
python3 scripts/package.py
```

The builder patches the bundled, SHA-256-pinned Panacea binary; it does not rebuild all of OpenKH or accept arbitrary future Panacea builds. An OpenKH update may overwrite the installed DLL. The observed missing-export crash occurred under Proton ARM64; exclusivity to Steam Beta has not been established.

CI runs on pushes, pull requests and manual dispatch. It checks PE structure, all 17 exports, the original entry point, forwarding ABI, trampoline behavior and reproducibility, then uploads the rebuilt DLL and ZIP. Tests execute x64 machine code with mocked Windows APIs on Linux; they do not run the game, Proton or FEX.

## License

OpenKH and the first-party additions: Apache-2.0. HDE64 has its own BSD-style license. See [NOTICE.txt](NOTICE.txt), [LICENSE-OpenKH.txt](LICENSE-OpenKH.txt) and [LICENSE-HDE.txt](LICENSE-HDE.txt).
