# Experimental 16-bit DOS port (TandyPy)

This directory preserves the **MicroPython 1.24.1** Python 3 interpreter port built for
16-bit MS-DOS on an Intel 8086-class CPU, including the NEC V20 in a Tandy 1000 EX.
It was developed and tested separately from the current `master` branch.

**Status:** experimental, 16-bit Open Watcom build. A DOSBox 8086-mode run in the
provided November 10, 2026 development archive reported `PASS` for its bundled
smoke, core-language, memory-management, input, and REPL tests. **No physical
Tandy 1000 EX test or independent rebuild is claimed here.**

## Versioning and source changes

The port requires an exact checkout of **MicroPython v1.24.1**, commit
`ecfdd5d6f9be971852003c2049600dc7b3e2a838`. **Do not apply the patch to current
`master`**: this repository has advanced since the port was developed. The
`compat-v1.24.1.patch` file is a complete, reproducible diff of the 31 substantively changed
`py/` source files from the uploaded development snapshot. Its changes include
Open Watcom C compatibility, 16-bit pointer/GC fixes, parse-node alignment,
integer/floating-point conversions, and VM/label adaptations.

Use a **separate source checkout** when building, so the rest of the repository
remains unaffected. The provided Open Watcom distribution from the archive is
not checked into the repository.

## Build on Windows

Prerequisites: Python 3 on the **build PC**, Git, a Windows build of Open Watcom
with `binnt64\wcc.exe` and `binnt64\wlink.exe`, and an optional DOSBox binary
for emulator testing.

Run from this directory (PowerShell):

```powershell
# Obtain the exact MicroPython 1.24.1 source in a separate directory.
git clone https://github.com/micropython/micropython.git C:\src\micropython-v1.24.1
git -C C:\src\micropython-v1.24.1 checkout ecfdd5d6f9be971852003c2049600dc7b3e2a838

# Apply the recorded source changes, then compile using Open Watcom C16.
python prepare_source.py --source C:\src\micropython-v1.24.1
python build.py --source C:\src\micropython-v1.24.1 --watcom C:\watcom

# Optional: run the DOSBox tests (change the path to the installed executable).
python run_dos.py --dosbox 'C:\Program Files (x86)\DOSBox-0.74-3\DOSBox.exe'
```

The output is `build/tandypy.exe`. Copy that executable and your `.PY` files to
the DOS/CF drive. Start with `TANDYPY` for `>>>`, `TANDYPY SCRIPT.PY` for a
file, or `TANDYPY -c "print(1+2)"` for a one-line program.

To exit the console under DOS, use Ctrl-Z followed by Enter. End a multi-line
REPL block with a blank line. The source file path is resolved using DOS
filesystem semantics.

## Demonstrated language features

The bundled `tests/CORE.PY` covers integer division and modulo, big integers,
float/complex arithmetic, UTF-8/Unicode strings, bytes, lists, tuples, dicts,
sets, comprehensions, control flow, closures, default and variadic arguments,
exceptions and `finally`, generators, classes, and importing a neighboring `.PY`
module. `tests/GC.PY` exercises root preservation during repeated collections,
and `tests/REPL.IN` checks recovery from an exception.

This is **not full CPython 3.x**. Many standard-library and extension modules
are unavailable or disabled. The input `-c` option accepts exactly one string
argument. File loading is capped at 24,000 source bytes, the REPL buffer at
2,047 bytes per block, individual input lines at 255 bytes, and the configured
Python GC heap at 48,000 bytes. The default C stack allocation is 16 KiB.
Available conventional RAM and 64 KiB segmented memory limits still apply.
The slice-step limitation is documented in `tests/LIMITS.PY`. Runtime speed and
memory consumption on real 7 MHz V20 hardware are not yet characterized.

## Reproducibility and test evidence

The uploaded DOS executable was an MS-DOS MZ binary, 301,928 bytes, SHA-256:

`1f3cc49a94ecab5790b245b4af1c0739d0e50c8e3ae87bc0a14f22fc155b6e7b`

Its archived DOSBox batch run indicated `PASS` and all `CORE.PY` feature labels
were present. That report is historical evidence, not a current CI result. The
`run_dos.py` runner executes the bundled `.BAT` tests and checks required markers.
A build/test workflow on native Windows or DOSBox is a useful future addition.

The 2026-11-10 upload also contained an experimental `patch_source.py` one-off
mutation helper. This directory deliberately uses **one version-specific Git
patch** instead so that the final source state, including later manual fixes,
can be reconstructed exactly and reviewed.
