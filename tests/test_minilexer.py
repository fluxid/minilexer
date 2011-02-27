# -*- coding: utf-8 -*-

from fxd import minilexer
from unittest import TestCase
from io import StringIO

def pass_token(context):
    pass

class TestParserSubclass(minilexer.Parser):
    def __init__(self, lexer):
        super().__init__(lexer)
        self.matched = list()

    def token_match(self, token, match):
        super().token_match(token, match)
        self.matched.append(token)

BASE = dict(
    _begin = 'begin',
    finish = dict(
        match = minilexer.MRE('\n?$'),
        after = 'should not happen!',
    )
)

def parse(lexer, *lines):
    parser = TestParserSubclass(lexer)
    parser.parse_lines(lines)
    parser.finish()
    return parser

class WellDone(Exception):
    '''
    Ironic, isn't it?
    '''
    pass


class TestBaseLexerPositives(TestCase):
    '''
    Testing positive matches: no errors should be raised
    '''
    def test_ms(self):
        my_lexer = dict(
            BASE,
            begin = dict(
                match = minilexer.MS('word1'),
                after = 'word2',
            ),
            word2 = dict(
                match = minilexer.MS('word2', True),
                after = 'finish',
            ),
        )
        parse(my_lexer, 'word1wOrD2')

    def test_mre_simple(self):
        my_lexer = dict(
            BASE,
            begin = dict(
                match = minilexer.MRE('(word1){2}'),
                after = 'word2',
            ),
            word2 = dict(
                match = minilexer.MRE('wo?rd2', True),
                after = 'finish',
            ),
        )
        parse(my_lexer, 'word1word1wRD2')

    def test_mre_more(self):
        my_lexer = dict(
            BASE,
            begin = dict(
                match = minilexer.MS('left'),
                after = 'word',
            ),
            word = dict(
                match = minilexer.MRE('(?<=left)word(?=right)', True),
                after = 'right',
            ),
            right = dict(
                match = minilexer.MS('right'),
                after = 'finish',
            ),
        )
        parse(my_lexer, 'leftwordright')

    def test_mm_match(self):
        my_lexer = dict(
            BASE,
            begin = dict(
                match = minilexer.MM(
                    minilexer.MS("won't match"),
                    minilexer.MRE("won't\s+match\s+either"),
                    minilexer.MS('word1'),
                ),
                after = 'word2',
            ),
            word2 = dict(
                match = minilexer.MS('word2'),
                after = 'finish',
            ),
        )
        parse(my_lexer, 'word1word2')

    def test_mm_nomatch(self):
        my_lexer = dict(
            BASE,
            begin = dict(
                match = (
                    'mmatch',
                    'word1',
                ),
            ),
            mmatch = dict(
                match = minilexer.MM(
                    minilexer.MS("won't match"),
                    minilexer.MRE("won't\s+match\s+either"),
                ),
                after = 'will not happen',
            ),
            word1 = dict(
                match = minilexer.MS('word1'),
                after = 'word2',
            ),
            word2 = dict(
                match = minilexer.MS('word2'),
                after = 'finish',
            ),
        )
        parse(my_lexer, 'word1word2')

    def test_groups(self):
        my_lexer = dict(
            BASE,
            begin = dict(
                match = (
                    'word1',
                    'word2',
                    'finish',
                ),
            ),
            word1 = dict(
                match = minilexer.MS('word1'),
                after = 'begin',
            ),
            word2 = dict(
                match = minilexer.MS('word2'),
                after = 'begin',
            ),
        )
        parse(my_lexer, 'word1word2')

    def test_nested_groups(self):
        my_lexer = dict(
            BASE,
            begin = dict(
                match = (
                    'wontmatch',
                    'words',
                    'finish',
                ),
            ),
            wontmatch = dict(
                match = (
                    'nomatch1',
                    'nomatch2',
                ),
            ),
            nomatch1 = dict(
                match = minilexer.MS('should not happen 1'),
                after = 'should not happen 1',
            ),
            nomatch2 = dict(
                match = minilexer.MS('should not happen 2'),
                after = 'should not happen 2',
            ),
            words = dict(
                match = (
                    'word1',
                    'word2',
                ),
            ),
            word1 = dict(
                match = minilexer.MS('word1'),
                after = 'begin',
            ),
            word2 = dict(
                match = minilexer.MS('word2'),
                after = 'begin',
            ),
        )
        parse(my_lexer, 'word1word2')

    def test_after_is_call(self):
        my_lexer = dict(
            BASE,
            begin = dict(
                match = minilexer.MS('matchme!'),
                after = lambda context: 'finish',
            ),
        )
        parse(my_lexer, 'matchme!')

    def test_on_match_call(self):
        did_it = False
        def do_it(context):
            nonlocal did_it
            did_it = True

        my_lexer = dict(
            BASE,
            begin = dict(
                match = minilexer.MS('matchme!'),
                on_match = do_it,
                after = 'finish',
            ),
        )
        parse(my_lexer, 'matchme!')
        self.assertTrue(did_it)

    def test_readline(self):
        string = StringIO('word1\nword2')
        # make sure...
        self.assertListEqual(string.readlines(), ['word1\n', 'word2'])
        string.seek(0)

        my_lexer = dict(
            BASE,
            begin = dict(
                match = minilexer.MRE('word1$'),
                after = 'word2',
            ),
            word2 = dict(
                match = minilexer.MS('word2'),
                after = 'finish',
            ),
        )
        parser = minilexer.Parser(my_lexer)
        parser.parse_readline(string.readline)
        parser.finish()

    def test_splitlines(self):
        my_lexer = dict(
            BASE,
            begin = dict(
                match = minilexer.MRE('word1$'),
                after = 'word2',
            ),
            word2 = dict(
                match = minilexer.MS('word2'),
                after = 'finish',
            ),
        )
        parse(my_lexer, 'word1\nword2')


class TestBaseLexerNegatives(TestCase):
    '''
    Testing negative matches - error handling etc
    '''
    def assertRaisesLexerError(self, my_lexer, string, error_id):
        try:
            parse(my_lexer, string)
        except minilexer.LexerError as e:
            if e.error_id != error_id:
                self.fail('Incorrect LexerError raised: {} (kwargs = {})'.format(e.error_id, e.kwargs))
            return e.kwargs # We may be interested in further details ;)
        except:
            raise
        else:
            self.fail('Exception not raised')

    def test_e_token_not_found(self):
        my_lexer = BASE
        self.assertRaisesLexerError(my_lexer, 'anything sould do', minilexer.LexerError.E_TOKEN_NOT_FOUND)

    def test_e_missing_match(self):
        my_lexer = dict(
            BASE,
            begin = dict(),
        )
        self.assertRaisesLexerError(my_lexer, 'anything sould do', minilexer.LexerError.E_MISSING_MATCH)

    def test_e_missing_after(self):
        my_lexer = dict(
            BASE,
            begin = dict(
                match = minilexer.MS('spam and eggs'),
            ),
        )
        self.assertRaisesLexerError(my_lexer, 'anything sould do', minilexer.LexerError.E_MISSING_AFTER)

    def test_e_loop_and_visits(self):
        class socrazy:
            def __init__(self, *args):
                self.args = args
                self.counter = 0

            def __iter__(self):
                self.counter += 1
                return iter(self.args)

        a_subtokens = socrazy('a1', 'a2')

        my_lexer = dict(
            BASE,
            begin = dict(match = ('a', 'b')),
            a = dict(match = a_subtokens),
            a1 = dict(match = minilexer.MS('Y'), after = 'foo'), # Won't match
            a2 = dict(match = minilexer.MS('Z'), after = 'bar'), # Won't match
            b = dict(match = ('a', 'b1')),
            b1 = dict(match = ('a', 'b')),
        )
        kwargs = self.assertRaisesLexerError(my_lexer, 'X', minilexer.LexerError.E_LOOP)
        # Should detect 'b' as loop, not 'a'
        self.assertEqual(kwargs['name'], 'b')

        # And by the way, check if we iterated through a subtokens just once
        # to check if really ignore reduntant token matches
        self.assertEqual(a_subtokens.counter, 1)

    def test_e_no_match(self):
        my_lexer = dict(
            BASE,
            begin = dict(
                match = minilexer.MS('spam and eggs'),
                after = 'finish'
            ),
        )
        self.assertRaisesLexerError(my_lexer, 'anything sould do', minilexer.LexerError.E_NO_MATCH)

    def test_on_match_call_raising(self):
        def do_it(context):
            raise WellDone()

        my_lexer = dict(
            BASE,
            begin = dict(
                match = minilexer.MRE("no+! I won't!"),
                on_fail = do_it,
                after = 'finish',
            ),
        )
        self.assertRaises(WellDone, parse, my_lexer, 'matchme!')

    def test_on_match_call_ignoring(self):
        did_it = [False, False]
        def do_it(idx):
            def really_do_it(context):
                did_it[idx] = True
            return really_do_it

        my_lexer = dict(
            BASE,
            begin = dict(
                match = (
                    'maybe_me',
                    'or_maybe_this_one',
                ),
            ),
            maybe_me = dict(
                match = minilexer.MS('not me!'),
                on_fail = do_it(0),
                after = 'finish',
            ),
            or_maybe_this_one = dict(
                match = minilexer.MRE('match(?:someone|me)!'),
                on_match = do_it(1),
                after = 'finish',
            ),
        )
        parse(my_lexer, 'matchme!')
        # Make sure we really did fail...
        self.assertTrue(did_it[0])
        # ... and make sure we continued
        self.assertTrue(did_it[1])

class TestBugFixes(TestCase):
    '''
    Test cases I found invalid, trying to reproduce bugs.
    '''
    def test_percent_wtf(self):
        my_lexer = dict(
            BASE,
            begin = dict(
                match = (
                    'a',
                    'b',
                )
            ),
            a = dict(
                match = minilexer.MS('a'),
                after = 'finish',
            ),
            b = dict(
                match = minilexer.MS('b'),
                after = 'finish',
            ),
        )
        parser = parse(my_lexer, 'b')
        self.assertListEqual(parser.matched, ['b'])


class CoveragePenisEnlargement(TestCase):
    '''
    Just make sure we have 100% coverage...
    '''
    def test_stuff(self):
        matcher = minilexer.Matcher()
        self.assertRaises(NotImplementedError, matcher.match, None, None, None)

    def test_lexer_error(self):
        # This did actually fail at first test... shame on me
        self.assertIn('spam', str(minilexer.LexerError(minilexer.LexerError.E_TOKEN_NOT_FOUND, name='spam')))
        self.assertIn('spam', str(minilexer.LexerError(minilexer.LexerError.E_MISSING_MATCH, name='spam')))
        self.assertIn('spam', str(minilexer.LexerError(minilexer.LexerError.E_MISSING_AFTER, name='spam')))
        self.assertIn('spam', str(minilexer.LexerError(minilexer.LexerError.E_LOOP, name='spam')))
        self.assertIn('spam', str(minilexer.LexerError(minilexer.LexerError.E_NO_MATCH, lineno='spam', pos='eggs')))
