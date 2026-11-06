"""CPython regex parser adapter for BiRe."""

from __future__ import annotations

import re
import re._constants as rc  # type: ignore[import-not-found]
import re._parser as rp  # type: ignore[import-not-found]
from typing import Any

from bire.ast.exceptions import ParseError
from bire.ast.nodes import (
    AlternationNode,
    AnchorKind,
    AnchorNode,
    ASTNode,
    AtomicGroup,
    Backreference,
    ByteLiteral,
    ByteRange,
    CaptureGroup,
    CharacterClass,
    CharClassElement,
    CharRange,
    Conditional,
    EmptyNode,
    Lookaround,
    NonCapturingGroup,
    PredefinedClass,
    PredefinedKind,
    Quantifier,
    QuantifierMode,
    RegexPattern,
    SequenceNode,
    TextLiteral,
)

_CATEGORY_MAP: dict[Any, PredefinedKind] = {
    rc.CATEGORY_DIGIT: PredefinedKind.DIGIT,
    rc.CATEGORY_NOT_DIGIT: PredefinedKind.NOT_DIGIT,
    rc.CATEGORY_SPACE: PredefinedKind.WHITESPACE,
    rc.CATEGORY_NOT_SPACE: PredefinedKind.NOT_WHITESPACE,
    rc.CATEGORY_WORD: PredefinedKind.WORD,
    rc.CATEGORY_NOT_WORD: PredefinedKind.NOT_WORD,
    rc.CATEGORY_UNI_DIGIT: PredefinedKind.DIGIT,
    rc.CATEGORY_UNI_NOT_DIGIT: PredefinedKind.NOT_DIGIT,
    rc.CATEGORY_UNI_SPACE: PredefinedKind.WHITESPACE,
    rc.CATEGORY_UNI_NOT_SPACE: PredefinedKind.NOT_WHITESPACE,
    rc.CATEGORY_UNI_WORD: PredefinedKind.WORD,
    rc.CATEGORY_UNI_NOT_WORD: PredefinedKind.NOT_WORD,
    rc.CATEGORY_LOC_WORD: PredefinedKind.WORD,
    rc.CATEGORY_LOC_NOT_WORD: PredefinedKind.NOT_WORD,
}


def _convert_item(
    op: Any,
    av: Any,
    is_bytes: bool,
    id_to_name: dict[int, str],
) -> ASTNode:
    """Convert a single CPython AST opcode tuple to a BiRe ASTNode."""
    if op == rc.LITERAL:
        return ByteLiteral(bytes([av])) if is_bytes else TextLiteral(chr(av))

    if op == rc.NOT_LITERAL:
        elem = ByteLiteral(bytes([av])) if is_bytes else TextLiteral(chr(av))
        return CharacterClass(negated=True, elements=(elem,))

    if op == rc.IN:
        elements_list = list(av)
        negated = False
        if elements_list and elements_list[0][0] == rc.NEGATE:
            negated = True
            elements_list = elements_list[1:]

        char_elems: list[CharClassElement] = []
        for sub_op, sub_av in elements_list:
            if sub_op == rc.LITERAL:
                char_elems.append(
                    ByteLiteral(bytes([sub_av])) if is_bytes else TextLiteral(chr(sub_av))
                )
            elif sub_op == rc.RANGE:
                low, high = sub_av
                if is_bytes:
                    char_elems.append(ByteRange(low, high))
                else:
                    char_elems.append(CharRange(chr(low), chr(high)))
            elif sub_op == rc.CATEGORY:
                if sub_av in _CATEGORY_MAP:
                    char_elems.append(PredefinedClass(_CATEGORY_MAP[sub_av]))
                else:
                    raise ParseError(f"Unsupported category in IN: {sub_av}")
            else:
                raise ParseError(f"Unsupported opcode inside IN: {sub_op}")

        if (
            not negated
            and len(char_elems) == 1
            and isinstance(char_elems[0], PredefinedClass)
        ):
            return char_elems[0]

        return CharacterClass(negated=negated, elements=tuple(char_elems))

    if op == rc.ANY:
        return PredefinedClass(PredefinedKind.ANY)

    if op == rc.AT:
        if av == rc.AT_BEGINNING:
            return AnchorNode(AnchorKind.LINE_START)
        if av == rc.AT_END:
            return AnchorNode(AnchorKind.LINE_END)
        if av == rc.AT_BEGINNING_STRING:
            return AnchorNode(AnchorKind.STRING_START)
        if av == rc.AT_END_STRING:
            return AnchorNode(AnchorKind.STRING_END)
        if av == rc.AT_BOUNDARY:
            return AnchorNode(AnchorKind.WORD_BOUNDARY)
        if av == rc.AT_NON_BOUNDARY:
            return AnchorNode(AnchorKind.NOT_WORD_BOUNDARY)
        raise ParseError(f"Unsupported AT anchor code: {av}")

    if op == rc.SUBPATTERN:
        group, flags_add, flags_remove, sub_data = av
        child = _convert_subpattern(sub_data, is_bytes, id_to_name)
        if group is not None:
            name = id_to_name.get(group)
            return CaptureGroup(child=child, group_id=group, name=name)
        return NonCapturingGroup(
            child=child, flags_add=flags_add, flags_remove=flags_remove
        )

    if op == rc.ATOMIC_GROUP:
        child = _convert_subpattern(av, is_bytes, id_to_name)
        return AtomicGroup(child=child)

    if op == rc.BRANCH:
        _, branch_list = av
        branches = tuple(
            _convert_subpattern(b, is_bytes, id_to_name) for b in branch_list
        )
        return AlternationNode(branches=branches)

    if op in (rc.MAX_REPEAT, rc.MIN_REPEAT, rc.POSSESSIVE_REPEAT):
        min_c, max_c, sub_data = av
        child = _convert_subpattern(sub_data, is_bytes, id_to_name)
        max_count = None if max_c == rc.MAXREPEAT else max_c
        if op == rc.MAX_REPEAT:
            mode = QuantifierMode.GREEDY
        elif op == rc.MIN_REPEAT:
            mode = QuantifierMode.LAZY
        else:
            mode = QuantifierMode.POSSESSIVE
        return Quantifier(child=child, min_count=min_c, max_count=max_count, mode=mode)

    if op == rc.ASSERT:
        dir_c, sub_data = av
        child = _convert_subpattern(sub_data, is_bytes, id_to_name)
        return Lookaround(child=child, behind=(dir_c == -1), negative=False)

    if op == rc.ASSERT_NOT:
        dir_c, sub_data = av
        child = _convert_subpattern(sub_data, is_bytes, id_to_name)
        return Lookaround(child=child, behind=(dir_c == -1), negative=True)

    if op == rc.GROUPREF:
        ref = id_to_name.get(av, av)
        return Backreference(reference=ref)

    if op == rc.GROUPREF_EXISTS:
        group_ref, if_true_data, if_false_data = av
        cond_ref = id_to_name.get(group_ref, group_ref)
        if_true = _convert_subpattern(if_true_data, is_bytes, id_to_name)
        if_false = (
            _convert_subpattern(if_false_data, is_bytes, id_to_name)
            if if_false_data is not None
            else None
        )
        return Conditional(condition=cond_ref, if_true=if_true, if_false=if_false)

    raise ParseError(f"Unsupported CPython opcode: {op}")


def _convert_subpattern(
    items: list[Any],
    is_bytes: bool,
    id_to_name: dict[int, str],
) -> ASTNode:
    """Convert a list of CPython opcodes to a single ASTNode, coalescing literals."""
    if not items:
        return EmptyNode()

    converted: list[ASTNode] = []
    idx = 0
    n = len(items)

    while idx < n:
        op, av = items[idx]
        if op == rc.LITERAL:
            # Coalesce contiguous literals
            literal_chars: list[str] = []
            literal_bytes: list[int] = []
            while idx < n and items[idx][0] == rc.LITERAL:
                code = items[idx][1]
                if is_bytes:
                    literal_bytes.append(code)
                else:
                    literal_chars.append(chr(code))
                idx += 1
            if is_bytes:
                converted.append(ByteLiteral(bytes(literal_bytes)))
            else:
                converted.append(TextLiteral("".join(literal_chars)))
        else:
            converted.append(_convert_item(op, av, is_bytes, id_to_name))
            idx += 1

    if len(converted) == 1:
        return converted[0]
    return SequenceNode(items=tuple(converted))


def parse_python_regex(pattern: str | bytes, flags: int = 0) -> RegexPattern:
    """Parse a Python regex string or bytes into a BiRe AST.

    Raises:
        ParseError: When pattern syntax is invalid.
    """
    is_bytes = isinstance(pattern, (bytes, bytearray))

    try:
        parsed = rp.parse(pattern, flags)
    except Exception as exc:
        raise ParseError(f"Failed to parse regex pattern: {exc}") from exc

    id_to_name: dict[int, str] = {
        group_id: name for name, group_id in parsed.state.groupdict.items()
    }

    effective_flags = parsed.state.flags
    if is_bytes:
        flags_to_store = effective_flags
    else:
        flags_to_store = effective_flags & ~re.UNICODE

    root = _convert_subpattern(parsed.data, is_bytes, id_to_name)
    return RegexPattern(root=root, flags=flags_to_store, is_bytes=is_bytes)
