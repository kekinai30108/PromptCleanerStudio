import json
import tempfile
import unittest
from pathlib import Path
from PIL import Image, PngImagePlugin
from metadata_parser import MAX_RAW_CHARS, MAX_SECTION_CHARS, inspect_image, parse_a1111, parse_comfy, read_metadata
from metadata_remover import remove_metadata
import settings


class MetadataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)

    def tearDown(self): self.temp.cleanup()

    def fixture(self):
        path = self.folder/'sample.png'
        meta = PngImagePlugin.PngInfo()
        meta.add_text('parameters', 'cat\nNegative prompt: dog\nSteps: 20, Sampler: Euler a, CFG scale: 7, Seed: 42, Size: 8x5, Model: test, VAE: auto, Clip skip: 2')
        Image.new('RGBA', (8, 5), (12, 34, 56, 77)).save(path, pnginfo=meta, icc_profile=b'test')
        return path

    def test_a1111(self):
        data = read_metadata(self.fixture())
        for key, value in {'Positive':'cat', 'Negative':'dog', 'Steps':'20', 'Seed':'42', 'Model':'test', 'Clip skip':'2'}.items(): self.assertEqual(data[key], value)

    def test_a1111_lora_and_full_parameter_list(self):
        text = '<lora:detail:0.8>, cat\nNegative prompt: bad\nSteps: 35, Sampler: Euler a, Schedule type: Automatic, CFG scale: 6, Seed: 2139347506, Size: 1080x1552, Model hash: 5d255f746e, Model: example_v69, Denoising strength: 0.59, Clip skip: 2, RNG: CPU, Soft inpainting enabled: True, Mask blur: 4, Inpaint area: Only masked, Masked area padding: 32, Version: neo, Module 1: illustriousXLV20_v10'
        data = parse_a1111(text)
        self.assertEqual(data['Positive'], 'cat')
        self.assertEqual(data['LoRA'], '<lora:detail:0.8>')
        for key in ('Steps', 'Sampler', 'Schedule type', 'CFG scale', 'Seed', 'Size', 'Model hash', 'Model', 'Denoising strength', 'Clip skip', 'RNG', 'Soft inpainting enabled', 'Mask blur', 'Inpaint area', 'Masked area padding', 'Version', 'Module 1'):
            self.assertIn(key, data)

    def test_comfy(self):
        data = parse_comfy({'1': {'class_type':'CLIPTextEncode', '_meta':{'title':'Positive'}, 'inputs':{'text':'cat'}}, '2': {'class_type':'CLIPTextEncode', 'title':'Negative', 'inputs':{'text':'dog'}}, '3':{'class_type':'LoraLoader','inputs':{'lora_name':'model'}}})
        self.assertTrue(any(k.startswith('Positive') and v == 'cat' for k,v in data.items()))
        self.assertTrue(any(k.startswith('Negative') and v == 'dog' for k,v in data.items()))
        self.assertTrue(any(k.startswith('LoRA') for k in data))
        self.assertIn('Heuristic', data['Classification / 分類'])

    def test_workflow(self):
        data = parse_comfy({'nodes':[{'type':'CLIPTextEncode', 'widgets_values':['cat']}]})
        self.assertEqual(data['Positive'], 'cat')

    def test_large_metadata_is_bounded_and_targeted(self):
        source = self.folder/'large.png'
        huge = 'x' * (MAX_RAW_CHARS + 500)
        workflow = json.dumps({'1': {'class_type': 'CLIPTextEncode', 'title': 'Positive', 'inputs': {'text': huge}},
                               '2': {'class_type': 'CLIPTextEncode', 'title': 'Negative', 'inputs': {'text': 'bad'}}})
        meta = PngImagePlugin.PngInfo(); meta.add_text('prompt', workflow)
        Image.new('RGB', (2, 2)).save(source, pnginfo=meta)
        result = inspect_image(source)
        self.assertTrue(result.raw_truncated)
        self.assertEqual(len(result.raw), MAX_RAW_CHARS)
        self.assertLessEqual(len(result.positive[0]), MAX_SECTION_CHARS + 32)
        self.assertEqual(result.negative, ['bad'])

    def test_clean_transparency_and_unique(self):
        source = self.fixture(); original = source.read_bytes()
        first, second = remove_metadata(source), remove_metadata(source)
        self.assertEqual(first.parent.name, 'Cleaned_Output')
        self.assertNotEqual(first, second)
        self.assertEqual(source.read_bytes(), original)
        with Image.open(first) as image:
            self.assertEqual(image.info, {})
            self.assertEqual(len(image.getexif()), 0)
            self.assertEqual(image.getpixel((0, 0)), (12, 34, 56, 77))

    def test_orientation(self):
        source = self.folder/'rotated.jpg'
        exif = Image.Exif(); exif[274] = 6
        Image.new('RGB', (8, 5), 'red').save(source, exif=exif)
        with Image.open(remove_metadata(source)) as image:
            self.assertEqual(image.size, (5, 8)); self.assertFalse(image.getexif())

    def test_webp(self):
        source = self.folder/'a.webp'
        Image.new('RGBA', (8, 5), (1, 2, 3, 99)).save(source, lossless=True, exif=b'')
        with Image.open(remove_metadata(source)) as image: self.assertEqual(image.getpixel((0,0))[3], 99)

    def test_animated_rejected(self):
        source = self.folder/'anim.png'
        Image.new('RGB', (4,4), 'red').save(source, save_all=True, append_images=[Image.new('RGB', (4,4), 'blue')])
        with self.assertRaises(ValueError): remove_metadata(source)

    def test_settings(self):
        path = self.folder/'settings.json'
        path.write_text('{broken', encoding='utf-8')
        self.assertEqual(settings.load(path), settings.DEFAULTS)
        settings.save({'lang':'en', 'theme':[], 'deduplicate':'false'}, path)
        self.assertEqual(settings.load(path)['lang'], 'en')
        self.assertTrue(settings.load(path)['deduplicate'])
        self.assertEqual(path.with_name('settings.json.bak').read_text(), '{broken')


if __name__ == '__main__': unittest.main()
