import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ctypes
import tempfile
import time
from types import SimpleNamespace
from PIL import ImageGrab
from tkinterdnd2 import TkinterDnD
from app import App

def pump(root):
    for _ in range(12):
        root.update()
        time.sleep(.025)

with tempfile.TemporaryDirectory() as folder:
    root = TkinterDnD.Tk()
    app = App(root, Path(folder)/'settings.json')
    try:
        pump(root)
        user = ctypes.windll.user32
        user.GetParent.restype = ctypes.c_void_p
        user.GetParent.argtypes = [ctypes.c_void_p]
        user.GetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int]
        def check_style():
            style = user.GetWindowLongW(user.GetParent(root.winfo_id()), -20)
            assert style & 0x40000 and not style & 0x80
        check_style()
        for _ in range(3):
            app.chrome.minimize()
            pump(root)
            root.deiconify()
            pump(root)
            assert root.state() == 'normal'
            check_style()
        x, y = root.winfo_x(), root.winfo_y()
        app.chrome.title.event_generate('<ButtonPress-1>', rootx=x+60, rooty=y+15)
        app.chrome.title.event_generate('<B1-Motion>', rootx=x+85, rooty=y+35)
        pump(root)
        assert root.winfo_x() == x+25 and root.winfo_y() == y+20
        assert app.blacklist.cget('height') == 4
        for size in ('1100x760', '1280x880'):
            root.geometry(size)
            pump(root)
            for language in range(2):
                for index in range(3):
                    app.switch(index)
                    pump(root)
                    assert app.pages[index].winfo_height() > 500
                    if index == 0:
                        assert app.report.winfo_rooty()+app.report.winfo_height() < root.winfo_rooty()+root.winfo_height()
                        assert app.input.winfo_height() >= 75
                app.change_language()
        app.switch(0)
        app.blacklist.insert('1.0', 'watermark, signature, username')
        app.input.insert('1.0', '? 1girl 9680036? ahoge 943626? animal ears 1782067')
        app.vars['remove_excl'].set(True)
        app.run_clean()
        pump(root)
        out = Path(__file__).resolve().parents[1]/'docs/images'
        ImageGrab.grab(window=root.winfo_id()).save(out/'prompt-cleaner.png')
        app.switch(1)
        pump(root)
        ImageGrab.grab(window=root.winfo_id()).save(out/'image-inspector.png')
        app.switch(2)
        pump(root)
        ImageGrab.grab(window=root.winfo_id()).save(out/'metadata-removal.png')
    finally:
        app.close()
print('PASS: native styles, three minimize/restore cycles, title drag, both languages, minimum/default layout and screenshots')
