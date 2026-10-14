"""Small Tk front end; workers never call Tk APIs directly."""
import os
from pathlib import Path
import platform
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from core import (APPID, Plan, Runner, SetupError, Target, accounts, execute,
                  game_dirs, libraries, prefixes, proton_candidates,
                  proton_hint, require_stopped, setup_lock, shortcuts, steam_roots, plan_summary)


class Assistant:
    def __init__(self, window):
        self.window = window
        window.title('Panacea ARM – DroidDeck Setup')
        window.geometry('960x800')
        self.busy = False
        self.events = queue.Queue()
        self.home = Path.home()
        self.state = Path(os.environ.get('XDG_STATE_HOME', self.home/'.local/state'))/'panacea-arm'
        self.shortcut_map = {}
        self.vars = {key: tk.StringVar() for key in ['steam','account','game','game_prefix','game_proton',
                                                   'shortcut','openkh_prefix','openkh_proton','batch','batch_target','backup']}
        self.flags = {key: tk.BooleanVar(value=value) for key,value in
                      [('game',True),('openkh',False),('runtimes',True),('dll',True),('launch',True)]}
        self.vars['backup'].set(str(self.home/'panacea-prefix-backups'))
        self.vars['batch_target'].set(APPID)
        outer = ttk.Frame(window, padding=12); outer.pack(fill='both', expand=True)
        ttk.Label(outer, text='Panacea / OpenKH einrichten', font=('',16,'bold')).pack(anchor='w')
        ttk.Label(outer, text='Steam, Spiel und Windows-Anwendungen vor der Installation vollständig schließen.\n'
                             'DroidDeck, Steam sowie Spiel/OpenKH müssen bereits installiert und einmal gestartet worden sein.').pack(anchor='w', pady=(4,10))
        form = ttk.Frame(outer); form.pack(fill='x'); form.columnconfigure(1,weight=1)
        self.form = form
        self.row = 0
        self.widgets = []
        self.field('Steam-Verzeichnis', 'steam')
        button = ttk.Button(form, text='Installationen suchen / neu einlesen', command=self.detect)
        button.grid(row=self.row,column=1,sticky='w',pady=4); self.widgets.append(button); self.row += 1
        self.account = self.field('Steam-Konto (userdata-ID)', 'account', combo=True)
        self.account.bind('<<ComboboxSelected>>', lambda _: self.read_account())
        self.check('Kingdom Hearts einrichten', 'game')
        self.field('Spielordner', 'game')
        self.game_prefix = self.field('KH compatdata (ohne /pfx)', 'game_prefix', combo=True, browse=True)
        self.game_prefix.bind('<<ComboboxSelected>>',lambda _: self.suggest_proton('game'))
        self.game_proton = self.field('KH ARM64-Proton', 'game_proton', combo=True,browse=True)
        self.check('OpenKH zusätzlich / separat einrichten', 'openkh')
        self.shortcut = self.field('OpenKH Steam-Verknüpfung', 'shortcut',combo=True)
        self.shortcut.bind('<<ComboboxSelected>>',lambda _: self.choose_shortcut())
        self.openkh_prefix = self.field('OpenKH compatdata (ohne /pfx)', 'openkh_prefix',combo=True,browse=True)
        self.openkh_prefix.bind('<<ComboboxSelected>>',lambda _: self.suggest_proton('openkh'))
        self.openkh_proton = self.field('OpenKH ARM64-Proton', 'openkh_proton',combo=True,browse=True)
        self.field('Backup-Verzeichnis', 'backup')
        self.field('Optional: originale add_registry.bat', 'batch',file=True)
        self.batch_target = self.field('Registry-Batch ausführen in AppID', 'batch_target',combo=True)
        self.batch_target['values'] = [APPID]
        options = ttk.Frame(outer); options.pack(fill='x',pady=8)
        for key,label in [('runtimes','Fehlende Runtimes installieren'),('dll','Main version.dll einsetzen'),('launch','Steam-Startoptionen einrichten')]:
            widget = ttk.Checkbutton(options,text=label,variable=self.flags[key]);widget.pack(side='left',padx=(0,12));self.widgets.append(widget)
        buttons = ttk.Frame(outer);buttons.pack(fill='x')
        for text,command in [('Auswahl prüfen',self.review),('Einrichten',self.install)]:
            button=ttk.Button(buttons,text=text,command=command);button.pack(side='left',padx=(0,8));self.widgets.append(button)
        ttk.Button(buttons,text='Ordner mit Setup-Log öffnen',command=self.open_log).pack(side='left')
        self.status = tk.StringVar(value='Bereit. Die Auswahl wird vor Änderungen noch einmal angezeigt.')
        ttk.Label(outer,textvariable=self.status,wraplength=900).pack(anchor='w',pady=6)
        self.output = tk.Text(outer,height=10,wrap='word',state='disabled')
        self.output.pack(fill='both',expand=True)
        self.progress = ttk.Progressbar(outer, mode='indeterminate');self.progress.pack(fill='x',pady=(6,0))
        window.protocol('WM_DELETE_WINDOW',self.close)
        window.after(100,self.poll)
        roots=steam_roots(self.home)
        if len(roots)==1:
            self.vars['steam'].set(str(roots[0]));self.detect()

    def field(self,label,key,combo=False,browse=None,file=False):
        ttk.Label(self.form,text=label).grid(row=self.row,column=0,sticky='w',pady=2,padx=(0,10))
        widget=(ttk.Combobox(self.form,textvariable=self.vars[key],state='readonly') if combo else
                ttk.Entry(self.form,textvariable=self.vars[key]))
        widget.grid(row=self.row,column=1,sticky='ew',pady=2)
        self.widgets.append(widget)
        if browse is True or (browse is None and not combo):
            button=ttk.Button(self.form,text='…',width=3,command=lambda:self.browse(key,file))
            button.grid(row=self.row,column=2,padx=(6,0));self.widgets.append(button)
        self.row+=1
        return widget

    def check(self,label,key):
        widget=ttk.Checkbutton(self.form,text=label,variable=self.flags[key]);widget.grid(row=self.row,column=0,columnspan=3,sticky='w',pady=(6,0));self.widgets.append(widget);self.row+=1

    def browse(self,key,file):
        path=filedialog.askopenfilename(title='Originale add_registry.bat wählen',filetypes=[('Registry batch','*.bat')]) if file else filedialog.askdirectory()
        if path:
            self.vars[key].set(path)
            if key in ('game_prefix','openkh_prefix'):self.suggest_proton(key.split('_')[0])

    def path(self,key):
        s=self.vars[key].get().strip()
        if not s:raise SetupError('Fehlende Auswahl: '+key)
        return Path(s).expanduser().resolve()

    def display(self,text):
        self.output.configure(state='normal');self.output.insert('end',text+'\n');self.output.see('end');self.output.configure(state='disabled')

    def detect(self):
        try:
            steam=self.path('steam');self.libs=libraries(steam,self.home)
            games=game_dirs(self.libs)
            if len(games)==1:self.vars['game'].set(str(games[0]))
            elif len(games)>1:self.display('Mehrere Spielordner gefunden. Bitte über … auswählen:\n'+'\n'.join(map(str,games)))
            ps=prefixes(self.libs,APPID);self.game_prefix['values']=list(map(str,ps))
            self.vars['game_prefix'].set(str(ps[0]) if len(ps)==1 else '')
            self.candidates=proton_candidates(self.home,self.libs,steam)
            for widget in (self.game_proton,self.openkh_proton):widget['values']=list(map(str,self.candidates))
            self.suggest_proton('game')
            users=accounts(steam);self.account['values']=users
            if self.vars['account'].get() not in users:self.vars['account'].set(users[0] if len(users)==1 else '')
            self.read_account()
            self.status.set('Erkennung abgeschlossen. Leere Felder auswählen; Proton muss dem in Steam verwendeten Build entsprechen.')
        except (SetupError,OSError,UnicodeError) as e:messagebox.showerror('Erkennung',str(e))

    def suggest_proton(self,kind):
        current=self.vars[kind+'_prefix'].get()
        hint=proton_hint(Path(current),getattr(self,'candidates',[])) if current else None
        self.vars[kind+'_proton'].set(str(hint) if hint else '')

    def read_account(self):
        self.shortcut_map={};self.vars['shortcut'].set('');self.vars['openkh_prefix'].set('');self.vars['openkh_proton'].set('')
        account=self.vars['account'].get()
        if account:
            p=self.path('steam')/'userdata'/account/'config/shortcuts.vdf'
            if p.exists():
                try:
                    for s in shortcuts(p.read_bytes()):
                        if 'openkh' in (s.name+' '+s.exe).lower():self.shortcut_map[f'{s.name} — {s.appid}']=s
                except (SetupError,OSError,UnicodeError) as e:self.display('OpenKH-Verknüpfungen: '+str(e))
        self.shortcut['values']=list(self.shortcut_map)
        self.batch_target['values']=[APPID]+[s.appid for s in self.shortcut_map.values()]
        if len(self.shortcut_map)==1:
            self.vars['shortcut'].set(next(iter(self.shortcut_map)));self.choose_shortcut()

    def choose_shortcut(self):
        s=self.shortcut_map.get(self.vars['shortcut'].get())
        if not s:return
        ps=prefixes(self.libs,s.appid);self.openkh_prefix['values']=list(map(str,ps))
        self.vars['openkh_prefix'].set(str(ps[0]) if len(ps)==1 else '');self.suggest_proton('openkh')
        # Never silently execute a batch discovered in a downloaded directory.
        self.display(f'OpenKH erkannt: AppID {s.appid}. Für dessen Einrichtung das OpenKH-Kästchen aktivieren.')

    def plan(self):
        targets=[]
        if self.flags['game'].get():targets.append(Target('Kingdom Hearts',APPID,self.path('game_prefix'),self.path('game_proton'),True))
        if self.flags['openkh'].get():
            s=self.shortcut_map.get(self.vars['shortcut'].get())
            if not s:raise SetupError('OpenKH muss als Steam-Verknüpfung existieren. Steam danach vollständig schließen und neu einlesen.')
            targets.append(Target('OpenKH',s.appid,self.path('openkh_prefix'),self.path('openkh_proton')))
        dll=self.flags['dll'].get()
        if dll and not self.flags['game'].get():raise SetupError('Für OpenKH allein bitte „Main version.dll einsetzen“ abwählen.')
        plan=Plan(self.path('steam'),self.vars['account'].get(),self.path('game') if dll else Path('/'),
                  self.path('backup'),targets,self.flags['runtimes'].get(),dll,self.flags['launch'].get(),
                  self.path('batch') if self.vars['batch'].get().strip() else None,self.vars['batch_target'].get())
        plan.validate()
        return plan

    def summary(self,plan):
        return plan_summary(plan)

    def review(self):
        try:
            plan=self.plan();text=self.summary(plan)
            self.display(text);messagebox.showinfo('Auswahl prüfen — noch keine Installation',text)
        except (SetupError,OSError,UnicodeError,ValueError) as e:messagebox.showerror('Auswahl prüfen',str(e))

    def install(self):
        try:
            plan=self.plan();require_stopped();summary=self.summary(plan)
            if not messagebox.askokcancel('Einrichtung starten?',summary+'\n\nDie ausgewählten Änderungen jetzt ausführen?'):return
        except (SetupError,OSError,UnicodeError,ValueError) as e:
            messagebox.showerror('Einrichtung',str(e));return
        self.busy=True
        for w in self.widgets:w.configure(state='disabled')
        self.progress.start();self.status.set('Einrichtung läuft. Installer können einige Minuten benötigen. Fenster bitte geöffnet lassen.')
        threading.Thread(target=self.worker,args=(plan,),daemon=False).start()

    def worker(self,plan):
        try:
            with setup_lock(self.state):
                with (self.state/'setup.log').open('w') as log:
                    runner=Runner(lambda text:self.events.put(('log',text)),log)
                    runner.log('Panacea DroidDeck Setup — '+str(self.state/'setup.log'))
                    runner.log(self.summary(plan))
                    try:folder=execute(plan,runner)
                    except Exception as e:
                        runner.log('FAILED: '+str(e));raise
            self.events.put(('done',str(folder)))
        except Exception as e:self.events.put(('error',str(e)))

    def poll(self):
        try:
            while True:
                kind,text=self.events.get_nowait()
                if kind=='log':self.display(text)
                else:
                    self.busy=False;self.progress.stop()
                    for w in self.widgets:w.configure(state='readonly' if isinstance(w,ttk.Combobox) else 'normal')
                    if kind=='done':
                        self.status.set('Einrichtung abgeschlossen. Jetzt Steam öffnen und Spiel/OpenKH testen.')
                        messagebox.showinfo('Fertig','Backup: '+text+'\n\nSteam neu öffnen und Spiel/OpenKH testen.\nDie Runtime-Prüfung ersetzt keinen Spieltest.')
                    else:
                        self.status.set('Einrichtung abgebrochen. Vorhandene Backups bleiben erhalten; Details im Setup-Log.')
                        messagebox.showerror('Einrichtung fehlgeschlagen',text+'\n\nLog: '+str(self.state/'setup.log')+'\nEs wird kein Backup automatisch zurückgespielt.')
        except queue.Empty:pass
        self.window.after(100,self.poll)

    def open_log(self):
        import subprocess
        self.state.mkdir(parents=True,exist_ok=True)
        subprocess.Popen(['xdg-open',str(self.state)])

    def close(self):
        if self.busy:messagebox.showinfo('Einrichtung läuft','Bitte die laufende Installation abwarten. Ein Abbruch während eines Windows-Installers kann einen unvollständigen Prefix hinterlassen.')
        else:self.window.destroy()


def main():
    root=tk.Tk()
    if platform.machine().lower() not in ('aarch64','arm64'):
        messagebox.showerror('DroidDeck erforderlich','Dieses Setup ist für die ARM64-Linux-Umgebung von DroidDeck bestimmt.');root.destroy();return
    Assistant(root);root.mainloop()


if __name__=='__main__':main()
