# OpenKH / Panacea unter Linux ARM64: bisherige Einrichtung

[English](README.md) · [Setup-ZIP herunterladen](../packages/Panacea-ARM-Linux-Setup.zip?raw=true)

Stand: 12. Oktober 2026. Für deine Arch-Linux-ARM-/DroidDeck-Umgebung unter Android mit Steam und Proton Experimental ARM64. Im Terminal dieser Linux-Umgebung ausführen, nicht in einer beliebigen Android-/Termux-Shell.

## Grafischer Setup-Assistent für DroidDeck

1. Das [vollständige Setup-ZIP](../packages/Panacea-ARM-Linux-Setup.zip?raw=true) **im Linux-Desktop von DroidDeck** herunterladen und entpacken.
2. Steam, Kingdom Hearts, OpenKH und andere Windows-Anwendungen vollständig schließen. **`Panacea-Setup.desktop`** im entpackten Ordner doppelklicken. Falls der Dateimanager nachfragt: Ausführung erlauben / Starter als vertrauenswürdig markieren. Den Ordner zusammenlassen.
3. Steam-Konto auswählen und bei Bedarf **OpenKH** aktivieren. Die Pfade aus der funktionierenden manuellen Einrichtung unten prüfen. Kein Programmstart und keine Live-Erkennung erforderlich; Steam und Windows-Anwendungen während des gesamten Setups geschlossen lassen.
4. **Einrichten** anklicken, die angezeigten Änderungen prüfen und bestätigen. Vor der Installation werden alle ausgewählten Prefixe, die ersetzte DLL und geänderte Steam-Dateien gesichert. Anschließend Steam neu öffnen.

Auswählbar sind Runtime-Prüfung/-Installation, Einsetzen der beiliegenden main-version.dll, Ausführen einer ausdrücklich ausgewählten originalen `add_registry.bat` im gewählten Prefix und Einrichten der Startoptionen. Nicht benötigte Schritte abwählen. Für OpenKH allein Kingdom Hearts und DLL-Installation abwählen. OpenKH muss bereits als Steam-Verknüpfung existieren und einmal gestartet worden sein; seine AppID ist nicht fest vorgegeben.

Python 3 gehört zu DroidDecks Linux-Werkzeugen. Fehlt Tk, öffnet der Starter automatisch einen **Terminal-Assistenten** mit derselben Erkennung, Prüfung, Sicherung und Installation. Konto und gegebenenfalls OpenKH-Verknüpfung wählen, die Profilpfade und Zusammenfassung prüfen und zum Installieren genau `JA` eingeben. Enter bei dieser letzten Frage beendet ohne Installation. Explizit starten: `bash start-setup.sh --terminal`. Zum Öffnen sind weder Tk-Download noch `sudo` nötig.

DroidDeck kann den Benutzernamen `root` anzeigen, obwohl der Desktop mit der Android-App-UID läuft. Vorhandene Hilfsprogramme werden weiterverwendet; allein für den Download des geprüften Winetricks-Skripts wird kein Paketmanager gestartet. Fehlen tatsächlich Programme wie `cabextract` und gibt es weder Root-Rechte noch `sudo`, nennt das Setup die fehlenden Programme und stoppt **vor jeder Prefix-Änderung**. Diese über die unterstützte Paketinstallation der Linux-Umgebung ergänzen und erneut starten. DroidDecks separater Fake-Root-Installer wird hier nicht automatisiert; Android-Geräte-Root ist nicht nötig.

**Startoptionen:** Beim Spiel werden `version=n,b;dinput8=n,b;LuaBackend=n,b` gesetzt. Weitere DLL-Overrides, Wrapper und Argumente bleiben erhalten. `PROTON_USE_WINED3D=1` wird ausschließlich für die ausgewählte OpenKH-Verknüpfung gesetzt. Steam muss geschlossen sein. Bei komplexen Shell-Ausdrücken oder zwischenzeitlich geänderten Konfigurationsdateien stoppt der Assistent; hierfür bleiben die manuellen Schritte unten verfügbar.

Die beiliegende DLL wird per SHA-256 geprüft, während der Einrichtung nicht von einem veränderlichen Branch heruntergeladen. KH2 Asset Size Cache bleibt eine separate Mod. DroidDeck, Steam, Spiel, OpenKH und dessen ursprüngliche Panacea/BASS-Abhängigkeiten müssen vorhanden sein. Der Assistent lädt OpenKH nicht herunter.

.NET wird über die Windows-x86/x64-Hosts geprüft, auch unter `Program Files/dotnet/x64`. Funktionierende **8.x**-Runtimes bleiben erhalten. Fehlende Runtimes werden mit dem unten dokumentierten Winetricks/.NET-8.0.12-Stand installiert. Ist eine Runtime bei Winetricks eingetragen, besteht aber die Prüfung nicht, wird ohne erzwungene Neuinstallation abgebrochen. `ucrtbase2019` wird nie installiert. Bei den älteren Runtimes werden Winetricks-Installationsnachweise geprüft; ein abschließender Spiel-/OpenKH-Test bleibt nötig.

**Log und Wiederherstellung:** `~/.local/state/panacea-arm/setup.log` (bzw. `$XDG_STATE_HOME/panacea-arm/setup.log`) wird bei jedem Installationsversuch neu geschrieben. Backups liegen mit Zeitstempel im gewählten Sicherungsordner. `backup.json` ordnet Originale und Sicherungen zu; `RESTORE.txt` erklärt die Wiederherstellung. Es gibt keinen automatischen Prefix-Rollback. Eine vollständige Wiederherstellung setzt auch spätere Spielstände/Einstellungen zurück; deshalb den aktuellen Prefix vorher behalten. Panaceas bestehende Logs bleiben unberührt.

### Pfade der funktionierenden manuellen Einrichtung

Für bestehende und neue Einrichtungen gelten dieselben Standardorte. Andere gefundene Prefixe oder `config_info` lösen keinen Bibliothekswechsel aus:

| Bestandteil | Standardort |
|---|---|
| Steam | `~/.local/share/Steam` |
| KH-Prefix | `~/.local/share/Steam/steamapps/compatdata/2552430/pfx` |
| OpenKH-Prefix | `~/.local/share/Steam/steamapps/compatdata/<Shortcut-AppID>/pfx` |
| Spieldateien | `~/Games/Windows/steamapps/common/KINGDOM HEARTS -HD 1.5+2.5 ReMIX-` |
| Proton | `~/.local/share/droiddeck-esync/dist/<Build>` |
| Backups | `~/panacea-prefix-backups` |

Solange vorhanden, wird der getestete Build `valve-experimental-11.0-20261001-arm64-1790819359-76e24eb8146d-r1~015ab1a0` verwendet. Fehlt er, ist ein einzelner gültiger Build im selben esync-Verzeichnis zulässig. Bei mehreren Alternativen `KH_PROTON_ROOT` ausdrücklich in `config.env` setzen. Es wird weder automatisch der neueste Build noch Steams andere Proton-Installation gewählt.

Eine vorhandene **`config.env` neben `start-setup.sh` hat Vorrang**. Der Assistent liest einfache `KH_…=…`-Zuweisungen, Anführungszeichen, `$HOME` und zuvor definierte Variablen, führt daraus aber keine Shell-Befehle aus. Fehlt ein ausdrücklich konfigurierter Pfad, wird ohne Ausweichpfad abgebrochen. Gewollte Änderungen in `config.env` eintragen und den Assistenten neu starten beziehungsweise das Profil neu einlesen.

Fehlt ein Prefix am vorgesehenen Ort, stoppt das Setup. Es verschiebt nichts und verwendet keinen anderen Prefix aus der Spielebibliothek. Der Assistent richtet Abhängigkeiten in bestehenden Steam-Prefixen ein; er lädt Steam/Spiel nicht herunter und erzeugt keine neuen Prefixe. Neu installierte Windows-Komponenten landen in denselben vorgesehenen Prefixen. Die Pfade sind bewährte manuelle Vorgaben, kein Nachweis einer aktuell beobachteten Steam-Laufzeit.

## Was wir damals gemacht haben

| Schritt | Ergebnis |
|---|---|
| Linux-Hilfsprogramme eingerichtet | Protontricks 1.15.0, Winetricks 20260125-next, pip 26.2.1 und cabextract 1.11 wurden im damaligen Verlauf als installiert festgehalten. |
| Steam-Prefixe gefunden | Kingdom Hearts: `2552430`; der separat gestartete OpenKH-Mod-Manager: `4018651221`. |
| Protontricks ausprobiert | Erkannte beide Einträge, konnte den angepassten ARM64-Proton-Build aber nicht korrekt verwenden. |
| Auf das Wine des aktiven Proton-Builds gewechselt | `files/bin-arm64/wine` und `files/bin-arm64/wineserver`, mit dem ausdrücklich ausgewählten Spiel-Prefix. Kein zusätzliches System-Wine. |
| Windows-Komponenten eingerichtet | `dotnet8`, `dotnetdesktop8`, `vcrun6`, `xaudio29`. Im damaligen Check waren .NET Core/Desktop 8.0.12 vorhanden. |
| `ucrtbase2019` versucht | Danach traten `c000007b`/`c0000135` auf. Die beiden `ucrtbase.dll` aus `system32` und `syswow64` wurden aus der Prefix-Sicherung zurückkopiert. |
| Wine danach geprüft | `WINE_TEST_OK`, Exit-Code 0. |
| Originale `add_registry.bat` ausgeführt | Registry-Einrichtung aus dem OpenKH-Paket durchgeführt. |
| DLL-Overrides gesetzt | `version`, `dinput8`, `LuaBackend`: jeweils `native,builtin`. |
| Panacea-Startfehler untersucht | Fehlender `VerQueryValueA`-Export; anschließend zusätzliche Hook-Probleme. Unsere angepasste `version.dll` ergänzt die Exporte und verwendet stabile Trampoline. |

Diese Zusammenfassung rekonstruiert den belegten Ablauf. Nicht alle ursprünglichen Terminalzeilen und Downloadbefehle sind vollständig erhalten. Die beigefügten Skripte sind **neu daraus erstellte Hilfsskripte**, keine unveränderte Kopie des damaligen Terminalverlaufs.

`vcrun6` ist die alte Visual-C++-6-Laufzeit, nicht Visual C++ 2022. Eine zusätzliche Installation von `vcrun2022`, `d3dcompiler_47`, kompletter DirectX-Pakete oder ein Wechsel des Proton-Builds ist durch die rekonstruierten Schritte nicht belegt und wird hier nicht automatisch vorgenommen.

## Pfade aus deinem Aufbau

Im Proton-Log steht dieser Build:

```text
/root/.local/share/droiddeck-esync/dist/valve-experimental-11.0-20261001-arm64-1790819359-76e24eb8146d-r1~015ab1a0
```

Spielordner aus demselben Log:

```text
/root/Games/Windows/steamapps/common/KINGDOM HEARTS -HD 1.5+2.5 ReMIX-
```

Der rekonstruierte Prefix-Pfad ist `$HOME/.local/share/Steam/steamapps/compatdata/2552430/pfx`. Die Konfiguration verwendet `$HOME`, also in deinem damaligen Linux-Container `/root`. Nach einem DroidDeck-/Proton-Update kann der Buildordner anders heißen. Es wird bewusst nicht automatisch der vermeintlich neueste Ordner gewählt.

## Verwendung der Skripte

Das ZIP entpacken und im Unterordner `Panacea-ARM-Linux-Setup` ein Terminal öffnen. Bei einem Repository-Checkout stattdessen nach `linux-setup` wechseln. Alle Skripte lassen sich mit `bash` aufrufen, ein `chmod` ist nicht erforderlich.

```bash
cp config.example.env config.env
nano config.env
bash 01-check.sh
```

Anstelle von `nano` kann ein beliebiger Texteditor verwendet werden. Skriptmeldungen und Konfigurationskommentare sind auf Englisch; diese Anleitung bleibt deutsch.

In `config.env` vor allem `KH_PROTON_ROOT`, `KH_STEAM_ROOT` und `KH_COMPATDATA` kontrollieren. Das Skript akzeptiert nur einen bereits bestehenden Prefix mit `system.reg` und `drive_c`; es legt keinen neuen an. Den separaten OpenKH-Prefix nur dann auswählen, wenn du tatsächlich den Mod Manager dort reparieren willst: dafür **AppID und Compatdata-Pfad gemeinsam** auf die ID deiner OpenKH-Verknüpfung ändern (im ursprünglichen Setup `4018651221`). Die OpenKH-ID ist benutzerspezifisch und keine allgemeine AppID für OpenKH. Die Skripte akzeptieren gültige unsigned Steam-AppIDs; der compatdata-Ordnername muss zur ID passen. Installationen in einem Prefix gelten nicht automatisch im anderen.

**Auf deinem bereits funktionierenden System reicht zunächst die Prüfung. Eine Neuinstallation ist nicht erforderlich.**

| Datei | Zweck |
|---|---|
| `00-host-tools.sh` | Installiert fehlende Linux-Hilfsprogramme und lädt Winetricks mit festgelegtem Commit und SHA-256-Prüfung. Optional Protontricks in einer eigenen Python-Umgebung. |
| `01-check.sh` | Prüft Pfade, Werkzeuge, Runtime-Verzeichnisse und DLL-Dateien. Standardmäßig ohne Wine-Start; `--wine` führt zusätzlich Wine und die installierten .NET-Hosts aus. |
| `02-install-runtimes.sh` | Installiert nur ausdrücklich angegebene Komponenten aus der damaligen Liste. Sichert vorher den vollständigen Prefix. |
| `03-add-registry.sh` | Führt die von dir angegebene originale `add_registry.bat` aus, ebenfalls nach einer Prefix-Sicherung. |
| `04-launch-options.sh` | Gibt die normalen Startoptionen, die Diagnosevariante und den Gegencheck ohne Panacea aus. Ändert Steam nicht automatisch. |
| `common.sh` | Gemeinsame Prefix-/Wine-Auswahl und Backup-Funktionen. |

### 1. Linux-Hilfsprogramme

```bash
bash 00-host-tools.sh --install
```

Unter Arch verwendet das Skript `pacman -S --needed`, unter Debian/Ubuntu `apt-get`. Es installiert kein anderes Wine. Winetricks wird lokal im Unterordner `tools` gespeichert. Der gepinnte Commit ist `f3890f670867b5ffbc3938726db45c0f7d16c8ba`; dessen Datei wird vor Verwendung per SHA-256 geprüft.

Nur wenn du Protontricks zusätzlich wieder haben möchtest:

```bash
bash 00-host-tools.sh --install --with-protontricks
tools/protontricks-venv/bin/protontricks -l
```

Das optionale Protontricks wird nicht für die eigentliche ARM64-Installation verwendet. Die früheren pip-/cabextract-Versionen sind historische Angaben; das Skript verwendet hierfür die Pakete deiner Distribution.

### 2. Windows-Runtimes im richtigen Prefix

Vorher Spiel, Launcher und OpenKH vollständig beenden. Steam selbst darf geöffnet bleiben. Jede Installation erstellt eine vollständige Sicherung unter `KH_BACKUP_ROOT`; genügend freien Speicher einplanen.

Beispiel für eine fehlende Audio-Komponente:

```bash
bash 02-install-runtimes.sh --install xaudio29
```

Den gesamten damaligen Komponentenstand bei Bedarf reproduzieren:

```bash
bash 02-install-runtimes.sh --install dotnet8 dotnetdesktop8 vcrun6 xaudio29
bash 01-check.sh --wine
```

Winetricks lädt die zugehörigen Microsoft-Pakete anhand seiner Downloaddefinitionen und Prüfsummen. Die gepinnten `dotnet8`-/`dotnetdesktop8`-Verben installieren **8.0.12**: Das bildet den damaligen Stand ab und ist keine Zusage, die aktuellste .NET-8-Sicherheitsversion zu installieren. Für das x64-Spiel/OpenKH werden Windows-x86/x64-Komponenten verwendet; der ARM64-Host ist kein Grund, Windows-ARM64-Installer einzusetzen.

`ucrtbase2019` ist nicht erlaubt. Auch beliebige andere Winetricks-Verben werden vom Skript abgelehnt. Bereits vorhandene Komponenten werden ohne `--force` behandelt. Bei einem Fehler wird die weitere Installation abgebrochen; es gibt keinen automatischen Rollback, der spätere Änderungen überdecken könnte.

### 3. OpenKH-Registry

Nur falls diese Einrichtung noch fehlt: `KH_REGISTRY_BAT` in `config.env` auf die vorhandene originale `add_registry.bat` setzen, dann:

```bash
bash 03-add-registry.sh --apply
```

Das Skript startet die Batchdatei aus ihrem eigenen Verzeichnis. Es erzeugt keine unbekannten OpenKH-Registry-Einträge selbst. Die benötigten BASS-/LuaBackend-Dateien kommen weiterhin aus deinem bestehenden OpenKH-/Panacea-Paket; dieses Skriptpaket ersetzt dessen Installation nicht.

### 4. Steam-Startoptionen

Normal:

```text
WINEDLLOVERRIDES="version=n,b;dinput8=n,b;LuaBackend=n,b" %command%
```

Mit Proton-Log:

```text
PROTON_LOG=1 WINEDLLOVERRIDES="version=n,b;dinput8=n,b;LuaBackend=n,b" %command%
```

Weitere bei dir erforderliche Optionen beibehalten. `%command%` ist ein Steam-Platzhalter, kein Terminalbefehl. Für FPS-Messungen das zusätzliche `PROTON_LOG=1` wieder entfernen. Panacea nicht in `dinput8.dll` umbenennen. Unsere reparierte DLL bleibt `version.dll` im Spielordner; der allgemeine KH2 Asset Size Cache bleibt separat in `mod/kh2/dll/KH2AssetSizeCache.dll`.

## OpenKH öffnet sich kurz und schließt wieder

**Bestätigter Workaround in deinem DroidDeck-/Proton-Experimental-ARM64-Aufbau:** WineD3D für den OpenKH Mod Manager verwenden. In Steam unter **OpenKH → Eigenschaften → Startoptionen** eintragen:

```text
PROTON_USE_WINED3D=1 %command%
```

Mit zusätzlichem Diagnose-Log:

```text
PROTON_LOG=1 PROTON_USE_WINED3D=1 %command%
```

Das gilt **nur für den eigenen OpenKH-Steam-Eintrag**. Die funktionierenden Startoptionen von Kingdom Hearts unverändert lassen. Weitere benötigte Optionen beibehalten und `%command%` nur einmal verwenden. Zum Zurücknehmen `PROTON_USE_WINED3D=1` wieder entfernen.

Im fehlgeschlagenen Lauf wurden x64 .NET Core und Windows Desktop **8.0.30** bereits aus `C:\Program Files\dotnet\x64\…` geladen. Anschließend nutzte WPF Direct3D 9 über DXVK; am Ende des Logs standen eine abgebrochene X-Verbindung und Speicherzugriffsfehler in `vkCreateGraphicsPipelines` und `vkQueuePresentKHR`. WineD3D verwendet für Direct3D 9 OpenGL statt des DXVK-/Vulkan-Pfads. Damit startete OpenKH bei dir erfolgreich. Welche Grafikkomponente den ursprünglichen Fehler auslöst, ist noch nicht isoliert; die Option ist kein pauschales Erfordernis für alle ARM64-Systeme.

Das Prüfskript und der Assistent prüfen jetzt auch `Program Files/dotnet/x64` und `dotnet/x86`. Der Assistent führt die gefundenen Windows-Hosts zusätzlich aus; vorhandene Verzeichnisse allein belegen keine funktionierende Runtime.

Quelle: [Valve: Proton-Laufzeitoptionen](https://github.com/ValveSoftware/Proton#runtime-config-options).

## Der damalige UCRT-Rollback

Zurückgesetzt wurden genau `drive_c/windows/system32/ucrtbase.dll` und `drive_c/windows/syswow64/ucrtbase.dll`, jeweils aus der zugehörigen alten Prefix-Sicherung. Das ist **kein normaler Installationsschritt** und wird auf dem jetzt funktionierenden System nicht wiederholt. Eine Vollwiederherstellung würde zusätzlich Registry, Einstellungen und mögliche spätere Spielstände zurücksetzen; vorhandene Backups deshalb nicht blind über den aktuellen Prefix kopieren.

## Prüfung und Grenzen

Für den Assistenten prüft die CI Steam-Erkennung, VDF-Änderungen, getrennte Prefix-Backups, Fehlerfälle und Runtime-Erkennung. Sie öffnet außerdem das Tk-Fenster unter Xvfb und validiert den Desktop-Starter. Ein Test auf einem echten DroidDeck-Gerät steht noch aus. Zusätzlich geprüft werden feste Profilpfade, Vorrang des bekannten Builds, explizite Konfiguration, Ablehnung von Shell-Code, fehlende Prefixe und mehrdeutige Ersatz-Builds.

Die Skripte wurden hier syntaktisch und mit nachgebildeten Wine-/Installationsaufrufen geprüft, einschließlich Pfaden mit Leerzeichen, Prefix-Sicherung, Ablehnung unerlaubter Komponenten und Abbruch bei Wine-Fehlern. Dein Android-/ARM64-System wurde hier nicht ausgeführt. Ein positiver Dateicheck allein belegt noch keine funktionierende Runtime; `--wine`, .NET-Runtime-Ausgabe und der tatsächliche Spielstart sind die nächsten praktischen Prüfungen.

Die Library-Pfade in `common.sh` folgen dem aktuellen Proton-11-Code; ihre exakte damalige Shell-Belegung war nicht rekonstruierbar. Andere Umgebungsvariablen deines DroidDeck-Terminals bleiben erhalten.

## Quellen und Projekte

- [Unser Panacea-Paket](https://github.com/BeZide93/panacea-arm)
- [KH2 Asset Size Cache](https://github.com/BeZide93/kh2-asset-size-cache)
- [Winetricks: geprüfter Quellstand und Downloaddefinitionen](https://github.com/Winetricks/winetricks/blob/f3890f670867b5ffbc3938726db45c0f7d16c8ba/src/winetricks)
- [Valve Proton 11: ARM64-Wine-Auswahl und init_wine](https://github.com/ValveSoftware/Proton/blob/proton_11.0/proton)
- [DroidDeck](https://github.com/Droid-Deck/DroidDeck)
- [Microsoft: .NET unter Windows](https://learn.microsoft.com/dotnet/core/install/windows)
