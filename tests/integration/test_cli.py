"""Integration tests for bire CLI commands and piping."""

import subprocess
import sys


def test_cli_to_human_and_to_python_pipe() -> None:
    # 1. Pipe regex into `bire to-human`
    p1 = subprocess.run(
        [sys.executable, "-m", "bire.cli", "to-human"],
        input="cat|dog",
        text=True,
        capture_output=True,
        check=False,
    )
    assert p1.returncode == 0
    dsl_output = p1.stdout
    assert "EITHER:" in dsl_output
    assert 'LITERAL "cat"' in dsl_output

    # 2. Pipe DSL into `bire to-python`
    p2 = subprocess.run(
        [sys.executable, "-m", "bire.cli", "to-python"],
        input=dsl_output,
        text=True,
        capture_output=True,
        check=False,
    )
    assert p2.returncode == 0
    assert "cat|dog" in p2.stdout


def test_cli_verify_success_and_failure() -> None:
    # Verify match success -> exit code 0
    p_ok = subprocess.run(
        [sys.executable, "-m", "bire.cli", "verify", "^hello[0-9]+$", "hello1234"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert p_ok.returncode == 0
    assert "VERIFIED" in p_ok.stdout

    # Invalid regex syntax -> exit code 1
    p_err = subprocess.run(
        [sys.executable, "-m", "bire.cli", "verify", "[a-", "input"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert p_err.returncode == 1


def test_cli_demo_and_inline_args() -> None:
    # Test demo command
    p_demo = subprocess.run(
        [sys.executable, "-m", "bire.cli", "demo"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert p_demo.returncode == 0
    assert "bire demo" in p_demo.stdout

    # Test direct inline string argument
    p_inline = subprocess.run(
        [sys.executable, "-m", "bire.cli", "to-human", "a+"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert p_inline.returncode == 0
    assert "REPEAT ONE OR MORE TIMES:" in p_inline.stdout
