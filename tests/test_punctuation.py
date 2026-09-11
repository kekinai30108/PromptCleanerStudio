import unittest
from core import Rules, clean


class PunctuationTests(unittest.TestCase):
    def test_each_website_question_survives_deduplication(self):
        text = '? 1girl 9680036? ahoge 943626? animal ears 1782067'
        self.assertEqual(clean(text).output, '?, 1girl, ?, ahoge, ?, animal ears')
        self.assertEqual(clean(text, Rules(remove_excl=True)).output, '1girl, ahoge, animal ears')

    def test_punctuation_and_repeated_tags_are_independent(self):
        self.assertEqual(clean('?, cat, ?, CAT, !, !').output, '?, cat, ?, !, !')
        self.assertEqual(clean('?, cat, ?, CAT, !, !', Rules(remove_excl=True)).output, 'cat')

