import tempfile
import unittest
from pathlib import Path
from io import BytesIO
from unittest.mock import patch
from PIL import Image, PngImagePlugin
from image_source import resolve_drop, download_image, load_image, MAX_DOWNLOAD


class Response(BytesIO):
    def __init__(self, content, headers=None):
        super().__init__(content)
        self.headers = headers or {}

    def geturl(self): return 'https://example.com/image.png'


class ImageSourceTests(unittest.TestCase):
    def fixture(self):
        data = BytesIO()
        meta = PngImagePlugin.PngInfo()
        meta.add_text('parameters', 'cat\nNegative prompt: dog\nSteps: 20, Seed: 42')
        Image.new('RGBA', (12, 10), (20, 40, 60, 100)).save(data, 'PNG', pnginfo=meta)
        return data.getvalue()

    def test_browser_payloads(self):
        split = lambda s: (s.strip('{}'),)
        self.assertEqual(resolve_drop('{https://example.com/a.png}', split), 'https://example.com/a.png')
        self.assertEqual(resolve_drop('#comment\r\nhttps://example.com/a.png\r\n', split), 'https://example.com/a.png')
        self.assertEqual(resolve_drop('<a href="https://example.com/page"><img src="https://example.com/a.png?a=1&amp;b=2"></a>', split), 'https://example.com/a.png?a=1&b=2')
        self.assertEqual(resolve_drop('https://example.com/a.png\nImage title', split), 'https://example.com/a.png')

    def test_file_url_and_spaces(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'圖片 with spaces.png'
            path.write_bytes(self.fixture())
            self.assertEqual(Path(resolve_drop(path.as_uri(), lambda s: (s,))), path)
            self.assertEqual(resolve_drop(str(path), lambda s: (s,)), str(path))

    def test_unsupported_payload(self):
        for text in ('blob:https://example.com/1', 'data:image/png;base64,xxx', 'javascript:alert(1)'):
            with self.assertRaises(ValueError): resolve_drop(text, lambda s: (s,))

    def test_remote_preserves_metadata_and_pixels(self):
        data = self.fixture()
        with patch('image_source.urlopen', return_value=Response(data)) as request:
            result = load_image('https://example.com/image.png')
        self.assertEqual(result.metadata['Seed'], '42')
        self.assertTrue(result.raw.startswith('cat\nNegative prompt: dog'))
        self.assertEqual(result.preview.getpixel((0,0)), (20,40,60,100))
        self.assertEqual(request.call_args.kwargs['timeout'], 15)

    def test_limits_and_non_image(self):
        for response in (Response(b'', {'Content-Length': str(MAX_DOWNLOAD+1)}), Response(b'<html>login page</html>')):
            with patch('image_source.urlopen', return_value=response):
                with self.assertRaises((ValueError, OSError)): download_image('https://example.com/image')

    def test_http_failure(self):
        with patch('image_source.urlopen', side_effect=TimeoutError('timeout')):
            with self.assertRaises(TimeoutError): load_image('https://example.com/image')


if __name__ == '__main__': unittest.main()
