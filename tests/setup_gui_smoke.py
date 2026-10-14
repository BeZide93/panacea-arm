"""Exercise real wizard navigation and installation against disposable fake Wine."""
from pathlib import Path
import sys
import time
import tkinter as tk
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'linux-setup/assistant'))
import gui
from setup_profile import Profile
from test_setup_assistant import Execution

fixture=Execution(methodName='runTest');fixture.setUp()
profile=Profile(fixture.steam,fixture.game,fixture.targets[0].compat,fixture.root/'backups',fixture.proton,'Test profile')
try:
    with patch('pathlib.Path.home',return_value=fixture.root), patch('gui.load_profile',return_value=profile), patch('gui.require_stopped'), patch('core.require_stopped'):
        root=tk.Tk();app=gui.Assistant(root);app.state=fixture.root/'gui-state'
        root.geometry('800x560');root.update()
        assert app.page==0 and not app.busy
        app.next();root.update();assert app.page==1
        assert app.next_button.winfo_rooty()+app.next_button.winfo_height() <= root.winfo_rooty()+root.winfo_height()
        # Missing user selections remain on the components page, with an inline error.
        app.vars['account'].set('');app.review()
        assert app.page==1 and app.status.get() and app.reviewed is None
        # Fixture account is taken from the original plan, not a real Steam account.
        app.vars['account'].set(fixture.plan.account);app.read_account()
        app.flags['openkh'].set(True)
        app.flags['runtimes'].set(False)
        app.review();assert app.page==2, app.status.get()
        assert not app.state.exists(), 'Review must not install or create a log'
        app.back();assert app.page==1 and app.reviewed is None
        app.review();assert app.page==2
        # Closing is refused while installing; completion remains in the same window.
        app.install();assert app.busy and app.page==3
        app.close();assert root.winfo_exists()
        deadline=time.monotonic()+30
        while app.busy and time.monotonic()<deadline:
            root.update();time.sleep(.02)
        assert not app.busy, 'Worker did not finish'
        assert app.result.cget('text')=='Einrichtung abgeschlossen', app.output.get('1.0','end')
        assert 'SETUP COMPLETE' in (app.state/'setup.log').read_text()
        root.destroy()
finally:fixture.tearDown()
print('PASS: native wizard navigation, review, compact layout, fake-Wine install and completion.')
