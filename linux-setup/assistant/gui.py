"""Small Tk front end; workers never call Tk APIs directly."""
import os
from pathlib import Path
import platform
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from core import (APPID, Plan, Runner, SetupError, Target, accounts, execute,
                  require_stopped, setup_lock, shortcuts, plan_summary, host_env)
from setup_profile import load_profile


class Assistant:
    def __init__(self, window):
        self.window = window
        window.tk.call('::msgcat::mclocale', 'en')
        window.title('Panacea ARM – DroidDeck Setup')
        window.geometry('960x800')
        self.busy = False
        self.events = queue.Queue()
        self.home = Path.home()
        self.profile = None
        self.state = Path(os.environ.get('XDG_STATE_HOME', self.home/'.local/state'))/'panacea-arm'
        self.shortcut_map = {}
        self.vars = {key: tk.StringVar() for key in ['steam','account','game','game_prefix','game_proton',
                                                   'shortcut','openkh_prefix','openkh_proton','batch','batch_target','backup']}
        self.flags = {key: tk.BooleanVar(value=value) for key,value in
                      [('game',True),('openkh',False),('runtimes',True),('dll',True),('launch',True)]}
        self.vars['backup'].set(str(self.home/'panacea-prefix-backups'))
        self.vars['batch_target'].set(APPID)
        self.page = 0
        self.reviewed = None
        self.widgets = []
        self.status = tk.StringVar(value='')
        style = ttk.Style(window)
        style.theme_use('clam')
        style.configure('TButton', padding=(14, 8))
        style.configure('TCheckbutton', padding=5)
        style.configure('Title.TLabel', font=('', 20, 'bold'))
        window.geometry('980x680')
        window.minsize(760, 540)
        shell = ttk.Frame(window, padding=18); shell.pack(fill='both', expand=True)
        ttk.Label(shell, text='Panacea · DroidDeck Setup', style='Title.TLabel').pack(anchor='w')
        self.steps = ttk.Label(shell, text=''); self.steps.pack(anchor='w', pady=(8,12))
        ttk.Separator(shell).pack(fill='x')
        self.body = ttk.Frame(shell); self.body.pack(fill='both', expand=True, pady=12)
        self.pages = [ttk.Frame(self.body) for _ in range(4)]
        welcome, components, review, progress_page = self.pages
        ttk.Label(welcome, text='Welcome', font=('',16,'bold')).pack(anchor='w', pady=(14,18))
        ttk.Label(welcome, text='This wizard sets up Panacea and optionally OpenKH in your existing\n'
                  'DroidDeck installation, using the established paths.\n\n'
                  '• Install missing Linux helpers and Windows runtimes\n'
                  '• Install the patched version.dll\n'
                  '• Configure Steam launch options\n\n'
                  'Backups are created before making changes.\n'
                  'Fully close Steam, the game and Windows applications now.\n\n'
                  'DroidDeck, Steam, the game and optionally OpenKH must already be installed\n'
                  'and have been started once. Downloads require Internet access.',
                  justify='left', wraplength=700).pack(anchor='w')
        # Scrollable components keep navigation visible on DroidDeck's short display.
        canvas = tk.Canvas(components, highlightthickness=0)
        scrollbar = ttk.Scrollbar(components, orient='vertical', command=canvas.yview)
        scrollbar.pack(side='right',fill='y'); canvas.pack(side='left',fill='both',expand=True)
        canvas.configure(yscrollcommand=scrollbar.set)
        self.form = ttk.Frame(canvas, padding=(0,0,12,0)); self.form.columnconfigure(1, weight=1)
        item = canvas.create_window(0,0,window=self.form,anchor='nw')
        self.form.bind('<Configure>',lambda _:canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>',lambda e:canvas.itemconfigure(item,width=e.width))
        self.row = 0
        self.field('Steam directory', 'steam', combo=True)
        self.account = self.field('Steam account (userdata ID)', 'account', combo=True)
        self.account.bind('<<ComboboxSelected>>', lambda _: self.read_account())
        self.check('Set up Kingdom Hearts', 'game')
        self.field('Game directory', 'game', combo=True)
        self.game_prefix = self.field('KH compatdata (without /pfx)', 'game_prefix', combo=True)
        self.game_proton = self.field('KH ARM64-Proton', 'game_proton', combo=True)
        self.check('Set up OpenKH as well / separately', 'openkh')
        self.shortcut = self.field('OpenKH Steam shortcut', 'shortcut',combo=True)
        self.shortcut.bind('<<ComboboxSelected>>',lambda _: self.choose_shortcut())
        self.openkh_prefix = self.field('OpenKH compatdata (without /pfx)', 'openkh_prefix',combo=True)
        self.openkh_proton = self.field('OpenKH ARM64-Proton', 'openkh_proton',combo=True)
        for key,label in [('runtimes','Install missing runtimes'),('dll','Install main version.dll'),('launch','Configure Steam launch options')]:
            self.check(label,key)
        self.field('Backup directory', 'backup')
        self.field('Optional: original add_registry.bat', 'batch',file=True)
        self.batch_target = self.field('Run registry batch in AppID', 'batch_target',combo=True)
        self.batch_target['values'] = [APPID]
        ttk.Button(self.form,text='Reload profile',command=self.detect).grid(row=self.row,column=1,sticky='w',pady=8)
        ttk.Label(review,text='Ready to install',font=('',16,'bold')).pack(anchor='w',pady=(0,10))
        self.review_text = self.text_area(review)
        ttk.Label(review,text='Only “Install” applies these changes. Choose “Back” to change your selection.',
                  wraplength=700).pack(anchor='w',pady=(10,0))
        self.result = ttk.Label(progress_page,text='Installation in progress',font=('',16,'bold'))
        self.result.pack(anchor='w',pady=(0,10))
        self.output = self.text_area(progress_page)
        self.progress = ttk.Progressbar(progress_page, mode='indeterminate'); self.progress.pack(fill='x',pady=10)
        ttk.Label(progress_page,text='Setup log: '+str(self.state/'setup.log'),wraplength=700).pack(anchor='w')
        ttk.Label(shell,textvariable=self.status,wraplength=720,foreground='#9a3412').pack(anchor='w',pady=(0,8))
        ttk.Separator(shell).pack(fill='x')
        nav = ttk.Frame(shell); nav.pack(fill='x',pady=(12,0))
        self.cancel_button = ttk.Button(nav,text='Cancel',command=self.close); self.cancel_button.pack(side='left')
        self.next_button = ttk.Button(nav,text='Next >',command=self.next); self.next_button.pack(side='right')
        self.back_button = ttk.Button(nav,text='< Back',command=self.back); self.back_button.pack(side='right',padx=8)
        window.protocol('WM_DELETE_WINDOW',self.close)
        window.after(100,self.poll)
        self.detect()
        self.show_page(0)

    def text_area(self,parent):
        frame=ttk.Frame(parent);frame.pack(fill='both',expand=True)
        text=tk.Text(frame,height=8,wrap='word',state='disabled',padx=10,pady=10)
        scroll=ttk.Scrollbar(frame,command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right',fill='y');text.pack(side='left',fill='both',expand=True)
        return text

    def show_page(self,page):
        self.page=page
        for panel in self.pages:panel.pack_forget()
        self.pages[page].pack(fill='both',expand=True)
        labels=['Welcome','Components','Review','Install']
        self.steps.configure(text='   ›   '.join(('● ' if i==page else '')+name for i,name in enumerate(labels)))
        self.back_button.configure(state='normal' if page in (1,2) else 'disabled')
        self.next_button.configure(text='Install' if page==2 else 'Next >',state='disabled' if page==3 else 'normal')

    def next(self):
        if self.busy:return
        self.status.set('')
        if self.page==0:self.show_page(1)
        elif self.page==1:self.review()
        elif self.page==2:self.install()

    def back(self):
        if not self.busy and self.page in (1,2):
            self.reviewed=None;self.status.set('');self.show_page(self.page-1)

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
        path=filedialog.askopenfilename(title='Select the original add_registry.bat',filetypes=[('Registry batch','*.bat')]) if file else filedialog.askdirectory()
        if path:
            self.vars[key].set(path)

    def path(self,key):
        s=self.vars[key].get().strip()
        if not s:raise SetupError('Missing selection: '+key)
        return Path(s).expanduser().resolve()

    def display(self,text):
        self.output.configure(state='normal');self.output.insert('end',text+'\n');self.output.see('end');self.output.configure(state='disabled')

    def detect(self):
        try:
            self.profile=load_profile(self.home)
            p=self.profile
            for key,value in [('steam',p.steam),('game',p.game),('game_prefix',p.game_compat),
                              ('game_proton',p.proton),('backup',p.backup)]:
                self.vars[key].set(str(value) if value else '')
            self.game_prefix['values']=[str(p.game_compat)]
            self.game_proton['values']=[str(p.proton)] if p.proton else []
            self.openkh_proton['values']=self.game_proton['values']
            users=accounts(p.steam);self.account['values']=users
            if self.vars['account'].get() not in users:self.vars['account'].set(users[0] if len(users)==1 else '')
            self.read_account()
            self.display(p.note)
            self.status.set('Manual DroidDeck profile loaded. Set explicit path changes in config.env; libraries are not switched.')
        except (SetupError,OSError,UnicodeError) as e:self.status.set('Load profile: '+str(e))

    def read_account(self):
        self.shortcut_map={};self.vars['shortcut'].set('');self.vars['openkh_prefix'].set('');self.vars['openkh_proton'].set('')
        account=self.vars['account'].get()
        if account:
            p=self.path('steam')/'userdata'/account/'config/shortcuts.vdf'
            if p.exists():
                try:
                    for s in shortcuts(p.read_bytes()):
                        if 'openkh' in (s.name+' '+s.exe).lower():self.shortcut_map[f'{s.name} — {s.appid}']=s
                except (SetupError,OSError,UnicodeError) as e:self.display('OpenKH shortcuts: '+str(e))
        self.shortcut['values']=list(self.shortcut_map)
        self.batch_target['values']=[APPID]+[s.appid for s in self.shortcut_map.values()]
        if len(self.shortcut_map)==1:
            self.vars['shortcut'].set(next(iter(self.shortcut_map)));self.choose_shortcut()

    def choose_shortcut(self):
        s=self.shortcut_map.get(self.vars['shortcut'].get())
        if not s:return
        compat=self.profile.compat(s.appid)
        self.openkh_prefix['values']=[str(compat)]
        self.vars['openkh_prefix'].set(str(compat))
        self.vars['openkh_proton'].set(str(self.profile.proton) if self.profile.proton else '')
        # Never silently execute a batch discovered in a downloaded directory.
        self.display(f'OpenKH detected: AppID {s.appid}. Enable the OpenKH checkbox to set it up.')

    def plan(self):
        if self.profile is None:raise SetupError('Could not load the profile.')
        self.profile.require_proton()
        targets=[]
        if self.flags['game'].get():targets.append(Target('Kingdom Hearts',APPID,self.path('game_prefix'),self.path('game_proton'),True))
        if self.flags['openkh'].get():
            s=self.shortcut_map.get(self.vars['shortcut'].get())
            if not s:raise SetupError('OpenKH must exist as a Steam shortcut. Fully close Steam afterwards and reload the profile.')
            targets.append(Target('OpenKH',s.appid,self.path('openkh_prefix'),self.path('openkh_proton')))
        dll=self.flags['dll'].get()
        if dll and not self.flags['game'].get():raise SetupError('For OpenKH only, uncheck “Install main version.dll”.')
        plan=Plan(self.path('steam'),self.vars['account'].get(),self.path('game') if dll else Path('/'),
                  self.path('backup'),targets,self.flags['runtimes'].get(),dll,self.flags['launch'].get(),
                  self.path('batch') if self.vars['batch'].get().strip() else None,self.vars['batch_target'].get())
        plan.validate()
        return plan

    def summary(self,plan):
        return plan_summary(plan)

    def review(self):
        try:
            self.reviewed=self.plan();text=self.summary(self.reviewed)
            self.review_text.configure(state='normal');self.review_text.delete('1.0','end')
            self.review_text.insert('end',text);self.review_text.configure(state='disabled')
            self.show_page(2)
        except (SetupError,OSError,UnicodeError,ValueError) as e:
            self.reviewed=None;self.status.set(str(e))

    def install(self):
        if self.busy or self.page!=2 or self.reviewed is None:return
        try:
            plan=self.plan()
            if plan != self.reviewed:raise SetupError('Selection changed. Go back and review it again.')
            require_stopped()
        except (SetupError,OSError,UnicodeError,ValueError) as e:
            self.status.set(str(e));return
        self.busy=True
        self.show_page(3)
        self.cancel_button.configure(state='disabled')
        self.output.configure(state='normal');self.output.delete('1.0','end');self.output.configure(state='disabled')
        self.progress.start();self.status.set('Setup is running. Installers may take several minutes. Keep this window open.')
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
                    self.cancel_button.configure(state='normal',text='Close')
                    if kind=='done':
                        self.result.configure(text='Setup complete')
                        self.status.set('Now open Steam and test the game/OpenKH.')
                        self.display('Backup: '+text+'\nRuntime checks do not replace an in-game test.')
                    else:
                        self.result.configure(text='Setup failed')
                        self.status.set('See the setup log for details. Existing backups are kept.')
                        self.display(text+'\nBackups are not restored automatically.')

        except queue.Empty:pass
        self.window.after(100,self.poll)

    def open_log(self):
        import subprocess
        self.state.mkdir(parents=True,exist_ok=True)
        subprocess.Popen(['xdg-open',str(self.state)],env=host_env())

    def close(self):
        if self.busy:self.status.set('Please wait for installation to finish. This window will remain open until then.')
        else:self.window.destroy()


def main():
    root=tk.Tk()
    if platform.machine().lower() not in ('aarch64','arm64'):
        messagebox.showerror('DroidDeck required','This setup is intended for the DroidDeck ARM64 Linux environment.');root.destroy();return
    Assistant(root);root.mainloop()


if __name__=='__main__':main()
