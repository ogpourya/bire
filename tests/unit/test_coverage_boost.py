"""Targeted unit tests to achieve >= 95% total test coverage."""

import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from bire.api import compile_human, verify
from bire.ast.exceptions import ParseError, RenderError, ValidationError
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
from bire.ast.validator import compute_width, validate_ast
from bire.ast.visitor import iter_children
from bire.cli import main
from bire.parsers.human_parser import parse_human_dsl
from bire.parsers.python_parser import parse_python_regex
from bire.renderers.human_renderer import render_human
from bire.renderers.python_renderer import (
    _escape_char_bytes,
    _escape_char_str,
    _get_precedence,
    _starts_with_digit,
    render_python,
)


def test_api_compile_and_verify_coverage() -> None:
    pat = compile_human('LITERAL "foo"\n')
    assert pat.search("foobar") is not None

    assert verify(r"^a$", "a") is True
    assert verify(r"a", "b") is True
    assert verify(r"^a", "a") is True

    # Test all mismatch branches in verify() using mock compiled objects
    mock_orig1 = MagicMock()
    mock_trans1 = MagicMock()
    m1 = MagicMock()
    m1.span.return_value = (0, 1)
    m2 = MagicMock()
    m2.span.return_value = (0, 2)
    mock_orig1.search.return_value = m1
    mock_trans1.search.return_value = m2
    with patch("re.compile", side_effect=[mock_orig1, mock_trans1]):
        assert verify(r"a", "a") is False

    # Groups mismatch in search
    m1.span.return_value = (0, 1)
    m2.span.return_value = (0, 1)
    m1.groups.return_value = ("a",)
    m2.groups.return_value = ("b",)
    with patch("re.compile", side_effect=[mock_orig1, mock_trans1]):
        assert verify(r"a", "a") is False

    # Groupdict mismatch in search
    m1.groups.return_value = ()
    m2.groups.return_value = ()
    m1.groupdict.return_value = {"x": "1"}
    m2.groupdict.return_value = {"x": "2"}
    with patch("re.compile", side_effect=[mock_orig1, mock_trans1]):
        assert verify(r"a", "a") is False

    # Match mismatch
    m1.groupdict.return_value = {}
    m2.groupdict.return_value = {}
    mock_orig1.match.return_value = m1
    mock_trans1.match.return_value = None
    with patch("re.compile", side_effect=[mock_orig1, mock_trans1]):
        assert verify(r"a", "a") is False

    # Fullmatch mismatch
    mock_trans1.match.return_value = m2
    mock_orig1.fullmatch.return_value = m1
    mock_trans1.fullmatch.return_value = None
    with patch("re.compile", side_effect=[mock_orig1, mock_trans1]):
        assert verify(r"a", "a") is False

    # Findall mismatch
    mock_trans1.fullmatch.return_value = m2
    mock_orig1.findall.return_value = ["a"]
    mock_trans1.findall.return_value = ["b"]
    with patch("re.compile", side_effect=[mock_orig1, mock_trans1]):
        assert verify(r"a", "a") is False

    # Split mismatch
    mock_orig1.findall.return_value = ["a"]
    mock_trans1.findall.return_value = ["a"]
    mock_orig1.split.return_value = ["a", ""]
    mock_trans1.split.return_value = ["b", ""]
    with patch("re.compile", side_effect=[mock_orig1, mock_trans1]):
        assert verify(r"a", "a") is False


def test_cli_direct_invocation(tmp_path: Path) -> None:
    in_file = tmp_path / "in.regex"
    out_file = tmp_path / "out.dsl"
    in_file.write_text("cat|dog")

    ret = main(["to-human", str(in_file), "-o", str(out_file), "--flags", "IGNORECASE"])
    assert ret == 0
    assert "EITHER:" in out_file.read_text()

    py_out = tmp_path / "out.py"
    ret = main(["to-python", str(out_file), "-o", str(py_out)])
    assert ret == 0
    assert "cat|dog" in py_out.read_text()

    assert main(["verify", "^abc$", "abc"]) == 0
    assert main(["verify", "^abc$", "xyz"]) == 0
    assert main(["verify", "[a-", "abc"]) == 1

    with patch("bire.cli.verify", return_value=False):
        assert main(["verify", "a", "a"]) == 2

    with patch("bire.cli.to_human", side_effect=Exception("boom")):
        assert main(["to-human", str(in_file)]) == 1


def test_validator_comprehensive_edges() -> None:
    assert compute_width(EmptyNode()) == 0
    assert compute_width(TextLiteral("abc")) == 3
    assert compute_width(ByteLiteral(b"abc")) == 3
    assert compute_width(PredefinedClass(PredefinedKind.DIGIT)) == 1
    assert compute_width(AnchorNode(AnchorKind.LINE_START)) == 0
    assert compute_width(CharRange("a", "b")) == 1
    assert compute_width(ByteRange(10, 20)) == 1
    assert compute_width(CharacterClass(False, (CharRange("a", "b"),))) == 1
    assert compute_width(SequenceNode((TextLiteral("a"), TextLiteral("b")))) == 2
    assert compute_width(SequenceNode((TextLiteral("a"), Quantifier(TextLiteral("b"), 0, None, QuantifierMode.GREEDY)))) is None
    assert compute_width(AlternationNode(())) == 0
    assert compute_width(AlternationNode((TextLiteral("a"), TextLiteral("b")))) == 1
    assert compute_width(AlternationNode((TextLiteral("a"), TextLiteral("bb")))) is None
    assert compute_width(AlternationNode((Quantifier(TextLiteral("b"), 0, None, QuantifierMode.GREEDY),))) is None
    assert compute_width(Quantifier(TextLiteral("a"), 2, 2, QuantifierMode.GREEDY)) == 2
    assert compute_width(Quantifier(TextLiteral("a"), 1, 2, QuantifierMode.GREEDY)) is None
    assert compute_width(Quantifier(Quantifier(TextLiteral("a"), 0, None, QuantifierMode.GREEDY), 2, 2, QuantifierMode.GREEDY)) is None
    assert compute_width(CaptureGroup(TextLiteral("abc"), 1)) == 3
    assert compute_width(NonCapturingGroup(TextLiteral("abc"))) == 3
    assert compute_width(AtomicGroup(TextLiteral("abc"))) == 3
    assert compute_width(Lookaround(TextLiteral("abc"), behind=True, negative=False)) == 0
    assert compute_width(Conditional(1, TextLiteral("a"), TextLiteral("b"))) == 1
    assert compute_width(Conditional(1, TextLiteral("a"), TextLiteral("bb"))) is None
    assert compute_width(Backreference(1)) is None
    assert compute_width(object()) is None  # type: ignore[arg-type]

    with pytest.raises(ValidationError, match="must each be exactly one character"):
        validate_ast(CharRange("aa", "b"))

    with pytest.raises(ValidationError, match="Disallowed construct"):
        validate_ast(CharacterClass(False, (AnchorNode(AnchorKind.LINE_START),)))  # type: ignore[arg-type]

    with pytest.raises(ValidationError, match="must be 1 byte"):
        validate_ast(RegexPattern(root=CharacterClass(False, (ByteLiteral(b"ab"),)), is_bytes=True))

    with pytest.raises(ValidationError, match="Invalid backreference type"):
        validate_ast(SequenceNode((CaptureGroup(TextLiteral("a"), 1), Backreference(1.5))))  # type: ignore[arg-type]

    with pytest.raises(ValidationError, match="Invalid conditional type"):
        validate_ast(SequenceNode((CaptureGroup(TextLiteral("a"), 1), Conditional(1.5, TextLiteral("x")))))  # type: ignore[arg-type]


def test_visitor_iter_children() -> None:
    class Dummy(ASTNode):
        pass
    assert list(iter_children(Dummy())) == []


def test_python_renderer_edge_cases() -> None:
    assert _escape_char_str("\a") == r"\a"
    assert _escape_char_str("\b") == r"\b"
    assert _escape_char_str("\f") == r"\f"
    assert _escape_char_str("\v") == r"\v"
    assert _escape_char_str("\x01") == r"\x01"

    assert _escape_char_bytes(ord(b"\a")) == b"\\a"
    assert _escape_char_bytes(ord(b"\b")) == b"\\b"
    assert _escape_char_bytes(ord(b"\f")) == b"\\f"
    assert _escape_char_bytes(ord(b"\v")) == b"\\v"
    assert _escape_char_bytes(1) == b"\\x01"
    assert _escape_char_bytes(255) == b"\\xff"

    assert _starts_with_digit(ByteLiteral(b"9")) is True
    assert _starts_with_digit(ByteLiteral(b"a")) is False
    assert _starts_with_digit(SequenceNode((ByteLiteral(b"5"),))) is True
    assert _starts_with_digit(EmptyNode()) is False

    assert _get_precedence(SequenceNode(())) == 3
    assert _get_precedence(AlternationNode(())) == 3
    assert _get_precedence(AlternationNode((TextLiteral("a"),))) == 3

    b_ast = RegexPattern(
        root=SequenceNode((
            EmptyNode(),
            ByteLiteral(b"ab"),
            PredefinedClass(PredefinedKind.NOT_DIGIT),
            PredefinedClass(PredefinedKind.WORD),
            PredefinedClass(PredefinedKind.NOT_WORD),
            PredefinedClass(PredefinedKind.WHITESPACE),
            PredefinedClass(PredefinedKind.NOT_WHITESPACE),
            PredefinedClass(PredefinedKind.ANY),
            AnchorNode(AnchorKind.STRING_START),
            AnchorNode(AnchorKind.STRING_END),
            AnchorNode(AnchorKind.ABSOLUTE_END),
            AnchorNode(AnchorKind.LINE_START),
            AnchorNode(AnchorKind.LINE_END),
            AnchorNode(AnchorKind.WORD_BOUNDARY),
            AnchorNode(AnchorKind.NOT_WORD_BOUNDARY),
            Quantifier(ByteLiteral(b"a"), 0, 1, QuantifierMode.GREEDY),
            Quantifier(ByteLiteral(b"a"), 3, 3, QuantifierMode.LAZY),
            Quantifier(ByteLiteral(b"a"), 2, None, QuantifierMode.POSSESSIVE),
            Quantifier(ByteLiteral(b"a"), 2, 4, QuantifierMode.GREEDY),
            CaptureGroup(ByteLiteral(b"c"), 1),
            CaptureGroup(ByteLiteral(b"d"), 2, name="named"),
            NonCapturingGroup(ByteLiteral(b"e"), flags_add=re.IGNORECASE, flags_remove=re.MULTILINE),
            AtomicGroup(ByteLiteral(b"f")),
            Lookaround(ByteLiteral(b"g"), behind=False, negative=True),
            Lookaround(ByteLiteral(b"h"), behind=True, negative=False),
            Lookaround(ByteLiteral(b"i"), behind=True, negative=True),
            Backreference(1),
            Backreference("named"),
            Conditional(1, ByteLiteral(b"t"), ByteLiteral(b"f")),
            Conditional(
                1,
                AlternationNode((ByteLiteral(b"t1"), ByteLiteral(b"t2"))),
                AlternationNode((ByteLiteral(b"f1"), ByteLiteral(b"f2"))),
            ),
            Conditional(1, ByteLiteral(b"t")),
            CharacterClass(
                negated=True,
                elements=(
                    ByteLiteral(b"x"),
                    ByteRange(ord(b"0"), ord(b"9")),
                    PredefinedClass(PredefinedKind.DIGIT),
                ),
            ),
            AlternationNode((ByteLiteral(b"1"), ByteLiteral(b"2"))),
        )),
        is_bytes=True,
    )
    rendered_b = render_python(b_ast)
    assert isinstance(rendered_b, bytes)
    re.compile(rendered_b)

    with pytest.raises(RenderError, match="Unsupported AST node"):
        render_python(RegexPattern(root=object()))  # type: ignore[arg-type]

    with pytest.raises(RenderError, match="Unexpected element in string CharacterClass"):
        render_python(CharacterClass(False, (object(),)))  # type: ignore[arg-type]

    with pytest.raises(RenderError, match="Unexpected element in bytes CharacterClass"):
        render_python(RegexPattern(root=CharacterClass(False, (object(),)), is_bytes=True))  # type: ignore[arg-type]

    with pytest.raises(RenderError, match="Unsupported AST node in bytes renderer"):
        render_python(RegexPattern(root=object(), is_bytes=True))  # type: ignore[arg-type]


def test_human_parser_and_renderer_edges() -> None:
    dsl_inline = "REPEAT(LITERAL \"abc\", ZERO OR MORE TIMES)\n"
    ast_inline = parse_human_dsl(dsl_inline)
    assert isinstance(ast_inline.root, Quantifier)

    dsl_bytes = """MODE: BYTES
FLAGS: [IGNORECASE]

BYTE 0x61
BYTES "\\x62\\x63"
ONE OF:
    BYTE 0x30
    BYTES "abc"
    BYTE_RANGE 0x41 TO 0x5a
REPEAT EXACTLY 3 TIMES:
    ANY CHARACTER
REPEAT AT MOST 5 TIMES:
    NOT DIGIT
REPEAT BETWEEN 1 AND 2 TIMES:
    NOT WORD CHARACTER
REPEAT ONE OR MORE TIMES:
    NOT WHITESPACE
"""
    p_bytes = parse_human_dsl(dsl_bytes)
    assert p_bytes.is_bytes
    rendered_dsl = render_human(p_bytes)
    assert "MODE: BYTES" in rendered_dsl

    dsl_scoped = """WITH FLAGS [IGNORECASE, -MULTILINE]:
    LITERAL "foo"
"""
    p_scoped = parse_human_dsl(dsl_scoped)
    assert isinstance(p_scoped.root, NonCapturingGroup)
    rendered_scoped = render_human(p_scoped)
    assert "WITH FLAGS [IGNORECASE, -MULTILINE]:" in rendered_scoped

    with pytest.raises(ParseError):
        parse_human_dsl("INVALID SYNTAX !!!")

    with pytest.raises(RenderError):
        render_human(object())  # type: ignore[arg-type]

    with pytest.raises(RenderError):
        render_human(CharacterClass(False, (object(),)))  # type: ignore[arg-type]


def test_python_parser_unsupported_edge() -> None:
    import re._constants as rc  # type: ignore[import-not-found]
    with patch("re._parser.parse") as mock_parse:
        mock_res = type("MockParsed", (), {"data": [(rc.AT, 9999)], "state": type("State", (), {"groupdict": {}, "flags": 0})()})()
        mock_parse.return_value = mock_res
        with pytest.raises(ParseError):
            parse_python_regex("a")
