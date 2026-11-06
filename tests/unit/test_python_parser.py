"""Unit tests for CPython regex parser adapter."""

import re

import pytest

from bire.ast.exceptions import ParseError
from bire.ast.nodes import (
    AnchorKind,
    AnchorNode,
    AtomicGroup,
    ByteRange,
    CaptureGroup,
    CharacterClass,
    CharRange,
    Conditional,
    EmptyNode,
    Lookaround,
    NonCapturingGroup,
    PredefinedClass,
    PredefinedKind,
    Quantifier,
    QuantifierMode,
    SequenceNode,
    TextLiteral,
)
from bire.ast.validator import validate_ast
from bire.parsers.python_parser import parse_python_regex


def test_parse_literals_and_empty() -> None:
    ast_empty = parse_python_regex("")
    assert isinstance(ast_empty.root, EmptyNode)
    validate_ast(ast_empty)

    ast_lit = parse_python_regex("abc")
    assert isinstance(ast_lit.root, TextLiteral)
    assert ast_lit.root.value == "abc"
    validate_ast(ast_lit)

    ast_seq = parse_python_regex("a^b")
    assert isinstance(ast_seq.root, SequenceNode)
    assert len(ast_seq.root.items) == 3
    validate_ast(ast_seq)


def test_parse_character_classes() -> None:
    ast_range = parse_python_regex(r"[a-z0-9_]")
    assert isinstance(ast_range.root, CharacterClass)
    assert not ast_range.root.negated
    assert len(ast_range.root.elements) == 3
    assert ast_range.root.elements[0] == CharRange("a", "z")
    assert ast_range.root.elements[1] == CharRange("0", "9")
    assert ast_range.root.elements[2] == TextLiteral("_")
    validate_ast(ast_range)

    ast_neg = parse_python_regex(r"[^a]")
    assert isinstance(ast_neg.root, CharacterClass)
    assert ast_neg.root.negated
    assert ast_neg.root.elements == (TextLiteral("a"),)
    validate_ast(ast_neg)

    ast_predef = parse_python_regex(r"\d")
    assert isinstance(ast_predef.root, PredefinedClass)
    assert ast_predef.root.kind == PredefinedKind.DIGIT
    validate_ast(ast_predef)


def test_parse_quantifiers() -> None:
    ast_star = parse_python_regex(r"a*")
    assert isinstance(ast_star.root, Quantifier)
    assert ast_star.root.min_count == 0
    assert ast_star.root.max_count is None
    assert ast_star.root.mode == QuantifierMode.GREEDY

    ast_lazy = parse_python_regex(r"a+?")
    assert isinstance(ast_lazy.root, Quantifier)
    assert ast_lazy.root.min_count == 1
    assert ast_lazy.root.max_count is None
    assert ast_lazy.root.mode == QuantifierMode.LAZY

    ast_poss = parse_python_regex(r"a*+")
    assert isinstance(ast_poss.root, Quantifier)
    assert ast_poss.root.mode == QuantifierMode.POSSESSIVE

    ast_bound = parse_python_regex(r"a{2,5}")
    assert isinstance(ast_bound.root, Quantifier)
    assert ast_bound.root.min_count == 2
    assert ast_bound.root.max_count == 5


def test_parse_groups_and_atomic() -> None:
    ast_cap = parse_python_regex(r"(?P<username>\w+)")
    assert isinstance(ast_cap.root, CaptureGroup)
    assert ast_cap.root.group_id == 1
    assert ast_cap.root.name == "username"
    validate_ast(ast_cap)

    ast_noncap = parse_python_regex(r"(?i:abc)")
    assert isinstance(ast_noncap.root, NonCapturingGroup)
    assert bool(ast_noncap.root.flags_add & re.IGNORECASE)

    ast_atomic = parse_python_regex(r"(?>\w+)")
    assert isinstance(ast_atomic.root, AtomicGroup)
    validate_ast(ast_atomic)


def test_parse_lookarounds() -> None:
    ast_pla = parse_python_regex(r"(?=abc)")
    assert isinstance(ast_pla.root, Lookaround)
    assert not ast_pla.root.behind and not ast_pla.root.negative
    validate_ast(ast_pla)

    ast_nla = parse_python_regex(r"(?!abc)")
    assert isinstance(ast_nla.root, Lookaround)
    assert not ast_nla.root.behind and ast_nla.root.negative
    validate_ast(ast_nla)

    ast_plb = parse_python_regex(r"(?<=abc)")
    assert isinstance(ast_plb.root, Lookaround)
    assert ast_plb.root.behind and not ast_plb.root.negative
    validate_ast(ast_plb)

    ast_nlb = parse_python_regex(r"(?<!abc)")
    assert isinstance(ast_nlb.root, Lookaround)
    assert ast_nlb.root.behind and ast_nlb.root.negative
    validate_ast(ast_nlb)


def test_parse_conditionals_and_backrefs() -> None:
    pattern = r"(?P<tag>[a-z]+)foo(?P=tag)(?(tag)yes|no)"
    ast = parse_python_regex(pattern)
    assert isinstance(ast.root, SequenceNode)
    validate_ast(ast)

    # Numbered conditional
    ast_num = parse_python_regex(r"(a)(?(1)b)")
    assert isinstance(ast_num.root, SequenceNode)
    assert isinstance(ast_num.root.items[1], Conditional)
    assert ast_num.root.items[1].condition == 1
    assert ast_num.root.items[1].if_false is None
    validate_ast(ast_num)


def test_parse_anchors() -> None:
    pattern = r"\A^word\b\B$\Z"
    ast = parse_python_regex(pattern)
    assert isinstance(ast.root, SequenceNode)
    kinds = [item.kind for item in ast.root.items if isinstance(item, AnchorNode)]
    assert kinds == [
        AnchorKind.STRING_START,
        AnchorKind.LINE_START,
        AnchorKind.WORD_BOUNDARY,
        AnchorKind.NOT_WORD_BOUNDARY,
        AnchorKind.LINE_END,
        AnchorKind.STRING_END,
    ]
    validate_ast(ast)


def test_parse_flags() -> None:
    ast = parse_python_regex(r"(?im)abc")
    assert bool(ast.flags & re.IGNORECASE)
    assert bool(ast.flags & re.MULTILINE)
    validate_ast(ast)


def test_parse_bytes_mode() -> None:
    ast = parse_python_regex(rb"(?i)[\x00-\x7f]\w+")
    assert ast.is_bytes
    assert bool(ast.flags & re.IGNORECASE)
    assert isinstance(ast.root, SequenceNode)
    cc = ast.root.items[0]
    assert isinstance(cc, CharacterClass)
    assert isinstance(cc.elements[0], ByteRange)
    assert cc.elements[0].start == 0 and cc.elements[0].end == 127
    validate_ast(ast)


def test_parse_invalid_syntax_raises_parse_error() -> None:
    with pytest.raises(ParseError, match="Failed to parse regex pattern"):
        parse_python_regex(r"[a-")

    with pytest.raises(ParseError, match="Failed to parse regex pattern"):
        parse_python_regex(r"(?P<bad-name>a)")
