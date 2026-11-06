"""4-space indentation postlexer for bire human DSL."""

from __future__ import annotations

from typing import ClassVar

from lark.indenter import Indenter


class BiReIndenter(Indenter):
    """Postlexer that generates _INDENT and _DEDENT tokens based on 4-space indentation."""

    NL_type = "_NL"
    OPEN_PAREN_types: ClassVar[list[str]] = ["LPAR", "LSQB"]
    CLOSE_PAREN_types: ClassVar[list[str]] = ["RPAR", "RSQB"]
    INDENT_type = "_INDENT"
    DEDENT_type = "_DEDENT"
    tab_len = 4


bireIndenter = BiReIndenter
