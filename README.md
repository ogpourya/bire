# bire

Deterministic, bidirectional transpiler between Python regular expressions and an indentation-based human DSL.

Guarantees behavioral equivalence across standard `re` methods (`search`, `match`, `fullmatch`, `findall`, `split`, `sub`).

## Installation

```bash
uv tool install https://github.com/ogpourya/bire.git --force
```

Or add to an existing project:

```bash
uv add git+https://github.com/ogpourya/bire.git
```

## CLI

```bash
# Run the interactive demo
bire demo

# Regex -> human DSL
bire to-human "^[a-zA-Z_][a-zA-Z0-9_]*$"

# Human DSL -> regex
bire to-python dsl.txt

# Verify behavioral equivalence against sample input
bire verify "^hello\d+$" "hello1234"
```

## Python API

```python
import bire

# Regex -> human DSL
dsl = bire.to_human(r"(?P<user>\w+)@(?P<host>\w+)")

# Human DSL -> regex
pattern, flags = bire.to_python(dsl)

# Direct compilation from human DSL
regex = bire.compile_human("""
CAPTURE "user":
    REPEAT AT LEAST 1 TIMES:
        WORD CHARACTER
""")

# Differential verification
assert bire.verify(r"(a)(?(1)b|c)", "ab") is True
```

## DSL Syntax Reference

| Construct | Python `re` | bire DSL |
|---|---|---|
| Literal | `abc` | `LITERAL "abc"` |
| Alternation | `cat\|dog` | `EITHER:`<br>`    LITERAL "cat"`<br>`OR:`<br>`    LITERAL "dog"` |
| Character set | `[a-z0-9]` | `ONE OF:`<br>`    RANGE "a" TO "z"`<br>`    RANGE "0" TO "9"` |
| Inverted set | `[^0-9]` | `NONE OF:`<br>`    DIGIT` |
| Repeat | `\d+` | `REPEAT ONE OR MORE TIMES:`<br>`    DIGIT` |
| Lazy repeat | `a*?` | `REPEAT ZERO OR MORE TIMES LAZILY:`<br>`    LITERAL "a"` |
| Named capture | `(?P<id>\d+)` | `CAPTURE "id":`<br>`    REPEAT ONE OR MORE TIMES:`<br>`        DIGIT` |
| Lookaround | `(?<=foo)bar` | `LOOKBEHIND:`<br>`    LITERAL "foo"`<br>`LITERAL "bar"` |
| Conditional | `(?(1)a\|b)` | `IF CAPTURE 1:`<br>`    LITERAL "a"`<br>`ELSE:`<br>`    LITERAL "b"` |
| Backreference | `\1` / `(?P=x)` | `MATCH CAPTURE 1` / `MATCH CAPTURE "x"` |

## Test Suite

```bash
uv run pytest --cov=bire --cov-fail-under=95
```

## License

MIT
