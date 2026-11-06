"""Command-line interface for BiRe."""

from __future__ import annotations

import argparse
import sys

from bire.api import to_human, to_python, verify
from bire.ast.exceptions import BiReError
from bire.ast.flags import names_to_flags


def _parse_flags(flags_str: str | None) -> int:
    if not flags_str:
        return 0
    names = [f.strip() for f in flags_str.split(",") if f.strip()]
    return names_to_flags(names)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="bire",
        description="BiRe: Bilingual Regex bidirectional transpiler",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # to-human
    to_human_p = subparsers.add_parser("to-human", help="Transpile Python regex to BiRe Human DSL")
    to_human_p.add_argument("input_file", nargs="?", default="-", help="Input file or '-' for stdin")
    to_human_p.add_argument("-o", "--output", help="Output file path (default stdout)")
    to_human_p.add_argument("--flags", help="Comma-separated flag names (e.g. IGNORECASE,MULTILINE)")

    # to-python
    to_python_p = subparsers.add_parser("to-python", help="Transpile BiRe Human DSL to Python regex")
    to_python_p.add_argument("input_file", nargs="?", default="-", help="Input file or '-' for stdin")
    to_python_p.add_argument("-o", "--output", help="Output file path (default stdout)")

    # verify
    verify_p = subparsers.add_parser("verify", help="Verify behavioral equivalence against test input")
    verify_p.add_argument("pattern", help="Python regex pattern")
    verify_p.add_argument("test_input", help="Test input string to check")
    verify_p.add_argument("--flags", help="Comma-separated flag names")

    args = parser.parse_args(argv)

    try:
        if args.command == "to-human":
            if args.input_file == "-":
                content = sys.stdin.read().strip("\r\n")
            else:
                with open(args.input_file, encoding="utf-8") as f:
                    content = f.read().strip("\r\n")

            flags = _parse_flags(args.flags)
            result = to_human(content, flags=flags)

            if args.output:
                with open(args.output, "w", encoding="utf-8") as f:
                    f.write(result)
            else:
                sys.stdout.write(result)
            return 0

        if args.command == "to-python":
            if args.input_file == "-":
                content = sys.stdin.read()
            else:
                with open(args.input_file, encoding="utf-8") as f:
                    content = f.read()

            py_pattern, _ = to_python(content)
            output_str = py_pattern.decode("latin1") if isinstance(py_pattern, bytes) else py_pattern

            if args.output:
                with open(args.output, "w", encoding="utf-8") as f:
                    f.write(output_str + "\n")
            else:
                sys.stdout.write(output_str + "\n")
            return 0

        if args.command == "verify":
            flags = _parse_flags(args.flags)
            is_valid = verify(args.pattern, args.test_input, flags=flags)
            if is_valid:
                sys.stdout.write("VERIFICATION SUCCESS: Behavioral equivalence verified.\n")
                return 0
            sys.stderr.write("VERIFICATION FAILURE: Output mismatch.\n")
            return 2

    except BiReError as err:
        sys.stderr.write(f"Compilation error: {err}\n")
        return 1
    except Exception as err:  # noqa: BLE001
        sys.stderr.write(f"Unexpected error: {err}\n")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
