"""Bounded A1111 and ComfyUI inspection, modeled after PromptCleaner_v2.0.py."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO

from PIL import Image

MAX_SECTION_CHARS = 24_000
MAX_RAW_CHARS = 1_000_000
MAX_VALUES_PER_SECTION = 16
MAX_OTHER_ITEMS = 12


@dataclass
class Inspection:
    """Small presentation result. Raw source is deliberately never rendered."""
    image: str
    positive: list[str] = field(default_factory=list)
    negative: list[str] = field(default_factory=list)
    lora: list[str] = field(default_factory=list)
    raw_nodes: list[str] = field(default_factory=list)
    settings: dict[str, str] = field(default_factory=dict)
    other: dict[str, str] = field(default_factory=dict)
    source_type: str = ''
    raw: str = ''
    raw_truncated: bool = False

    def compact(self) -> dict[str, str]:
        result = {'Image / 圖片': self.image}
        if self.positive: result['Positive'] = '\n\n'.join(self.positive)
        if self.negative: result['Negative'] = '\n\n'.join(self.negative)
        if self.lora: result['LoRA'] = '\n'.join(self.lora)
        if self.raw_nodes: result['Raw node text / 原始節點文字'] = '\n\n'.join(self.raw_nodes)
        result.update(self.settings)
        result.update({f'Other / 其他 · {key}': value for key, value in self.other.items()})
        if self.source_type == 'ComfyUI': result['Classification / 分類'] = 'Heuristic / 啟發式結果；未完整追蹤節點連線'
        if len(result) == 1: result['Status / 狀態'] = 'No generation metadata / 無生成中繼資料'
        return result


def decode(value: object) -> str:
    if isinstance(value, bytes):
        if value.startswith(b'UNICODE\x00'):
            payload = value[8:]
            encoding = 'utf-16' if payload[:2] in (b'\xff\xfe', b'\xfe\xff') else 'utf-16-be'
            return payload.decode(encoding, errors='replace').rstrip('\x00')
        if value.startswith(b'ASCII\x00\x00\x00'):
            value = value[8:]
        return value.decode('utf-8', errors='replace').rstrip('\x00')
    return str(value)


def _limited(value: object, limit: int = MAX_SECTION_CHARS) -> str:
    text = decode(value)
    return text if len(text) <= limit else text[:limit] + '\n…（此區顯示已截斷）'


def _raw_limited(value: object) -> tuple[str, bool]:
    text = decode(value)
    return (text, False) if len(text) <= MAX_RAW_CHARS else (text[:MAX_RAW_CHARS], True)


def _unique(values: list[str], limit: int = MAX_VALUES_PER_SECTION) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        bounded = _limited(value)
        if bounded and bounded not in seen:
            seen.add(bounded)
            result.append(bounded)
            if len(result) >= limit:
                break
    return result


def _parse_parameters(text: str, inspection: Inspection) -> None:
    positive = text
    negative = ''
    setting_text = ''
    if 'Negative prompt:' in positive:
        positive, remainder = positive.split('Negative prompt:', 1)
        if '\nSteps: ' in remainder:
            negative, setting_text = remainder.split('\nSteps: ', 1)
            setting_text = 'Steps: ' + setting_text
        else:
            negative = remainder
    elif '\nSteps: ' in positive:
        positive, setting_text = positive.split('\nSteps: ', 1)
        setting_text = 'Steps: ' + setting_text
    networks = re.findall(r'<(?:lora|lyco|lycoris):[^>]+>', positive, re.I)
    positive = re.sub(r'<(?:lora|lyco|lycoris):[^>]+>', '', positive, flags=re.I).strip(' ,\n')
    if positive:
        inspection.positive.append(_limited(positive.strip()))
    if negative.strip():
        inspection.negative.append(_limited(negative.strip()))
    inspection.lora.extend(networks[:MAX_VALUES_PER_SECTION])
    for pair in setting_text.split(', '):
        if ': ' in pair and len(inspection.settings) < 30:
            key, value = pair.split(': ', 1)
            inspection.settings[key] = _limited(value, 2_000)


def _node_values(node: dict[str, object]) -> list[object]:
    values: list[object] = []
    widgets = node.get('widgets_values')
    if isinstance(widgets, list): values.extend(widgets)
    inputs = node.get('inputs')
    if isinstance(inputs, dict): values.extend(inputs.values())
    return values


def _parse_comfy(raw: str, inspection: Inspection) -> None:
    """v2.0's node-title heuristic, but bounded before it reaches the UI."""
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError('ComfyUI JSON must be an object')
    nodes_value: object = data.get('nodes', data.values())
    nodes = nodes_value.values() if isinstance(nodes_value, dict) else nodes_value
    if not hasattr(nodes, '__iter__'):
        return
    positive: list[str] = []
    negative: list[str] = []
    raw_nodes: list[str] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_type = str(node.get('type', '') or node.get('class_type', '')).lower()
        meta = node.get('_meta')
        meta_title = meta.get('title', '') if isinstance(meta, dict) else ''
        node_title = str(node.get('title', '') or meta_title).lower()
        full_title = f'{node_type} {node_title}'
        is_text_node = any(item in node_type for item in ('text', 'string', 'prompt', 'primitive'))
        is_lora_node = 'lora' in node_type
        for value in _node_values(node):
            if isinstance(value, bool):
                continue
            if isinstance(value, (int, float)):
                if 'steps' in full_title: inspection.settings.setdefault('Steps', str(value))
                elif 'cfg' in full_title: inspection.settings.setdefault('CFG', str(value))
                elif 'denoise' in full_title: inspection.settings.setdefault('Denoise', str(value))
                elif 'seed' in full_title and isinstance(value, int) and value > 10_000:
                    inspection.settings.setdefault('Seed (Possible)', str(value))
                continue
            if not isinstance(value, str) or len(value) < 2:
                continue
            if is_lora_node and ('lora' in full_title or value.endswith(('.safetensors', '.pt', '.ckpt', '.pth'))):
                inspection.lora.append(_limited(value, 2_000))
                continue
            if value.endswith(('.safetensors', '.pt', '.ckpt', '.pth')):
                inspection.settings.setdefault('Checkpoint', _limited(value, 2_000))
                continue
            if not is_text_node:
                continue
            display = str(node.get('title') or node.get('type') or 'Node')
            raw_nodes.append(f'[{display}]: {_limited(value)}')
            if 'negative' in full_title:
                negative.append(value)
            elif 'positive' in full_title or 'clip' in node_type:
                positive.append(value)
    inspection.positive = [value for value in _unique(positive) if value not in set(_unique(negative))]
    inspection.negative = _unique(negative)
    inspection.raw_nodes = _unique(raw_nodes)
    inspection.lora = _unique(inspection.lora)


def inspect_image(path: str | Path | BinaryIO) -> Inspection:
    with Image.open(path) as image:
        if image.format not in {'PNG', 'JPEG', 'WEBP'}:
            raise ValueError('Unsupported format / 不支援的格式')
        image.load()
        info = dict(image.info)
        inspection = Inspection(f'{image.format} · {image.width} × {image.height} · {image.mode}')
        exif = image.getexif()
        comment = exif.get(37510) or exif.get_ifd(34665).get(37510)
        parameters = info.get('parameters') or comment or info.get('comment') or exif.get(270)
        comfy = info.get('workflow') or info.get('prompt')
        if comfy:
            inspection.raw, inspection.raw_truncated = _raw_limited(comfy)
            inspection.source_type = 'ComfyUI'
            _parse_comfy(decode(comfy), inspection)
        elif parameters:
            inspection.raw, inspection.raw_truncated = _raw_limited(parameters)
            inspection.source_type = 'A1111'
            _parse_parameters(decode(parameters), inspection)
        for key, value in info.items():
            if key not in ('parameters', 'workflow', 'prompt') and len(inspection.other) < MAX_OTHER_ITEMS:
                inspection.other[str(key)] = _limited(value, 500)
        return inspection


def parse_a1111(text: str) -> dict[str, str]:
    inspection = Inspection('Unknown')
    _parse_parameters(text, inspection)
    return inspection.compact()


def parse_comfy(data: object) -> dict[str, str]:
    raw = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
    inspection = Inspection('Unknown', source_type='ComfyUI')
    _parse_comfy(raw, inspection)
    return inspection.compact()


def read_metadata(path: str | Path | BinaryIO) -> dict[str, str]:
    return inspect_image(path).compact()
