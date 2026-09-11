import unittest
from core import Rules, clean


class WebsiteCountTests(unittest.TestCase):
    def test_mixed_counts_all_filters(self):
        text = '? 1girl 9680036? ahoge 943626? animal ears 1782067? armband 81830? bandaid 98450? bike shorts 70823? bike shorts under skirt 6191? rare tag 3'
        rules = Rules(remove_lora=True, remove_weights=True, remove_chinese=True,
                      remove_excl=True)
        self.assertEqual(clean(text, rules).output,
                         '1girl, ahoge, animal ears, armband, bandaid, bike shorts, bike shorts under skirt, rare tag')

    def test_options_independent(self):
        text = '? bike shorts 70823? bike shorts under skirt 6191'
        self.assertEqual(clean(text, Rules(remove_excl=True)).output,
                         'bike shorts, bike shorts under skirt')
        self.assertEqual(clean(text, Rules()).output,
                         '?, bike shorts, ?, bike shorts under skirt')
        self.assertEqual(clean(text).output, '?, bike shorts, ?, bike shorts under skirt')

    def test_count_lengths_and_whitespace(self):
        for count in ('0', '9', '42', '123', '6191', '70823', '9680036', '1.2k'):
            for boundary in ('?', ' ? ', '\n?', ', ?'):
                with self.subTest(count=count, boundary=boundary):
                    self.assertEqual(clean('? blue eyes '+count+boundary+' cat 7  ',
                        Rules(remove_excl=True)).output, 'blue eyes, cat')

    def test_prompt_numbers_and_syntax_survive(self):
        text = r'1girl, 2girls, (cat:1.2), [day:night:0.5], literal\? tag'
        self.assertEqual(clean(text, Rules(remove_excl=True)).output, text)


if __name__ == '__main__':
    unittest.main()
