"""Run under xvfb-run in CI; this opens the real Tk form without installing."""
from pathlib import Path
import sys
import tempfile
import tkinter as tk
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'linux-setup/assistant'))
import gui

with tempfile.TemporaryDirectory() as home, patch('pathlib.Path.home',return_value=Path(home)):
    root=tk.Tk()
    app=gui.Assistant(root)
    root.update()
    assert app.output.winfo_ismapped()
    assert app.output.winfo_height() >= 80, 'Progress output is clipped'
    assert app.progress.winfo_y()+app.progress.winfo_height() <= app.progress.master.winfo_height()
    assert app.vars['steam'].get()==''
    with patch('gui.messagebox.showerror') as error:
        app.review()
        assert error.called, 'Empty selections should show a validation message'
    root.destroy()
print('PASS: Tk form opens, controls fit, empty selections are rejected without changes.')
