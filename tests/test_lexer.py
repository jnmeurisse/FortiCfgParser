import io
import unittest

from FortiCfgParser._parser import FgtConfigParser, FgtConfigEosError, FgtConfigSyntaxError


class TestLexer(unittest.TestCase):
    def test_lexer_1(self):
        m = io.StringIO("")
        lexer = FgtConfigParser.Lexer(m)
        self.assertEqual(lexer.next_token(), FgtConfigParser.Lexer.EOS)

    def test_lexer_2(self):
        m = io.StringIO("   A     B    C     D")
        lexer = FgtConfigParser.Lexer(m)
        self.assertEqual(lexer.next_token(), 'A')
        self.assertEqual(lexer.next_token(), 'B')
        self.assertEqual(lexer.next_token(), 'C')
        self.assertEqual(lexer.next_token(), 'D')
        self.assertTrue(lexer._is_eol(lexer.next_token()))

    def test_lexer_3(self):
        m = io.StringIO("   A B C\n  D E")
        lexer = FgtConfigParser.Lexer(m)
        self.assertEqual(lexer.next_token(), 'A')
        self.assertEqual(lexer.next_token(), 'B')
        self.assertEqual(lexer.next_token(), 'C')
        self.assertEqual(lexer.next_token(), FgtConfigParser.Lexer.EOL)
        self.assertEqual(lexer.next_token(), 'D')
        self.assertEqual(lexer.next_token(), 'E')
        self.assertTrue(lexer._is_eol(lexer.next_token()))

    def test_lexer_4(self):
        m = io.StringIO("\n\n\nconfig   A B C\n  D E")
        lexer = FgtConfigParser.Lexer(m)
        self.assertEqual(lexer.next_snl_token(), 'config')
        self.assertListEqual(lexer.next_parameters(), ['A', 'B', 'C'])
        self.assertEqual(lexer.next_token(), 'D')
        self.assertEqual(lexer.next_token(), 'E')
        self.assertTrue(lexer._is_eol(lexer.next_token()))

    def test_lexer_5(self):
        m = io.StringIO("   A B C\n  D E")
        lexer = FgtConfigParser.Lexer(m)
        self.assertListEqual(lexer.next_parameters(), ['A', 'B', 'C'])
        self.assertEqual(lexer.next_token(), 'D')
        self.assertEqual(lexer.next_token(), 'E')
        self.assertTrue(lexer._is_eol(lexer.next_token()))

    def test_lexer_6(self):
        m = io.StringIO('#c1\n#c2\n\nconfig   A "B" C\n  D E')
        lexer = FgtConfigParser.Lexer(m)
        self.assertEqual(lexer.next_token(), '#c1')
        self.assertEqual(lexer.next_token(), '#c2')
        self.assertEqual(lexer.next_snl_token(), 'config')
        self.assertListEqual(lexer.next_parameters(), ['A', '"B"', 'C'])
        self.assertEqual(lexer.next_token(), 'D')
        self.assertEqual(lexer.next_token(), 'E')
        self.assertTrue(lexer._is_eol(lexer.next_token()))
        self.assertTrue(lexer._is_eol(lexer.next_snl_token(raise_eos=False)))
        with self.assertRaises(FgtConfigEosError):
            lexer.next_snl_token()

    def test_lexer_7(self):
        comment = ' "COMMENT 1\nX" '
        m = io.StringIO(comment)
        lexer = FgtConfigParser.Lexer(m)
        self.assertEqual(lexer.next_token(), comment.strip())

    def test_lexer_8(self):
        comment = ' "COMMENT 2 '
        m = io.StringIO(comment)
        lexer = FgtConfigParser.Lexer(m)
        with self.assertRaises(FgtConfigSyntaxError):
            lexer.next_token()
