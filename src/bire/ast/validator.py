"""Semantic validator for bire ASTs."""

from __future__ import annotations

import re

from bire.ast.exceptions import ValidationError
from bire.ast.nodes import (
    AlternationNode,
    AnchorNode,
    ASTNode,
    AtomicGroup,
    Backreference,
    ByteLiteral,
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
    RegexPattern,
    SequenceNode,
    TextLiteral,
)
from bire.ast.visitor import walk

_NAME_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def compute_width(node: ASTNode) -> int | None:
    """Compute the fixed match width of an ASTNode, or None if variable or unbounded."""
    match node:
        case EmptyNode():
            return 0
        case TextLiteral(value=v):
            return len(v)
        case ByteLiteral(value=v):
            return len(v)
        case PredefinedClass():
            return 1
        case AnchorNode():
            return 0
        case CharRange() | ByteRange():
            return 1
        case CharacterClass():
            return 1
        case SequenceNode(items=items):
            total = 0
            for item in items:
                w = compute_width(item)
                if w is None:
                    return None
                total += w
            return total
        case AlternationNode(branches=branches):
            if not branches:
                return 0
            first = compute_width(branches[0])
            if first is None:
                return None
            for b in branches[1:]:
                if compute_width(b) != first:
                    return None
            return first
        case Quantifier(child=child, min_count=min_c, max_count=max_c):
            if max_c is None or min_c != max_c:
                return None
            cw = compute_width(child)
            if cw is None:
                return None
            return min_c * cw
        case CaptureGroup(child=child) | NonCapturingGroup(child=child) | AtomicGroup(child=child):
            return compute_width(child)
        case Lookaround():
            return 0
        case Conditional(if_true=if_true, if_false=if_false):
            tw = compute_width(if_true)
            fw = compute_width(if_false) if if_false is not None else 0
            if tw is not None and tw == fw:
                return tw
            return None
        case Backreference():
            return None
        case _:
            return None


def validate_ast(pattern: RegexPattern | ASTNode) -> None:
    """Validate that an AST complies with all semantic and Python regex rules.

    Raises:
        ValidationError: When semantic constraints are violated.
    """
    root: ASTNode
    is_bytes: bool
    flags: int

    if isinstance(pattern, RegexPattern):
        root = pattern.root
        is_bytes = pattern.is_bytes
        flags = pattern.flags
    else:
        root = pattern
        is_bytes = False
        flags = 0

    # 4. Mode purity: flags checks
    if is_bytes:
        if bool(flags & (re.UNICODE | re.LOCALE)):
            raise ValidationError("Bytes mode forbids UNICODE and LOCALE flags.")
    else:
        if bool(flags & re.ASCII) and bool(flags & re.UNICODE):
            raise ValidationError("String mode cannot combine ASCII and UNICODE flags.")

    expected_group_id = 1
    named_groups: dict[str, int] = {}
    defined_group_ids: set[int] = set()

    for node in walk(root):
        # 1. Repetition of zero-width anchors
        if isinstance(node, Quantifier):
            if isinstance(node.child, AnchorNode):
                raise ValidationError(f"Cannot repeat zero-width anchor: {node.child.kind}")
            # 2. Quantifier bounds
            if node.min_count < 0:
                raise ValidationError(f"min_count cannot be negative: {node.min_count}")
            if node.max_count is not None and node.min_count > node.max_count:
                raise ValidationError(
                    f"min_count ({node.min_count}) cannot exceed max_count ({node.max_count})"
                )

        # 3. Range bounds
        if isinstance(node, CharRange):
            if len(node.start) != 1 or len(node.end) != 1:
                raise ValidationError("CharRange bounds must each be exactly one character.")
            if ord(node.start) > ord(node.end):
                raise ValidationError(
                    f"Invalid CharRange bounds: '{node.start}' > '{node.end}'"
                )

        if isinstance(node, ByteRange):
            if not (0 <= node.start <= 255) or not (0 <= node.end <= 255):
                raise ValidationError(
                    f"ByteRange bounds must be within 0..255: got {node.start}..{node.end}"
                )
            if node.start > node.end:
                raise ValidationError(
                    f"Invalid ByteRange bounds: {node.start} > {node.end}"
                )

        # 4. Mode purity: node types
        if is_bytes:
            if isinstance(node, (TextLiteral, CharRange)):
                raise ValidationError(
                    f"Text construct {type(node).__name__} forbidden in bytes mode."
                )
        else:
            if isinstance(node, (ByteLiteral, ByteRange)):
                raise ValidationError(
                    f"Byte construct {type(node).__name__} forbidden in string mode."
                )

        # 5. Character class validation
        if isinstance(node, CharacterClass):
            for elem in node.elements:
                if isinstance(elem, PredefinedClass) and elem.kind == PredefinedKind.ANY:
                    raise ValidationError("Predefined ANY (.) forbidden inside CharacterClass.")
                if not isinstance(
                    elem, (TextLiteral, ByteLiteral, CharRange, ByteRange, PredefinedClass)
                ):
                    raise ValidationError(
                        f"Disallowed construct {type(elem).__name__} inside CharacterClass."
                    )
                if isinstance(elem, TextLiteral) and len(elem.value) != 1:
                    raise ValidationError(
                        f"TextLiteral inside CharacterClass must be 1 character, got: {elem.value!r}"
                    )
                if isinstance(elem, ByteLiteral) and len(elem.value) != 1:
                    raise ValidationError(
                        f"ByteLiteral inside CharacterClass must be 1 byte, got: {elem.value!r}"
                    )

        # 6. Lookbehinds: fixed width check
        if isinstance(node, Lookaround) and node.behind:
            w = compute_width(node.child)
            if w is None:
                raise ValidationError(
                    "Lookbehind child must have fixed width and no unbounded repetitions or varying branches."
                )

        # Group collection
        if isinstance(node, CaptureGroup):
            if node.group_id != expected_group_id:
                raise ValidationError(
                    f"Group ID {node.group_id} does not match pre-order index {expected_group_id}."
                )
            defined_group_ids.add(node.group_id)
            expected_group_id += 1
            if node.name is not None:
                if not _NAME_RE.match(node.name):
                    raise ValidationError(f"Invalid group name: {node.name!r}")
                if node.name in named_groups:
                    raise ValidationError(f"Duplicate group name: {node.name!r}")
                named_groups[node.name] = node.group_id

    # 7. References and conditions validation
    for node in walk(root):
        if isinstance(node, Backreference):
            ref = node.reference
            if isinstance(ref, int):
                if ref not in defined_group_ids:
                    raise ValidationError(f"Backreference to undefined group index: {ref}")
            elif isinstance(ref, str):
                if ref not in named_groups:
                    raise ValidationError(f"Backreference to undefined group name: {ref!r}")
            else:
                raise ValidationError(f"Invalid backreference type: {type(ref).__name__}")

        if isinstance(node, Conditional):
            cond = node.condition
            if isinstance(cond, int):
                if cond not in defined_group_ids:
                    raise ValidationError(f"Conditional check on undefined group index: {cond}")
            elif isinstance(cond, str):
                if cond not in named_groups:
                    raise ValidationError(f"Conditional check on undefined group name: {cond!r}")
            else:
                raise ValidationError(f"Invalid conditional type: {type(cond).__name__}")
