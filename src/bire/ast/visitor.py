"""Visitor and traversal utilities for AST nodes."""

from __future__ import annotations

from collections.abc import Iterator

from bire.ast.nodes import (
    AlternationNode,
    ASTNode,
    AtomicGroup,
    CaptureGroup,
    CharacterClass,
    Conditional,
    Lookaround,
    NonCapturingGroup,
    Quantifier,
    RegexPattern,
    SequenceNode,
)


def iter_children(node: ASTNode) -> Iterator[ASTNode]:
    """Yield all immediate child AST nodes in logical order."""
    match node:
        case RegexPattern(root=root):
            yield root
        case SequenceNode(items=items):
            yield from items
        case AlternationNode(branches=branches):
            yield from branches
        case CharacterClass(elements=elements):
            yield from elements
        case Quantifier(child=child):
            yield child
        case CaptureGroup(child=child):
            yield child
        case NonCapturingGroup(child=child):
            yield child
        case AtomicGroup(child=child):
            yield child
        case Lookaround(child=child):
            yield child
        case Conditional(if_true=if_true, if_false=if_false):
            yield if_true
            if if_false is not None:
                yield if_false
        case _:
            pass


def walk(node: ASTNode) -> Iterator[ASTNode]:
    """Pre-order traversal of all nodes in the tree."""
    yield node
    for child in iter_children(node):
        yield from walk(child)
