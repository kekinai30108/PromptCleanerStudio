"""Create exclusively named pixel-only PNG copies; never write source files."""
from __future__ import annotations
from pathlib import Path
from PIL import Image, ImageOps


def remove_metadata(source: str | Path) -> Path:
    source = Path(source)
    with Image.open(source) as image:
        if image.format not in {'PNG', 'JPEG', 'WEBP'}:
            raise ValueError('Unsupported format / 不支援的格式')
        if getattr(image, 'n_frames', 1) != 1:
            raise ValueError('Animated images are unsupported / 不支援動畫圖片')
        image.load()
        oriented = ImageOps.exif_transpose(image)
        mode = 'RGBA' if 'A' in oriented.getbands() or 'transparency' in oriented.info else 'RGB'
        converted = oriented.convert(mode)
        clean = Image.frombytes(mode, converted.size, converted.tobytes())
    folder = source.parent / 'Cleaned_Output'
    folder.mkdir(exist_ok=True)
    n = 0
    while True:
        dest = folder / f'{source.stem}{"_" + str(n) if n else ""}.png'
        try:
            stream = dest.open('xb')
            break
        except FileExistsError: n += 1
    try:
        with stream: clean.save(stream, format='PNG')
    except Exception:
        dest.unlink(missing_ok=True)
        raise
    return dest
