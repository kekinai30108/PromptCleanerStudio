"""Native desktop application. Workers communicate with Tk through a queue."""
from __future__ import annotations
import ctypes
import json
import os
import queue
import sys
import threading
import tempfile
import tkinter as tk
from dataclasses import asdict
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageOps, ImageTk
from tkinterdnd2 import DND_FILES, DND_TEXT, TkinterDnD
from core import Rules, clean
import settings
import theme
from metadata_parser import read_metadata
from metadata_remover import remove_metadata
from window_chrome import WindowChrome
from widgets import RoundedButton, RoundedCard
from image_source import load_image, resolve_drop

MAX_RENDER_CHARS = 24_000

TEXT = {
    'clean_page': ('提示詞淨化', 'Prompt cleaner'), 'image_page': ('圖片資訊', 'Image inspector'),
    'batch_page': ('中繼資料移除', 'Metadata removal'), 'input': ('原始提示詞', 'Original prompt'),
    'output': ('淨化結果', 'Cleaned prompt'), 'paste': ('貼上', 'Paste'), 'clear': ('清空', 'Clear'),
    'copy': ('複製結果', 'Copy result'), 'export': ('匯出 TXT', 'Export TXT'), 'clean': ('執行淨化  Ctrl+Enter', 'Clean  Ctrl+Enter'),
    'blacklist': ('黑名單（逗號或換行分隔）', 'Blacklist (commas or new lines)'),
    'history': ('本次歷史紀錄', 'Session history'), 'restore': ('還原選取紀錄', 'Restore selected'),
    'remove_lora': ('移除 LoRA / LyCORIS', 'Remove LoRA / LyCORIS'), 'remove_weights': ('移除強調權重', 'Remove emphasis weights'),
    'deduplicate': ('移除重複標籤', 'Remove duplicate tags'), 'remove_chinese': ('移除中文字元', 'Remove Chinese characters'),
    'remove_excl': ('移除驚嘆號與問號', 'Remove ! and ?'), 'tag_counts': ('移除尾端計數', 'Remove trailing counts'),
    'open': ('選擇圖片', 'Select image'), 'recent': ('最近開啟', 'Recent images'), 'copy_meta': ('複製中繼資料', 'Copy metadata'),
    'add': ('加入圖片', 'Add images'), 'remove': ('移除選取', 'Remove selected'), 'start': ('建立乾淨 PNG 副本', 'Create clean PNG copies'),
    'batch_hint': ('輸出至來源同層 Cleaned_Output，自動編號、不覆寫原圖。可拖放多張圖片。', 'Saves to Cleaned_Output beside each source. Unique names; originals preserved. Drop images here.'),
    'image_hint': ('從本機或瀏覽器拖入圖片，預覽並檢視生成資訊。', 'Drop an image from your computer or browser to inspect its generation data.'),
    'prompt_hint': ('整理標籤，同時保留 Stable Diffusion 生成語法。', 'Organize tags while preserving Stable Diffusion syntax.'),
    'ready': ('', ''), 'loading': ('讀取中…', 'Reading…'),
    'rules': ('過濾規則', 'Filter settings'), 'preview': ('圖片預覽', 'Image preview'),
    'results': ('解析結果', 'Inspection results'), 'copy_raw': ('複製原始資料', 'Copy raw data'),
    'meta_image': ('圖片資訊 (Image)', 'Image'), 'meta_positive': ('正向提示詞 (Positive)', 'Positive'),
    'meta_negative': ('負向提示詞 (Negative)', 'Negative'), 'meta_lora': ('使用的 LoRA (LoRA Models)', 'LoRA Models'),
    'meta_raw_nodes': ('原始節點文本 (Raw Node Text)', 'Raw Node Text'),
    'meta_parameters': ('生成參數 (Parameters)', 'Parameters'), 'meta_other': ('其他資訊 (Other Info)', 'Other Info'),
    'open_output': ('開啟輸出資料夾', 'Open output folder'), 'queue': ('待處理圖片', 'Images in queue'),
    'export_settings': ('匯出設定', 'Export settings'), 'import_settings': ('匯入設定', 'Import settings'),
    'drop_empty': ('將圖片拖放到這裡\n或點擊選擇圖片', 'Drop an image here\nor click to choose a file'),
    'drop_support': ('PNG / JPEG / WebP · 支援中繼資料解析與瀏覽器拖放', 'PNG / JPEG / WebP · Metadata inspection and browser drops'),
    'paste_blocked': ('內容過大或包含工作流 JSON，請貼上提示詞文字。', 'Large content or workflow JSON detected. Paste prompt text instead.'),
}


class App:
    def __init__(self, root: tk.Tk, settings_file: Path | None = None) -> None:
        self.root, self.settings_file = root, settings_file
        # Keep Tk's undecorated default root hidden until the complete UI exists.
        root.withdraw()
        self.config = settings.load(settings_file)
        self.labels: list[tuple[tk.Misc, str]] = []
        self.events: queue.Queue = queue.Queue()
        self.history: list[dict] = []
        self.recent: list[str] = []
        self.files: list[str] = []
        self.busy = False
        self.image_request = 0
        self.preview: Image.Image | None = None
        self.metadata: dict[str, str] = {}
        self.raw_metadata = ''
        self.raw_metadata_truncated = False
        self.last_output_dir: Path | None = None
        self.current_page = 0
        self.vars = {k: tk.BooleanVar(value=self.config[k]) for k in asdict(Rules()) if k != 'blacklist'}
        root.title('Prompt Cleaner Studio v1.0.2')
        icon = Path(getattr(sys, '_MEIPASS', Path(__file__).parent)) / 'assets/PromptCleanerStudio.ico'
        if icon.exists(): root.iconbitmap(str(icon))
        self.chrome = WindowChrome(root, self.close)
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.bind('<Control-Return>', lambda e: self.run_clean())
        root.bind('<Alt-F4>', lambda e: self.close())
        self.shell = ttk.Frame(root)
        self.shell.pack(fill='both', expand=True, padx=12, pady=(0, 4))
        self.sidebar = ttk.Frame(self.shell, width=190)
        self.sidebar.pack(side='left', fill='y', padx=(0, 18))
        self.sidebar.pack_propagate(False)
        self.nav = []
        for index, key in enumerate(('clean_page', 'image_page', 'batch_page')):
            self.nav.append(self.button(self.sidebar, key, lambda i=index: self.switch(i)))
            self.nav[-1].pack(fill='x', pady=(24, 5) if index == 0 else 5)
        self.lang_button = RoundedButton(self.sidebar, command=self.change_language)
        self.lang_button.pack(side='bottom', fill='x', pady=(6, 10))
        self.theme_button = RoundedButton(self.sidebar, command=self.change_theme)
        self.theme_button.pack(side='bottom', fill='x', pady=6)
        self.button(self.sidebar, 'export_settings', self.export_settings).pack(side='bottom', fill='x', pady=(6, 22))
        self.button(self.sidebar, 'import_settings', self.import_settings).pack(side='bottom', fill='x', pady=6)
        self.main = ttk.Frame(self.shell)
        self.main.pack(side='left', fill='both', expand=True)
        self.status = ttk.Label(root, style='Muted.TLabel', padding=(20, 4))
        self.status.pack(side='bottom', fill='x')
        self.pages = [ttk.Frame(self.main) for _ in range(3)]
        self.build_clean()
        self.build_image()
        self.build_batch()
        self.translate()
        self.pages[0].pack(fill='both', expand=True)
        self.nav[0].configure(style='Accent.TButton')
        theme.apply(root, self.config['theme'])
        self.status.configure(text=self.t('ready'))
        self.poll_id = root.after(100, self.poll)
        root.after_idle(self.show_main_window)

    def show_main_window(self) -> None:
        """Reveal one fully laid-out custom window without the default Tk flash."""
        if not self.root.winfo_exists():
            return
        self.root.update_idletasks()
        self.root.deiconify()
        self.root.lift()
        self.root.after(20, self.chrome.taskbar)

    def t(self, key: str) -> str:
        return TEXT[key][0 if self.config['lang'] == 'zh' else 1]

    def label(self, parent: tk.Misc, key: str, **kwargs: object) -> ttk.Label:
        widget = ttk.Label(parent, text=self.t(key), **kwargs)
        self.labels.append((widget, key))
        return widget

    def button(self, parent: tk.Misc, key: str, command: object) -> RoundedButton:
        widget = RoundedButton(parent, text=self.t(key), command=command,
                               variant='primary' if key in ('clean', 'start', 'open') else 'normal')
        self.labels.append((widget, key))
        return widget

    def text_box(self, parent: tk.Misc, height: int = 8, readonly: bool = False) -> tk.Text:
        card = RoundedCard(parent, padding=8, surface='input')
        card.pack(fill='both', expand=True, pady=6)
        frame = card.content
        text = tk.Text(frame, height=height, width=15, wrap='word', undo=not readonly, font=('Segoe UI', 10), relief='flat', padx=4, pady=4, highlightthickness=0)
        bar = ttk.Scrollbar(frame, command=text.yview)
        bar.pack(side='right', fill='y')
        text.pack(side='left', fill='both', expand=True)
        text.configure(yscrollcommand=bar.set)
        if readonly: text.configure(state='disabled')
        text.bind('<Button-3>', lambda e: self.context_menu(e, text, readonly))
        return text

    def heading(self, page: ttk.Frame, key: str, hint: str) -> None:
        title = self.label(page, key, style='Title.TLabel')
        title.pack(anchor='w', pady=(20, 4))
        self.label(page, hint, style='Muted.TLabel', wraplength=790).pack(anchor='w', pady=(0, 12))

    def build_clean(self) -> None:
        page = self.pages[0]
        self.heading(page, 'clean_page', 'prompt_hint')
        self.rules_card = RoundedCard(page, padding=14)
        self.rules_card.pack(fill='x', pady=(0, 12))
        row = ttk.Frame(self.rules_card.content)
        row.pack(fill='x')
        self.label(row, 'rules', font=('Segoe UI', 11, 'bold')).pack(side='left')
        self.preset = ttk.Combobox(row, state='readonly', width=23)
        self.preset.pack(side='right')
        self.preset.bind('<<ComboboxSelected>>', self.set_preset)
        self.label(self.rules_card.content, 'blacklist', style='Muted.TLabel').pack(anchor='w', pady=(8, 0))
        self.blacklist = self.text_box(self.rules_card.content, 2)
        self.blacklist.insert('1.0', self.config['blacklist'])
        options = ttk.Frame(self.rules_card.content)
        options.pack(fill='x', pady=(3, 0))
        for i, (key, var) in enumerate(self.vars.items()):
            cb = ttk.Checkbutton(options, text=self.t(key), variable=var)
            cb.grid(row=i//3, column=i%3, sticky='w', padx=(0, 20), pady=3)
            options.columnconfigure(i%3, weight=1)
            self.labels.append((cb, key))
        columns = ttk.Frame(page)
        columns.pack(fill='both', expand=True)
        columns.columnconfigure((0, 1), weight=1, uniform='editors')
        columns.rowconfigure(0, weight=1)
        self.input_card, self.output_card = RoundedCard(columns), RoundedCard(columns)
        self.input_card.grid(row=0, column=0, sticky='nsew', padx=(0, 7))
        self.output_card.grid(row=0, column=1, sticky='nsew', padx=(7, 0))
        self.label(self.input_card.content, 'input', font=('Segoe UI', 11, 'bold')).pack(anchor='w')
        self.input = self.text_box(self.input_card.content, 5)
        self.input.bind('<<Paste>>', self.guarded_paste)
        tools = ttk.Frame(self.input_card.content)
        tools.pack(fill='x')
        self.button(tools, 'paste', self.paste).pack(side='left')
        self.button(tools, 'clear', self.clear_all).pack(side='left', padx=5)
        self.label(self.output_card.content, 'output', font=('Segoe UI', 11, 'bold')).pack(anchor='w')
        self.output = self.text_box(self.output_card.content, 5, readonly=True)
        tools = ttk.Frame(self.output_card.content)
        tools.pack(fill='x')
        self.button(tools, 'export', self.export).pack(side='left', padx=5)
        bottom = ttk.Frame(page)
        bottom.pack(fill='x', pady=(12, 0))
        self.button(bottom, 'clean', self.run_clean).pack(side='left')
        self.button(bottom, 'copy', lambda: self.copy(self.output.get('1.0', 'end-1c'))).pack(side='left', padx=6)
        self.button(bottom, 'restore', self.restore_history).pack(side='right')
        self.history_box = ttk.Combobox(bottom, state='readonly', width=24)
        self.history_box.pack(side='right', padx=8)
        self.label(bottom, 'history', style='Muted.TLabel').pack(side='right', padx=6)
        self.report = self.text_box(page, 2, readonly=True)

    def build_image(self) -> None:
        page = self.pages[1]
        self.heading(page, 'image_page', 'image_hint')
        workspace = ttk.Frame(page)
        workspace.pack(fill='both', expand=True, pady=(0, 8))
        workspace.columnconfigure(0, weight=4, minsize=305)
        workspace.columnconfigure(1, weight=6, minsize=430)
        workspace.rowconfigure(0, weight=1)
        self.preview_card = RoundedCard(workspace)
        self.preview_card.grid(row=0, column=0, sticky='nsew', padx=(0, 7))
        self.metadata_card = RoundedCard(workspace)
        self.metadata_card.grid(row=0, column=1, sticky='nsew', padx=(7, 0))
        left, right = self.preview_card.content, self.metadata_card.content
        self.label(left, 'preview', font=('Segoe UI', 11, 'bold')).pack(anchor='w', pady=(0, 8))
        self.preview_frame = ttk.Frame(left)
        self.preview_frame.pack(fill='both', expand=True)
        self.preview_frame.rowconfigure(0, weight=1)
        self.preview_frame.columnconfigure(0, weight=1)
        self.canvas = tk.Canvas(self.preview_frame, width=260, height=180, highlightthickness=0, cursor='hand2')
        self.canvas.grid(row=0, column=0, sticky='nsew')
        self.canvas.bind('<Button-1>', lambda e: self.open_image())
        self.canvas.bind('<Configure>', lambda e: self.draw_preview())
        self.label(left, 'drop_support', style='Muted.TLabel', wraplength=280).pack(anchor='w', pady=(8, 6))
        zoom_row = ttk.Frame(left)
        zoom_row.pack(fill='x')
        self.zoom = tk.DoubleVar(value=1.0)
        RoundedButton(zoom_row, text='−', width=36, command=lambda: self.change_zoom(-0.1)).pack(side='left')
        self.zoom_label = ttk.Label(zoom_row, text='100%', anchor='center', width=7)
        self.zoom_label.pack(side='left')
        RoundedButton(zoom_row, text='+', width=36, command=lambda: self.change_zoom(0.1)).pack(side='left')
        self.label(left, 'recent', style='Muted.TLabel').pack(anchor='w', pady=(12, 4))
        self.recent_box = tk.Listbox(left, height=4, font=('Segoe UI', 9), relief='flat', bd=0,
                                     exportselection=False, highlightthickness=0)
        self.recent_box.pack(fill='x', pady=(0, 10))
        self.recent_box.bind('<<ListboxSelect>>', self.open_recent)
        self.button(left, 'open', self.open_image).pack(fill='x')
        self.label(right, 'results', font=('Segoe UI', 11, 'bold')).pack(anchor='w')
        toolbar = ttk.Frame(right)
        toolbar.pack(fill='x', pady=(10, 0))
        self.button(toolbar, 'copy_meta', lambda: self.copy(self.meta_text.get('1.0', 'end-1c'))).pack(side='left')
        self.button(toolbar, 'copy_raw', lambda: self.copy(self.raw_metadata)).pack(side='left', padx=6)
        self.image_path = ttk.Label(right, text='', style='Muted.TLabel', wraplength=420)
        self.image_path.pack(fill='x', pady=(5, 5))
        self.meta_text = self.text_box(right, readonly=True)
        for widget in (self.canvas, self.preview_card, self.meta_text, page):
            widget.drop_target_register(DND_FILES, DND_TEXT, 'HTML Format', 'text/uri-list')
            widget.dnd_bind('<<Drop>>', self.handle_image_drop)

    def build_batch(self) -> None:
        page = self.pages[2]
        self.heading(page, 'batch_page', 'batch_hint')
        action_card = RoundedCard(page)
        action_card.pack(fill='x', pady=(0, 12))
        row = action_card.content
        self.button(row, 'add', self.add_files).pack(side='left')
        self.button(row, 'remove', self.remove_selected).pack(side='left', padx=6)
        self.start_button = self.button(row, 'start', self.start_batch)
        self.start_button.pack(side='right')
        self.button(row, 'open_output', self.open_output).pack(side='right', padx=6)
        list_card = RoundedCard(page)
        list_card.pack(fill='both', expand=True)
        self.label(list_card.content, 'queue', font=('Segoe UI', 11, 'bold')).pack(anchor='w', pady=(0, 10))
        list_frame = ttk.Frame(list_card.content)
        list_frame.pack(fill='both', expand=True)
        self.file_list = tk.Listbox(list_frame, selectmode='extended', relief='flat', bd=0,
                                    height=8, font=('Segoe UI', 10), highlightthickness=0)
        scrollbar = ttk.Scrollbar(list_frame, command=self.file_list.yview)
        scrollbar.pack(side='right', fill='y')
        self.file_list.pack(side='left', fill='both', expand=True)
        self.file_list.configure(yscrollcommand=scrollbar.set)
        self.file_list.drop_target_register(DND_FILES)
        self.file_list.dnd_bind('<<Drop>>', lambda e: self.add_files(list(self.root.tk.splitlist(e.data))))
        self.progress = ttk.Progressbar(page)
        self.progress.pack(fill='x', pady=(14, 0))
        self.batch_status = ttk.Label(page)
        self.batch_status.pack(anchor='w', pady=8)
        self.batch_log = self.text_box(page, height=5, readonly=True)

    def collect(self) -> dict:
        self.config.update({k: v.get() for k, v in self.vars.items()})
        self.config['blacklist'] = self.blacklist.get('1.0', 'end-1c')
        return self.config.copy()

    def persist(self) -> None:
        try:
            current = self.collect()
            if not (self.settings_file or settings.settings_path()).exists() or current != settings.load(self.settings_file):
                settings.save(current, self.settings_file)
        except OSError as exc: self.error(exc)

    def translate(self) -> None:
        for widget, key in self.labels: widget.configure(text=self.t(key))
        index = self.preset.current()
        self.preset.configure(values=['保留生成語法', '純文字標籤', '僅去除重複'] if self.config['lang'] == 'zh' else ['Preserve syntax', 'Plain text tags', 'Deduplicate only'])
        self.preset.current(max(0, index))
        self.lang_button.configure(text='語言  /  English' if self.config['lang'] == 'zh' else 'Language  /  繁體中文')
        target_theme = ('淺色外觀' if self.config['theme'] == 'dark' else '深色外觀') if self.config['lang'] == 'zh' else ('Light appearance' if self.config['theme'] == 'dark' else 'Dark appearance')
        self.theme_button.configure(text=target_theme)
        self.draw_preview()
        if self.metadata:
            self.render_metadata()

    def change_language(self, event: object = None) -> None:
        self.config['lang'] = 'en' if self.config['lang'] == 'zh' else 'zh'
        self.translate(); self.persist()

    def change_theme(self, event: object = None) -> None:
        self.config['theme'] = 'light' if self.config['theme'] == 'dark' else 'dark'
        theme.apply(self.root, self.config['theme'])
        self.translate(); self.persist()

    def switch(self, index: int) -> None:
        self.persist()
        self.current_page = index
        for i, page in enumerate(self.pages):
            page.pack_forget()
            self.nav[i].configure(style='Accent.TButton' if i == index else 'TButton')
        self.pages[index].pack(fill='both', expand=True)

    def set_preset(self, event: object = None) -> None:
        index = self.preset.current()
        for k, v in self.vars.items(): v.set(k == 'deduplicate' or index == 1 and k in ('remove_lora', 'remove_weights', 'remove_excl', 'tag_counts'))
        if index == 2: self.blacklist.delete('1.0', 'end')

    @staticmethod
    def put(widget: tk.Text, text: str) -> None:
        widget.configure(state='normal'); widget.delete('1.0', 'end'); widget.insert('1.0', text); widget.configure(state='disabled')

    def run_clean(self) -> None:
        data = self.collect()
        source = self.input.get('1.0', 'end-1c')
        report = clean(source, Rules(**{k: data[k] for k in asdict(Rules())}))
        self.put(self.output, report.output)
        summary = f'保留 / Kept {report.kept}    移除 / Removed {len(report.removed)}    字元 / Characters {len(report.output)}'
        details = '\n'.join(f'{tag} → {reason}' for tag, reason in report.removed[:8])
        self.put(self.report, '\n'.join(filter(None, [summary, details, *report.warnings])))
        self.history.insert(0, dict(input=source, output=report.output, rules=data.copy(), report=self.report.get('1.0', 'end-1c')))
        self.history = self.history[:30]
        self.history_box.configure(values=[f'{i+1:02d}  {h["input"][:65]}' for i, h in enumerate(self.history)])
        self.history_box.current(0)
        self.persist()

    def restore_history(self) -> None:
        index = self.history_box.current()
        if index < 0: return
        entry = self.history[index]
        self.input.delete('1.0', 'end'); self.input.insert('1.0', entry['input'])
        self.put(self.output, entry['output']); self.put(self.report, entry['report'])
        for key, var in self.vars.items(): var.set(entry['rules'][key])
        self.blacklist.delete('1.0', 'end'); self.blacklist.insert('1.0', entry['rules']['blacklist'])

    def copy(self, value: str) -> None:
        self.root.clipboard_clear(); self.root.clipboard_append(value)
        self.status.configure(text='已複製 / Copied')

    def paste(self) -> None:
        try:
            if self.guarded_paste() != 'break':
                self.input.insert('insert', self.root.clipboard_get())
        except tk.TclError: self.status.configure(text='剪貼簿無文字 / Clipboard has no text')

    def guarded_paste(self, event: object = None) -> str | None:
        try:
            text = self.root.clipboard_get()
            if len(text) > 5000 or ('"nodes"' in text and '"links"' in text) or '"version":' in text:
                self.status.configure(text=self.t('paste_blocked'))
                return 'break'
        except tk.TclError:
            return 'break'
        return None

    def clear_all(self) -> None:
        self.input.delete('1.0', 'end')
        self.put(self.output, '')
        self.put(self.report, '')
        self.status.configure(text='')

    def context_menu(self, event: tk.Event, widget: tk.Text, readonly: bool) -> None:
        menu = tk.Menu(self.root, tearoff=False)
        labels = ('剪下', '複製', '貼上', '全選') if self.config['lang'] == 'zh' else ('Cut', 'Copy', 'Paste', 'Select all')
        if not readonly: menu.add_command(label=labels[0], command=lambda: widget.event_generate('<<Cut>>'))
        menu.add_command(label=labels[1], command=lambda: widget.event_generate('<<Copy>>'))
        if not readonly: menu.add_command(label=labels[2], command=lambda: widget.event_generate('<<Paste>>'))
        menu.add_command(label=labels[3], command=lambda: widget.tag_add('sel', '1.0', 'end-1c'))
        try: menu.tk_popup(event.x_root, event.y_root)
        finally: menu.grab_release()

    def export_settings(self) -> None:
        path = filedialog.asksaveasfilename(parent=self.root, defaultextension='.json', filetypes=[('JSON', '*.json')])
        if path:
            try:
                with open(path, 'x', encoding='utf-8') as stream:
                    json.dump(self.collect(), stream, ensure_ascii=False, indent=2)
            except OSError as exc: self.error(exc)

    def import_settings(self) -> None:
        path = filedialog.askopenfilename(parent=self.root, filetypes=[('JSON', '*.json')])
        if not path: return
        try:
            data = json.loads(Path(path).read_text(encoding='utf-8-sig'))
            if not isinstance(data, dict): raise ValueError('Settings must contain an object / 設定必須是 JSON 物件')
            # Accept the appearance names used by the supplied v2.0 reference.
            if data.get('theme') == 'japanese': data['theme'] = 'light'
            elif data.get('theme') == 'discord': data['theme'] = 'dark'
            self.config = settings.validate({**self.collect(), **data})
            for key, var in self.vars.items(): var.set(self.config[key])
            self.blacklist.delete('1.0', 'end')
            self.blacklist.insert('1.0', self.config['blacklist'])
            theme.apply(self.root, self.config['theme'])
            self.translate(); self.persist()
        except (OSError, ValueError) as exc: self.error(exc)

    def export(self) -> None:
        path = filedialog.asksaveasfilename(parent=self.root, defaultextension='.txt', filetypes=[('Text', '*.txt')])
        if path:
            try:
                with open(path, 'x', encoding='utf-8') as stream: stream.write(self.output.get('1.0', 'end-1c'))
            except OSError as exc: self.error(exc)

    def error(self, exc: Exception) -> None:
        messagebox.showerror('Prompt Cleaner Studio', str(exc), parent=self.root)

    def drop_image(self, data: str) -> None:
        try:
            self.open_image(resolve_drop(data, self.root.tk.splitlist))
        except (ValueError, OSError) as exc:
            self.put(self.meta_text, str(exc))

    def handle_image_drop(self, event: tk.Event) -> str:
        self.drop_image(event.data)
        return 'copy'

    def open_recent(self, event: object = None) -> None:
        selected = self.recent_box.curselection()
        if selected: self.open_image(self.recent[selected[0]])

    @staticmethod
    def render_value(value: str) -> str:
        """A final UI guard even if a future parser returns an unexpectedly large value."""
        if len(value) <= MAX_RENDER_CHARS:
            return value
        return value[:MAX_RENDER_CHARS] + '\n…（此區顯示已截斷）'

    def open_image(self, path: str | None = None) -> None:
        path = path or filedialog.askopenfilename(parent=self.root, filetypes=[('Images', '*.png *.jpg *.jpeg *.webp')])
        if not path: return
        self.image_request += 1
        request = self.image_request
        self.metadata = {}; self.raw_metadata = ''; self.raw_metadata_truncated = False
        self.preview = None; self.canvas.delete('all')
        self.image_path.configure(text=path if len(path) < 150 else path[:147] + '…')
        self.draw_preview()
        self.put(self.meta_text, self.t('loading'))
        events = self.events
        def worker() -> None:
            try:
                result = load_image(path)
                events.put(('image', request, result))
            except Exception as exc: events.put(('image_error', request, str(exc)))
        threading.Thread(target=worker, daemon=True).start()

    def draw_preview(self) -> None:
        if self.preview is None:
            self.canvas.delete('all')
            self.canvas.create_text(max(130, self.canvas.winfo_width()/2), max(70, self.canvas.winfo_height()/2),
                                    text=self.t('drop_empty'), fill=theme.PALETTES[self.config['theme']]['muted'],
                                    font=('Segoe UI', 11), justify='center', width=240)
            return
        canvas_width = max(self.canvas.winfo_width(), 100)
        canvas_height = max(self.canvas.winfo_height(), 100)
        scale = min(canvas_width/self.preview.width, canvas_height/self.preview.height) * self.zoom.get()
        size = max(1, int(self.preview.width*scale)), max(1, int(self.preview.height*scale))
        self.photo = ImageTk.PhotoImage(self.preview.resize(size, Image.Resampling.LANCZOS))
        self.canvas.delete('all')
        self.canvas.create_image(canvas_width/2, canvas_height/2, image=self.photo, anchor='center')
        self.zoom_label.configure(text=f'{self.zoom.get():.0%}')

    def render_metadata(self) -> None:
        """Render only the v2-style sections; workflow JSON never enters the Text widget."""
        headings = {
            'Image / 圖片': ('meta_image', 'heading'),
            'Positive': ('meta_positive', 'positive'),
            'Negative': ('meta_negative', 'negative'),
            'LoRA': ('meta_lora', 'lora'),
            'Raw node text / 原始節點文字': ('meta_raw_nodes', 'settings'),
        }
        excluded = set(headings) | {'Classification / 分類'}
        parameters = [(key, value) for key, value in self.metadata.items()
                      if key not in excluded and not key.startswith('Other / 其他 ·') and key != 'Status / 狀態']
        others = [(key.split('·', 1)[-1].strip(), value) for key, value in self.metadata.items()
                  if key.startswith('Other / 其他 ·')]
        self.meta_text.configure(state='normal')
        self.meta_text.delete('1.0', 'end')
        for key, (label, tag) in headings.items():
            value = self.metadata.get(key)
            if value:
                self.meta_text.insert('end', self.t(label) + '\n', tag)
                self.meta_text.insert('end', self.render_value(value) + '\n\n', 'body')
        if parameters:
            self.meta_text.insert('end', self.t('meta_parameters') + '\n', 'settings')
            for key, value in parameters:
                self.meta_text.insert('end', f'  [{key}]: ', 'heading')
                self.meta_text.insert('end', self.render_value(value) + '\n', 'body')
            self.meta_text.insert('end', '\n')
        if others:
            self.meta_text.insert('end', self.t('meta_other') + '\n', 'heading')
            for key, value in others:
                self.meta_text.insert('end', f'  [{key}]: ', 'heading')
                self.meta_text.insert('end', self.render_value(value) + '\n', 'body')
            self.meta_text.insert('end', '\n')
        status = self.metadata.get('Status / 狀態')
        if status:
            self.meta_text.insert('end', status + '\n', 'body')
        if self.raw_metadata_truncated:
            notice = ('原始資料超過 1 MiB，複製原始資料時只提供前 1 MiB。' if self.config['lang'] == 'zh'
                      else 'Raw metadata exceeds 1 MiB; Copy raw data provides the first 1 MiB only.')
            self.meta_text.insert('end', notice + '\n', 'settings')
        self.meta_text.configure(state='disabled')

    def change_zoom(self, delta: float) -> None:
        self.zoom.set(min(3, max(0.1, self.zoom.get()+delta)))
        self.draw_preview()

    def open_output(self) -> None:
        if self.last_output_dir and self.last_output_dir.is_dir():
            try: os.startfile(str(self.last_output_dir))
            except OSError as exc: self.error(exc)
        else:
            self.status.configure(text='請先完成圖片處理 / Process images first')

    def add_files(self, paths: list[str] | None = None) -> None:
        if self.busy: return
        paths = paths or list(filedialog.askopenfilenames(parent=self.root, filetypes=[('Images', '*.png *.jpg *.jpeg *.webp')]))
        for path in paths:
            if path not in self.files: self.files.append(path); self.file_list.insert('end', path)

    def remove_selected(self) -> None:
        if self.busy: return
        for index in reversed(self.file_list.curselection()): self.files.pop(index); self.file_list.delete(index)

    def start_batch(self) -> None:
        if self.busy or not self.files: return
        self.busy = True
        self.start_button.configure(state='disabled')
        paths = self.files.copy()
        self.progress.configure(maximum=len(paths), value=0)
        self.put(self.batch_log, '')
        events = self.events
        def worker() -> None:
            success = failure = 0
            for i, path in enumerate(paths, 1):
                try:
                    dest = remove_metadata(path); success += 1
                    line = f'OK  {dest}'
                except Exception as exc:
                    failure += 1; line = f'FAIL  {path}: {exc}'
                events.put(('batch', i, len(paths), success, failure, line, dest.parent if line.startswith('OK') else None))
            events.put(('batch_done',))
        threading.Thread(target=worker, daemon=True).start()

    def poll(self) -> None:
        try:
            while True:
                event = self.events.get_nowait()
                if event[0] == 'image' and event[1] == self.image_request:
                    result = event[2]
                    path, self.metadata, self.preview = result.source, result.metadata, result.preview
                    self.raw_metadata = result.raw
                    self.raw_metadata_truncated = result.raw_truncated
                    self.recent = [path] + [p for p in self.recent if p != path][:19]
                    self.recent_box.delete(0, 'end')
                    for source in self.recent:
                        self.recent_box.insert('end', Path(source).name if '://' not in source else source)
                    self.render_metadata()
                    self.zoom.set(1.0); self.draw_preview()
                elif event[0] == 'image_error' and event[1] == self.image_request:
                    self.put(self.meta_text, '讀取失敗 / Read failed\n' + event[2] + '\n\n網站可能只提供縮圖、需要登入或封鎖外部讀取。請另存原始圖片後再拖入。\nSome sites require login or block image requests. Save the original image and drop the file.')
                elif event[0] == 'batch':
                    _, i, total, success, failure, line, folder = event
                    if folder: self.last_output_dir = folder
                    self.progress.configure(value=i)
                    self.batch_status.configure(text=f'{i} / {total}    成功 / Success {success}    失敗 / Failed {failure}')
                    self.batch_log.configure(state='normal'); self.batch_log.insert('end', line+'\n'); self.batch_log.see('end'); self.batch_log.configure(state='disabled')
                elif event[0] == 'batch_done':
                    self.busy = False; self.start_button.configure(state='normal')
        except queue.Empty: pass
        self.poll_id = self.root.after(100, self.poll)

    def close(self) -> None:
        if self.busy:
            self.status.configure(text='請等待批次處理完成再關閉 / Wait for the batch to finish before closing')
            return
        self.persist()
        self.root.after_cancel(self.poll_id)
        self.root.destroy()


def main() -> None:
    if sys.platform == 'win32':
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('PromptCleanerStudio.Desktop.1')
        try: ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except OSError: pass
    root = TkinterDnD.Tk()
    smoke = '--smoke-test' in sys.argv
    temporary = tempfile.TemporaryDirectory() if smoke else None
    app = App(root, Path(temporary.name)/'settings.json' if temporary else None)
    if smoke:
        def smoke_check() -> None:
            result = {'ok': False}
            try:
                app.input.insert('1.0', 'cat, CAT, [day:night:0.5]')
                app.run_clean()
                assert app.output.get('1.0', 'end-1c') == 'cat, [day:night:0.5]'
                for index in (1, 2, 0): app.switch(index)
                app.lang_button.invoke()
                app.theme_button.invoke()
                assert root.overrideredirect()
                sample = Path(temporary.name)/'sample.webp'
                Image.new('RGBA', (5, 7), (10, 20, 30, 40)).save(sample, lossless=True)
                read_metadata(sample)
                assert load_image(str(sample)).preview.size == (5, 7)
                with Image.open(remove_metadata(sample)) as image:
                    assert not image.info and image.getpixel((0, 0))[3] == 40
                result = {'ok': True, 'python': sys.version, 'tcl': root.tk.call('info', 'patchlevel'), 'frozen': bool(getattr(sys, 'frozen', False)), 'checks': ['Tk', 'DnD', 'rounded controls', 'theme/language buttons', 'chrome', 'tabs', 'cleaner', 'image source loader', 'WebP', 'PNG removal', 'settings']}
            except Exception as exc:
                result['error'] = repr(exc)
            finally:
                folder = Path.cwd()/'test-artifacts'
                folder.mkdir(exist_ok=True)
                (folder/'frozen-smoke.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
                app.close()
        root.after(800, smoke_check)
    root.mainloop()
    if temporary: temporary.cleanup()


if __name__ == '__main__': main()
