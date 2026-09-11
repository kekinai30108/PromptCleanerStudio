"""Borderless Tk chrome with taskbar presence and explicit resize/minimize handling."""
from __future__ import annotations
import ctypes
import sys
import tkinter as tk
from tkinter import ttk
from widgets import RoundedButton


def work_area() -> tuple[int, int, int, int]:
    if sys.platform == 'win32':
        from ctypes import wintypes
        rect = wintypes.RECT()
        ctypes.windll.user32.SystemParametersInfoW(48, 0, ctypes.byref(rect), 0)
        return rect.left, rect.top, rect.right, rect.bottom
    return 0, 0, 1440, 1000


class WindowChrome:
    def __init__(self, root: tk.Tk, close: object) -> None:
        self.root = root
        self.maximized = False
        self.restoring = False
        self.drag_origin: tuple[int, int, int, int] | None = None
        self.resize_id = None
        self.pending_size = None
        root.minsize(1100, 760)
        left, top, right, bottom = work_area()
        width, height = max(1100, min(1280, right-left-60)), max(760, min(880, bottom-top-60))
        root.geometry(f'{width}x{height}+{max(left, left+(right-left-width)//2)}+{max(top, top+(bottom-top-height)//2)}')
        root.overrideredirect(True)
        self.bar = ttk.Frame(root)
        self.bar.pack(fill='x')
        self.title = ttk.Label(self.bar, text=' Prompt Cleaner Studio · v1.0.4', style='Muted.TLabel', padding=(12, 10))
        self.title.pack(side='left', fill='x', expand=True)
        for text, command in [('—', self.minimize), ('□', self.toggle_maximize), ('×', close)]:
            RoundedButton(self.bar, text=text, width=42, height=30, command=command,
                          variant='danger' if text == '×' else 'normal').pack(side='left', padx=3, pady=5)
        for w in (self.bar, self.title):
            w.bind('<ButtonPress-1>', self.start_drag)
            w.bind('<B1-Motion>', self.drag)
            w.bind('<Double-Button-1>', lambda e: self.toggle_maximize())
        self.grip = ttk.Label(root, text='◢', cursor='size_nw_se', anchor='e')
        self.grip.pack(side='bottom', fill='x')
        self.grip.bind('<ButtonPress-1>', self.start_resize)
        self.grip.bind('<B1-Motion>', self.resize)
        self.grip.bind('<ButtonRelease-1>', self.finish_resize)
        root.bind('<Map>', self.on_map, add='+')
        root.after(100, self.taskbar)

    def taskbar(self) -> None:
        if sys.platform != 'win32': return
        user = ctypes.windll.user32
        user.GetParent.restype = ctypes.c_void_p
        user.GetParent.argtypes = [ctypes.c_void_p]
        user.GetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int]
        user.SetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_long]
        user.SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int,
                                     ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
        user.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
        hwnd = user.GetParent(self.root.winfo_id())
        if not hwnd: return
        style = user.GetWindowLongW(hwnd, -20)
        new_style = (style | 0x40000) & ~0x80
        if new_style == style: return
        # Explorer needs a hide/show transition when a visible tool window
        # becomes an app window. On startup this runs before deiconify.
        visible = self.root.state() == 'normal' and self.root.winfo_ismapped()
        if visible: user.ShowWindow(hwnd, 0)
        user.SetWindowLongW(hwnd, -20, new_style)
        user.SetWindowPos(hwnd, None, 0, 0, 0, 0, 0x37)
        if visible: user.ShowWindow(hwnd, 4)

    def on_map(self, event: tk.Event) -> None:
        if event.widget is self.root:
            if self.restoring:
                self.restoring = False
                self.root.overrideredirect(True)
            self.root.after_idle(self.taskbar)

    def minimize(self) -> None:
        self.restoring = True
        self.root.overrideredirect(False)
        self.root.iconify()

    def toggle_maximize(self) -> None:
        if self.maximized:
            self.root.geometry(self.normal_geometry)
        else:
            self.normal_geometry = self.root.geometry()
            l, t, r, b = work_area()
            self.root.geometry(f'{r-l}x{b-t}+{l}+{t}')
        self.maximized = not self.maximized

    def start_drag(self, event: tk.Event) -> None:
        self.drag_origin = event.x_root, event.y_root, self.root.winfo_x(), self.root.winfo_y()

    def drag(self, event: tk.Event) -> None:
        if self.drag_origin and not self.maximized:
            x, y, left, top = self.drag_origin
            self.root.geometry(f'+{left+event.x_root-x}+{top+event.y_root-y}')

    def start_resize(self, event: tk.Event) -> None:
        self.resize_origin = event.x_root, event.y_root, self.root.winfo_width(), self.root.winfo_height()

    def resize(self, event: tk.Event) -> None:
        if not self.maximized:
            x, y, w, h = self.resize_origin
            self.pending_size = max(1100, w+event.x_root-x), max(760, h+event.y_root-y)
            if self.resize_id is None:
                self.resize_id = self.root.after(16, self.apply_resize)

    def apply_resize(self) -> None:
        self.resize_id = None
        if self.pending_size and not self.maximized:
            w, h = self.pending_size
            self.pending_size = None
            if (w, h) != (self.root.winfo_width(), self.root.winfo_height()):
                self.root.geometry(f'{w}x{h}')

    def finish_resize(self, event: tk.Event) -> None:
        self.resize(event)
        if self.resize_id is not None:
            self.root.after_cancel(self.resize_id)
        self.apply_resize()
