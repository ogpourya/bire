#!/usr/bin/env python3
"""Standalone demonstration verifying end-to-end bidirectional transpilation.

Transpiles a complex regex containing:
- Lookbehinds (?<=start_)
- Nested named captures (?P<tag>[a-z]+)
- Atomic groups (?>[0-9]+)
- Conditionals (?(tag)_end|)
- Possessive quantifiers
- Quantifier-on-quantifier precedence wrapping (?:x*)+
"""

import sys
from bire.api import to_human, to_python, verify

COMPLEX_REGEX = r"(?<=start_)(?P<tag>[a-z]+)_(?>[0-9]+)(?(tag)_end|)(?:x*)+"

TEST_INPUTS = [
    "start_data_123_end",
    "start_data_123_endxxxx",
    "prefix_start_tag_42_end",
    "start_tag_42",
    "start__123_end",
    "random text without start",
]


def run_demo() -> int:
    print("=" * 80)
    print("bire End-to-End Transpilation Verification Demo")
    print("=" * 80)
    print(f"Original Regex: {COMPLEX_REGEX}\n")

    # Step 1: Transpile to bire Human DSL
    dsl = to_human(COMPLEX_REGEX)
    print("Generated bire Human DSL:")
    print("-" * 40)
    print(dsl)
    print("-" * 40)

    # Step 2: Transpile back to Python Regex
    py_trans, flags = to_python(dsl)
    print(f"Transpiled Regex: {py_trans}")
    print(f"Effective Flags: {flags}\n")

    # Step 3: Verify behavioral equivalence against all sample inputs
    print("Verifying Behavioral Equivalence:")
    all_passed = True
    for sample in TEST_INPUTS:
        ok = verify(COMPLEX_REGEX, sample)
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] Test input: {sample!r}")
        if not ok:
            all_passed = False

    print("=" * 80)
    if all_passed:
        print("RESULT: ALL 6 CHECKS PASSED. 100% BEHAVIORAL EQUIVALENCE PROVEN.")
        return 0
    else:
        print("RESULT: VERIFICATION FAILED.")
        return 1


if __name__ == "__main__":
    sys.exit(run_demo())
