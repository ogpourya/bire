"""Command-line interface for BiRe (modern, cute, and minimal)."""

from __future__ import annotations

import argparse
import os
import sys

from bire.api import to_human, to_python, verify
from bire.ast.exceptions import BiReError
from bire.ast.flags import names_to_flags

__version__ = "0.1.0"


def _use_color() -> bool:
    if "NO_COLOR" in os.environ:
        return False
    return sys.stdout.isatty()


def _c(code: str, text: str) -> str:
    return f"{code}{text}\033[0m" if _use_color() else text


def _purple(text: str) -> str:
    return _c("\033[38;5;141m", text)


def _pink(text: str) -> str:
    return _c("\033[38;5;213m", text)


def _cyan(text: str) -> str:
    return _c("\033[38;5;117m", text)


def _dim(text: str) -> str:
    return _c("\033[38;5;244m", text)


def _green(text: str) -> str:
    return _c("\033[38;5;120m", text)


def _red(text: str) -> str:
    return _c("\033[38;5;203m", text)


def _bold(text: str) -> str:
    return _c("\033[1m", text)


def _read_input(target: str | None) -> str:
    if not target or target == "-":
        return sys.stdin.read()
    if os.path.isfile(target):
        with open(target, encoding="utf-8") as f:
            return f.read()
    return target


def _parse_flags(flags_str: str | None) -> int:
    if not flags_str:
        return 0
    names = [f.strip() for f in flags_str.split(",") if f.strip()]
    return names_to_flags(names)


def _run_demo() -> int:
    pattern = r"(?<=start_)(?P<tag>[a-z]+)_(?>[0-9]+)(?(tag)_end|)(?:x*)+"
    samples = [
        "start_data_123_end",
        "start_data_123_endxxxx",
        "prefix_start_tag_42_end",
        "start_tag_42",
        "start__123_end",
        "random text without start",
    ]

    sys.stdout.write(f"\n{_pink('✦')} {_bold('bire demo')} {_dim('v' + __version__)}\n")
    sys.stdout.write(f"{_dim('─' * 52)}\n")
    sys.stdout.write(f"{_purple('Python Regex:')} {pattern}\n\n")

    dsl = to_human(pattern)
    sys.stdout.write(f"{_cyan('Transpiled bire DSL:')}\n")
    sys.stdout.write(f"{_dim(dsl.strip())}\n\n")

    py_back, _ = to_python(dsl)
    py_str = py_back.decode("latin1") if isinstance(py_back, bytes) else py_back
    sys.stdout.write(f"{_purple('Roundtrip Regex:')} {py_str}\n\n")
    sys.stdout.write(f"{_bold('Behavioral Checks:')}\n")

    all_passed = True
    for s in samples:
        matched = verify(pattern, s)
        status = _green("✔ pass") if matched else _red("✘ fail")
        sys.stdout.write(f"  {status}  {_dim(repr(s))}\n")
        if not matched:
            all_passed = False

    sys.stdout.write(f"{_dim('─' * 52)}\n")
    if all_passed:
        sys.stdout.write(f"{_green('✔ All 6 checks passed cleanly.')} {_pink('✦')}\n\n")
        return 0
    sys.stdout.write(f"{_red('✘ Verification failed.')}\n\n")
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="bire",
        description=f"✦ bire (v{__version__}): Bilingual Regex transpiler",
    )
    parser.add_argument("-v", "--version", action="version", version=f"bire {__version__}")

    subparsers = parser.add_subparsers(dest="command")

    # to-human
    to_human_p = subparsers.add_parser("to-human", help="Transpile Python regex to bire human DSL")
    to_human_p.add_argument("input", nargs="?", default="-", help="Regex pattern, file path, or '-' for stdin")
    to_human_p.add_argument("-o", "--output", help="Output file path (default: stdout)")
    to_human_p.add_argument("--flags", help="Comma-separated flags (e.g. IGNORECASE,MULTILINE)")

    # to-python
    to_python_p = subparsers.add_parser("to-python", help="Transpile bire human DSL to Python regex")
    to_python_p.add_argument("input", nargs="?", default="-", help="DSL string, file path, or '-' for stdin")
    to_python_p.add_argument("-o", "--output", help="Output file path (default: stdout)")

    # verify
    verify_p = subparsers.add_parser("verify", help="Verify behavioral equivalence on sample input")
    verify_p.add_argument("pattern", help="Python regex pattern")
    verify_p.add_argument("test_input", help="Test input string to check")
    verify_p.add_argument("--flags", help="Comma-separated flags")

    # demo
    subparsers.add_parser("demo", help="Run interactive verification showcase")

    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    try:
        if args.command == "demo":
            return _run_demo()

        if args.command == "to-human":
            content = _read_input(args.input).strip("\r\n")
            flags = _parse_flags(args.flags)
            result = to_human(content, flags=flags)

            if args.output:
                with open(args.output, "w", encoding="utf-8") as f:
                    f.write(result)
            else:
                sys.stdout.write(result)
            return 0

        if args.command == "to-python":
            content = _read_input(args.input)
            py_pattern, _ = to_python(content)
            out_str = py_pattern.decode("latin1") if isinstance(py_pattern, bytes) else py_pattern

            if args.output:
                with open(args.output, "w", encoding="utf-8") as f:
                    f.write(out_str + "\n")
            else:
                sys.stdout.write(out_str + "\n")
            return 0

        if args.command == "verify":
            flags = _parse_flags(args.flags)
            is_valid = verify(args.pattern, args.test_input, flags=flags)
            if is_valid:
                sys.stdout.write(f"{_green('✔ VERIFIED:')} {_dim('behavioral equivalence confirmed.')}\n")
                return 0
            sys.stderr.write(f"{_red('✘ MISMATCH:')} {_dim('transpiled behavior diverges on this input.')}\n")
            return 2

    except BiReError as err:
        sys.stderr.write(f"{_red('✘ compilation error:')} {err}\n")
        return 1
    except Exception as err:  # noqa: BLE001
        sys.stderr.write(f"{_red('✘ unexpected error:')} {err}\n")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
