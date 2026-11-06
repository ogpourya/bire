"""CPython Regression Corpus: 100+ patterns verifying behavioral equivalence."""

import re

from bire.api import to_human, to_python

CORPUS_PATTERNS: list[tuple[str, list[str]]] = [
    # 1. Literals and Sequences
    (r"abc", ["abc", "xabcy", "ab", ""]),
    (r"hello\ world", ["hello world", "hello  world", ""]),
    (r"a\nb\tc", ["a\nb\tc", "abc", ""]),
    (r"foo\.bar", ["foo.bar", "fooxbar", "foo.bar.baz"]),
    (r"123", ["123", "0123", "12", ""]),
    # 2. Anchors
    (r"^abc", ["abc", "xabc", "abc\nxyz", ""]),
    (r"abc$", ["abc", "abcx", "xyz\nabc", ""]),
    (r"^abc$", ["abc", "xabc", "abcx", "abc\n"]),
    (r"\Aabc", ["abc", "xyz\nabc", ""]),
    (r"abc\Z", ["abc", "abc\n", "abcx", ""]),
    (r"\bword\b", ["word", "a word b", "wordless", "sword"]),
    (r"\Bword\B", ["swordless", "word", " sword "]),
    (r"^$", ["", "\n", "a"]),
    (r"\A\Z", ["", "\n", "a"]),
    # 3. Predefined Classes
    (r"\d+", ["123", "a123b", "abc", ""]),
    (r"\D+", ["abc", "a123b", "123", ""]),
    (r"\w+", ["hello_123", " hello ", "---", ""]),
    (r"\W+", ["   ", "!@#$", "abc", ""]),
    (r"\s+", ["   \t\n", "a  b", "abc", ""]),
    (r"\S+", ["abc123", " a ", "   "]),
    (r".+", ["hello", "hello\nworld", ""]),
    # 4. Character Classes & Negations
    (r"[a-z]+", ["abc", "ABC", "123", "a-z"]),
    (r"[A-Z0-9]+", ["ABC123", "abc", "!@#"]),
    (r"[^0-9]+", ["abc", "abc123", "123"]),
    (r"[^a-zA-Z]+", ["123!@", "abc", "ABC"]),
    (r"[-a-z]+", ["-abc", "abc-", "a-b-c", "ABC"]),
    (r"[a-z-]+", ["abc-", "-abc", "ABC"]),
    (r"[\[\]\-\^]+", ["[]-^", "[abc]", "^", "-"]),
    (r"[\d\s]+", ["123   456", "abc", ""]),
    (r"[^\d\s]+", ["abc", "123", "   "]),
    # 5. Greedy Quantifiers
    (r"a*", ["", "a", "aaaa", "b"]),
    (r"a+", ["a", "aaaa", "", "b"]),
    (r"a?", ["", "a", "aa"]),
    (r"a{3}", ["aaa", "aa", "aaaa"]),
    (r"a{2,4}", ["a", "aa", "aaa", "aaaa", "aaaaa"]),
    (r"a{2,}", ["a", "aa", "aaaaa", ""]),
    # 6. Lazy Quantifiers
    (r"a*?", ["", "a", "aaaa"]),
    (r"a+?", ["a", "aaaa", ""]),
    (r"a??", ["", "a", "aa"]),
    (r"a{2,4}?", ["aa", "aaa", "aaaa", "a"]),
    (r"a{2,}?", ["aa", "aaaa", "a"]),
    # 7. Possessive Quantifiers
    (r"a*+", ["", "a", "aaaa"]),
    (r"a++", ["a", "aaaa", ""]),
    (r"a?+", ["", "a", "aa"]),
    (r"a{2,4}+", ["aa", "aaa", "aaaa"]),
    (r"a{2,}+", ["aa", "aaaa", "a"]),
    # 8. Nested Quantifier Precedence (equal precedence wrapping)
    (r"(?:a*)+", ["", "a", "aaaa", "b"]),
    (r"(?:a+)+", ["a", "aaaa", "b"]),
    (r"(?:a*)*", ["", "a", "aaaa"]),
    (r"(?:a{2,3})+", ["aa", "aaaa", "aaaaa", "a"]),
    (r"(?:ab)+", ["ab", "abab", "aba", ""]),
    (r"(?:ab)*", ["", "ab", "abab", "a"]),
    # 9. Alternation
    (r"cat|dog", ["cat", "dog", "bird", ""]),
    (r"cat|dog|bird|fish", ["cat", "fish", "dog", "horse"]),
    (r"a|", ["a", "", "b"]),
    (r"|a", ["a", "", "b"]),
    (r"(?:a|b)c", ["ac", "bc", "c", "ab"]),
    (r"a(?:b|c)d", ["abd", "acd", "ad", "abcd"]),
    (r"(?:cat|dog)+", ["cat", "catdogcat", "dog", ""]),
    # 10. Groups and Captures
    (r"(a)", ["a", "aa", ""]),
    (r"(a)(b)", ["ab", "a", "b", ""]),
    (r"((a)b)", ["ab", "a", "b"]),
    (r"(a(b(c)))", ["abc", "ab", "c"]),
    (r"([a-z]+)@([a-z]+)", ["user@host", "test@domain", "bad"]),
    (r"(a)+", ["a", "aaaa", "b"]),
    (r"((?:a|b)+)", ["ababa", "a", "b", ""]),
    # 11. Named Captures
    (r"(?P<word>\w+)", ["hello", "123", ""]),
    (r"(?P<first>[a-z]+)-(?P<second>[0-9]+)", ["abc-123", "xyz-99", "abc-"]),
    (r"(?P<prefix>pre_)?(?P<core>core)", ["pre_core", "core", "pre_"]),
    # 12. Non-Capturing Groups & Scoped Flags
    (r"(?:abc)", ["abc", "x", ""]),
    (r"(?i:abc)", ["abc", "ABC", "AbC", "xyz"]),
    (r"(?m:^abc$)", ["abc", "xyz\nabc\n123", "xabc"]),
    (r"(?-i:abc)", ["abc", "ABC"]),
    # 13. Atomic Groups
    (r"(?>a+)b", ["aab", "b", "aaa"]),
    (r"(?>[a-z]+)x", ["foox", "barx", "x", "foo"]),
    (r"(?>\w+):", ["word:", "tag:", "word"]),
    # 14. Lookarounds
    (r"(?=abc)a", ["abc", "ax", ""]),
    (r"(?!abc)a", ["ax", "ay", "abc"]),
    (r"(?<=foo)bar", ["foobar", "bar", "xfoobar"]),
    (r"(?<!foo)bar", ["xbar", "foobar", "bar"]),
    (r"(?<=\d{3})[a-z]+", ["123abc", "12abc", "abc"]),
    (r"(?<!\d{3})[a-z]+", ["12abc", "123abc", "abc"]),
    (r"foo(?=bar)bar", ["foobar", "foobaz"]),
    (r"foo(?!bar)[a-z]+", ["foobaz", "foobar"]),
    # 15. Backreferences & Digit Collision
    (r"(a)\1", ["aa", "a", "ab"]),
    (r"(?P<tag>[a-z]+)_(?P=tag)", ["foo_foo", "bar_bar", "foo_bar"]),
    (r"([a-z])\1+", ["aa", "aaa", "aba", "a"]),
    (r"(a)(?:\1)0", ["aa0", "a0", "aa"]),
    (r"(a)(?:\1)9", ["aa9", "a9", "aa"]),
    (r"(a)\1x", ["aax", "ax", "aa"]),
    # 16. Conditionals
    (r"(a)(?(1)b|c)", ["ab", "b", "c", "ac"]),
    (r"(a)?(?(1)b|c)", ["ab", "c", "a", "b"]),
    (r"(?P<tag>a)?(?(tag)b|c)", ["ab", "c", "a", "b"]),
    (r"(a)(?(1)b)", ["ab", "a", "b"]),
    (r"(a)(?(1)(?:b|c)|(?:d|e))", ["ab", "ac", "ad", "ae"]),
    # 17. Practical Real-World Patterns
    (r"[a-zA-Z_][a-zA-Z0-9_]*", ["my_var1", "_init", "123bad", "hello"]),
    (r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", ["192.168.1.1", "10.0.0.1", "999.999.999.999", "abc"]),
    (r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", ["test@example.com", "user.name+tag@sub.domain.org", "bad"]),
    (r"https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+", ["http://example.com", "https://sub.domain.org/path", "ftp://"]),
    (r"\d{4}-\d{2}-\d{2}", ["2026-11-06", "1999-01-01", "2026-1-1"]),
    (r"(?:0[xX][0-9a-fA-F]+|[0-9]+)", ["0x1a", "0XFF", "1234", "0xG"]),
    (r"\"(?:[^\"\\]|\\.)*\"", ['"hello"', '"hello \\"world\\""', '""', '"unclosed']),
    (r"'(?:[^'\\]|\\.)*'", ["'hello'", "'it\\'s'", "''"]),
    (r"<!--(?:[^-]|-[^-])*-->", ["<!-- comment -->", "<!-- a - b -->", "<!-->"]),
    (r"\(\s*(?:[a-z]+(?:\s*,\s*[a-z]+)*)?\s*\)", ["()", "(a)", "(a, b, c)", "( a , b )"]),
    (r"(?P<key>[a-zA-Z_]\w*)\s*=\s*(?P<val>[^\s;]+)", ["foo = bar", "x=1", "a = b;"]),
    (r"(?:\d+\.){2}\d+", ["1.0.0", "2.15.3", "1.0"]),
    (r"v?(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)", ["v1.2.3", "0.1.0", "bad"]),
    (r"#[0-9a-fA-F]{6}", ["#ffffff", "#000000", "#1a2b3c", "#fff"]),
    (r"#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?", ["#fff", "#ffffff", "#123456"]),
    (r"\b(?:true|false|null)\b", ["true", "false", "null", "truename"]),
    (r"(?:\r\n|\r|\n)", ["\r\n", "\n", "\r", " "]),
    (r"(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d", ["12:30:45", "00:00:00", "23:59:59", "24:00:00"]),
    (r"(?:[01]\d|2[0-3]):[0-5]\d", ["12:30", "23:59", "25:00"]),
    (r"[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?", ["123", "-45.67", "+.5", "1e10", "-2.5E-3"]),
    (r"\b[A-Z]{2,}\b", ["USA", "HTML", "A", "lowercase"]),
    (r"(?P<quote>[\"'])(.*?)(?P=quote)", ['"hello"', "'world'", '"mismatch\'']),
    (r"\b(?:SELECT|INSERT|UPDATE|DELETE)\b", ["SELECT", "DELETE", "select", "UPDATE"]),
    (r"(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)", ["255", "192", "0", "99", "256"]),
]


def test_cpython_corpus_count() -> None:
    assert len(CORPUS_PATTERNS) >= 100, f"Expected at least 100 patterns, got {len(CORPUS_PATTERNS)}"


def test_cpython_corpus_behavioral_equivalence() -> None:
    for pattern, test_inputs in CORPUS_PATTERNS:
        dsl = to_human(pattern)
        py_trans, flags_trans = to_python(dsl)

        assert isinstance(py_trans, str)
        orig_re = re.compile(pattern)
        trans_re = re.compile(py_trans, flags_trans)

        for s in test_inputs:
            m1 = orig_re.search(s)
            m2 = trans_re.search(s)
            assert (m1 is None) == (m2 is None), f"Search mismatch on {pattern!r} against {s!r}"
            if m1 is not None and m2 is not None:
                assert m1.span() == m2.span(), f"Span mismatch on {pattern!r} against {s!r}"
                assert m1.groups() == m2.groups(), f"Groups mismatch on {pattern!r} against {s!r}"
                assert m1.groupdict() == m2.groupdict(), f"Groupdict mismatch on {pattern!r} against {s!r}"

            assert orig_re.findall(s) == trans_re.findall(s), f"Findall mismatch on {pattern!r} against {s!r}"
            assert orig_re.split(s) == trans_re.split(s), f"Split mismatch on {pattern!r} against {s!r}"
            assert orig_re.sub("x", s) == trans_re.sub("x", s), f"Sub mismatch on {pattern!r} against {s!r}"
