"""Public API for BiRe (Bilingual Regex transpiler)."""

from __future__ import annotations

import re
from typing import Any

from bire.ast.nodes import RegexPattern
from bire.parsers.human_parser import parse_human_dsl
from bire.parsers.python_parser import parse_python_regex
from bire.renderers.human_renderer import render_human
from bire.renderers.python_renderer import render_python


def to_human(pattern: str | bytes, flags: int = 0) -> str:
    """Transpile a Python regular expression into BiRe Human DSL code."""
    ast_tree = parse_python_regex(pattern, flags=flags)
    return render_human(ast_tree)


def to_python(dsl_code: str) -> tuple[str | bytes, int]:
    """Transpile BiRe Human DSL code into a Python regex pattern and flag bitmask."""
    ast_tree: RegexPattern = parse_human_dsl(dsl_code)
    rendered_pattern = render_python(ast_tree)
    return rendered_pattern, ast_tree.flags


def compile_human(dsl_code: str) -> re.Pattern[Any]:
    """Compile BiRe Human DSL code directly into a standard Python re.Pattern object."""
    pattern, flags = to_python(dsl_code)
    return re.compile(pattern, flags)


def verify(pattern: str | bytes, test_input: str | bytes, flags: int = 0) -> bool:
    """Verify behavioral equivalence between a Python regex and its transpiled counterpart.

    Checks search, match, fullmatch, findall, split, and sub methods for identical results.
    """
    human_dsl = to_human(pattern, flags=flags)
    trans_pattern, trans_flags = to_python(human_dsl)

    orig = re.compile(pattern, flags)
    trans = re.compile(trans_pattern, trans_flags)

    sub_replacement = b"x" if isinstance(test_input, (bytes, bytearray)) else "x"

    # 1. search
    m_orig = orig.search(test_input)  # type: ignore[arg-type]
    m_trans = trans.search(test_input)  # type: ignore[arg-type]
    if (m_orig is None) != (m_trans is None):
        return False
    if m_orig is not None and m_trans is not None:
        if m_orig.span() != m_trans.span():
            return False
        if m_orig.groups() != m_trans.groups():
            return False
        if m_orig.groupdict() != m_trans.groupdict():
            return False

    # 2. match
    m_orig = orig.match(test_input)  # type: ignore[arg-type]
    m_trans = trans.match(test_input)  # type: ignore[arg-type]
    if (m_orig is None) != (m_trans is None):
        return False
    if m_orig is not None and m_trans is not None:
        if m_orig.span() != m_trans.span():
            return False
        if m_orig.groups() != m_trans.groups():
            return False
        if m_orig.groupdict() != m_trans.groupdict():
            return False

    # 3. fullmatch
    m_orig = orig.fullmatch(test_input)  # type: ignore[arg-type]
    m_trans = trans.fullmatch(test_input)  # type: ignore[arg-type]
    if (m_orig is None) != (m_trans is None):
        return False
    if m_orig is not None and m_trans is not None:
        if m_orig.span() != m_trans.span():
            return False
        if m_orig.groups() != m_trans.groups():
            return False
        if m_orig.groupdict() != m_trans.groupdict():
            return False

    # 4. findall
    if orig.findall(test_input) != trans.findall(test_input):  # type: ignore[arg-type]
        return False

    # 5. split
    if orig.split(test_input) != trans.split(test_input):  # type: ignore[arg-type]
        return False

    # 6. sub
    return orig.sub(sub_replacement, test_input) == trans.sub(sub_replacement, test_input)  # type: ignore[arg-type]
