"""Comprehensive real-world production regex suite from open-source libraries.

Patterns sourced from Django, SemVer, Pygments, Werkzeug, Sphinx, and RFCs.
"""

from __future__ import annotations

import re

from bire.api import to_human, to_python, verify

REAL_WORLD_PATTERNS: list[tuple[str, list[str]]] = [
    # 1. Official SemVer 2.0.0 regex (from semver.org)
    (
        r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)(?:-(?P<prerelease>(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(?:\+(?P<buildmetadata>[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$",
        [
            "1.0.0-alpha+001",
            "1.2.3-beta.1",
            "2.0.0+build.1848",
            "0.0.4",
            "1.2.3.4",
            "v1.0.0",
        ],
    ),
    # 2. ISO 8601 UTC / Offset Timestamp (RFC 3339)
    (
        r"^\d{4}-\d{2}-\d{2}[Tt](?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d(?:\.\d+)?(?:[Zz]|[+-](?:[01]\d|2[0-3]):[0-5]\d)$",
        [
            "2026-11-06T05:30:00Z",
            "2026-11-06t12:00:00.123456+02:00",
            "2026-11-06 05:30:00Z",
            "invalid-date",
        ],
    ),
    # 3. RFC 5322 Simplified Email (Production Web Form Validator)
    (
        r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$",
        [
            "user.name+tag@example.sub.domain.co",
            "simple@domain.org",
            "bad..email@domain.com",
            "@domain.com",
        ],
    ),
    # 4. Django URL Path Parameter Pattern
    (
        r"^api/v(?P<version>[1-9]\d*)/(?P<resource>[a-z_-]+)/(?:(?P<id>\d+)/)?$",
        [
            "api/v1/users/42/",
            "api/v2/user-profiles/",
            "api/v0/users/1/",
            "api/v1/users",
        ],
    ),
    # 5. IPv4 Address with strict octet ranges
    (
        r"^(?:(?:25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9]?[0-9])\.){3}(?:25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9]?[0-9])$",
        [
            "127.0.0.1",
            "192.168.1.254",
            "255.255.255.255",
            "256.1.1.1",
            "1.2.3.4.5",
        ],
    ),
    # 6. IPv6 Address Pattern (standard full hex notation)
    (
        r"^(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$",
        [
            "2001:0db8:85a3:0000:0000:8a2e:0370:7334",
            "fe80:0000:0000:0000:0204:61ff:fe9d:f156",
            "1200::AB00:1234::",
        ],
    ),
    # 7. Strict UUID v4 Pattern
    (
        r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-4[0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$",
        [
            "550e8400-e29b-41d4-a716-446655440000",
            "f47ac10b-58cc-4372-a567-0e02b2c3d479",
            "550e8400-e29b-11d4-a716-446655440000",
        ],
    ),
    # 8. Markdown URL / Link extractor
    (
        r"\[(?P<text>[^\]]+)\]\((?P<url>https?://[^\s\)]+)(?:\s+\"(?P<title>[^\"]+)\")?\)",
        [
            '[GitHub](https://github.com/ogpourya/bire "Project")',
            "[Simple](http://example.com)",
            "plain text without link",
        ],
    ),
    # 9. ANSI Terminal Color Escape Sequence
    (
        r"\x1b\[[0-9;]*[mGKF]",
        [
            "\x1b[31;1mError\x1b[0m",
            "\x1b[2K",
            "clean string without ansi",
        ],
    ),
    # 10. HTTP Header Parser (Key: Value with folding)
    (
        r"^(?P<field>[A-Za-z0-9_-]+)\s*:\s*(?P<value>[^\r\n]+)$",
        [
            "Content-Type: application/json; charset=utf-8",
            "X-Forwarded-For: 10.0.0.1",
            ": invalid header",
        ],
    ),
    # 11. CSS Hex Color (#RGB, #RGBA, #RRGGBB, #RRGGBBAA)
    (
        r"^#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$",
        [
            "#fff",
            "#ffff",
            "#1a2b3c",
            "#1a2b3cff",
            "#12",
            "#12345",
        ],
    ),
    # 12. Git Commit Hash (40-char full SHA-1 or 7-8 char short)
    (
        r"^[0-9a-f]{7,40}$",
        [
            "b8470b8",
            "ac33579b2c9365eb7a71621dbb1b9b9a2961c638",
            "not-a-hash",
        ],
    ),
    # 13. Python Variable Identifier
    (
        r"^[a-zA-Z_][a-zA-Z0-9_]*$",
        [
            "__init__",
            "_private_var1",
            "bire_parser",
            "123bad",
            "bad-var",
        ],
    ),
    # 14. JSON Number Lexer Specification
    (
        r"^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?$",
        [
            "0",
            "-42",
            "3.14159",
            "-0.5e10",
            "1E+3",
            "0123",
            ".5",
        ],
    ),
    # 15. Pygments Python String Literal Regex (single or double quoted with escapes)
    (
        r"\"(?:[^\"\\]|\\.)*\"|'(?:[^'\\]|\\.)*'",
        [
            '"hello world"',
            "'single string'",
            '"nested \\"quote\\""',
            "'it\\'s fine'",
            "unquoted",
        ],
    ),
    # 16. Logfmt Line Key-Value Extractor
    (
        r'(?P<key>[a-zA-Z0-9_.-]+)=(?:\"(?P<quoted>[^\"]*)\"|(?P<raw>[^\s]+))',
        [
            'level=info msg="daemon started" duration=4.2s count=42',
            "foo=bar",
        ],
    ),
    # 17. Crontab Time Field Expression
    (
        r"^(?:\*|[0-5]?\d)(?:-(?:\*|[0-5]?\d))?(?:/(?:\*|[0-5]?\d))?$",
        [
            "*",
            "*/5",
            "10-20/2",
            "59",
            "60",
        ],
    ),
    # 18. Multi-line INI Section Header
    (
        r"^\[(?P<section>[a-zA-Z0-9_\.:-]+)\]$",
        [
            "[database.main]",
            "[service:worker-1]",
            "not a section",
        ],
    ),
    # 19. Slugified URL Path
    (
        r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
        [
            "hello-world",
            "fast-bire-parser-2026",
            "-start-dash",
            "trailing-dash-",
        ],
    ),
    # 20. XML / HTML Closing Tag
    (
        r"<\/(?P<tag>[a-zA-Z][a-zA-Z0-9_:-]*)\s*>",
        [
            "</div>",
            "</my-custom_element:v1>",
            "<div/>",
            "plain",
        ],
    ),
    # 21. Quoted CSV field with escaped commas
    (
        r'^"(?P<content>(?:[^"]|"")*)"$',
        [
            '"Hello, world"',
            '""',
            '"Line 1\nLine 2"',
            '"Escaped ""quotes"""',
            'Unquoted,text',
        ],
    ),
    # 22. C / C++ Style Multi-line Comment Block
    (
        r"\/\*[\s\S]*?\*\/",
        [
            "/* inline comment */",
            "/* multi\n * line\n */",
            "/* unclosed comment",
        ],
    ),
    # 23. Semantic Versioning Constraint Expression
    (
        r"^(?P<op>>=|<=|>|<|==|!=|~=)\s*(?P<version>\d+(?:\.\d+)*(?:\.[a-zA-Z0-9]+)?)$",
        [
            ">= 1.2.0",
            "~= 3.12",
            "< 2.0",
            "invalid op 1.0",
        ],
    ),
    # 24. Standard MAC Address (colon or hyphen separated)
    (
        r"^(?:[0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}$",
        [
            "00:1A:2B:3C:4D:5E",
            "00-1a-2b-3c-4d-5e",
            "00:1A:2B:3C:4D",
            "00:1A:2B:3C:4D:5E:6F",
        ],
    ),
    # 25. Python import statement parser
    (
        r"^(?:from\s+(?P<from_mod>[a-zA-Z0-9_.]+)\s+)?import\s+(?P<target>[a-zA-Z0-9_,\s*]+)$",
        [
            "import os, sys",
            "from bire.api import to_human, to_python",
            "from . import indenter",
            "bad import syntax",
        ],
    ),
]


def test_real_world_patterns_differential() -> None:
    for pattern, test_inputs in REAL_WORLD_PATTERNS:
        dsl = to_human(pattern)
        py_trans, flags = to_python(dsl)

        assert isinstance(py_trans, str)
        orig_re = re.compile(pattern)
        trans_re = re.compile(py_trans, flags)

        for s in test_inputs:
            # 1. search
            m1 = orig_re.search(s)
            m2 = trans_re.search(s)
            assert (m1 is None) == (m2 is None), f"search() diverged on {pattern!r} with {s!r}"
            if m1 is not None and m2 is not None:
                assert m1.span() == m2.span(), f"span() diverged on {pattern!r} with {s!r}"
                assert m1.groups() == m2.groups(), f"groups() diverged on {pattern!r} with {s!r}"
                assert m1.groupdict() == m2.groupdict(), f"groupdict() diverged on {pattern!r} with {s!r}"

            # 2. match
            assert (orig_re.match(s) is None) == (trans_re.match(s) is None), f"match() diverged on {pattern!r} with {s!r}"

            # 3. fullmatch
            assert (orig_re.fullmatch(s) is None) == (trans_re.fullmatch(s) is None), f"fullmatch() diverged on {pattern!r} with {s!r}"

            # 4. findall
            assert orig_re.findall(s) == trans_re.findall(s), f"findall() diverged on {pattern!r} with {s!r}"

            # 5. split
            assert orig_re.split(s) == trans_re.split(s), f"split() diverged on {pattern!r} with {s!r}"

            # 6. sub
            assert orig_re.sub("x", s) == trans_re.sub("x", s), f"sub() diverged on {pattern!r} with {s!r}"

            # 7. verify helper
            assert verify(pattern, s), f"verify() returned False on {pattern!r} with {s!r}"


def test_full_rfc5322_email_matcher() -> None:
    from bire.email import RFC5322_EMAIL_REGEX, validate_email

    valid_samples = [
        "simple@example.com",
        "very.common@example.com",
        "disposable.style.email.with+symbol@example.com",
        "other.email-with-hyphen@and.subdomains.example.com",
        "fully-qualified-domain@example.com",
        "user.name+tag+sorting@example.com",
        "x@example.com",
        "example-indeed@strange-example.com",
        "admin@mailserver1.domain.org",
        "example@s.example",
        '" "@example.org',
        '"john..doe"@example.org',
        '"very.unusual.@.unusual.com"@example.com',
        r'"very.(),:;<>[]\".VERY.\"very@\\ \"very\".unusual"@strange.example.com',
        "user%example.com@example.org",
        "user-@example.org",
        "postmaster@[123.123.123.123]",
        "postmaster@[IPv6:2001:0db8:85a3:0000:0000:8a2e:0370:7334]",
    ]

    invalid_samples = [
        "Abc.example.com",
        "A@b@c@example.com",
        'a"b(c)d,e:f;g<h>i[j\\k]l@example.com',
        'just"not"right@example.com',
        'this is"not\\allowed@example.com',
        'this\\ still\\"not\\\\allowed@example.com',
        "user@domain..com",
        "@example.com",
        "user@",
        "user@.example.com",
        "user@example.com.",
        "user@-example.com",
        "user@example-.com",
    ]

    for email in valid_samples:
        valid, local, dom = validate_email(email)
        assert valid is True, f"Failed on valid email: {email}"
        assert local is not None and dom is not None
        assert verify(RFC5322_EMAIL_REGEX, email) is True

    for email in invalid_samples:
        valid, local, dom = validate_email(email)
        assert valid is False, f"Failed on invalid email: {email}"
        assert verify(RFC5322_EMAIL_REGEX, email) is True
