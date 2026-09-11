import unittest
from core import Rules, clean, split_tags


class CoreTests(unittest.TestCase):
    def test_dedup(self):
        self.assertEqual(clean('cat, CAT, blue_eyes, blue eyes, 2026, 42').output, 'cat, blue_eyes')

    def test_blacklist(self):
        self.assertEqual(clean('watermark, watermark text, (WATERMARK:1.2), blue_eyes', Rules(blacklist='watermark\nblue eyes')).output, 'watermark text')

    def test_control(self):
        self.assertEqual(clean('cat BREAK dog BREAK cat AND dog AND').output, 'cat, BREAK, dog, BREAK, AND, AND')

    def test_lora(self):
        text = '<lora:model:0.8>, <lyco:model:1>, cat'
        self.assertEqual(clean(text).output, text)
        self.assertEqual(clean(text, Rules(remove_lora=True)).output, 'cat')

    def test_weights(self):
        self.assertEqual(clean('(masterpiece:1.2), [tag:0.8], ((cat:1.1)), [day:night:0.5], [red|blue]', Rules(remove_weights=True)).output, 'masterpiece, tag, cat, [day:night:0.5], [red|blue]')

    def test_syntax(self):
        text = r'(a, (b, c):1.2), [day:night:0.5], [red|blue], {a,b}, escaped\,comma, literal\(tag\)'
        self.assertEqual(clean(text).output, text)
        self.assertEqual(len(split_tags(text)[0]), 6)

    def test_malformed(self):
        for text in ('(cat, dog', '[cat', '{cat', 'cat)', '<lora:model:', '<lora>', '<lora:model:>'):
            self.assertTrue(clean(text).warnings)
            self.assertEqual(clean(text, Rules(remove_weights=True, remove_lora=True)).output, text)

    def test_distinct_weights(self):
        self.assertEqual(clean('(cat:1.2), (cat:1.3), cat').kept, 3)

    def test_filters(self):
        self.assertEqual(clean('貓cat!?, blue eyes 1.2k, 2026, cat', Rules(remove_chinese=True, remove_excl=True)).output, 'cat, blue eyes')

    def test_booru_question_delimited_counts(self):
        text = '? 1girl 9676799? ahoge 943224'
        self.assertEqual(clean(text, Rules(remove_excl=True)).output, '1girl, ahoge')
        self.assertEqual(clean(text, Rules()).output, '?, 1girl, ?, ahoge')
        self.assertEqual(clean(text, Rules(remove_excl=True)).output, '1girl, ahoge')
        self.assertEqual(clean('cat 2026, dog 42', Rules()).output, 'cat, dog')

    def test_weighted_blacklist_after_strip(self):
        self.assertEqual(clean('((blue_eyes:1.2)), blue eyeshadow', Rules(remove_weights=True, blacklist='blue eyes')).output, 'blue eyeshadow')

    def test_escaped_filters_and_network_names(self):
        text = r'\<lora:model:1>, literal\!'
        self.assertEqual(clean(text, Rules(remove_lora=True, remove_excl=True)).output, text)
        self.assertEqual(clean('<lora:blue_eyes:1>, <lora:blue eyes:1>').kept, 2)


if __name__ == '__main__': unittest.main()
