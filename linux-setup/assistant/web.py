"""Local browser interface using only Python's standard library."""
from __future__ import annotations
import dataclasses
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import json
import os
from pathlib import Path
import platform
import secrets
import threading
import webbrowser

from core import (APPID, Plan, Runner, SetupError, Target, accounts, digest, execute,
                  launch_edits, plan_summary, require_stopped, setup_lock, shortcuts)
from setup_profile import load_profile

HTML = Path(__file__).with_name('web.html')


class Application:
    def __init__(self, home=None):
        self.home = home or Path.home()
        self.state_dir = Path(os.environ.get('XDG_STATE_HOME', self.home/'.local/state'))/'panacea-arm'
        self.lock = threading.RLock()
        self.busy = False
        self.phase = 'Bereit'
        self.lines = ''
        self.error = ''
        self.backup = ''
        self.reviewed = None

    def choices(self, profile, account):
        path = profile.steam/'userdata'/account/'config/shortcuts.vdf'
        return [s for s in shortcuts(path.read_bytes()) if 'openkh' in (s.name+' '+s.exe).lower()] if path.is_file() else []

    def inventory(self):
        profile = load_profile(self.home)
        users = accounts(profile.steam)
        return {'steam':str(profile.steam), 'game':str(profile.game), 'prefix':str(profile.game_compat),
                'proton':str(profile.proton) if profile.proton else '', 'backup':str(profile.backup),
                'note':profile.note, 'accounts':users,
                'shortcuts':{user:[{'appid':s.appid,'name':s.name,'prefix':str(profile.compat(s.appid))}
                                   for s in self.choices(profile,user)] for user in users}}

    def make_plan(self, data):
        profile = load_profile(self.home)
        proton = profile.require_proton()
        account = data.get('account','')
        if account not in accounts(profile.steam):
            raise SetupError('Steam-Konto auswählen.')
        flags = {}
        for key in ('game','openkh','runtimes','dll','launch'):
            if type(data.get(key)) is not bool:
                raise SetupError('Ungültige Setup-Auswahl: '+key)
            flags[key] = data[key]
        targets = []
        if flags['game']:
            targets.append(Target('Kingdom Hearts',APPID,profile.compat(APPID),proton,True))
        if flags['openkh']:
            found = [s for s in self.choices(profile,account) if s.appid == data.get('shortcut')]
            if len(found) != 1:
                raise SetupError('OpenKH-Verknüpfung auswählen.')
            targets.append(Target('OpenKH',found[0].appid,profile.compat(found[0].appid),proton))
        backup = data.get('backup','')
        batch = data.get('batch','')
        if not isinstance(backup,str) or not isinstance(batch,str):
            raise SetupError('Ungültiger Pfad.')
        backup_path = Path(backup).expanduser()
        if not backup_path.is_absolute():
            raise SetupError('Absolutes Backup-Verzeichnis angeben.')
        batch_path = Path(batch).expanduser() if batch.strip() else None
        if batch_path and not batch_path.is_absolute():
            raise SetupError('Absoluten Pfad zur originalen add_registry.bat angeben.')
        plan = Plan(profile.steam,account,profile.game if flags['dll'] else Path('/'),backup_path,
                    targets,flags['runtimes'],flags['dll'],flags['launch'],batch_path,data.get('batch_target',APPID))
        plan.validate()
        return plan

    def fingerprint(self, plan):
        edits = launch_edits(plan) if plan.launch_options else []
        return digest(json.dumps({'plan':dataclasses.asdict(plan),
                                  'edits':[(str(p),digest(before),digest(after)) for p,before,after in edits]},
                                 sort_keys=True,default=str).encode())

    def review(self, data):
        with self.lock:
            if self.busy:
                raise SetupError('Die Installation läuft bereits.')
            self.reviewed = None
            plan = self.make_plan(data)
            require_stopped()
            summary = plan_summary(plan)
            review_id = secrets.token_urlsafe(24)
            self.reviewed = (review_id,dict(data),self.fingerprint(plan))
            return {'review_id':review_id,'summary':summary}

    def start(self, review_id):
        with self.lock:
            if self.busy:
                raise SetupError('Die Installation läuft bereits.')
            if self.reviewed is None or not hmac.compare_digest(str(review_id),self.reviewed[0]):
                raise SetupError('Bitte die Auswahl zuerst prüfen und bestätigen.')
            _, data, fingerprint = self.reviewed
            self.reviewed = None  # One confirmation can start at most one attempt.
            plan = self.make_plan(data)
            require_stopped()
            if self.fingerprint(plan) != fingerprint:
                raise SetupError('Konfiguration seit der Vorschau geändert. Bitte erneut prüfen.')
            self.busy = True
            self.phase = 'Einrichtung läuft'
            self.lines = self.error = self.backup = ''
            threading.Thread(target=self.worker,args=(plan,),daemon=False).start()
        return {'started':True}

    def log(self, message):
        with self.lock:
            self.lines = (self.lines+message+'\n')[-200000:]

    def worker(self, plan):
        try:
            with setup_lock(self.state_dir):
                with (self.state_dir/'setup.log').open('w') as stream:
                    runner = Runner(self.log,stream)
                    runner.log('Panacea DroidDeck Setup — '+str(self.state_dir/'setup.log'))
                    runner.log(plan_summary(plan))
                    try:
                        backup = execute(plan,runner)
                    except Exception as error:
                        runner.log('FAILED: '+str(error))
                        raise
            with self.lock:
                self.backup = str(backup)
                self.phase = 'Einrichtung abgeschlossen'
        except Exception as error:
            with self.lock:
                self.error = str(error)
                self.phase = 'Einrichtung fehlgeschlagen'
        finally:
            with self.lock:
                self.busy = False

    def status(self):
        with self.lock:
            return {'busy':self.busy,'phase':self.phase,'log':self.lines,'error':self.error,
                    'backup':self.backup,'log_path':str(self.state_dir/'setup.log')}


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, app, address=('127.0.0.1',0)):
        super().__init__(address,Handler)
        self.app = app
        self.token = secrets.token_urlsafe(32)
        self.origin = f'http://127.0.0.1:{self.server_port}'


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def log_message(self, *args):
        pass  # Do not write access logs, credentials or user paths.

    def send(self, code, body, content_type='application/json; charset=utf-8'):
        payload = body if isinstance(body,bytes) else json.dumps(body,ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type',content_type)
        self.send_header('Content-Length',str(len(payload)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Security-Policy',"default-src 'none'; script-src 'self' 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(payload)

    def authorized(self):
        expected = 'Bearer '+self.server.token
        origin = self.headers.get('Origin')
        return (self.headers.get('Host') == self.server.origin.removeprefix('http://') and
                (origin is None or origin == self.server.origin) and
                hmac.compare_digest(self.headers.get('Authorization',''),expected))

    def do_GET(self):
        if self.path == '/' and self.headers.get('Host') == self.server.origin.removeprefix('http://'):
            self.send(200,HTML.read_bytes(),'text/html; charset=utf-8')
            return
        if not self.authorized():
            self.send(403,{'error':'Zugriff nicht erlaubt. Den Desktop-Starter verwenden.'});return
        try:
            if self.path == '/api/inventory':
                self.send(200,self.server.app.inventory())
            elif self.path == '/api/status':
                self.send(200,self.server.app.status())
            else:
                self.send(404,{'error':'Nicht gefunden.'})
        except (SetupError,OSError,UnicodeError,ValueError) as error:
            self.send(400,{'error':str(error)})

    def do_POST(self):
        if not self.authorized():
            self.send(403,{'error':'Zugriff nicht erlaubt.'});return
        try:
            if self.headers.get('Content-Type','').split(';')[0] != 'application/json':
                raise SetupError('JSON erforderlich.')
            length = int(self.headers.get('Content-Length','0'))
            if not 0 < length <= 32768:
                raise SetupError('Ungültige Anfragegröße.')
            data = json.loads(self.rfile.read(length))
            if not isinstance(data,dict):
                raise SetupError('Ungültige Anfrage.')
            if self.path == '/api/review':
                result = self.server.app.review(data)
            elif self.path == '/api/start':
                result = self.server.app.start(data.get('review_id',''))
            elif self.path == '/api/close':
                with self.server.app.lock:
                    if self.server.app.busy:
                        raise SetupError('Bitte die laufende Installation abwarten.')
                    result = {'closed':True}
                    # Mark the instance closed before releasing the lock.
                    self.server.app.reviewed = None
                    self.server.app.busy = True
                threading.Thread(target=self.server.shutdown,daemon=True).start()
            else:
                self.send(404,{'error':'Nicht gefunden.'});return
            self.send(200,result)
        except (SetupError,OSError,UnicodeError,ValueError,TypeError) as error:
            self.send(400,{'error':str(error)})


def main():
    if platform.machine().lower() not in ('aarch64','arm64'):
        raise SystemExit('Im ARM64-Linux-Desktop von DroidDeck starten.')
    with Server(Application()) as server:
        url = server.origin+'/#'+server.token
        print('Panacea-Setup öffnet sich im Browser. Dieses Starter-Fenster geöffnet lassen.',flush=True)
        print('Falls sich kein Browser öffnet, diese lokale Adresse öffnen:\n'+url,flush=True)
        threading.Thread(target=lambda:webbrowser.open(url,new=1),daemon=True).start()
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print('Starter beendet. Eine laufende Installation wird noch abgearbeitet.',flush=True)


if __name__ == '__main__':
    main()
