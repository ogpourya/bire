"""Unit tests for Python regex renderer."""

import re

from bire.ast.nodes import (
    AlternationNode,
    AnchorKind,
    AnchorNode,
    Backreference,
    ByteLiteral,
    ByteRange,
    CaptureGroup,
    CharacterClass,
    CharRange,
    Conditional,
    EmptyNode,
    PredefinedClass,
    PredefinedKind,
    Quantifier,
    QuantifierMode,
    RegexPattern,
    SequenceNode,
    TextLiteral,
)
from bire.parsers.python_parser import parse_python_regex
from bire.renderers.python_renderer import render_python


def test_render_empty_and_literals() -> None:
    assert render_python(EmptyNode()) == ""
    assert render_python(TextLiteral("hello world.")) == r"hello world\."
    res = render_python(ByteLiteral(b"abc\x00\xff"), is_bytes=True)
    assert isinstance(res, bytes)
    assert res == rb"abc\x00\xff"


def test_quantifier_precedence_wrapping() -> None:
    # Quantifier on Quantifier: MUST wrap in (?:...)
    # Quantifier(Quantifier(a, *), +) must NOT produce a*+
    q_inner = Quantifier(
        child=TextLiteral("a"), min_count=0, max_count=None, mode=QuantifierMode.GREEDY
    )
    q_outer = Quantifier(
        child=q_inner, min_count=1, max_count=None, mode=QuantifierMode.GREEDY
    )
    rendered = render_python(q_outer)
    assert isinstance(rendered, str)
    assert rendered == r"(?:a*)+"
    cp = re.compile(rendered)
    assert cp.match("aaa") is not None

    # Quantifier on Sequence: MUST wrap in (?:...)
    seq = SequenceNode(items=(TextLiteral("a"), TextLiteral("b")))
    q_seq = Quantifier(child=seq, min_count=1, max_count=None, mode=QuantifierMode.GREEDY)
    assert render_python(q_seq) == r"(?:ab)+"

    # Quantifier on Multi-character TextLiteral: MUST wrap in (?:...)
    q_multi = Quantifier(child=TextLiteral("ab"), min_count=1, max_count=None, mode=QuantifierMode.GREEDY)
    assert render_python(q_multi) == r"(?:ab)+"

    # Quantifier on Atom (single char): no wrapping
    q_atom = Quantifier(child=TextLiteral("a"), min_count=1, max_count=None, mode=QuantifierMode.GREEDY)
    assert render_python(q_atom) == r"a+"


def test_alternation_precedence_wrapping() -> None:
    alt = AlternationNode(branches=(TextLiteral("a"), TextLiteral("b")))
    seq = SequenceNode(items=(alt, TextLiteral("c")))
    rendered = render_python(seq)
    assert isinstance(rendered, str)
    assert rendered == r"(?:a|b)c"
    cp = re.compile(rendered)
    assert cp.match("ac") is not None
    assert cp.match("bc") is not None


def test_backreference_digit_collision_protection() -> None:
    # Backreference(1) followed by TextLiteral("0") MUST be wrapped as (?:\1)0
    node_collision = SequenceNode(
        items=(
            CaptureGroup(child=TextLiteral("a"), group_id=1),
            Backreference(reference=1),
            TextLiteral("0"),
        )
    )
    rendered_col = render_python(node_collision)
    assert isinstance(rendered_col, str)
    assert rendered_col == r"(a)(?:\1)0"
    cp = re.compile(rendered_col)
    m = cp.match("aa0")
    assert m is not None
    assert m.group(1) == "a"

    # Backreference(1) followed by non-digit does NOT need wrapping
    node_safe = SequenceNode(
        items=(
            CaptureGroup(child=TextLiteral("a"), group_id=1),
            Backreference(reference=1),
            TextLiteral("x"),
        )
    )
    assert render_python(node_safe) == r"(a)\1x"


def test_conditional_alternation_wrapping() -> None:
    cond = Conditional(
        condition=1,
        if_true=AlternationNode(branches=(TextLiteral("a"), TextLiteral("b"))),
        if_false=AlternationNode(branches=(TextLiteral("c"), TextLiteral("d"))),
    )
    seq = SequenceNode(
        items=(
            CaptureGroup(child=TextLiteral("x"), group_id=1),
            cond,
        )
    )
    rendered = render_python(seq)
    assert isinstance(rendered, str)
    assert rendered == r"(x)(?(1)(?:a|b)|(?:c|d))"
    cp = re.compile(rendered)
    assert cp.match("xa") is not None
    assert cp.match("xb") is not None


def test_character_class_escaping() -> None:
    cc = CharacterClass(
        negated=False,
        elements=(
            TextLiteral("["),
            TextLiteral("]"),
            TextLiteral("-"),
            TextLiteral("^"),
            CharRange("a", "z"),
            PredefinedClass(PredefinedKind.DIGIT),
        ),
    )
    rendered = render_python(cc)
    assert isinstance(rendered, str)
    cp = re.compile(rendered)
    for test_char in ["[", "]", "-", "^", "m", "5"]:
        assert cp.match(test_char) is not None


def test_bytes_renderer() -> None:
    node = SequenceNode(
        items=(
            CaptureGroup(child=ByteLiteral(b"foo"), group_id=1, name="name"),
            AnchorNode(AnchorKind.WORD_BOUNDARY),
            CharacterClass(negated=False, elements=(ByteRange(0, 127),)),
            PredefinedClass(PredefinedKind.DIGIT),
        )
    )
    rendered = render_python(RegexPattern(root=node, is_bytes=True))
    assert isinstance(rendered, bytes)
    cp = re.compile(rendered)
    assert cp.match(b"foo\x205") is not None


def test_behavioral_equivalence_roundtrip() -> None:
    patterns = [
        r"abc",
        r"^foo[0-9]+bar$",
        r"(?:a|b)c",
        r"(?:a*)+",
        r"(?:ab)+",
        r"(?P<first>[a-z]+)\s+(?P=first)",
        r"(a)(?(1)b|c)",
        r"(?>[a-z]+)x",
        r"(?<=foo)bar",
        r"(?<!foo)bar",
        r"(?=foo)bar",
        r"(?!foo)bar",
        r"\A\b\B\Z",
    ]
    test_strings = [
        "abc",
        "foo123bar",
        "ac",
        "bc",
        "aaa",
        "ab",
        "hello hello",
        "ab",
        "hellox",
        "foobar",
        "bar",
        "",
    ]

    for p in patterns:
        ast = parse_python_regex(p)
        rendered = render_python(ast)
        assert isinstance(rendered, str)
        orig_cp = re.compile(p)
        trans_cp = re.compile(rendered)

        for s in test_strings:
            m1 = orig_cp.search(s)
            m2 = trans_cp.search(s)
            assert (m1 is None) == (m2 is None), f"Mismatch search on {p!r} with {s!r}"
            if m1 is not None and m2 is not None:
                assert m1.span() == m2.span()
                assert m1.groups() == m2.groups()
                assert m1.groupdict() == m2.groupdict()
