"""Python regex renderer with strict operator precedence and escaping."""

from __future__ import annotations

from bire.ast.exceptions import RenderError
from bire.ast.flags import SHORT_FLAG_MAP
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

# Operator Precedence Hierarchy
# Level 3: Atoms (Literals of len 1, classes, parenthesized groups)
# Level 2: Quantifiers (*, +, ?, {m,n})
# Level 1: Sequences (concatenations, multi-char literals)
# Level 0: Alternation (branches |)
PREC_ALTERNATION = 0
PREC_SEQUENCE = 1
PREC_QUANTIFIER = 2
PREC_ATOM = 3

_SPECIAL_CHARS_STR = set(r".^$*+?()[]{}\|")
_SPECIAL_CHARS_BYTES = set(b".^$*+?()[]{}\\|")

_CLASS_SPECIAL_STR = set(r"\[]-^&~|")
_CLASS_SPECIAL_BYTES = set(b"\\[]-^&~|")


def _get_precedence(node: ASTNode) -> int:
    """Return the precedence level of an ASTNode."""
    match node:
        case EmptyNode():
            return PREC_ATOM
        case TextLiteral(value=v):
            return PREC_ATOM if len(v) <= 1 else PREC_SEQUENCE
        case ByteLiteral(value=v):
            return PREC_ATOM if len(v) <= 1 else PREC_SEQUENCE
        case PredefinedClass() | AnchorNode() | CharRange() | ByteRange() | CharacterClass():
            return PREC_ATOM
        case CaptureGroup() | NonCapturingGroup() | AtomicGroup() | Lookaround() | Conditional():
            return PREC_ATOM
        case Backreference():
            return PREC_ATOM
        case Quantifier():
            return PREC_QUANTIFIER
        case SequenceNode(items=items):
            if len(items) == 0:
                return PREC_ATOM
            if len(items) == 1:
                return _get_precedence(items[0])
            return PREC_SEQUENCE
        case AlternationNode(branches=branches):
            if len(branches) == 0:
                return PREC_ATOM
            if len(branches) == 1:
                return _get_precedence(branches[0])
            return PREC_ALTERNATION
        case _:
            return PREC_ATOM


def _starts_with_digit(node: ASTNode) -> bool:
    """Check if the rendered output of a node starts with an unescaped literal digit."""
    match node:
        case TextLiteral(value=v):
            return len(v) > 0 and v[0].isdigit()
        case ByteLiteral(value=v):
            return len(v) > 0 and v[0:1] in b"0123456789"
        case SequenceNode(items=items):
            return len(items) > 0 and _starts_with_digit(items[0])
        case _:
            return False


def _escape_char_str(ch: str, in_class: bool = False) -> str:
    """Escape a single character for string regex patterns."""
    if ch == "\\":
        return r"\\"
    if ch == "\n":
        return r"\n"
    if ch == "\r":
        return r"\r"
    if ch == "\t":
        return r"\t"
    if ch == "\a":
        return r"\a"
    if ch == "\b":
        return r"\b"
    if ch == "\f":
        return r"\f"
    if ch == "\v":
        return r"\v"

    code = ord(ch)
    if code < 32 or code == 127:
        return f"\\x{code:02x}"

    if in_class:
        if ch in _CLASS_SPECIAL_STR:
            return f"\\{ch}"
        return ch

    if ch in _SPECIAL_CHARS_STR:
        return f"\\{ch}"
    return ch


def _escape_char_bytes(byte_val: int, in_class: bool = False) -> bytes:
    """Escape a single byte for bytes regex patterns."""
    if byte_val == ord(b"\\"):
        return b"\\\\"
    if byte_val == ord(b"\n"):
        return b"\\n"
    if byte_val == ord(b"\r"):
        return b"\\r"
    if byte_val == ord(b"\t"):
        return b"\\t"
    if byte_val == ord(b"\a"):
        return b"\\a"
    if byte_val == ord(b"\b"):
        return b"\\b"
    if byte_val == ord(b"\f"):
        return b"\\f"
    if byte_val == ord(b"\v"):
        return b"\\v"

    if byte_val < 32 or byte_val >= 127:
        return f"\\x{byte_val:02x}".encode("ascii")

    ch = bytes([byte_val])
    if in_class:
        if byte_val in _CLASS_SPECIAL_BYTES:
            return b"\\" + ch
        return ch

    if byte_val in _SPECIAL_CHARS_BYTES:
        return b"\\" + ch
    return ch


def _render_predefined_str(kind: PredefinedKind) -> str:
    match kind:
        case PredefinedKind.DIGIT:
            return r"\d"
        case PredefinedKind.NOT_DIGIT:
            return r"\D"
        case PredefinedKind.WORD:
            return r"\w"
        case PredefinedKind.NOT_WORD:
            return r"\W"
        case PredefinedKind.WHITESPACE:
            return r"\s"
        case PredefinedKind.NOT_WHITESPACE:
            return r"\S"
        case PredefinedKind.ANY:
            return "."


def _render_predefined_bytes(kind: PredefinedKind) -> bytes:
    match kind:
        case PredefinedKind.DIGIT:
            return rb"\d"
        case PredefinedKind.NOT_DIGIT:
            return rb"\D"
        case PredefinedKind.WORD:
            return rb"\w"
        case PredefinedKind.NOT_WORD:
            return rb"\W"
        case PredefinedKind.WHITESPACE:
            return rb"\s"
        case PredefinedKind.NOT_WHITESPACE:
            return rb"\S"
        case PredefinedKind.ANY:
            return b"."


def _render_anchor_str(kind: AnchorKind) -> str:
    match kind:
        case AnchorKind.STRING_START:
            return r"\A"
        case AnchorKind.STRING_END:
            return r"\Z"
        case AnchorKind.LINE_START:
            return "^"
        case AnchorKind.LINE_END:
            return "$"
        case AnchorKind.WORD_BOUNDARY:
            return r"\b"
        case AnchorKind.NOT_WORD_BOUNDARY:
            return r"\B"
        case AnchorKind.ABSOLUTE_END:
            return r"\z"


def _render_anchor_bytes(kind: AnchorKind) -> bytes:
    match kind:
        case AnchorKind.STRING_START:
            return rb"\A"
        case AnchorKind.STRING_END:
            return rb"\Z"
        case AnchorKind.LINE_START:
            return b"^"
        case AnchorKind.LINE_END:
            return b"$"
        case AnchorKind.WORD_BOUNDARY:
            return rb"\b"
        case AnchorKind.NOT_WORD_BOUNDARY:
            return rb"\B"
        case AnchorKind.ABSOLUTE_END:
            return rb"\z"


def _flags_to_letters(flags: int) -> str:
    """Convert an integer flag bitmask into short flag letters."""
    chars: list[str] = []
    for letter, bit in SHORT_FLAG_MAP.items():
        if flags & bit:
            chars.append(letter)
    return "".join(chars)


class _StringRenderer:
    """Renders BiRe AST nodes into Python regex str patterns."""

    def render(self, node: ASTNode, parent_prec: int = PREC_ALTERNATION) -> str:
        match node:
            case EmptyNode():
                return ""

            case TextLiteral(value=v):
                escaped = "".join(_escape_char_str(ch, in_class=False) for ch in v)
                # If len > 1 and parent requires higher precedence (e.g. Quantifier), wrap
                if len(v) > 1 and parent_prec >= PREC_QUANTIFIER:
                    return f"(?:{escaped})"
                return escaped

            case PredefinedClass(kind=kind):
                return _render_predefined_str(kind)

            case AnchorNode(kind=kind):
                return _render_anchor_str(kind)

            case CharacterClass(negated=negated, elements=elements):
                rendered_elems: list[str] = []
                for elem in elements:
                    if isinstance(elem, TextLiteral):
                        for ch in elem.value:
                            rendered_elems.append(_escape_char_str(ch, in_class=True))
                    elif isinstance(elem, CharRange):
                        s = _escape_char_str(elem.start, in_class=True)
                        e = _escape_char_str(elem.end, in_class=True)
                        rendered_elems.append(f"{s}-{e}")
                    elif isinstance(elem, PredefinedClass):
                        rendered_elems.append(_render_predefined_str(elem.kind))
                    else:
                        raise RenderError(f"Unexpected element in string CharacterClass: {elem}")
                prefix = "^" if negated else ""
                return f"[{prefix}{''.join(rendered_elems)}]"

            case Quantifier(child=child, min_count=min_c, max_count=max_c, mode=mode):
                child_prec = _get_precedence(child)
                # Precedence rule: if child precedence <= PREC_QUANTIFIER, must wrap in (?:...)
                # This guarantees (?:a*)+ and prevents collapsing into possessive quantifiers a*+
                if child_prec <= PREC_QUANTIFIER:
                    rendered_child = f"(?:{self.render(child, PREC_ALTERNATION)})"
                else:
                    rendered_child = self.render(child, PREC_QUANTIFIER)

                if min_c == 0 and max_c is None:
                    q_op = "*"
                elif min_c == 1 and max_c is None:
                    q_op = "+"
                elif min_c == 0 and max_c == 1:
                    q_op = "?"
                elif max_c is not None and min_c == max_c:
                    q_op = f"{{{min_c}}}"
                elif max_c is None:
                    q_op = f"{{{min_c},}}"
                else:
                    q_op = f"{{{min_c},{max_c}}}"

                if mode == QuantifierMode.GREEDY:
                    m_suffix = ""
                elif mode == QuantifierMode.LAZY:
                    m_suffix = "?"
                else:
                    m_suffix = "+"

                return f"{rendered_child}{q_op}{m_suffix}"

            case SequenceNode(items=items):
                rendered_parts: list[str] = []
                n = len(items)
                for i, item in enumerate(items):
                    # Precedence rule: wrap AlternationNode branches inside Sequences
                    item_prec = _get_precedence(item)
                    if item_prec < PREC_SEQUENCE:
                        part = f"(?:{self.render(item, PREC_ALTERNATION)})"
                    elif isinstance(item, Backreference) and isinstance(item.reference, int):
                        # Collision protection: if backreference is followed by a literal digit, wrap in (?:...)
                        if i + 1 < n and _starts_with_digit(items[i + 1]):
                            part = f"(?:\\{item.reference})"
                        else:
                            part = f"\\{item.reference}"
                    else:
                        part = self.render(item, PREC_SEQUENCE)
                    rendered_parts.append(part)

                joined = "".join(rendered_parts)
                if parent_prec >= PREC_QUANTIFIER and len(items) > 1:
                    return f"(?:{joined})"
                return joined

            case AlternationNode(branches=branches):
                rendered_branches: list[str] = [
                    self.render(b, PREC_ALTERNATION) for b in branches
                ]
                joined = "|".join(rendered_branches)
                if parent_prec > PREC_ALTERNATION:
                    return f"(?:{joined})"
                return joined

            case CaptureGroup(child=child, name=name):
                content = self.render(child, PREC_ALTERNATION)
                if name is not None:
                    return f"(?P<{name}>{content})"
                return f"({content})"

            case NonCapturingGroup(child=child, flags_add=flags_add, flags_remove=flags_remove):
                content = self.render(child, PREC_ALTERNATION)
                if flags_add or flags_remove:
                    add_str = _flags_to_letters(flags_add)
                    rem_str = f"-{_flags_to_letters(flags_remove)}" if flags_remove else ""
                    return f"(?{add_str}{rem_str}:{content})"
                return f"(?:{content})"

            case AtomicGroup(child=child):
                content = self.render(child, PREC_ALTERNATION)
                return f"(?>{content})"

            case Lookaround(child=child, behind=behind, negative=negative):
                content = self.render(child, PREC_ALTERNATION)
                if behind and negative:
                    return f"(?<!{content})"
                if behind and not negative:
                    return f"(?<={content})"
                if not behind and negative:
                    return f"(?!{content})"
                return f"(?={content})"

            case Backreference(reference=ref):
                if isinstance(ref, int):
                    return f"\\{ref}"
                return f"(?P={ref})"

            case Conditional(condition=cond, if_true=if_true, if_false=if_false):
                # Conditionals must wrap alternation branches in true/false paths
                if isinstance(if_true, AlternationNode) and len(if_true.branches) > 1:
                    t_rendered = f"(?:{self.render(if_true, PREC_ALTERNATION)})"
                else:
                    t_rendered = self.render(if_true, PREC_ALTERNATION)

                if if_false is not None:
                    if isinstance(if_false, AlternationNode) and len(if_false.branches) > 1:
                        f_rendered = f"|(?:{self.render(if_false, PREC_ALTERNATION)})"
                    else:
                        f_rendered = f"|{self.render(if_false, PREC_ALTERNATION)}"
                else:
                    f_rendered = ""

                return f"(?({cond}){t_rendered}{f_rendered})"

            case _:
                raise RenderError(f"Unsupported AST node in string renderer: {type(node).__name__}")


class _BytesRenderer:
    """Renders BiRe AST nodes into Python regex bytes patterns."""

    def render(self, node: ASTNode, parent_prec: int = PREC_ALTERNATION) -> bytes:
        match node:
            case EmptyNode():
                return b""

            case ByteLiteral(value=v):
                escaped = b"".join(_escape_char_bytes(b, in_class=False) for b in v)
                if len(v) > 1 and parent_prec >= PREC_QUANTIFIER:
                    return b"(?:" + escaped + b")"
                return escaped

            case PredefinedClass(kind=kind):
                return _render_predefined_bytes(kind)

            case AnchorNode(kind=kind):
                return _render_anchor_bytes(kind)

            case CharacterClass(negated=negated, elements=elements):
                rendered_elems: list[bytes] = []
                for elem in elements:
                    if isinstance(elem, ByteLiteral):
                        for b in elem.value:
                            rendered_elems.append(_escape_char_bytes(b, in_class=True))
                    elif isinstance(elem, ByteRange):
                        s = _escape_char_bytes(elem.start, in_class=True)
                        e = _escape_char_bytes(elem.end, in_class=True)
                        rendered_elems.append(s + b"-" + e)
                    elif isinstance(elem, PredefinedClass):
                        rendered_elems.append(_render_predefined_bytes(elem.kind))
                    else:
                        raise RenderError(f"Unexpected element in bytes CharacterClass: {elem}")
                prefix = b"^" if negated else b""
                return b"[" + prefix + b"".join(rendered_elems) + b"]"

            case Quantifier(child=child, min_count=min_c, max_count=max_c, mode=mode):
                child_prec = _get_precedence(child)
                if child_prec <= PREC_QUANTIFIER:
                    rendered_child = b"(?:" + self.render(child, PREC_ALTERNATION) + b")"
                else:
                    rendered_child = self.render(child, PREC_QUANTIFIER)

                if min_c == 0 and max_c is None:
                    q_op = b"*"
                elif min_c == 1 and max_c is None:
                    q_op = b"+"
                elif min_c == 0 and max_c == 1:
                    q_op = b"?"
                elif max_c is not None and min_c == max_c:
                    q_op = f"{{{min_c}}}".encode("ascii")
                elif max_c is None:
                    q_op = f"{{{min_c},}}".encode("ascii")
                else:
                    q_op = f"{{{min_c},{max_c}}}".encode("ascii")

                if mode == QuantifierMode.GREEDY:
                    m_suffix = b""
                elif mode == QuantifierMode.LAZY:
                    m_suffix = b"?"
                else:
                    m_suffix = b"+"

                return rendered_child + q_op + m_suffix

            case SequenceNode(items=items):
                rendered_parts: list[bytes] = []
                n = len(items)
                for i, item in enumerate(items):
                    item_prec = _get_precedence(item)
                    if item_prec < PREC_SEQUENCE:
                        part = b"(?:" + self.render(item, PREC_ALTERNATION) + b")"
                    elif isinstance(item, Backreference) and isinstance(item.reference, int):
                        if i + 1 < n and _starts_with_digit(items[i + 1]):
                            part = f"(?:\\{item.reference})".encode("ascii")
                        else:
                            part = f"\\{item.reference}".encode("ascii")
                    else:
                        part = self.render(item, PREC_SEQUENCE)
                    rendered_parts.append(part)

                joined = b"".join(rendered_parts)
                if parent_prec >= PREC_QUANTIFIER and len(items) > 1:
                    return b"(?:" + joined + b")"
                return joined

            case AlternationNode(branches=branches):
                rendered_branches: list[bytes] = [
                    self.render(b, PREC_ALTERNATION) for b in branches
                ]
                joined = b"|".join(rendered_branches)
                if parent_prec > PREC_ALTERNATION:
                    return b"(?:" + joined + b")"
                return joined

            case CaptureGroup(child=child, name=name):
                content = self.render(child, PREC_ALTERNATION)
                if name is not None:
                    return b"(?P<" + name.encode("ascii") + b">" + content + b")"
                return b"(" + content + b")"

            case NonCapturingGroup(child=child, flags_add=flags_add, flags_remove=flags_remove):
                content = self.render(child, PREC_ALTERNATION)
                if flags_add or flags_remove:
                    add_str = _flags_to_letters(flags_add)
                    rem_str = f"-{_flags_to_letters(flags_remove)}" if flags_remove else ""
                    tag = f"(?{add_str}{rem_str}:".encode("ascii")
                    return tag + content + b")"
                return b"(?:" + content + b")"

            case AtomicGroup(child=child):
                content = self.render(child, PREC_ALTERNATION)
                return b"(?>" + content + b")"

            case Lookaround(child=child, behind=behind, negative=negative):
                content = self.render(child, PREC_ALTERNATION)
                if behind and negative:
                    return b"(?<!" + content + b")"
                if behind and not negative:
                    return b"(?<=" + content + b")"
                if not behind and negative:
                    return b"(?!" + content + b")"
                return b"(?=" + content + b")"

            case Backreference(reference=ref):
                if isinstance(ref, int):
                    return f"\\{ref}".encode("ascii")
                return f"(?P={ref})".encode("ascii")

            case Conditional(condition=cond, if_true=if_true, if_false=if_false):
                if isinstance(if_true, AlternationNode) and len(if_true.branches) > 1:
                    t_rendered = b"(?:" + self.render(if_true, PREC_ALTERNATION) + b")"
                else:
                    t_rendered = self.render(if_true, PREC_ALTERNATION)

                if if_false is not None:
                    if isinstance(if_false, AlternationNode) and len(if_false.branches) > 1:
                        f_rendered = b"|(?:" + self.render(if_false, PREC_ALTERNATION) + b")"
                    else:
                        f_rendered = b"|" + self.render(if_false, PREC_ALTERNATION)
                else:
                    f_rendered = b""

                cond_bytes = str(cond).encode("ascii")
                return b"(?(" + cond_bytes + b")" + t_rendered + f_rendered + b")"

            case _:
                raise RenderError(f"Unsupported AST node in bytes renderer: {type(node).__name__}")


def render_python(pattern: RegexPattern | ASTNode, is_bytes: bool = False) -> str | bytes:
    """Render a BiRe AST node or RegexPattern into a valid Python regex string or bytes.

    Raises:
        RenderError: When an unsupported node is encountered.
    """
    root: ASTNode
    use_bytes = is_bytes

    if isinstance(pattern, RegexPattern):
        root = pattern.root
        use_bytes = pattern.is_bytes
    else:
        root = pattern

    if use_bytes:
        return _BytesRenderer().render(root)
    return _StringRenderer().render(root)
