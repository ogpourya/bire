"""Parser for bire Human DSL into AST nodes using Lark."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from lark import Lark, Token, Transformer

from bire.ast.exceptions import ParseError
from bire.ast.flags import names_to_flags
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
from bire.ast.validator import validate_ast
from bire.parsers.indenter import bireIndenter

_GRAMMAR_PATH = Path(__file__).parent / "grammar.lark"
with open(_GRAMMAR_PATH, encoding="utf-8") as _f:
    _GRAMMAR_TEXT = _f.read()

_PARSER = Lark(
    _GRAMMAR_TEXT,
    parser="lalr",
    postlex=bireIndenter(),
)


def _parse_str(raw: str) -> str:
    res: str = ast.literal_eval(raw)
    return res


def _parse_bytes(raw: str) -> bytes:
    res: bytes = ast.literal_eval("b" + raw)
    return res


def _assign_group_ids(root: ASTNode) -> ASTNode:
    """Assign deterministic 1-based group IDs to CaptureGroups in pre-order traversal."""
    current_id = 1

    def _walk(node: ASTNode) -> ASTNode:
        nonlocal current_id
        match node:
            case CaptureGroup(child=child, name=name):
                gid = current_id
                current_id += 1
                return CaptureGroup(child=_walk(child), group_id=gid, name=name)
            case SequenceNode(items=items):
                return SequenceNode(items=tuple(_walk(it) for it in items))
            case AlternationNode(branches=branches):
                return AlternationNode(branches=tuple(_walk(b) for b in branches))
            case Quantifier(child=child, min_count=min_c, max_count=max_c, mode=mode):
                return Quantifier(child=_walk(child), min_count=min_c, max_count=max_c, mode=mode)
            case NonCapturingGroup(child=child, flags_add=fa, flags_remove=fr):
                return NonCapturingGroup(child=_walk(child), flags_add=fa, flags_remove=fr)
            case AtomicGroup(child=child):
                return AtomicGroup(child=_walk(child))
            case Lookaround(child=child, behind=b, negative=neg):
                return Lookaround(child=_walk(child), behind=b, negative=neg)
            case Conditional(condition=cond, if_true=if_t, if_false=if_f):
                new_t = _walk(if_t)
                new_f = _walk(if_f) if if_f is not None else None
                return Conditional(condition=cond, if_true=new_t, if_false=new_f)
            case _:
                return node

    return _walk(root)


class _DSLTransformer(Transformer[Token, Any]):
    """Transform Lark parse tree into bire AST."""

    def __init__(self, is_bytes: bool = False) -> None:
        super().__init__()
        self.is_bytes = is_bytes

    def lit_stmt(self, items: list[Token]) -> ASTNode:
        val = _parse_str(items[0].value)
        return ByteLiteral(val.encode("utf-8")) if self.is_bytes else TextLiteral(val)

    def bytes_stmt(self, items: list[Token]) -> ASTNode:
        return ByteLiteral(_parse_bytes(items[0].value))

    def byte_stmt(self, items: list[Token]) -> ASTNode:
        val = int(items[0].value, 0)
        return ByteLiteral(bytes([val]))

    def empty_stmt(self, _: list[Any]) -> ASTNode:
        return EmptyNode()

    def match_capture_stmt(self, items: list[Any]) -> ASTNode:
        return Backreference(reference=items[0])

    def capture_ref(self, items: list[Token]) -> int | str:
        tok = items[0]
        if tok.type == "INT":
            return int(tok.value)
        return _parse_str(tok.value)

    # Anchors
    def start_of_string(self, _: list[Any]) -> ASTNode:
        return AnchorNode(AnchorKind.STRING_START)

    def end_of_string(self, _: list[Any]) -> ASTNode:
        return AnchorNode(AnchorKind.STRING_END)

    def absolute_end(self, _: list[Any]) -> ASTNode:
        return AnchorNode(AnchorKind.ABSOLUTE_END)

    def start_of_line(self, _: list[Any]) -> ASTNode:
        return AnchorNode(AnchorKind.LINE_START)

    def end_of_line(self, _: list[Any]) -> ASTNode:
        return AnchorNode(AnchorKind.LINE_END)

    def word_boundary(self, _: list[Any]) -> ASTNode:
        return AnchorNode(AnchorKind.WORD_BOUNDARY)

    def not_word_boundary(self, _: list[Any]) -> ASTNode:
        return AnchorNode(AnchorKind.NOT_WORD_BOUNDARY)

    # Predefined classes
    def any_char(self, _: list[Any]) -> ASTNode:
        return PredefinedClass(PredefinedKind.ANY)

    def digit(self, _: list[Any]) -> ASTNode:
        return PredefinedClass(PredefinedKind.DIGIT)

    def not_digit(self, _: list[Any]) -> ASTNode:
        return PredefinedClass(PredefinedKind.NOT_DIGIT)

    def word_char(self, _: list[Any]) -> ASTNode:
        return PredefinedClass(PredefinedKind.WORD)

    def not_word_char(self, _: list[Any]) -> ASTNode:
        return PredefinedClass(PredefinedKind.NOT_WORD)

    def whitespace(self, _: list[Any]) -> ASTNode:
        return PredefinedClass(PredefinedKind.WHITESPACE)

    def not_whitespace(self, _: list[Any]) -> ASTNode:
        return PredefinedClass(PredefinedKind.NOT_WHITESPACE)

    # Quantifier specs
    def q_zero_or_more(self, _: list[Any]) -> tuple[int, int | None]:
        return (0, None)

    def q_one_or_more(self, _: list[Any]) -> tuple[int, int | None]:
        return (1, None)

    def q_at_least(self, items: list[Token]) -> tuple[int, int | None]:
        return (int(items[0].value), None)

    def q_at_most(self, items: list[Token]) -> tuple[int, int | None]:
        return (0, int(items[0].value))

    def q_between(self, items: list[Token]) -> tuple[int, int | None]:
        return (int(items[0].value), int(items[1].value))

    def q_exactly(self, items: list[Token]) -> tuple[int, int | None]:
        v = int(items[0].value)
        return (v, v)

    def q_lazy(self, _: list[Any]) -> QuantifierMode:
        return QuantifierMode.LAZY

    def q_possessive(self, _: list[Any]) -> QuantifierMode:
        return QuantifierMode.POSSESSIVE

    # Repetition
    def inline_repeat_stmt(self, items: list[Any]) -> ASTNode:
        child = items[0]
        min_c, max_c = items[1]
        mode = items[2] if len(items) > 2 and items[2] is not None else QuantifierMode.GREEDY
        return Quantifier(child=child, min_count=min_c, max_count=max_c, mode=mode)

    def block_repeat_stmt(self, items: list[Any]) -> ASTNode:
        quant_spec, mode_or_none, body = items
        mode = mode_or_none if mode_or_none is not None else QuantifierMode.GREEDY
        min_c, max_c = quant_spec
        return Quantifier(child=body, min_count=min_c, max_count=max_c, mode=mode)

    # Alternation
    def alternation_stmt(self, items: list[Any]) -> ASTNode:
        branches = tuple(items)
        return AlternationNode(branches=branches)

    # Character class elements
    def class_char(self, items: list[Token]) -> list[CharClassElement]:
        s = _parse_str(items[0].value)
        return [ByteLiteral(s.encode("utf-8"))] if self.is_bytes else [TextLiteral(s)]

    def class_chars(self, items: list[Token]) -> list[CharClassElement]:
        s = _parse_str(items[0].value)
        if self.is_bytes:
            return [ByteLiteral(bytes([b])) for b in s.encode("utf-8")]
        return [TextLiteral(ch) for ch in s]

    def class_range(self, items: list[Token]) -> list[CharClassElement]:
        start_ch = _parse_str(items[0].value)
        end_ch = _parse_str(items[1].value)
        if self.is_bytes:
            return [ByteRange(ord(start_ch), ord(end_ch))]
        return [CharRange(start_ch, end_ch)]

    def class_byte(self, items: list[Token]) -> list[CharClassElement]:
        v = int(items[0].value, 0)
        return [ByteLiteral(bytes([v]))]

    def class_bytes(self, items: list[Token]) -> list[CharClassElement]:
        b_val = _parse_bytes(items[0].value)
        return [ByteLiteral(bytes([b])) for b in b_val]

    def class_byte_range(self, items: list[Token]) -> list[CharClassElement]:
        low = int(items[0].value, 0)
        high = int(items[1].value, 0)
        return [ByteRange(low, high)]

    def class_elem_item(self, items: list[Any]) -> list[CharClassElement]:
        val = items[0]
        if isinstance(val, list):
            return val
        return [val]

    def class_element(self, items: list[Any]) -> list[CharClassElement]:
        return items[0]  # type: ignore[no-any-return]

    def one_of_stmt(self, items: list[list[CharClassElement]]) -> ASTNode:
        flattened: list[CharClassElement] = []
        for elem_list in items:
            flattened.extend(elem_list)
        return CharacterClass(negated=False, elements=tuple(flattened))

    def none_of_stmt(self, items: list[list[CharClassElement]]) -> ASTNode:
        flattened: list[CharClassElement] = []
        for elem_list in items:
            flattened.extend(elem_list)
        return CharacterClass(negated=True, elements=tuple(flattened))

    # Flags
    def scoped_flag(self, items: list[Token]) -> tuple[str, str]:
        if len(items) == 2 and items[0] is not None:
            sign = items[0].value
            name = items[1].value
            return (sign, name)
        name = items[0].value if items[0] is not None else items[1].value
        return ("+", name)

    def flags_list(self, items: list[Any]) -> tuple[int, int]:
        add_flags: list[str] = []
        rem_flags: list[str] = []
        for item in items:
            if item is None:
                continue
            sign, name = item
            if sign == "-":
                rem_flags.append(name)
            else:
                add_flags.append(name)
        return (names_to_flags(add_flags), names_to_flags(rem_flags))

    # Groups
    def capture_stmt(self, items: list[Any]) -> ASTNode:
        name_tok, body = items
        name = _parse_str(name_tok.value) if name_tok is not None else None
        return CaptureGroup(child=body, group_id=0, name=name)

    def group_stmt(self, items: list[Any]) -> ASTNode:
        return NonCapturingGroup(child=items[0])

    def atomic_group_stmt(self, items: list[Any]) -> ASTNode:
        return AtomicGroup(child=items[0])

    def with_flags_stmt(self, items: list[Any]) -> ASTNode:
        flags_tuple, body = items
        flags_add, flags_remove = flags_tuple
        return NonCapturingGroup(child=body, flags_add=flags_add, flags_remove=flags_remove)

    # Lookarounds
    def lookahead(self, items: list[Any]) -> ASTNode:
        return Lookaround(child=items[0], behind=False, negative=False)

    def neg_lookahead(self, items: list[Any]) -> ASTNode:
        return Lookaround(child=items[0], behind=False, negative=True)

    def lookbehind(self, items: list[Any]) -> ASTNode:
        return Lookaround(child=items[0], behind=True, negative=False)

    def neg_lookbehind(self, items: list[Any]) -> ASTNode:
        return Lookaround(child=items[0], behind=True, negative=True)

    # Conditionals
    def conditional_stmt(self, items: list[Any]) -> ASTNode:
        cond_ref, if_true, if_false = items
        return Conditional(condition=cond_ref, if_true=if_true, if_false=if_false)

    # Statements & document wrapping
    def simple_stmt(self, items: list[Any]) -> ASTNode:
        return items[0]  # type: ignore[no-any-return]

    def compound_stmt(self, items: list[Any]) -> ASTNode:
        return items[0]  # type: ignore[no-any-return]

    def statement(self, items: list[Any]) -> ASTNode:
        return items[0]  # type: ignore[no-any-return]

    def statement_list(self, items: list[ASTNode]) -> ASTNode:
        if len(items) == 1:
            return items[0]
        return SequenceNode(items=tuple(items))

    def dsl_document(self, items: list[Any]) -> ASTNode:
        return items[-1]  # type: ignore[no-any-return]


def parse_human_dsl(dsl_code: str) -> RegexPattern:
    """Parse a bire Human DSL code string into a RegexPattern AST.

    Raises:
        ParseError: When grammar or syntax errors occur.
    """
    code = dsl_code.strip() + "\n"

    try:
        tree = _PARSER.parse(code)
    except Exception as exc:
        raise ParseError(f"Failed to parse Human DSL: {exc}") from exc

    is_bytes = False
    flags = 0

    # Inspect header
    header_node = next(tree.find_data("header"), None)
    if header_node is not None:
        mode_node = next(header_node.find_data("mode_decl"), None)
        if mode_node is not None:
            mode_tok = mode_node.children[0]
            if isinstance(mode_tok, Token) and mode_tok.value == "BYTES":
                is_bytes = True

        flags_node = next(header_node.find_data("flags_decl"), None)
        if flags_node is not None:
            flag_tokens: list[str] = []
            for sf in flags_node.find_data("scoped_flag"):
                flag_name = sf.children[-1].value  # type: ignore[union-attr]
                flag_tokens.append(flag_name)
            flags = names_to_flags(flag_tokens)

    # Transform body
    transformer = _DSLTransformer(is_bytes=is_bytes)
    root_node: ASTNode = transformer.transform(tree)

    final_root = _assign_group_ids(root_node)

    pattern = RegexPattern(root=final_root, flags=flags, is_bytes=is_bytes)
    validate_ast(pattern)
    return pattern
