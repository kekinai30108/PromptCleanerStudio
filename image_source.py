"""Resolve native/browser drops and load original image bytes in a background worker."""
from __future__ import annotations
from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
import re
import time
from urllib.parse import urlsplit, urlunsplit, quote
from urllib.request import Request, urlopen, url2pathname
from PIL import Image, ImageOps
from metadata_parser import inspect_image

MAX_DOWNLOAD = 25 * 1024 * 1024


class _ImageHTML(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.source = ''

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == 'img' and not self.source:
            self.source = dict(attrs).get('src') or ''


def resolve_drop(payload: str, splitlist: object) -> str:
    """Prioritize img.src over a surrounding link; never execute or browse HTML."""
    text = payload.strip().strip('\x00')
    parser = _ImageHTML()
    parser.feed(text)
    candidate = parser.source
    if not candidate:
        match = re.search(r'(?:^|[\r\n{])\s*((?:https?|file)://[^\s<>"{}]+)', text, re.I)
        if match: candidate = match[1]
    if not candidate:
        # A filename with spaces may itself be the payload rather than a Tcl list.
        if Path(text).is_file(): return text
        try:
            items = splitlist(text)
            candidate = items[0] if items else ''
        except Exception:
            candidate = text
    candidate = unescape(candidate).strip()
    parsed = urlsplit(candidate)
    if parsed.scheme.lower() in ('http', 'https') and parsed.netloc: return candidate
    if parsed.scheme.lower() == 'file':
        candidate = url2pathname(('//' + parsed.netloc if parsed.netloc and parsed.netloc != 'localhost' else '') + parsed.path)
    if candidate and Path(candidate).is_file(): return candidate
    raise ValueError('請拖放原始圖片或直接圖片網址；不支援網頁、blob: 或 data:。 / Drop an image file or direct image URL; page, blob: and data: URLs are unsupported.')


def download_image(url: str) -> bytes:
    parsed = urlsplit(url)
    if parsed.scheme.lower() not in ('http', 'https') or not parsed.netloc:
        raise ValueError('Only HTTP(S) image URLs are supported')
    host = parsed.hostname or ''
    headers = {'User-Agent': 'Mozilla/5.0 PromptCleanerStudio/1.1', 'Accept': 'image/png,image/jpeg,image/webp,*/*;q=0.5'}
    if host == 'pximg.net' or host.endswith('.pximg.net'): headers['Referer'] = 'https://www.pixiv.net/'
    elif host == 'sankakucomplex.com' or host.endswith('.sankakucomplex.com'): headers['Referer'] = 'https://sankakucomplex.com/'
    encoded = urlunsplit((parsed.scheme, parsed.netloc.encode('idna').decode('ascii'),
                         quote(parsed.path, safe='/%:@'), quote(parsed.query, safe='=&%/:?+@'), ''))
    deadline = time.monotonic() + 30
    with urlopen(Request(encoded, headers=headers), timeout=15) as response:
        if urlsplit(response.geturl()).scheme not in ('http', 'https'):
            raise ValueError('Unsupported redirect')
        if int(response.headers.get('Content-Length', '0')) > MAX_DOWNLOAD:
            raise ValueError('圖片超過 25 MiB / Image exceeds 25 MiB')
        chunks, size = [], 0
        while True:
            chunk = response.read(min(64 * 1024, MAX_DOWNLOAD - size + 1))
            if not chunk: break
            size += len(chunk)
            if size > MAX_DOWNLOAD: raise ValueError('圖片超過 25 MiB / Image exceeds 25 MiB')
            if time.monotonic() > deadline: raise TimeoutError('圖片下載逾時 / Download timed out')
            chunks.append(chunk)
    content = b''.join(chunks)
    with Image.open(BytesIO(content)) as image:
        if image.format not in ('PNG', 'JPEG', 'WEBP'): raise ValueError('Unsupported image format')
        image.verify()
    return content


@dataclass
class LoadedImage:
    source: str
    metadata: dict[str, str]
    raw: str
    raw_truncated: bool
    preview: Image.Image


def load_image(source: str) -> LoadedImage:
    remote = urlsplit(source).scheme.lower() in ('http', 'https')
    content = download_image(source) if remote else None
    inspection = inspect_image(BytesIO(content) if content is not None else source)
    with Image.open(BytesIO(content) if content is not None else source) as image:
        preview = ImageOps.exif_transpose(image).convert('RGBA')
        preview.thumbnail((1600, 1600))
    return LoadedImage(source, inspection.compact(), inspection.raw, inspection.raw_truncated, preview)
