# bire

**Deterministic, bidirectional transpiler between Python regular expressions and a 4-space indented human DSL.**

Python 3.12+ / 3.14 / 3.15 • 95.7% Test Coverage • 50 Tests Passed • MIT License

bire solves the regex maintainability problem: regular expressions are hard to read, review, and modify in team codebases. bire provides a readable, indentation-based syntax with a mathematical guarantee of **100% behavioral equivalence**.

---

## ✦ Installation

Install bire globally with `uv tool`:

```bash
uv tool install https://github.com/ogpourya/bire.git --force
```

Add to a Python project:
```bash
uv add git+https://github.com/ogpourya/bire.git
# or with pip:
pip install git+https://github.com/ogpourya/bire.git
```

---

## ✦ The Behavioral Equivalence Contract

CPython's regex compiler canonicalizes syntax trees (for example, rewriting `a|b` into `[ab]` and stripping comments `(?#...)`), so byte-for-byte text equality is impossible.

Instead, bire guarantees **exact behavioral equivalence** across all standard Python regex execution methods:

```python
orig = re.compile(python_pattern, flags)
trans = re.compile(transpiled_pattern, flags)

# Guaranteed identical for all inputs:
orig.search(s)    == trans.search(s)
orig.match(s)     == trans.match(s)
orig.fullmatch(s) == trans.fullmatch(s)
orig.findall(s)   == trans.findall(s)
orig.split(s)     == trans.split(s)
orig.sub("x", s)  == trans.sub("x", s)
```

Every execution produces identical match spans (`.span()`), ordered subgroup tuples (`.groups()`), named capture dictionaries (`.groupdict()`), and effective flag bits.

---

## ✦ CLI Usage

bire comes with a modern, clean, minimal CLI.

### 1. Interactive Demo
Run the built-in showcase to see transpilation and verification in action:

```bash
bire demo
```

Output:
```text
✦ bire demo v0.1.0
────────────────────────────────────────────────────
Python Regex: (?<=start_)(?P<tag>[a-z]+)_(?>[0-9]+)(?(tag)_end|)(?:x*)+

Transpiled bire DSL:
LOOKBEHIND:
    LITERAL "start_"
CAPTURE "tag":
    REPEAT ONE OR MORE TIMES:
        ONE OF:
            RANGE "a" TO "z"
LITERAL "_"
ATOMIC GROUP:
    REPEAT ONE OR MORE TIMES:
        ONE OF:
            RANGE "0" TO "9"
IF CAPTURE "tag":
    LITERAL "_end"
ELSE:
    EMPTY
REPEAT ONE OR MORE TIMES:
    REPEAT ZERO OR MORE TIMES:
        LITERAL "x"

Roundtrip Regex: (?<=start_)(?P<tag>[a-z]+)_(?>[0-9]+)(?(tag)_end|)(?:x*)+

Behavioral Checks:
  ✔ pass  'start_data_123_end'
  ✔ pass  'start_data_123_endxxxx'
  ✔ pass  'prefix_start_tag_42_end'
  ✔ pass  'start_tag_42'
  ✔ pass  'start__123_end'
  ✔ pass  'random text without start'
────────────────────────────────────────────────────
✔ All 6 checks passed cleanly. ✦
```

### 2. Transpile Python Regex to bire DSL
Pass a pattern directly, read a file, or pipe via stdin:

```bash
# Inline string:
bire to-human "^[a-zA-Z_][a-zA-Z0-9_]*$"

# Unix pipe:
echo "(?P<user>\w+)@(?P<domain>\w+)" | bire to-human
```

### 3. Transpile bire DSL to Python Regex
```bash
bire to-python "EITHER:\n    LITERAL \"cat\"\nOR:\n    LITERAL \"dog\""
# Output: cat|dog
```

### 4. Verify Equivalence
```bash
bire verify "^hello\d+$" "hello1234"
# Output: ✔ VERIFIED: behavioral equivalence confirmed.
```

---

## ✦ Python API

```python
import bire

# 1. Transpile Python regex to bire human DSL
dsl = bire.to_human(r"(?P<username>[a-z0-9_]+)@(?P<host>[a-z]+)")
print(dsl)

# 2. Transpile bire human DSL back to Python regex
pattern, flags = bire.to_python(dsl)

# 3. Direct compilation from human DSL
compiled = bire.compile_human("""
CAPTURE "code":
    REPEAT EXACTLY 4 TIMES:
        DIGIT
""")
m = compiled.match("1234")
assert m.group("code") == "1234"

# 4. Built-in differential equivalence tester
is_identical = bire.verify(r"(a)(?(1)b|c)", "ab")
assert is_identical is True
```

---

## ✦ DSL Syntax Reference

bire uses a strict 4-space indentation block grammar:

| Construct | Python Regex | bire DSL |
|---|---|---|
| **Literal** | `abc` | `LITERAL "abc"` |
| **Alternation** | `cat\|dog\|bird` | `EITHER:`<br>`    LITERAL "cat"`<br>`OR:`<br>`    LITERAL "dog"`<br>`OR:`<br>`    LITERAL "bird"` |
| **Character Class** | `[a-z0-9_]` | `ONE OF:`<br>`    RANGE "a" TO "z"`<br>`    RANGE "0" TO "9"`<br>`    CHAR "_"` |
| **Negated Class** | `[^0-9]` | `NONE OF:`<br>`    DIGIT` |
| **Greedy Repeat** | `\d+` | `REPEAT ONE OR MORE TIMES:`<br>`    DIGIT` |
| **Lazy Repeat** | `\w+?` | `REPEAT ONE OR MORE TIMES LAZILY:`<br>`    WORD CHARACTER` |
| **Possessive Repeat** | `a*+` | `REPEAT ZERO OR MORE TIMES POSSESSIVELY:`<br>`    LITERAL "a"` |
| **Bounded Repeat** | `a{2,4}` | `REPEAT BETWEEN 2 AND 4 TIMES:`<br>`    LITERAL "a"` |
| **Named Capture** | `(?P<id>\d+)` | `CAPTURE "id":`<br>`    REPEAT ONE OR MORE TIMES:`<br>`        DIGIT` |
| **Atomic Group** | `(?>\w+)` | `ATOMIC GROUP:`<br>`    REPEAT ONE OR MORE TIMES:`<br>`        WORD CHARACTER` |
| **Lookahead** | `(?=@)` | `LOOKAHEAD:`<br>`    LITERAL "@"` |
| **Lookbehind** | `(?<=foo)` | `LOOKBEHIND:`<br>`    LITERAL "foo"` |
| **Conditionals** | `(?(user)yes\|no)` | `IF CAPTURE "user":`<br>`    LITERAL "yes"`<br>`ELSE:`<br>`    LITERAL "no"` |
| **Backreference** | `(?P=user)` / `\1` | `MATCH CAPTURE "user"` / `MATCH CAPTURE 1` |
| **Inline Flags** | `(?i:abc)` | `WITH FLAGS [IGNORECASE]:`<br>`    LITERAL "abc"` |
| **Bytes Mode** | `b"[\x00-\x7f]"` | `MODE: BYTES`<br>`ONE OF:`<br>`    BYTE_RANGE 0x00 TO 0x7f` |

---

## ✦ Compiler Hardening & Invariants

bire implements strict solutions for subtle regex edge cases:

1. **Precedence Wrapping for Repetitions**:
   A quantifier wrapping another quantifier (equal precedence) is wrapped in non-capturing groups `(?:...)`. This prevents `Quantifier(Quantifier(a, *), +)` from collapsing into possessive `a*+`:
   ```python
   # Rendered correctly:
   (?:a*)+  # NOT a*+
   ```

2. **Backreference Digit Collision Protection**:
   In Python regex patterns, `\g<1>` is invalid syntax. Numbered backreferences render as `\1`. When immediately followed by a literal digit, bire wraps the reference:
   ```python
   # Backreference 1 followed by literal '0':
   (a)(?:\1)0  # NOT (a)\10 which fails looking for group 10
   ```

3. **Capture Group Value-Hash Disambiguation**:
   Sibling groups like `(a)(a)` evaluate equally by value in dataclasses. bire assigns every capture group a deterministic, unique pre-order integer `group_id: int` to prevent dictionary collisions.

4. **Anti-ReDoS Differential Property Testing**:
   Tested via Hypothesis with strict safety envelopes: bounded tree depth ($\le 2$), no quantifiers inside quantifiers, small repetitions ($\le 5$), and 1.0s execution timeouts.

---

## ✦ Verification & Testing

bire maintains a zero-skip, zero-xfail standard with $\ge 95\%$ test coverage:

```bash
# Run complete test suite with coverage
uv run pytest --cov=bire --cov-fail-under=95

# Run 105-pattern CPython stdlib regression corpus
uv run pytest tests/integration/test_cpython_corpus.py

# Run 1,000-iteration Hypothesis differential fuzzer
uv run pytest tests/property/test_differential.py

# Type checking & linting
uv run mypy --strict src/ tests/
uv run ruff check src/ tests/
```

---

## ✦ License

MIT License. Developed and maintained by [@ogpourya](https://github.com/ogpourya).
