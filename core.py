"""Conservative Stable Diffusion tokenization; malformed syntax is never repaired."""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class Rules:
    remove_lora: bool = False
    remove_weights: bool = False
    deduplicate: bool = True
    remove_chinese: bool = False
    remove_excl: bool = False
    tag_counts: bool = False
    blacklist: str = ""


@dataclass
class Report:
    output: str
    kept: int
    removed: list[tuple[str, str]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def split_tags(text: str) -> tuple[list[str], list[str]]:
    tags, warnings, stack = [], [], []
    buf = ""
    escaped = False
    pairs = {')': '(', ']': '[', '}': '{', '>': '<'}
    i = 0
    while i < len(text):
        ch = text[i]
        if escaped:
            buf += ch
            escaped = False
            i += 1
            continue
        if ch == '\\':
            buf += ch
            escaped = True
            i += 1
            continue
        control = re.match(r'(BREAK|AND)(?=$|[\s,])', text[i:]) if not stack and (not buf or buf[-1].isspace()) else None
        if control:
            if buf.strip():
                tags.append(buf.strip())
            tags.append(control[0])
            buf = ""
            i += len(control[0])
            continue
        if ch in '([{':
            stack.append(ch)
        elif ch == '<' and re.match(r'<(?:lora|lyco|lycoris):', text[i:], re.I):
            stack.append(ch)
        elif ch in pairs:
            if stack and stack[-1] == pairs[ch]:
                stack.pop()
            elif ch != '>':
                warnings.append('Unmatched closing bracket / 未配對右括號: ' + ch)
        if ch in ',\n\r' and not stack:
            if buf.strip():
                tags.append(buf.strip())
            buf = ""
        else:
            buf += ch
        i += 1
    if buf.strip():
        tags.append(buf.strip())
    if stack:
        warnings.append('Unclosed bracket / 未閉合括號: ' + ''.join(stack))
    if re.search(r'<(?:lora|lyco|lycoris)\b', text, re.I) and re.search(r'<(?:lora|lyco|lycoris)\b[^>]*(?:$)', text, re.I):
        warnings.append('Incomplete LoRA / LoRA 語法不完整')
    for network in re.finditer(r'(?<!\\)<(?:lora|lyco|lycoris)\b[^>]*>', text, re.I):
        if not re.fullmatch(r'<(?:lora|lyco|lycoris):[^:<>]+:[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?::[^<>]+)?>', network[0], re.I):
            warnings.append('Incomplete LoRA / LoRA 語法不完整: ' + network[0])
    return tags, warnings


def unweight(tag: str) -> str:
    """Strip only a whole balanced emphasis wrapper, never schedules/alternation."""
    while len(tag) > 1 and tag[0] in '([' and tag[-1] == {'(': ')', '[': ']'}[tag[0]]:
        depth, escaped, whole = 0, False, True
        for i, c in enumerate(tag):
            if escaped:
                escaped = False
                continue
            if c == '\\':
                escaped = True
                continue
            if c == tag[0]: depth += 1
            if c == tag[-1]: depth -= 1
            if depth == 0 and i < len(tag) - 1: whole = False
        if not whole: break
        inner = tag[1:-1]
        # More than one top-level colon denotes a schedule.
        level, separators = 0, []
        escaped = False
        for i, c in enumerate(inner):
            if escaped: escaped = False; continue
            if c == '\\': escaped = True; continue
            if c in '([{': level += 1
            elif c in ')]}': level -= 1
            elif level == 0 and c in ':|': separators.append((i, c))
        if any(c == '|' for _, c in separators) or len(separators) > 1: break
        if separators:
            pos = separators[0][0]
            if not re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)', inner[pos+1:]): break
            inner = inner[:pos]
        tag = inner.strip()
    return tag


def normalized(tag: str) -> str:
    return re.sub(r'\s+', ' ', tag.replace('_', ' ')).strip().casefold()


def clean(text: str, rules: Rules | None = None) -> Report:
    rules = rules or Rules()
    tags, warnings = split_tags(text)
    blocked = {normalized(unweight(t)) for t in split_tags(rules.blacklist)[0]}
    result, removed, seen = [], [], set()
    for original in tags:
        if original in ('BREAK', 'AND'):
            result.append(original)
            continue
        tag = original
        if split_tags(tag)[1]:
            result.append(tag)
            continue
        if rules.remove_lora:
            tag = re.sub(r'(?<!\\)<(?:lora|lyco|lycoris):[^<>]+>', '', tag, flags=re.I).strip()
        if rules.remove_weights: tag = unweight(tag)
        if rules.remove_chinese: tag = re.sub(r'[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\U00020000-\U0003134f]', '', tag)
        if rules.remove_excl: tag = re.sub(r'(?<!\\)[!?！？]', '', tag)
        if rules.tag_counts: tag = re.sub(r'\s+(?:\(\d+\)|\[\d+\]|\d+(?:\.\d+)?[kKmM])$', '', tag)
        tag = tag.strip()
        key = tag.casefold() if re.search(r'<(?:lora|lyco|lycoris):', tag, re.I) else normalized(tag)
        reason = ''
        if not tag: reason = 'Filtered / 規則移除'
        elif normalized(unweight(tag)) in blocked: reason = 'Blacklist / 黑名單'
        elif rules.deduplicate and key in seen: reason = 'Duplicate / 重複'
        if reason: removed.append((original, reason))
        else:
            result.append(tag)
            seen.add(key)
    return Report(', '.join(result), len(result), removed, warnings)
