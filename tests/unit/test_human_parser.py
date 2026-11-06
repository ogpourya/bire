"""Unit tests for BiRe Human DSL parser and renderer."""

import re

from bire.ast.flags import names_to_flags
from bire.ast.nodes import (
    AlternationNode,
    CaptureGroup,
    CharacterClass,
    CharRange,
    Conditional,
    EmptyNode,
    Lookaround,
    PredefinedClass,
    PredefinedKind,
    Quantifier,
    QuantifierMode,
    SequenceNode,
    TextLiteral,
)
from bire.parsers.human_parser import parse_human_dsl
from bire.parsers.python_parser import parse_python_regex
from bire.renderers.human_renderer import render_human
from bire.renderers.python_renderer import render_python


def test_parse_simple_dsl() -> None:
    dsl = 'LITERAL "hello"\n'
    pattern = parse_human_dsl(dsl)
    assert isinstance(pattern.root, TextLiteral)
    assert pattern.root.value == "hello"


def test_parse_alternation_dsl() -> None:
    dsl = """EITHER:
    LITERAL "cat"
OR:
    LITERAL "dog"
OR:
    EMPTY
"""
    pattern = parse_human_dsl(dsl)
    assert isinstance(pattern.root, AlternationNode)
    assert len(pattern.root.branches) == 3
    assert pattern.root.branches[0] == TextLiteral("cat")
    assert pattern.root.branches[1] == TextLiteral("dog")
    assert pattern.root.branches[2] == EmptyNode()


def test_parse_character_class_dsl() -> None:
    dsl = """ONE OF:
    RANGE "a" TO "z"
    CHARS "._-"
    DIGIT
"""
    pattern = parse_human_dsl(dsl)
    assert isinstance(pattern.root, CharacterClass)
    assert not pattern.root.negated
    assert len(pattern.root.elements) == 5
    assert pattern.root.elements[0] == CharRange("a", "z")
    assert pattern.root.elements[1] == TextLiteral(".")
    assert pattern.root.elements[2] == TextLiteral("_")
    assert pattern.root.elements[3] == TextLiteral("-")
    assert pattern.root.elements[4] == PredefinedClass(PredefinedKind.DIGIT)


def test_parse_quantifiers_dsl() -> None:
    dsl = """REPEAT ZERO OR MORE TIMES:
    DIGIT
REPEAT AT LEAST 1 TIMES LAZILY:
    WORD CHARACTER
REPEAT BETWEEN 2 AND 4 TIMES POSSESSIVELY:
    LITERAL "a"
"""
    pattern = parse_human_dsl(dsl)
    assert isinstance(pattern.root, SequenceNode)
    q1, q2, q3 = pattern.root.items
    assert isinstance(q1, Quantifier) and q1.min_count == 0 and q1.max_count is None and q1.mode == QuantifierMode.GREEDY
    assert isinstance(q2, Quantifier) and q2.min_count == 1 and q2.max_count is None and q2.mode == QuantifierMode.LAZY
    assert isinstance(q3, Quantifier) and q3.min_count == 2 and q3.max_count == 4 and q3.mode == QuantifierMode.POSSESSIVE


def test_parse_groups_and_lookarounds() -> None:
    dsl = """CAPTURE "user":
    REPEAT AT LEAST 1 TIMES:
        WORD CHARACTER
LOOKAHEAD:
    LITERAL "@"
NEGATIVE LOOKBEHIND:
    DIGIT
IF CAPTURE "user":
    LITERAL ".com"
ELSE:
    LITERAL ".org"
MATCH CAPTURE "user"
"""
    pattern = parse_human_dsl(dsl)
    assert isinstance(pattern.root, SequenceNode)
    cap = pattern.root.items[0]
    assert isinstance(cap, CaptureGroup)
    assert cap.group_id == 1
    assert cap.name == "user"

    la = pattern.root.items[1]
    assert isinstance(la, Lookaround) and not la.behind and not la.negative

    lb = pattern.root.items[2]
    assert isinstance(lb, Lookaround) and lb.behind and lb.negative

    cond = pattern.root.items[3]
    assert isinstance(cond, Conditional)
    assert cond.condition == "user"


def test_parse_header_and_bytes_mode() -> None:
    dsl = """MODE: BYTES
FLAGS: [IGNORECASE, MULTILINE]

BYTES "\\x00\\xff"
"""
    pattern = parse_human_dsl(dsl)
    assert pattern.is_bytes
    assert pattern.flags == names_to_flags(["IGNORECASE", "MULTILINE"])


def test_dsl_ast_roundtrip() -> None:
    patterns = [
        r"cat",
        r"(?:a*)+",
        r"(?:ab)+",
        r"(?P<first>[a-z]+)\s+(?P=first)",
        r"(a)(?(1)b|c)",
        r"(?>[a-z]+)x",
        r"(?<=foo)bar",
        r"(?<!foo)bar",
        r"(?=foo)bar",
        r"(?!foo)bar",
        r"\A^foo\b\Bbar$\Z",
        r"[a-zA-Z0-9_]",
        r"[^0-9]",
    ]

    for p in patterns:
        py_ast = parse_python_regex(p)
        dsl_rendered = render_human(py_ast)
        reparsed_ast = parse_human_dsl(dsl_rendered)

        py1 = render_python(py_ast)
        py2 = render_python(reparsed_ast)

        assert isinstance(py1, str)
        assert isinstance(py2, str)
        cp1 = re.compile(py1)
        cp2 = re.compile(py2)
        test_strings = ["cat", "foo", "bar", "foobar", "123", "hello hello", "ax", ""]
        for s in test_strings:
            m1 = cp1.search(s)
            m2 = cp2.search(s)
            assert (m1 is None) == (m2 is None)
            if m1 is not None and m2 is not None:
                assert m1.span() == m2.span()
                assert m1.groups() == m2.groups()
                assert m1.groupdict() == m2.groupdict()
