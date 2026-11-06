"""Human DSL Renderer for bire ASTs."""

from __future__ import annotations

import json

from bire.ast.exceptions import RenderError
from bire.ast.flags import flags_to_names
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

_PREDEFINED_NAMES: dict[PredefinedKind, str] = {
    PredefinedKind.ANY: "ANY CHARACTER",
    PredefinedKind.DIGIT: "DIGIT",
    PredefinedKind.NOT_DIGIT: "NOT DIGIT",
    PredefinedKind.WORD: "WORD CHARACTER",
    PredefinedKind.NOT_WORD: "NOT WORD CHARACTER",
    PredefinedKind.WHITESPACE: "WHITESPACE",
    PredefinedKind.NOT_WHITESPACE: "NOT WHITESPACE",
}

_ANCHOR_NAMES: dict[AnchorKind, str] = {
    AnchorKind.STRING_START: "START OF STRING",
    AnchorKind.STRING_END: "END OF STRING",
    AnchorKind.ABSOLUTE_END: "ABSOLUTE END",
    AnchorKind.LINE_START: "START OF LINE",
    AnchorKind.LINE_END: "END OF LINE",
    AnchorKind.WORD_BOUNDARY: "WORD BOUNDARY",
    AnchorKind.NOT_WORD_BOUNDARY: "NOT WORD BOUNDARY",
}


def _quote_str(val: str) -> str:
    """Format a string as a clean double-quoted literal with standard escapes."""
    return json.dumps(val, ensure_ascii=False)


def _quote_bytes(val: bytes) -> str:
    """Format bytes as a clean double-quoted literal with hex escapes for non-ASCII."""
    chars: list[str] = []
    for b in val:
        if b == ord('"'):
            chars.append(r'\"')
        elif b == ord("\\"):
            chars.append(r"\\")
        elif b == ord("\n"):
            chars.append(r"\n")
        elif b == ord("\r"):
            chars.append(r"\r")
        elif b == ord("\t"):
            chars.append(r"\t")
        elif 32 <= b < 127:
            chars.append(chr(b))
        else:
            chars.append(f"\\x{b:02x}")
    return '"' + "".join(chars) + '"'


def _format_quant_spec(min_count: int, max_count: int | None) -> str:
    if min_count == 0 and max_count is None:
        return "ZERO OR MORE TIMES"
    if min_count == 1 and max_count is None:
        return "ONE OR MORE TIMES"
    if min_count == 0 and max_count == 1:
        return "AT MOST 1 TIMES"
    if max_count is not None and min_count == max_count:
        return f"EXACTLY {min_count} TIMES"
    if max_count is None:
        return f"AT LEAST {min_count} TIMES"
    return f"BETWEEN {min_count} AND {max_count} TIMES"


def _format_quant_mode(mode: QuantifierMode) -> str:
    if mode == QuantifierMode.LAZY:
        return " LAZILY"
    if mode == QuantifierMode.POSSESSIVE:
        return " POSSESSIVELY"
    return ""


class _HumanDSLRenderer:
    def __init__(self, is_bytes: bool = False) -> None:
        self.is_bytes = is_bytes

    def render_block(self, node: ASTNode, indent_level: int = 0) -> list[str]:
        """Render an AST node into indented lines of bire DSL code."""
        prefix = "    " * indent_level

        match node:
            case EmptyNode():
                return [f"{prefix}EMPTY"]

            case TextLiteral(value=v):
                return [f"{prefix}LITERAL {_quote_str(v)}"]

            case ByteLiteral(value=v):
                return [f"{prefix}BYTES {_quote_bytes(v)}"]

            case PredefinedClass(kind=kind):
                return [f"{prefix}{_PREDEFINED_NAMES[kind]}"]

            case AnchorNode(kind=kind):
                return [f"{prefix}{_ANCHOR_NAMES[kind]}"]

            case Backreference(reference=ref):
                ref_repr = _quote_str(ref) if isinstance(ref, str) else str(ref)
                return [f"{prefix}MATCH CAPTURE {ref_repr}"]

            case SequenceNode(items=items):
                lines: list[str] = []
                for it in items:
                    lines.extend(self.render_block(it, indent_level))
                return lines

            case AlternationNode(branches=branches):
                lines = []
                for i, b in enumerate(branches):
                    keyword = "EITHER:" if i == 0 else "OR:"
                    lines.append(f"{prefix}{keyword}")
                    lines.extend(self.render_block(b, indent_level + 1))
                return lines

            case CharacterClass(negated=negated, elements=elements):
                header = f"{prefix}NONE OF:" if negated else f"{prefix}ONE OF:"
                elem_lines: list[str] = [header]
                sub_prefix = "    " * (indent_level + 1)
                for elem in elements:
                    if isinstance(elem, TextLiteral):
                        elem_lines.append(f"{sub_prefix}CHAR {_quote_str(elem.value)}")
                    elif isinstance(elem, ByteLiteral):
                        if len(elem.value) == 1:
                            elem_lines.append(f"{sub_prefix}BYTE 0x{elem.value[0]:02x}")
                        else:
                            elem_lines.append(f"{sub_prefix}BYTES {_quote_bytes(elem.value)}")
                    elif isinstance(elem, CharRange):
                        elem_lines.append(
                            f"{sub_prefix}RANGE {_quote_str(elem.start)} TO {_quote_str(elem.end)}"
                        )
                    elif isinstance(elem, ByteRange):
                        elem_lines.append(
                            f"{sub_prefix}BYTE_RANGE 0x{elem.start:02x} TO 0x{elem.end:02x}"
                        )
                    elif isinstance(elem, PredefinedClass):
                        elem_lines.append(f"{sub_prefix}{_PREDEFINED_NAMES[elem.kind]}")
                    else:
                        raise RenderError(f"Unsupported CharacterClass element: {elem}")
                return elem_lines

            case Quantifier(child=child, min_count=min_c, max_count=max_c, mode=mode):
                spec_str = _format_quant_spec(min_c, max_c)
                mode_str = _format_quant_mode(mode)
                header = f"{prefix}REPEAT {spec_str}{mode_str}:"
                lines = [header]
                lines.extend(self.render_block(child, indent_level + 1))
                return lines

            case CaptureGroup(child=child, name=name):
                header = f"{prefix}CAPTURE {_quote_str(name)}:" if name is not None else f"{prefix}CAPTURE:"
                lines = [header]
                lines.extend(self.render_block(child, indent_level + 1))
                return lines

            case NonCapturingGroup(child=child, flags_add=fa, flags_remove=fr):
                if fa or fr:
                    flags_list = flags_to_names(fa)
                    for f in flags_to_names(fr):
                        flags_list.append(f"-{f}")
                    header = f"{prefix}WITH FLAGS [{', '.join(flags_list)}]:"
                else:
                    header = f"{prefix}GROUP:"
                lines = [header]
                lines.extend(self.render_block(child, indent_level + 1))
                return lines

            case AtomicGroup(child=child):
                lines = [f"{prefix}ATOMIC GROUP:"]
                lines.extend(self.render_block(child, indent_level + 1))
                return lines

            case Lookaround(child=child, behind=behind, negative=negative):
                if behind and negative:
                    header = f"{prefix}NEGATIVE LOOKBEHIND:"
                elif behind and not negative:
                    header = f"{prefix}LOOKBEHIND:"
                elif not behind and negative:
                    header = f"{prefix}NEGATIVE LOOKAHEAD:"
                else:
                    header = f"{prefix}LOOKAHEAD:"
                lines = [header]
                lines.extend(self.render_block(child, indent_level + 1))
                return lines

            case Conditional(condition=cond, if_true=if_t, if_false=if_f):
                ref_repr = _quote_str(cond) if isinstance(cond, str) else str(cond)
                lines = [f"{prefix}IF CAPTURE {ref_repr}:"]
                lines.extend(self.render_block(if_t, indent_level + 1))
                if if_f is not None:
                    lines.append(f"{prefix}ELSE:")
                    lines.extend(self.render_block(if_f, indent_level + 1))
                return lines

            case _:
                raise RenderError(f"Unsupported node type in Human DSL renderer: {type(node).__name__}")


def render_human(pattern: RegexPattern | ASTNode) -> str:
    """Render a bire AST node or RegexPattern into clean, 4-space indented Human DSL code."""
    root: ASTNode
    flags = 0
    is_bytes = False

    if isinstance(pattern, RegexPattern):
        root = pattern.root
        flags = pattern.flags
        is_bytes = pattern.is_bytes
    else:
        root = pattern

    headers: list[str] = []
    if is_bytes:
        headers.append("MODE: BYTES")
    if flags != 0:
        names = flags_to_names(flags)
        if names:
            headers.append(f"FLAGS: [{', '.join(names)}]")

    renderer = _HumanDSLRenderer(is_bytes=is_bytes)
    body_lines = renderer.render_block(root, indent_level=0)

    all_lines: list[str] = []
    if headers:
        all_lines.extend(headers)
        all_lines.append("")  # blank line separating header from statements

    all_lines.extend(body_lines)
    return "\n".join(all_lines) + "\n"
