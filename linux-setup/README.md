# Linux ARM64 dependency setup

[Deutsch](README-DE.md) · [Download the complete setup kit](https://github.com/BeZide93/panacea-arm/raw/refs/heads/main/packages/Panacea-ARM-Linux-Setup.zip)

Helper scripts for an existing OpenKH / Kingdom Hearts installation in **DroidDeck's Linux environment on Android**, using Proton Experimental ARM64. Run them in that environment's terminal. The Windows game, Panacea and OpenKH still use x86/x64 components.

This kit reconstructs the dependency setup used on October 12, 2026. It is not a complete Steam, DroidDeck or OpenKH installer. The scripts were newly written from the recorded steps; they are not a verbatim terminal transcript.

## Quick start

Extract the ZIP and open a terminal in its `Panacea-ARM-Linux-Setup` folder. If using a repository checkout, enter `linux-setup` instead.

```bash
cp config.example.env config.env
nano config.env
bash 01-check.sh
```

Use any text editor in place of `nano`. Check these settings before installing anything:

| Setting | Meaning |
|---|---|
| `KH_PROTON_ROOT` | Your active DroidDeck Proton build, containing `files/bin-arm64/wine` and `wineserver`. |
| `KH_STEAM_ROOT` | The Steam client installation directory inside the Linux environment. |
| `KH_APPID` | `2552430` for Kingdom Hearts HD 1.5+2.5 ReMIX. |
| `KH_COMPATDATA` | The game's existing `steamapps/compatdata/2552430` directory, without `/pfx`. |
| `KH_BACKUP_ROOT` | Location for complete prefix backups. Keep it outside the prefix. |
| `KH_REGISTRY_BAT` | Optional absolute path to the original `add_registry.bat` supplied with your OpenKH setup. |

The example Proton path identifies the build used in the original setup; it may change after an update. Select the build actually used by the game. No automatic newest-build selection is performed.

The scripts require an existing prefix with `system.reg` and `drive_c`. They will not create a new one. The original user's separate OpenKH shortcut had AppID **4018651221**; this is a user-specific shortcut ID, not a universal OpenKH AppID. If you need that prefix instead, change **both** the AppID and compatdata path. These scripts accept the two IDs from the recorded setup. Installing a runtime in one prefix does not install it in the other.

**If your installation already works, start with the checks. Reinstalling its dependencies is unnecessary.**

## Scripts

| File | Purpose |
|---|---|
| `00-host-tools.sh` | Installs Linux helper packages and downloads a pinned, SHA-256-verified Winetricks script. Optionally installs Protontricks in its own Python environment. |
| `01-check.sh` | Checks paths, helper tools, runtime directories and DLL files. Add `--wine` to run Wine and the installed .NET hosts. |
| `02-install-runtimes.sh` | Installs only explicitly selected components, after backing up the entire prefix. |
| `03-add-registry.sh` | Runs your original OpenKH registry batch from its own directory, after a prefix backup. |
| `04-launch-options.sh` | Prints Steam launch options. Does not change Steam configuration. |
| `common.sh` | Shared Wine selection, configuration and backup functions. |

All scripts can be run using `bash`; executable permissions are not required. `config.env` is a local shell configuration: edit your own copy. Keep it out of commits and public downloads.

## 1. Install Linux helper tools

```bash
bash 00-host-tools.sh --install
```

Supports Arch with `pacman -S --needed` and Debian/Ubuntu with `apt-get`. Installs Python, pip, curl, cabextract, unzip and file. It does not install another Wine. Winetricks is stored in `tools`, pinned to commit `f3890f670867b5ffbc3938726db45c0f7d16c8ba` and checked before installation or use.

Protontricks is optional. In the recorded setup it found the Steam entries but could not use the custom ARM64 Proton build, so the scripts select that build's Wine directly.

```bash
bash 00-host-tools.sh --install --with-protontricks
tools/protontricks-venv/bin/protontricks -l
```

This optional environment uses Protontricks 1.15.0. The installation scripts do not depend on it. Host packages such as pip and cabextract come from your distribution; the historical versions are not forced.

## 2. Install missing Windows runtimes

Close the game, launcher and OpenKH first. Steam itself may remain open. Ensure there is enough space for a complete prefix backup under `KH_BACKUP_ROOT`.

For a missing audio dependency:

```bash
bash 02-install-runtimes.sh --install xaudio29
```

To reproduce the recorded component set when needed:

```bash
bash 02-install-runtimes.sh --install dotnet8 dotnetdesktop8 vcrun6 xaudio29
bash 01-check.sh --wine
```

The four allowed verbs are:

| Component | Purpose / pinned setup |
|---|---|
| `dotnet8` | .NET runtime 8.0.12. |
| `dotnetdesktop8` | Windows Desktop Runtime 8.0.12. |
| `vcrun6` | Legacy Visual C++ 6 runtime; this is not Visual C++ 2022. |
| `xaudio29` | Microsoft XAudio 2.9 redistributable. |

Winetricks downloads the Microsoft packages using its own download definitions and checksums. The pinned .NET verbs reproduce **8.0.12**, not the newest .NET 8 security update. The ARM64 host does not mean that Windows ARM64 installers should replace these x86/x64 dependencies.

The scripts do not force reinstallation. An error stops subsequent components. `ucrtbase2019` and other unlisted verbs are rejected. No automatic rollback overwrites the prefix after an error; the backup path is printed for recovery.

## 3. Apply the OpenKH registry setup

Only if this setup is still missing: set `KH_REGISTRY_BAT` to the existing original `add_registry.bat`, then run:

```bash
bash 03-add-registry.sh --apply
```

The batch runs from its own directory. The kit does not invent OpenKH registry entries or supply a substitute batch. Keep the BASS dependencies, LuaBackend and other files from your existing OpenKH/Panacea installation.

## 4. Steam launch options

The recorded working overrides were:

```text
WINEDLLOVERRIDES="version=n,b;dinput8=n,b;LuaBackend=n,b" %command%
```

To collect a Proton log:

```text
PROTON_LOG=1 WINEDLLOVERRIDES="version=n,b;dinput8=n,b;LuaBackend=n,b" %command%
```

Keep any additional options your environment requires, and use `%command%` only once. These are Steam launch options, not shell commands. Remove the additional `PROTON_LOG=1` for FPS comparisons.

The repaired `version.dll` belongs in the game folder. Do not rename Panacea to `dinput8.dll`; keep a real `dinput8.dll` supplied by another mod if needed. The separate Riku fix remains in `mod/kh2/dll/KH2RikuSizeFix.dll`. `04-launch-options.sh` also prints a `version=b` diagnostic option that disables Panacea, but does not necessarily disable other mod loaders.

## Recorded UCRT failure and recovery

Installing `ucrtbase2019` caused `c000007b` / `c0000135` errors in the original setup. The previous `ucrtbase.dll` files in **both** `drive_c/windows/system32` and `drive_c/windows/syswow64` were restored from that prefix's backup. Wine then returned `WINE_TEST_OK` with exit code 0.

This recovery is not a normal installation step and should not be repeated on a working prefix. A complete prefix restore would also revert registry settings and potentially newer saves. The kit therefore leaves recovery as an explicit action rather than automatically copying a backup over the active prefix.

## Validation and limits

The scripts have been syntax-checked and exercised with mocked Wine/installer calls, including paths with spaces, prefix backups, rejected components and failure handling. They have not been executed here on an Android ARM64 device. File presence alone does not prove a working runtime; use `01-check.sh --wine`, inspect the runtime list and then test the game.

Wine and wineserver are explicitly selected from `files/bin-arm64`. Library search paths follow Valve Proton 11's `init_wine()` layout; their exact historical terminal values were not recoverable. Other environment variables from the DroidDeck terminal are retained.

## References

- [Panacea compatibility DLL](https://github.com/BeZide93/panacea-arm)
- [Riku performance fix](https://github.com/BeZide93/kh2-riku-perf-fix)
- [Pinned Winetricks source and package definitions](https://github.com/Winetricks/winetricks/blob/f3890f670867b5ffbc3938726db45c0f7d16c8ba/src/winetricks)
- [Valve Proton 11](https://github.com/ValveSoftware/Proton/blob/proton_11.0/proton)
- [DroidDeck](https://github.com/Droid-Deck/DroidDeck)
- [Microsoft .NET installation on Windows](https://learn.microsoft.com/dotnet/core/install/windows)
