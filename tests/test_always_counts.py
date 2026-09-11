import itertools
import unittest
from dataclasses import asdict
from core import Rules, clean
import settings


class AlwaysCountTests(unittest.TestCase):
    def test_all_option_combinations_blacklist(self):
        names = ['remove_lora', 'remove_weights', 'deduplicate', 'remove_chinese', 'remove_excl']
        for flags in itertools.product((False, True), repeat=5):
            rules = Rules(**dict(zip(names, flags)), blacklist='bike shorts under skirt, watermark')
            text = '? bike shorts 70823? bike shorts under skirt 6191? watermark 9'
            with self.subTest(flags=flags):
                output = clean(text, rules).output
                self.assertNotIn('watermark', output)
                self.assertNotIn('under skirt', output)
                self.assertNotIn('70823', output)
                self.assertIn('bike shorts', output)

    def test_plain_counts_and_blacklist(self):
        self.assertEqual(clean('watermark 9, blue eyes 42, 6191', Rules(blacklist='watermark')).output, 'blue eyes')
        self.assertEqual(clean('cat 3, CAT 999', Rules()).output, 'cat')
        self.assertEqual(clean('cat 3, CAT 999', Rules(deduplicate=False)).output, 'cat, CAT')

    def test_weights_and_blacklist(self):
        text = '(watermark:1.2) 42, (blue eyes:1.3) 6191, <lora:model2:0.8>, [day:night:0.5], 1girl, 4k'
        self.assertEqual(clean(text, Rules(blacklist='watermark')).output,
            '(blue eyes:1.3), <lora:model2:0.8>, [day:night:0.5], 1girl, 4k')
        self.assertEqual(clean(text, Rules(blacklist='watermark', remove_weights=True, remove_lora=True)).output,
            'blue eyes, [day:night:0.5], 1girl, 4k')

    def test_old_settings_cannot_disable_cleanup(self):
        for value in (True, False):
            data = settings.validate({'tag_counts': value, 'blacklist': 'watermark'})
            self.assertNotIn('tag_counts', data)
            rules = Rules(**{key: data[key] for key in asdict(Rules())})
            self.assertEqual(clean('watermark 42, cat 3', rules).output, 'cat')
