"""AST node definitions for bire."""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass
from enum import Enum


class PredefinedKind(str, Enum):
    DIGIT = "DIGIT"
    NOT_DIGIT = "NOT_DIGIT"
    WORD = "WORD"
    NOT_WORD = "NOT_WORD"
    WHITESPACE = "WHITESPACE"
    NOT_WHITESPACE = "NOT_WHITESPACE"
    ANY = "ANY"


class AnchorKind(str, Enum):
    STRING_START = "STRING_START"          # \A
    STRING_END = "STRING_END"              # \Z
    LINE_START = "LINE_START"              # ^
    LINE_END = "LINE_END"                  # $
    WORD_BOUNDARY = "WORD_BOUNDARY"        # \b
    NOT_WORD_BOUNDARY = "NOT_WORD_BOUNDARY"# \B
    ABSOLUTE_END = "ABSOLUTE_END"          # \z (Python 3.14+)


class QuantifierMode(str, Enum):
    GREEDY = "GREEDY"
    LAZY = "LAZY"
    POSSESSIVE = "POSSESSIVE"


@dataclass(frozen=True)
class ASTNode(ABC):
    """Abstract base class for all AST nodes."""


@dataclass(frozen=True)
class RegexPattern(ASTNode):
    root: ASTNode
    flags: int = 0
    is_bytes: bool = False


@dataclass(frozen=True)
class SequenceNode(ASTNode):
    items: tuple[ASTNode, ...]


@dataclass(frozen=True)
class AlternationNode(ASTNode):
    branches: tuple[ASTNode, ...]


@dataclass(frozen=True)
class EmptyNode(ASTNode):
    """Represents an empty branch (e.g. a|) or empty group (())."""


@dataclass(frozen=True)
class TextLiteral(ASTNode):
    value: str


@dataclass(frozen=True)
class ByteLiteral(ASTNode):
    value: bytes


@dataclass(frozen=True)
class PredefinedClass(ASTNode):
    kind: PredefinedKind


@dataclass(frozen=True)
class AnchorNode(ASTNode):
    kind: AnchorKind


@dataclass(frozen=True)
class CharRange(ASTNode):
    start: str
    end: str


@dataclass(frozen=True)
class ByteRange(ASTNode):
    start: int
    end: int


CharClassElement = TextLiteral | ByteLiteral | CharRange | ByteRange | PredefinedClass


@dataclass(frozen=True)
class CharacterClass(ASTNode):
    negated: bool
    elements: tuple[CharClassElement, ...]


@dataclass(frozen=True)
class Quantifier(ASTNode):
    child: ASTNode
    min_count: int
    max_count: int | None
    mode: QuantifierMode


@dataclass(frozen=True)
class CaptureGroup(ASTNode):
    child: ASTNode
    group_id: int
    name: str | None = None


@dataclass(frozen=True)
class NonCapturingGroup(ASTNode):
    child: ASTNode
    flags_add: int = 0
    flags_remove: int = 0


@dataclass(frozen=True)
class AtomicGroup(ASTNode):
    child: ASTNode


@dataclass(frozen=True)
class Lookaround(ASTNode):
    child: ASTNode
    behind: bool
    negative: bool


@dataclass(frozen=True)
class Conditional(ASTNode):
    condition: int | str
    if_true: ASTNode
    if_false: ASTNode | None = None


@dataclass(frozen=True)
class Backreference(ASTNode):
    reference: int | str
