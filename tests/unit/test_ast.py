"""Unit tests for bire AST definitions and semantic validator."""

import re

import pytest

from bire.ast.exceptions import ValidationError
from bire.ast.flags import flags_to_names, names_to_flags
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
    Lookaround,
    PredefinedClass,
    PredefinedKind,
    Quantifier,
    QuantifierMode,
    RegexPattern,
    SequenceNode,
    TextLiteral,
)
from bire.ast.validator import validate_ast


def test_flag_roundtrip() -> None:
    flags = re.IGNORECASE | re.MULTILINE | re.DOTALL
    names = flags_to_names(flags)
    assert set(names) == {"IGNORECASE", "MULTILINE", "DOTALL"}
    assert names_to_flags(names) == flags


def test_flag_unknown() -> None:
    with pytest.raises(ValueError, match="Unknown flag"):
        names_to_flags(["NOT_A_FLAG"])


def test_valid_simple_pattern() -> None:
    pattern = RegexPattern(
        root=SequenceNode(
            items=(
                TextLiteral("hello"),
                PredefinedClass(PredefinedKind.DIGIT),
                AnchorNode(AnchorKind.LINE_END),
            )
        )
    )
    validate_ast(pattern)


def test_reject_anchor_repetition() -> None:
    pattern = Quantifier(
        child=AnchorNode(AnchorKind.LINE_START),
        min_count=1,
        max_count=None,
        mode=QuantifierMode.GREEDY,
    )
    with pytest.raises(ValidationError, match="Cannot repeat zero-width anchor"):
        validate_ast(pattern)


def test_reject_invalid_quantifier_bounds() -> None:
    with pytest.raises(ValidationError, match="min_count cannot be negative"):
        validate_ast(
            Quantifier(
                child=TextLiteral("a"), min_count=-1, max_count=2, mode=QuantifierMode.GREEDY
            )
        )

    with pytest.raises(ValidationError, match="min_count .* cannot exceed max_count"):
        validate_ast(
            Quantifier(
                child=TextLiteral("a"), min_count=5, max_count=3, mode=QuantifierMode.GREEDY
            )
        )


def test_char_and_byte_range_bounds() -> None:
    validate_ast(CharRange("a", "z"))
    validate_ast(RegexPattern(root=ByteRange(0, 127), is_bytes=True))

    with pytest.raises(ValidationError, match="Invalid CharRange bounds"):
        validate_ast(CharRange("z", "a"))

    with pytest.raises(ValidationError, match="Invalid ByteRange bounds"):
        validate_ast(RegexPattern(root=ByteRange(200, 10), is_bytes=True))

    with pytest.raises(ValidationError, match="within 0..255"):
        validate_ast(RegexPattern(root=ByteRange(-1, 100), is_bytes=True))


def test_mode_purity() -> None:
    with pytest.raises(ValidationError, match="Text construct TextLiteral forbidden in bytes mode"):
        validate_ast(RegexPattern(root=TextLiteral("abc"), is_bytes=True))

    with pytest.raises(ValidationError, match="Byte construct ByteLiteral forbidden in string mode"):
        validate_ast(RegexPattern(root=ByteLiteral(b"abc"), is_bytes=False))

    with pytest.raises(ValidationError, match="Bytes mode forbids UNICODE"):
        validate_ast(
            RegexPattern(root=ByteLiteral(b"a"), flags=re.UNICODE, is_bytes=True)
        )

    with pytest.raises(ValidationError, match="cannot combine ASCII and UNICODE"):
        validate_ast(
            RegexPattern(root=TextLiteral("a"), flags=re.ASCII | re.UNICODE, is_bytes=False)
        )


def test_character_class_validation() -> None:
    cc = CharacterClass(
        negated=False,
        elements=(
            TextLiteral("a"),
            CharRange("0", "9"),
            PredefinedClass(PredefinedKind.WORD),
        ),
    )
    validate_ast(cc)

    cc_any = CharacterClass(
        negated=False,
        elements=(PredefinedClass(PredefinedKind.ANY),),
    )
    with pytest.raises(ValidationError, match="Predefined ANY"):
        validate_ast(cc_any)

    cc_multi = CharacterClass(
        negated=False,
        elements=(TextLiteral("abc"),),
    )
    with pytest.raises(ValidationError, match="must be 1 character"):
        validate_ast(cc_multi)


def test_lookbehind_fixed_width() -> None:
    valid_lb = Lookaround(
        child=SequenceNode(items=(TextLiteral("abc"),)),
        behind=True,
        negative=False,
    )
    validate_ast(valid_lb)

    valid_branches = Lookaround(
        child=AlternationNode(
            branches=(TextLiteral("cat"), TextLiteral("dog"))
        ),
        behind=True,
        negative=False,
    )
    validate_ast(valid_branches)

    unbounded_lb = Lookaround(
        child=Quantifier(
            child=TextLiteral("a"), min_count=1, max_count=None, mode=QuantifierMode.GREEDY
        ),
        behind=True,
        negative=False,
    )
    with pytest.raises(ValidationError, match="Lookbehind child must have fixed width"):
        validate_ast(unbounded_lb)

    varying_lb = Lookaround(
        child=AlternationNode(
            branches=(TextLiteral("a"), TextLiteral("ab"))
        ),
        behind=True,
        negative=False,
    )
    with pytest.raises(ValidationError, match="Lookbehind child must have fixed width"):
        validate_ast(varying_lb)


def test_group_identity_and_preorder() -> None:
    root = SequenceNode(
        items=(
            CaptureGroup(child=TextLiteral("a"), group_id=1, name="first"),
            CaptureGroup(child=TextLiteral("b"), group_id=2, name="second"),
        )
    )
    validate_ast(root)

    root_bad = SequenceNode(
        items=(
            CaptureGroup(child=TextLiteral("a"), group_id=2, name="first"),
            CaptureGroup(child=TextLiteral("b"), group_id=1, name="second"),
        )
    )
    with pytest.raises(ValidationError, match="does not match pre-order index"):
        validate_ast(root_bad)

    root_dup = SequenceNode(
        items=(
            CaptureGroup(child=TextLiteral("a"), group_id=1, name="dup"),
            CaptureGroup(child=TextLiteral("b"), group_id=2, name="dup"),
        )
    )
    with pytest.raises(ValidationError, match="Duplicate group name"):
        validate_ast(root_dup)

    root_bad_name = CaptureGroup(child=TextLiteral("a"), group_id=1, name="123bad")
    with pytest.raises(ValidationError, match="Invalid group name"):
        validate_ast(root_bad_name)


def test_references_and_conditionals() -> None:
    root = SequenceNode(
        items=(
            CaptureGroup(child=TextLiteral("a"), group_id=1, name="named"),
            Backreference(reference=1),
            Backreference(reference="named"),
            Conditional(condition=1, if_true=TextLiteral("x")),
            Conditional(condition="named", if_true=TextLiteral("y")),
        )
    )
    validate_ast(root)

    bad_ref_idx = SequenceNode(
        items=(
            CaptureGroup(child=TextLiteral("a"), group_id=1),
            Backreference(reference=2),
        )
    )
    with pytest.raises(ValidationError, match="Backreference to undefined group index"):
        validate_ast(bad_ref_idx)

    bad_ref_name = Backreference(reference="unknown")
    with pytest.raises(ValidationError, match="Backreference to undefined group name"):
        validate_ast(bad_ref_name)

    bad_cond = Conditional(condition="missing", if_true=TextLiteral("a"))
    with pytest.raises(ValidationError, match="Conditional check on undefined group name"):
        validate_ast(bad_cond)
