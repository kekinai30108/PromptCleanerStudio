"""Contrast-safe palettes shared by ttk, classic widgets and metadata tags."""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from widgets import RoundedButton, RoundedCard

PALETTES = {
    'dark': dict(bg='#15181F', panel='#1F242E', input='#191E27', fg='#EDF2F7', muted='#AAB5C6', accent='#B5C8FF', select='#2E3B57', border='#343C4B', button='#2B3240', hover='#394459', primary='#4C65A5', primary_hover='#5876BC', positive='#9ADBC0', negative='#F0ACB2', lora='#D8B6F2', settings='#E5CA99'),
    'light': dict(bg='#F0F2F6', panel='#FFFFFF', input='#F7F8FB', fg='#253145', muted='#5B687D', accent='#38589A', select='#E5ECFC', border='#DEE3EC', button='#EDF0F6', hover='#E0E7F3', primary='#4C65A5', primary_hover='#3F5795', positive='#216B50', negative='#A34454', lora='#774694', settings='#856021'),
}


def apply(root: tk.Misc, mode: str) -> dict[str, str]:
    p = PALETTES[mode]
    style = ttk.Style(root)
    style.theme_use('clam')
    style.configure('.', background=p['panel'], foreground=p['fg'], font=('Segoe UI', 10), bordercolor=p['border'])
    style.configure('TFrame', background=p['bg'])
    style.configure('Card.TFrame', background=p['panel'])
    style.configure('TLabel', background=p['bg'], foreground=p['fg'])
    style.configure('Muted.TLabel', foreground=p['muted'])
    style.configure('Title.TLabel', font=('Segoe UI', 20, 'bold'))
    style.configure('TButton', padding=(12, 8), background=p['panel'], foreground=p['fg'])
    style.map('TButton', background=[('active', p['select'])], foreground=[('disabled', p['muted'])])
    style.configure('Accent.TButton', foreground=p['accent'])
    style.configure('TCheckbutton', background=p['bg'], foreground=p['fg'])
    style.map('TCheckbutton', background=[('active', p['bg'])])
    style.configure('TCombobox', fieldbackground=p['input'], foreground=p['fg'], selectbackground=p['select'], selectforeground=p['fg'])
    style.map('TCombobox', fieldbackground=[('readonly', p['input'])], foreground=[('readonly', p['fg'])])
    style.configure('Horizontal.TProgressbar', background=p['accent'], troughcolor=p['input'])
    root.option_add('*TCombobox*Listbox.background', p['input'])
    root.option_add('*TCombobox*Listbox.foreground', p['fg'])
    style.configure('TScrollbar', background=p['button'], troughcolor=p['input'], borderwidth=0, arrowsize=12)
    style.configure('TScale', background=p['panel'], troughcolor=p['input'])
    def visit(widget: tk.Misc, surface: str = p['bg']) -> None:
        if isinstance(widget, RoundedButton):
            widget.apply_palette(p, surface)
            return
        if isinstance(widget, RoundedCard):
            widget.apply_palette(p, surface)
            visit(widget.content, p[widget.surface_key])
            return
        if isinstance(widget, (tk.Text, tk.Listbox)):
            widget.configure(bg=p['input'], fg=p['fg'], selectbackground=p['select'], selectforeground=p['fg'], highlightbackground=p['border'], highlightcolor=p['accent'])
            if isinstance(widget, tk.Text):
                widget.configure(insertbackground=p['fg'])
                widget.tag_configure('heading', foreground=p['accent'], font=('Segoe UI', 11, 'bold'))
                widget.tag_configure('body', foreground=p['fg'])
                for tag in ('positive', 'negative', 'lora', 'settings'):
                    widget.tag_configure(tag, foreground=p[tag], font=('Segoe UI', 11, 'bold'))
        elif isinstance(widget, tk.Canvas): widget.configure(bg=p['input'])
        elif isinstance(widget, (tk.Tk, tk.Toplevel)): widget.configure(bg=p['bg'])
        elif isinstance(widget, ttk.Frame):
            name = f'S{surface[1:]}.TFrame'
            style.configure(name, background=surface)
            widget.configure(style=name)
        elif isinstance(widget, ttk.Label): widget.configure(background=surface)
        elif isinstance(widget, ttk.Checkbutton):
            name = f'S{surface[1:]}.TCheckbutton'
            style.configure(name, background=surface, foreground=p['fg'])
            style.map(name, background=[('active', surface)], indicatorcolor=[('selected', p['primary']), ('!selected', p['input'])])
            widget.configure(style=name)
        for child in widget.winfo_children(): visit(child, surface)
    visit(root)
    return p
