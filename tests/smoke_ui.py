"""Real Tk integration tests; run in an interactive Windows desktop session."""
import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[1]))
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from PIL import Image, ImageGrab, PngImagePlugin
from tkinterdnd2 import TkinterDnD
from app import App
from window_chrome import work_area


class UITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = TkinterDnD.Tk()
        self.app = App(self.root, Path(self.temp.name)/'settings.json')
        self.initial_state = self.root.state()
        self.root.attributes('-topmost', True)
        self.pump(.3)

    def pump(self, seconds=.2):
        end = time.monotonic() + seconds
        while time.monotonic() < end: self.root.update(); time.sleep(.02)

    def tearDown(self):
        self.pump(.1)
        self.app.close(); self.temp.cleanup()
        # Collect destroyed Tk objects on their owner thread before a worker allocates.
        del self.app, self.root
        import gc
        gc.collect()

    def test_chrome_layout_and_state(self):
        a, r = self.app, self.root
        self.assertEqual(self.initial_state, 'withdrawn')
        self.assertEqual(r.state(), 'normal')
        self.assertTrue(r.overrideredirect())
        import ctypes
        user = ctypes.windll.user32
        hwnd = user.GetParent(r.winfo_id())
        self.assertTrue(user.GetWindowLongW(hwnd, -20) & 0x40000)
        self.assertFalse(user.GetWindowLongW(hwnd, -20) & 0x80)
        l,t,right,b = work_area()
        self.assertLess(abs(r.winfo_x() - (l+(right-l-r.winfo_width())//2)), 5)
        self.assertLess(a.sidebar.winfo_rootx(), a.main.winfo_rootx())
        self.assertLess(a.input.winfo_rootx(), a.output.winfo_rootx())
        a.input.insert('1.0', 'cat, CAT, [day:night:0.5]')
        a.run_clean()
        for page in (1,2,0): a.switch(page)
        a.lang_button.invoke()
        a.theme_button.invoke()
        a.theme_button.invoke()
        self.assertEqual(a.input.get('1.0','end-1c'), 'cat, CAT, [day:night:0.5]')
        self.assertEqual(a.output.get('1.0','end-1c'), 'cat, [day:night:0.5]')
        self.assertEqual(a.meta_text.tag_cget('heading','foreground'), '#B5C8FF')
        self.assertEqual(a.meta_text.tag_cget('body','foreground'), '#EDF2F7')
        self.pump()
        before = r.winfo_x()
        a.chrome.start_drag(SimpleNamespace(x_root=100,y_root=100))
        a.chrome.drag(SimpleNamespace(x_root=120,y_root=110)); self.pump()
        self.assertEqual(r.winfo_x(), before+20)
        old_width = r.winfo_width()
        a.chrome.start_resize(SimpleNamespace(x_root=100,y_root=100))
        a.chrome.resize(SimpleNamespace(x_root=140,y_root=120)); self.pump()
        self.assertEqual(r.winfo_width(), old_width+40)
        a.chrome.toggle_maximize(); self.pump()
        self.assertEqual(r.winfo_width(), right-l)
        a.chrome.toggle_maximize(); self.pump()
        a.chrome.minimize(); self.pump()
        self.assertEqual(r.state(), 'iconic')
        r.deiconify(); self.pump()
        self.assertTrue(r.overrideredirect())

    def test_browser_drop_and_minimum_layout(self):
        from unittest.mock import patch
        from io import BytesIO
        from image_source import LoadedImage
        from widgets import RoundedButton
        a, r = self.app, self.root
        r.geometry('1100x760')
        self.pump()
        self.assertIsInstance(a.lang_button, RoundedButton)
        self.assertIsInstance(a.theme_button, RoundedButton)
        self.assertLess(a.blacklist.winfo_rooty(), a.input.winfo_rooty())
        self.assertGreater(a.input.winfo_height(), 40)
        a.lang_button.invoke()
        self.pump()
        for index in range(3):
            a.switch(index)
            self.pump()
            self.assertLessEqual(a.pages[index].winfo_rootx()+a.pages[index].winfo_width(), r.winfo_rootx()+r.winfo_width())
            folder = Path(__file__).resolve().parents[1]/'test-artifacts'
            folder.mkdir(exist_ok=True)
            box = (r.winfo_rootx(), r.winfo_rooty(), r.winfo_rootx()+r.winfo_width(), r.winfo_rooty()+r.winfo_height())
            ImageGrab.grab(bbox=box).save(folder/f'minimum-en-{index}.png')
        a.switch(1)
        loaded = LoadedImage('https://example.com/image.png', {'Positive':'cat', 'Negative':'dog'}, 'parameters: cat', False, Image.new('RGB',(50,50)))
        with patch('app.load_image', return_value=loaded) as loader:
            a.handle_image_drop(SimpleNamespace(data='<img src="https://example.com/image.png">'))
            deadline = time.monotonic()+3
            while not a.metadata and time.monotonic()<deadline: self.pump()
            loader.assert_called_once_with('https://example.com/image.png')
        self.assertEqual(a.raw_metadata, 'parameters: cat')
        a.change_zoom(.1)
        self.assertEqual(a.zoom_label.cget('text'), '110%')
        a.lang_button.invoke(); a.theme_button.invoke()
        self.assertEqual(a.metadata['Negative'], 'dog')
        self.assertIsNotNone(a.preview)
        import tkinter.ttk as ttk
        self.assertFalse(any(isinstance(child, ttk.Scrollbar) for child in a.preview_frame.winfo_children()))
        self.assertEqual(a.canvas.coords(a.canvas.find_withtag('all')[-1]), [a.canvas.winfo_width()/2, a.canvas.winfo_height()/2])
        with patch.object(a, 'open_image') as choose_again:
            a.canvas.event_generate('<Button-1>', x=20, y=20)
            self.pump()
            choose_again.assert_called_once_with()

    def test_metadata_render_is_bounded(self):
        a, r = self.app, self.root
        a.switch(1)
        from image_source import LoadedImage
        huge = 'x' * 2_000_000
        a.events.put(('image', 1, LoadedImage('large.png', {'Positive': huge, 'Negative': 'bad'}, huge, True, Image.new('RGB', (4, 4)))))
        a.image_request = 1
        self.pump()
        rendered = a.meta_text.get('1.0', 'end-1c')
        self.assertLess(len(rendered), 30_000)
        self.assertIn('已截斷', rendered)
        self.assertIn('正向提示詞 (Positive)', rendered)
        a.metadata = {'Image / 圖片': 'PNG · 1080 × 1552 · RGB', 'Positive': 'cat',
                      'LoRA': '<lora:detail:0.8>', 'Steps': '35', 'Sampler': 'Euler a',
                      'Schedule type': 'Automatic', 'CFG scale': '6', 'Checkpoint': 'model.safetensors',
                      'Raw node text / 原始節點文字': '[Positive]: cat'}
        a.raw_metadata_truncated = False
        a.render_metadata()
        rendered = a.meta_text.get('1.0', 'end-1c')
        for expected in ('正向提示詞 (Positive)', '使用的 LoRA (LoRA Models)',
                         '原始節點文本 (Raw Node Text)', '生成參數 (Parameters)',
                         '[Steps]: 35', '[Sampler]: Euler a', '[Schedule type]: Automatic',
                         '[Checkpoint]: model.safetensors'):
            self.assertIn(expected, rendered)
        a.change_language()
        english = a.meta_text.get('1.0', 'end-1c')
        self.assertIn('Positive\ncat', english)
        self.assertNotIn('正向提示詞', english)
        a.switch(0)
        a.input.insert('1.0', 'draft')
        r.clipboard_clear(); r.clipboard_append('{"nodes": [], "links": []}')
        a.paste()
        self.assertEqual(a.input.get('1.0','end-1c'), 'draft')
        a.clear_all()
        self.assertEqual(a.input.get('1.0','end-1c'), '')
        self.assertEqual(a.output.get('1.0','end-1c'), '')

    def test_images_batch_history(self):
        a = self.app
        path = Path(self.temp.name)/'fixture.png'
        meta = PngImagePlugin.PngInfo()
        meta.add_text('parameters','cat\nNegative prompt: dog\nSteps: 20, Seed: 42')
        meta.add_text('prompt','{"1":{"class_type":"CLIPTextEncode","title":"Positive","inputs":{"text":"cat"}}}')
        Image.new('RGBA',(80,60),(0,128,80,180)).save(path,pnginfo=meta)
        a.switch(1); a.open_image(str(path))
        deadline = time.monotonic()+5
        while not a.metadata and time.monotonic()<deadline: self.pump()
        self.assertEqual(a.metadata['Positive'],'cat')
        self.assertTrue(any('Classification' in key for key in a.metadata))
        self.assertIsNotNone(a.preview)
        a.switch(2); a.add_files([str(path),str(path.parent/'missing.png')]); a.start_batch()
        while a.busy and time.monotonic()<deadline+5: self.pump()
        self.assertFalse(a.busy)
        self.assertTrue((path.parent/'Cleaned_Output/fixture.png').exists())
        self.assertIn('Failed 1',a.batch_status.cget('text'))
        a.switch(0)
        for i in range(32):
            a.input.delete('1.0','end'); a.input.insert('1.0',f'cat, {i}'); a.run_clean()
        self.assertEqual(len(a.history),30)
        a.history_box.current(1); a.restore_history()
        self.assertEqual(a.input.get('1.0','end-1c'),'cat, 30')
        folder = Path(__file__).resolve().parents[1]/'test-artifacts'
        folder.mkdir(exist_ok=True)
        self.pump()
        box = (self.root.winfo_rootx(), self.root.winfo_rooty(), self.root.winfo_rootx()+self.root.winfo_width(), self.root.winfo_rooty()+self.root.winfo_height())
        ImageGrab.grab(bbox=box).save(folder/'prompt-dark.png')
        a.theme_button.invoke(); self.pump()
        self.assertEqual(a.input.cget('background'), '#F7F8FB')
        ImageGrab.grab(bbox=box).save(folder/'prompt-light.png')
        a.switch(1); a.theme_button.invoke(); self.pump()
        ImageGrab.grab(bbox=box).save(folder/'metadata-dark.png')

    def test_settings_import_export_and_readonly(self):
        from unittest.mock import patch
        import json
        a = self.app
        source = Path(self.temp.name)/'reference-config.json'
        source.write_text(json.dumps({'blacklist':'watermark', 'theme':'japanese', 'lang':'en', 'remove_lora': True}), encoding='utf-8')
        original = source.read_bytes()
        a.input.insert('1.0', 'draft stays')
        with patch('app.filedialog.askopenfilename', return_value=str(source)):
            a.import_settings()
        self.assertEqual(a.input.get('1.0','end-1c'), 'draft stays')
        self.assertEqual(a.blacklist.get('1.0','end-1c'), 'watermark')
        self.assertEqual(a.config['theme'], 'light')
        self.assertEqual(a.config['lang'], 'en')
        self.assertEqual(source.read_bytes(), original)
        export = Path(self.temp.name)/'export.json'
        with patch('app.filedialog.asksaveasfilename', return_value=str(export)):
            a.export_settings()
        self.assertEqual(json.loads(export.read_text(encoding='utf-8'))['blacklist'], 'watermark')
        self.assertEqual(a.output.cget('state'), 'disabled')
        self.assertEqual(a.meta_text.cget('state'), 'disabled')


if __name__ == '__main__': unittest.main(verbosity=2)
