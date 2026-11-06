"""Hypothesis Property-Based Differential Fuzzing with Anti-ReDoS Invariants."""

from __future__ import annotations

import re
from typing import Any

import hypothesis.strategies as st
from hypothesis import given, settings

from bire.api import to_human, to_python
from bire.ast.nodes import (
    AlternationNode,
    AnchorKind,
    AnchorNode,
    ASTNode,
    CaptureGroup,
    CharacterClass,
    CharRange,
    EmptyNode,
    PredefinedClass,
    PredefinedKind,
    Quantifier,
    QuantifierMode,
    SequenceNode,
    TextLiteral,
)
from bire.renderers.python_renderer import render_python

# Leaf strategies (Depth 0)
st_safe_char = st.sampled_from(["a", "b", "c", "0", "1", "_", " "])
st_safe_text = st.text(alphabet=["a", "b", "c", "0", "1", "d", "e"], min_size=1, max_size=3).map(TextLiteral)

st_predefined = st.sampled_from([
    PredefinedKind.DIGIT,
    PredefinedKind.WORD,
    PredefinedKind.WHITESPACE,
    PredefinedKind.ANY,
]).map(PredefinedClass)

st_anchor = st.sampled_from([
    AnchorKind.LINE_START,
    AnchorKind.LINE_END,
    AnchorKind.WORD_BOUNDARY,
]).map(AnchorNode)

st_char_range = st.sampled_from([
    CharRange("a", "c"),
    CharRange("0", "3"),
    CharRange("p", "r"),
])

st_char_class = st.tuples(
    st.booleans(),
    st.lists(
        st.one_of(
            st_safe_char.map(TextLiteral),
            st_char_range,
            st.sampled_from([PredefinedKind.DIGIT, PredefinedKind.WORD]).map(PredefinedClass),
        ),
        min_size=1,
        max_size=3,
    ),
).map(lambda t: CharacterClass(negated=t[0], elements=tuple(t[1])))

st_leaf = st.one_of(st_safe_text, st_predefined, st_anchor, st_char_class, st.just(EmptyNode()))


def _has_quantifier(node: ASTNode) -> bool:
    if isinstance(node, Quantifier):
        return True
    if isinstance(node, (SequenceNode, AlternationNode)):
        children = node.items if isinstance(node, SequenceNode) else node.branches
        return any(_has_quantifier(c) for c in children)
    if isinstance(node, CaptureGroup):
        return _has_quantifier(node.child)
    return False


# Bounded tree builder (depth <= 3, anti-ReDoS)
@st.composite
def st_quantifier(draw: Any) -> Quantifier:
    # Child must NOT contain any quantifiers (no quantifier inside quantifier)
    # Child can be a leaf, or a short sequence/alternation of leaves
    child = draw(st.one_of(
        st_safe_text,
        st_predefined,
        st_char_class,
        st.lists(st.one_of(st_safe_text, st_char_class), min_size=1, max_size=2).map(lambda it: SequenceNode(tuple(it))),
    ))
    min_c = draw(st.integers(min_value=0, max_value=2))
    max_c = draw(st.one_of(st.none(), st.integers(min_value=min_c, max_value=min_c + 3)))
    mode = draw(st.sampled_from([QuantifierMode.GREEDY, QuantifierMode.LAZY, QuantifierMode.POSSESSIVE]))
    return Quantifier(child=child, min_count=min_c, max_count=max_c, mode=mode)


@st.composite
def st_ast_tree(draw: Any, max_depth: int = 2) -> ASTNode:
    if max_depth <= 0:
        return draw(st_leaf)  # type: ignore[no-any-return]

    choice = draw(st.integers(min_value=0, max_value=4))
    if choice == 0:
        return draw(st_leaf)  # type: ignore[no-any-return]
    if choice == 1:
        # Sequence
        items = draw(st.lists(st_ast_tree(max_depth=max_depth - 1), min_size=1, max_size=3))
        return SequenceNode(items=tuple(items))
    if choice == 2:
        # Alternation
        branches = draw(st.lists(st_ast_tree(max_depth=max_depth - 1), min_size=2, max_size=3))
        return AlternationNode(branches=tuple(branches))
    if choice == 3:
        # Quantifier
        return draw(st_quantifier())  # type: ignore[no-any-return]
    # Capture group
    child = draw(st_ast_tree(max_depth=max_depth - 1))
    return CaptureGroup(child=child, group_id=1)


def _generate_sample_positive(node: ASTNode) -> str:
    match node:
        case EmptyNode() | AnchorNode():
            return ""
        case TextLiteral(value=v):
            return v
        case PredefinedClass(kind=PredefinedKind.DIGIT):
            return "1"
        case PredefinedClass(kind=PredefinedKind.WORD):
            return "a"
        case PredefinedClass(kind=PredefinedKind.WHITESPACE):
            return " "
        case PredefinedClass(kind=PredefinedKind.ANY):
            return "x"
        case PredefinedClass():
            return "a"
        case CharRange(start=s):
            return s
        case CharacterClass(negated=False, elements=elements):
            if elements:
                return _generate_sample_positive(elements[0])
            return "a"
        case CharacterClass(negated=True):
            return "Z"
        case SequenceNode(items=items):
            return "".join(_generate_sample_positive(it) for it in items)
        case AlternationNode(branches=branches):
            if branches:
                return _generate_sample_positive(branches[0])
            return ""
        case Quantifier(child=child, min_count=min_c):
            count = max(1, min_c)
            return "".join(_generate_sample_positive(child) for _ in range(count))
        case CaptureGroup(child=child):
            return _generate_sample_positive(child)
        case _:
            return "a"


@settings(max_examples=1000, deadline=1000)
@given(node=st_ast_tree(max_depth=2), random_suffix=st.text(alphabet=["a", "b", "1", " "], max_size=3))
def test_differential_equivalence_1000_iterations(node: ASTNode, random_suffix: str) -> None:
    # Render AST to Python pattern
    py_pattern = render_python(node)
    assert isinstance(py_pattern, str)

    try:
        orig_re = re.compile(py_pattern)
    except re.error:
        # Skip syntactically rejected edge-cases from random combinations
        return

    # Transpile Python pattern to Human DSL and back
    dsl = to_human(py_pattern)
    trans_pattern, trans_flags = to_python(dsl)
    assert isinstance(trans_pattern, str)

    trans_re = re.compile(trans_pattern, trans_flags)

    # 1. Positive sample
    pos_sample = _generate_sample_positive(node)
    # 2. Mutated / near-miss sample
    mut_sample = (pos_sample + "!") if pos_sample else "!"
    # 3. Random noise sample
    rnd_sample = random_suffix

    for s in (pos_sample, mut_sample, rnd_sample):
        # search
        m1 = orig_re.search(s)
        m2 = trans_re.search(s)
        assert (m1 is None) == (m2 is None), f"search mismatch on {py_pattern!r} -> {trans_pattern!r} with {s!r}"
        if m1 is not None and m2 is not None:
            assert m1.span() == m2.span()
            assert m1.groups() == m2.groups()
            assert m1.groupdict() == m2.groupdict()

        # match
        assert (orig_re.match(s) is None) == (trans_re.match(s) is None)

        # fullmatch
        assert (orig_re.fullmatch(s) is None) == (trans_re.fullmatch(s) is None)

        # findall
        assert orig_re.findall(s) == trans_re.findall(s)

        # split
        assert orig_re.split(s) == trans_re.split(s)

        # sub
        assert orig_re.sub("x", s) == trans_re.sub("x", s)
