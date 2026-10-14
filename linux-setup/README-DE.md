# OpenKH / Panacea unter Linux ARM64: bisherige Einrichtung

[English](README.md) · [Setup-ZIP herunterladen](../packages/Panacea-ARM-Linux-Setup.zip?raw=true)

Stand: 12. Oktober 2026. Für deine Arch-Linux-ARM-/DroidDeck-Umgebung unter Android mit Steam und Proton Experimental ARM64. Im Terminal dieser Linux-Umgebung ausführen, nicht in einer beliebigen Android-/Termux-Shell.

## Grafischer Setup-Assistent für DroidDeck

### Eigenständiges Setup-Fenster (empfohlen)

1. Unter [GitHub Actions → Build and validate](https://github.com/BeZide93/panacea-arm/actions/workflows/build.yml) den erfolgreichen Lauf für den gewünschten Branch öffnen. Solange dieser PR offen ist, **feat/droiddeck-setup-assistant** wählen.
2. Unter **Artifacts** das Paket **Panacea-DroidDeck-Native-Setup** herunterladen (GitHub-Anmeldung erforderlich). Die heruntergeladene ZIP **einmal** entpacken. Sie enthält direkt den fertigen Ordner **Panacea-DroidDeck-Native-Setup**, keine zweite Setup-ZIP.
3. Im Linux-Desktop von DroidDeck Steam und Windows-Anwendungen schließen und **Panacea-Setup.desktop** doppelklicken. Bei Nachfrage die Ausführung erlauben. Der gesamte Paketordner muss zusammenbleiben.
4. **Welcome → Components → Review → Install** durchlaufen. Konto auswählen, optional OpenKH aktivieren und die Zusammenfassung prüfen. Erst **Install** verändert die Einrichtung. Fortschritt, Fehler und Abschluss bleiben im selben Fenster.

Alle Setup-Oberflächen, Bestätigungen und eigenen Meldungen sind auf Englisch. Im Terminal lautet die abschließende Bestätigung **YES**.

Dieses Paket enthält ein natives Linux-ARM64-Programm mit Python und Tcl/Tk für die Oberfläche. Es startet weder Browser noch Terminal und benötigt keine separat installierte Tk-Version. Es ist keine Windows-EXE: Der Assistent muss direkt auf die Linux-Pfade, Proton und Steam-Konfiguration zugreifen. DroidDecks bestehende Linux-Basis einschließlich `python3` für den Desktop-Starter und die manuellen Skripte bleibt Voraussetzung.

Der Starter entpackt seine Laufzeit vorübergehend nach `~/.local/share/panacea-arm/native/session.*`, damit auch Downloads auf Android-Speicher ohne Ausführungsrechte und Symlink-Unterstützung funktionieren. Nach normalem Beenden wird dieser temporäre Ordner entfernt. Spiel, Prefixe und Backups behalten ihre bisherigen Orte. Eine optionale **config.env** bleibt neben **Panacea-Setup.desktop** im entpackten Paket. Bei Startproblemen steht die Meldung in `~/.local/state/panacea-arm/native-start.log`; diese Datei wird bei jedem Start neu geschrieben.

### Kleines Skriptpaket / alternative Oberflächen

Das [Panacea-ARM-Linux-Setup.zip](../packages/Panacea-ARM-Linux-Setup.zip?raw=true) ist weiterhin das kleine **Skriptpaket**, nicht das eigenständige native Paket. Es enthält dieselbe Installationslogik. Sein Starter verwendet vorhandenes Python/Tk, sonst den lokalen Browser. `bash start-setup.sh --web` startet ausdrücklich den Browser und `bash start-setup.sh --terminal` den Text-Assistenten. Der Browser-Server bleibt auf `127.0.0.1` mit Sitzungstoken und Herkunftsprüfung beschränkt.

In allen Oberflächen: Runtime-Prüfung/-Installation, beiliegende main-version.dll, ausdrücklich ausgewählte originale `add_registry.bat` und Steam-Startoptionen sind auswählbar. Für OpenKH allein Kingdom Hearts und DLL-Installation abwählen. OpenKH muss bereits als Steam-Verknüpfung existieren und einmal gestartet worden sein. Seine AppID wird aus dem gewählten Konto gelesen. Steam und Windows-Anwendungen bleiben während des Setups geschlossen; es gibt keine Live-Erkennung. Die Zusammenfassung allein installiert nichts. Vor Änderungen werden ausgewählte Prefixe, ersetzte DLL und geänderte Steam-Dateien gesichert.

**Lokal installierte Hilfsprogramme:** Desktop-Starter, Prüfungen und Installationsaufrufe berücksichtigen ausdrücklich `~/.local/bin`, wie bei der funktionierenden manuellen Einrichtung. Ein vorhandenes `~/.local/bin/cabextract` wird ohne `sudo` oder Paketinstallation weiterverwendet, auch wenn der Desktop dein Shell-Profil nicht geladen hat. Der verwendete `cabextract`-Pfad steht in `setup.log`.

Auf DroidDeck ARM64 installiert der Assistent fehlendes oder nicht startfähiges `cabextract`, `curl`, `unzip` und `file` automatisch unter `~/.local`, einschließlich der von pacman ermittelten Abhängigkeiten. Pacman erstellt nur einen Paketplan anhand frisch geladener, separater Arch-Linux-ARM-Metadaten; Systempakete und System-Paketdatenbank bleiben unverändert. Downloads erfolgen per HTTPS mit Prüfung der Repository-SHA-256-Prüfsummen. Paket-Installationsskripte werden nicht ausgeführt. Jedes Hilfsprogramm muss erfolgreich starten, bevor es unter `~/.local/bin` bereitgestellt wird. Diese Prüfungen erfolgen vor Änderungen am Wine-Prefix. Dafür sind weder `sudo`, Android-Root noch eine Fake-Root-Sitzung nötig. Vorausgesetzt wird eine funktionierende DroidDeck-Linux-Basis mit Python 3, pacman und (für zstd-Pakete) bsdtar; die Linux-Umgebung selbst wird nicht neu installiert.

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

Auf DroidDeck erstellt dieser optionale Aufruf eine separate Python-Umgebung, richtet pip 26.2.1 aus einem per SHA-256 geprüften PyPI-Wheel ein und installiert Protontricks 1.15.0 samt Python-Abhängigkeiten. System-pip und sudo sind nicht nötig; das System-Python bleibt unverändert. Der normale grafische Ablauf benötigt Protontricks nicht und verwendet Proton-Wine direkt.

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

### Lokale Hilfsprogramme und Entfernen

Starter liegen unter `~/.local/bin`; Pakete, Lizenzen, Paket-Prüfsummen und Sicherungen eventuell ersetzter Starter unter `~/.local/share/panacea-arm/host-tools/install-*`. Funktionierende vorhandene Helfer bleiben erhalten. Das Setup setzt den Suchpfad für sich und alle Installationsprozesse; Shell-Startdateien werden nicht umgeschrieben. Zum Entfernen Setup schließen und nur einen Starter löschen, der `# Managed by Panacea ARM setup.` enthält; gegebenenfalls seine passende Sicherung `previous/<name>` wiederherstellen. Den zugehörigen Installationsordner erst entfernen, wenn kein anderer Starter mehr darauf verweist. Die Wiederherstellung des Wine-Prefixes ist davon unabhängig.

Unter ARM64-Wine kann der x64-.NET-Host unter `Program Files/dotnet/x64/dotnet.exe` liegen. Winetricks beendet dann unter Umständen die Installation, meldet aber beim abschließenden Test auf `Program Files/dotnet/dotnet.exe` Fehler 1. Das Setup erkennt ausschließlich diese konkrete Pfadmeldung und setzt nur fort, wenn Wine und die Runtime-Prüfungen für x86 und x64 erfolgreich sind. Andere Installationsfehler oder fehlende Runtimes führen weiterhin zum Abbruch; Winetricks-Installationsnachweise werden nicht künstlich ergänzt.
