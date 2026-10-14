"""Frozen desktop entry. The launcher supplies the adjacent, editable setup kit."""
import os
from pathlib import Path
import sys


def main():
    import gui
    if '--smoke-test' in sys.argv:
        # CI only: opens every page, performs validation, never installs.
        import tkinter as tk
        import core
        assert getattr(sys, 'frozen', False)
        assert (core.KIT/'payload/version.dll').is_file()
        assert core.digest((core.KIT/'payload/version.dll').read_bytes()) == core.DLL_SHA256
        root=tk.Tk();app=gui.Assistant(root)
        for page in range(4):
            app.show_page(page);root.update()
            assert app.cancel_button.winfo_ismapped()
        app.show_page(1);app.review()
        assert app.reviewed is None and app.status.get()
        env=core.host_env()
        assert str(sys._MEIPASS) not in env.get('LD_LIBRARY_PATH','')
        root.destroy()
        print('PASS: frozen ARM64 wizard, bundled Tk, payload and clean child environment')
    else:
        gui.main()


if __name__=='__main__':main()
