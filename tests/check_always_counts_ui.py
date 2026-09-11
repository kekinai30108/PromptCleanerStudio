import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import json
import tempfile
from tkinterdnd2 import TkinterDnD
from app import App

with tempfile.TemporaryDirectory() as folder:
    config = Path(folder)/'settings.json'
    config.write_text(json.dumps({'tag_counts': False, 'blacklist': 'watermark'}))
    root = TkinterDnD.Tk()
    app = App(root, config)
    try:
        root.update()
        assert len(app.vars) == 5 and 'tag_counts' not in app.vars
        assert all(key != 'tag_counts' for widget, key in app.labels)
        for lang in range(2):
            for preset in range(3):
                app.preset.current(preset)
                app.set_preset()
                app.input.delete('1.0', 'end')
                app.input.insert('1.0', 'watermark 42, cat 6191')
                app.run_clean()
                assert app.output.get('1.0', 'end-1c') == 'cat'
            app.change_language()
        app.change_theme()
        root.update()
    finally:
        app.close()
    assert 'tag_counts' not in json.loads(config.read_text())
print('PASS: five options, both languages, all presets, old settings, blacklist and automatic counts')
