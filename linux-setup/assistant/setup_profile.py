"""Offline defaults from the working manual DroidDeck setup; never source shell code."""
from dataclasses import dataclass
from pathlib import Path
import re
import shlex

from core import APPID, KIT, SetupError, valid_proton

KNOWN_BUILD = 'valve-experimental-11.0-20261001-arm64-1790819359-76e24eb8146d-r1~015ab1a0'
GAME_FOLDER = 'KINGDOM HEARTS -HD 1.5+2.5 ReMIX-'
KEYS = {'KH_APPID','KH_STEAM_ROOT','KH_COMPATDATA','KH_PROTON_ROOT','KH_GAME_DIR','KH_BACKUP_ROOT','KH_REGISTRY_BAT'}


def read_config(path, home):
    """Accept the kit's simple assignments, not arbitrary executable config.env."""
    if not path.is_file():
        return {}
    values = {'HOME': str(home)}
    selected = {}
    for number, line in enumerate(path.read_text().splitlines(), 1):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        match = re.fullmatch(r'(KH_[A-Z_]+)=(.*)', line)
        if not match or match[1] not in KEYS:
            raise SetupError(f'config.env Zeile {number}: nur einfache KH_…-Zuweisungen unterstützt; keine Shell-Befehle.')
        key, raw = match.groups()
        try:
            parts = shlex.split(raw, comments=True)
        except ValueError as error:
            raise SetupError(f'config.env Zeile {number}: ungültige Anführungszeichen.') from error
        if len(parts) != 1 or '$(' in parts[0] or '`' in parts[0]:
            raise SetupError(f'config.env Zeile {number}: einfacher Wert erforderlich; keine Befehlsauswertung.')
        value = parts[0]
        if not raw.startswith("'"):
            def expand(m):
                variable = m[1] or m[2]
                if variable not in values:
                    raise SetupError(f'config.env: unbekannte Variable {variable}.')
                return values[variable]
            value = re.sub(r'\$\{([A-Za-z_][A-Za-z_0-9]*)\}|\$([A-Za-z_][A-Za-z_0-9]*)', expand, value)
        values[key] = selected[key] = value
    if selected.get('KH_APPID', APPID) != APPID:
        raise SetupError('Der Assistent erwartet KH_APPID=2552430. OpenKH wird separat über seine Steam-Verknüpfung gewählt.')
    return selected


@dataclass
class Profile:
    steam: Path
    game: Path
    game_compat: Path
    backup: Path
    proton: Path | None
    note: str

    def compat(self, appid):
        return self.game_compat if appid == APPID else self.steam/'steamapps/compatdata'/appid

    def require_proton(self):
        if self.proton is None or not valid_proton(self.proton):
            raise SetupError(self.note)
        return self.proton


def load_profile(home, kit=KIT):
    home = Path(home)
    values = read_config(kit/'config.env', home)
    def path(key, default):
        p = Path(values.get(key, str(default)))
        if not p.is_absolute():
            raise SetupError(f'{key}: absoluter Pfad erforderlich.')
        return p
    steam = path('KH_STEAM_ROOT', home/'.local/share/Steam')
    compat = path('KH_COMPATDATA', steam/'steamapps/compatdata'/APPID)
    game = path('KH_GAME_DIR', home/'Games/Windows/steamapps/common'/GAME_FOLDER)
    backup = path('KH_BACKUP_ROOT', home/'panacea-prefix-backups')
    dist = home/'.local/share/droiddeck-esync/dist'
    known = dist/KNOWN_BUILD
    if 'KH_PROTON_ROOT' in values:
        proton = path('KH_PROTON_ROOT', known)
        note = 'Proton aus deiner config.env. Bei fehlendem Build KH_PROTON_ROOT ausdrücklich aktualisieren.'
    elif valid_proton(known):
        proton = known
        note = 'Proton aus der bisher funktionierenden manuellen Einrichtung.'
    else:
        candidates = [p for p in sorted(dist.glob('*')) if valid_proton(p)]
        proton = candidates[0] if len(candidates) == 1 else None
        note = ('Einziger vorhandener ARM64-Build im vorgesehenen droiddeck-esync/dist-Verzeichnis.' if proton else
                'Kein eindeutiger esync-Build am vorgesehenen Ort. In config.env KH_PROTON_ROOT auf den gewünschten '
                'vorhandenen ARM64-Build setzen. Kein automatischer Wechsel zu Steams anderer Proton-Installation.')
    return Profile(steam, game, compat, backup, proton, note)
