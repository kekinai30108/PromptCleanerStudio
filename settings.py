"""Validated settings, with atomic updates and a backup of the prior file."""
from __future__ import annotations
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from dataclasses import asdict
from core import Rules

DEFAULTS = {**asdict(Rules()), 'lang': 'zh', 'theme': 'dark'}


def settings_path() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData/Local')) / 'PromptCleanerStudio/settings.json'
    return Path(__file__).parent / 'settings.json'


def validate(data: object) -> dict:
    out = DEFAULTS.copy()
    if isinstance(data, dict):
        for k, v in out.items():
            if type(data.get(k)) is type(v): out[k] = data[k]
    if out['lang'] not in ('zh', 'en'): out['lang'] = 'zh'
    if out['theme'] not in ('dark', 'light'): out['theme'] = 'dark'
    return out


def load(path: Path | None = None) -> dict:
    try: return validate(json.loads((path or settings_path()).read_text(encoding='utf-8')))
    except (OSError, ValueError, UnicodeError): return DEFAULTS.copy()


def save(data: dict, path: Path | None = None) -> None:
    path = path or settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=path.name, suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(validate(data), stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        if path.exists():
            # Keep every previous settings version without overwriting it.
            backup = path.with_name(path.name + '.bak')
            n = 1
            while backup.exists():
                backup = path.with_name(f'{path.name}.{n}.bak'); n += 1
            shutil.copy2(path, backup)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp): os.unlink(temp)
