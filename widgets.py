"""Small native Tk controls with rounded surfaces and keyboard-accessible buttons."""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk, font as tkfont
from collections.abc import Callable
from PIL import Image, ImageDraw, ImageTk


def rounded(canvas: tk.Canvas, box_width: int, box_height: int, radius: int, **kwargs: object) -> int:
    """Supersample only the control surface for smooth, true circular corners."""
    w, h = max(2, box_width), max(2, box_height)
    scale = 2
    bitmap = Image.new('RGB', (w*scale, h*scale), canvas.cget('bg'))
    ImageDraw.Draw(bitmap).rounded_rectangle((1, 1, w*scale-2, h*scale-2),
                                             radius=min(radius, w//2, h//2)*scale,
                                             fill=kwargs.get('fill'), outline=kwargs.get('outline'), width=scale)
    bitmap = bitmap.resize((w, h), Image.Resampling.LANCZOS)
    canvas.surface_image = ImageTk.PhotoImage(bitmap, master=canvas)
    return canvas.create_image(0, 0, anchor='nw', image=canvas.surface_image)


class RoundedButton(tk.Canvas):
    def __init__(self, master: tk.Misc, text: str = '', command: Callable | None = None,
                 variant: str = 'normal', width: int | None = None, height: int = 38) -> None:
        self.text, self.command, self.variant = text, command, variant
        self.disabled = self.hover = self.focused = False
        self.fixed_width = width
        self.palette: dict[str, str] = {}
        self.surface = '#14191F'
        self.font = tkfont.Font(master, family='Segoe UI', size=10)
        super().__init__(master, height=height, width=width or self.font.measure(text)+32,
                         highlightthickness=0, bd=0, takefocus=1, cursor='hand2')
        self.bind('<Configure>', lambda e: self.draw())
        self.bind('<Enter>', lambda e: self.set_hover(True))
        self.bind('<Leave>', lambda e: self.set_hover(False))
        self.bind('<ButtonPress-1>', lambda e: self.focus_set())
        self.bind('<ButtonRelease-1>', lambda e: self.invoke() if 0 <= e.x <= self.winfo_width() and 0 <= e.y <= self.winfo_height() else None)
        self.bind('<space>', lambda e: self.invoke())
        self.bind('<Return>', lambda e: self.invoke())
        self.bind('<FocusIn>', lambda e: self.set_focus(True))
        self.bind('<FocusOut>', lambda e: self.set_focus(False))

    def set_focus(self, value: bool) -> None:
        self.focused = value
        self.draw()

    def set_hover(self, value: bool) -> None:
        self.hover = value
        self.draw()

    def invoke(self) -> None:
        if not self.disabled and self.command: self.command()

    def configure(self, cnf: dict | None = None, **kwargs: object) -> object:
        options = dict(cnf or {}, **kwargs)
        if 'text' in options:
            self.text = str(options.pop('text'))
            if self.fixed_width is None: options['width'] = self.font.measure(self.text)+32
        if 'command' in options: self.command = options.pop('command')
        if 'state' in options: self.disabled = options.pop('state') == 'disabled'
        if 'style' in options:
            self.variant = 'selected' if options.pop('style') == 'Accent.TButton' else 'normal'
        if 'variant' in options: self.variant = str(options.pop('variant'))
        result = super().configure(**options) if options else None
        self.draw()
        return result

    config = configure

    def apply_palette(self, palette: dict[str, str], surface: str) -> None:
        self.palette, self.surface = palette, surface
        super().configure(bg=surface)
        self.draw()

    def draw(self) -> None:
        if not self.palette: return
        p = self.palette
        self.delete('all')
        fill = p['hover'] if self.hover and not self.disabled else p['button']
        foreground = p['fg']
        if self.variant == 'primary':
            fill = p['primary_hover'] if self.hover else p['primary']
            foreground = '#FFFFFF'
        elif self.variant == 'selected':
            fill, foreground = p['select'], p['accent']
        elif self.variant == 'danger': foreground = p['negative']
        if self.disabled: foreground = p['muted']
        rounded(self, self.winfo_width(), self.winfo_height(), 12,
                fill=fill, outline=p['accent'] if self.focused else fill, width=1)
        self.create_text(self.winfo_width()/2, self.winfo_height()/2,
                         text=self.text, fill=foreground, font=self.font)


class RoundedCard(tk.Frame):
    def __init__(self, master: tk.Misc, padding: int = 16, surface: str = 'panel') -> None:
        super().__init__(master, bd=0, highlightthickness=0)
        self.surface_key = surface
        self.palette: dict[str, str] = {}
        self.back = tk.Canvas(self, highlightthickness=0, bd=0)
        self.back.place(x=0, y=0, relwidth=1, relheight=1)
        self.content = ttk.Frame(self)
        self.content.pack(fill='both', expand=True, padx=padding, pady=padding)
        self.bind('<Configure>', lambda e: self.draw())

    def apply_palette(self, palette: dict[str, str], surrounding: str) -> None:
        self.palette = palette
        self.configure(bg=surrounding)
        self.back.configure(bg=surrounding)
        self.draw()

    def draw(self) -> None:
        if not self.palette: return
        self.back.delete('all')
        rounded(self.back, self.winfo_width(), self.winfo_height(), 18,
                fill=self.palette[self.surface_key], outline=self.palette['border'])
