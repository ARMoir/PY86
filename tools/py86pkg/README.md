# py86pkg: PyPI-to-Py86 converter

An **independent modern-PC tool**, checked into the active Py86 DOS port
branch. The 16-bit interpreter, its memory footprint, and its build scripts
are unchanged. Runs on host CPython 3.10+.

This first version is a **static converter and compatibility reporter**, not
a general Python compiler or proof of DOS compatibility. It never executes
downloaded package source or its setup/build scripts.

## Run on a modern PC

From the repo root:

    python tools/py86pkg/py86pkg.py convert https://pypi.org/project/roman/
    python tools/py86pkg/py86pkg.py convert roman --version 5.0
    python tools/py86pkg/py86pkg.py convert --source path/to/unpacked/library
    python tools/py86pkg/py86pkg.py convert --source path/to/archive.whl
    python tools/py86pkg/py86pkg.py convert --source source_dir --strip-docstrings
    python tools/py86pkg/py86pkg.py convert --source source_dir --profile tools/py86pkg/profiles/v20.json

For development, use pip install -e tools/py86pkg to expose a py86pkg
command. No third-party runtime dependencies are needed.

Output is PY86PKG.ZIP containing converted .PY files plus REPORT.JSON and
README.TXT. Exit code 0 means no *statically detected* blockers; code 2 means
the archive was written but manual porting is required; code 1 means the
operation could not complete. Every result is marked **unverified on DOS**.

## Implemented

- Accept PyPI names and project/release URLs. Retrieve source from a
  universal pure-Python wheel (preferred), otherwise a source distribution.
- Verify distribution SHA-256 against PyPI metadata, limit archive sizes,
  read only regular files, and refuse traversal paths and archive links.
- Use Python's AST to remove annotations, prune unused typing imports, lower
  simple f-strings, and optionally strip docstrings.
- Parse/compile transformed code on the host without running package code.
- Report imports needing porting, basic unsupported APIs, modern syntax,
  per-file 24,000-byte source limits, and DOS 8.3 filename violations.
- Record PyPI dependency requirements without installing or hiding them.
- Generate structured compatibility reports and a candidate DOS ZIP.
- Run offline unit tests in a separate GitHub Actions workflow.

## Current limitations

The tool does not recursively convert dependencies, rename long modules,
split files, port native extensions, fully lower match/case, dataclasses or
asyncio, or execute the resulting code in Py86/DOSBox. Conditional or dynamic
imports and missing runtime APIs may escape static analysis. AST reformatting
removes source comments. Removing docstrings can change __doc__ behavior.

The profile is advisory: current builds have had a conservative 48 KB heap
and demonstrated 60 KB auto-sized heap capacity, but free runtime heap varies.
A package is not guaranteed to fit in memory just because its files pass the
24 KB source limit. Review distribution license terms before redistribution.

Run the converter tests without compiling DOS code:

    python -m unittest discover -s tools/py86pkg/tests -v

Future iterations should include a DOSBox smoke-test runner and actual
heap/time checks for the newly converted modules.
