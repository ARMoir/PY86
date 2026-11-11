# Py86: Python 3 for 16-bit DOS

**Py86** is an experimental Python 3 interpreter for 16-bit MS-DOS, based on
**MicroPython 1.24.1**. It targets Intel 8086/8088-class CPUs and compatibles,
including NEC V20 machines such as the Tandy 1000 EX.
It was developed and tested separately from the current `master` branch.

**Status:** experimental 16-bit Open Watcom build. GitHub Actions now
rebuilds and packages Py86 successfully. The original PythonClock has run on
physical Tandy 1000 EX hardware, but the newly expanded modules have not yet
been tested there. Older archived DOSBox tests reported `PASS`; these were
not a fresh emulator test of the expanded module build.

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

The output is `build/py86.exe` (`PY86.EXE` on DOS). Copy it and your `.PY`
files to the DOS/CF drive. Start with `PY86` for the interactive `>>>` prompt,
`PY86 SCRIPT.PY` for a file, or `PY86 -c "print(1+2)"` for a one-line program.

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

The original pre-rename `TANDYPY.EXE` in the uploaded development archive
was an MS-DOS MZ binary, 301,928 bytes, SHA-256:

`1f3cc49a94ecab5790b245b4af1c0739d0e50c8e3ae87bc0a14f22fc155b6e7b`

The historical SHA-256 above identifies the original executable, **not** a
newly compiled `PY86.EXE`. Rebuild with `build.py` to produce the renamed program.

Its archived DOSBox batch run indicated `PASS` and all `CORE.PY` feature labels
were present. That report is historical evidence, not a current CI result. The
`run_dos.py` runner executes the bundled `.BAT` tests and checks required markers.
A build/test workflow on native Windows or DOSBox is a useful future addition.

The 2026-11-10 upload also contained an experimental `patch_source.py` one-off
mutation helper. This directory deliberately uses **one version-specific Git
patch** instead so that the final source state, including later manual fixes,
can be reconstructed exactly and reviewed.

## PythonClock integration (unchanged application)

The five original source files from
[ARMoir/PythonClock](https://github.com/ARMoir/PythonClock), pinned to
commit `3f1a7040e1e374238f59d9da3087679368c2cb70`, are stored unchanged
under `tests/pythonclock/`. The DOSBox runner stages them along with Py86's
`datetime.py` shim and generates a two-tick `CLKTEST.PY` from the original
`Clock.py` by changing only its loop bound in the disposable DOSBox staging
folder, leaving the checked-in application source unmodified.

Native support is provided by a small, registered DOS-backed `os` module
(`os.name == "dos"`, `os.system("cls")` via BIOS video; other commands use
COMMAND.COM through the C runtime) and `time` module (`sleep()` via BIOS timer
and `localtime()` via DOS date/time). A native, registered `datetime` module (`port/moddatetime.c`) supplies
`datetime.datetime.now()`, `today()`, a validated constructor, and the basic
date/time fields. It is built into `PY86.EXE` rather than loaded from a `.PY`
file. It is **not** CPython's full `datetime` module; no timezone support,
date arithmetic, or `timedelta` are implemented. `time.localtime()` takes no positional argument, and sleep
is quantized to BIOS ticks (about 55 ms) with a one-hour call limit.

For the unchanged clock, copy `PY86.EXE`, `Clock.py`, `face.py`, `hour.py`,
`minute.py`, and `second.py` into the same DOS working directory. No
`datetime.py` is required. Then run:

```
C:\>PY86 CLOCK.PY
```

**Verification:** the current Py86 interpreter builds in GitHub Actions and
PythonClock has been observed on real Tandy hardware. A new DOSBox integration
run and real-hardware checks of the expanded standard library remain outstanding. Text-mode BIOS screen
clearing may behave differently in graphics modes; the intended target is a
standard DOS text console. The clock's drawing routines are unchanged.


## GitHub Actions: ready-to-run PythonClock package

Every push to `tandypy-dos16-port` (and `master` after this port merges) runs
[the Py86 package workflow](../../.github/workflows/py86-package.yml).
It checks out the pinned MicroPython v1.24.1 core, downloads the pinned
**2026-11-01 Open Watcom Linux x64 snapshot**, applies the DOS compatibility
patch, rebuilds `PY86.EXE`, and packages the unchanged clock files.

In the **Actions** tab, open the latest **Py86 DOS + PythonClock package** run
and download the **PY86** artifact. GitHub downloads it as **PY86.zip**.
The ZIP has everything at its root (no extra directory or nested ZIP):

- `PY86.EXE` (newly compiled 16-bit DOS interpreter)
- `Clock.py`, `face.py`, `hour.py`, `minute.py`, `second.py` (original,
  unchanged PythonClock files)
- `RUNCLK.BAT` (launches the unchanged clock)
- `README.TXT` (DOS startup instructions)

Extract these files into one folder on the DOS/CF drive, then run `RUNCLK`
(or `PY86 CLOCK.PY`). The Actions workflow produces a package **artifact only**
(no release publishing, deployment, or automatic firmware/CF image writing).
Before publishing the ZIP, the GitHub Actions job now runs the DOSBox 8086
integration suite, including the clock and module tests. This is an emulator
check, not proof of compatibility with every physical DOS machine.


## Flicker-free clock redraw on slow DOS hardware

The original PythonClock invokes `os.system("cls")` after displaying each
frame. On a 7 MHz 8086/V20-class machine, recomputing the next frame can
take multiple seconds, leaving the screen blank after an ordinary clear.

Use **`RUNCLK.BAT`**, which starts `PY86 --home-cls CLOCK.PY`. In this
opt-in mode, `os.system("cls")` homes the BIOS text cursor to row 0, column 0
**without clearing the previous clock**. The next full-sized frame overwrites
the old one; the five original PythonClock source files remain unchanged.
This improves perceived redraw smoothness but not Python execution speed.

Plain `PY86 CLOCK.PY` retains normal `cls` clearing behavior, so other programs
aren't affected. Cursor-home mode is intended for fixed-size full-screen text
programs; differing line lengths or stray output may leave old characters.
The mode assumes a DOS BIOS-compatible text console.


## Expanded standard-library imports (16-bit DOS)

The DOS build enables MicroPython 1.24.1's C-backed **`math`** and
**`random`** modules and extends Py86's DOS-backed **`os`** and **`time`**
modules. The goal is usable Python 3 APIs without needing newer x86 hardware.

| Import | Available APIs in this port |
| --- | --- |
| `math` | Core math functions such as `sqrt`, `sin`, `cos`, `tan`, `log`, `exp`, `floor`, `ceil`, `isclose`, `factorial`, plus `pi` and `e` |
| `random` | Upstream MicroPython native generator: `seed`, `getrandbits`, `random`, `randrange`, `randint`, `choice`, `uniform` |
| `os` | `name='dos'`, `sep`, `system`, `getcwd`, `chdir`, `listdir`, `mkdir`, `rmdir`, `rename`, `remove`, `unlink`, `stat`, `getenv` |
| `time` | `sleep`, `sleep_ms`, `time`, `localtime` (current time or supplied timestamp), `ticks_ms`, `ticks_diff` |

### Known limitations

- `math.tau`, `math.inf`, `math.nan` are disabled because Open Watcom C16
  does not support their required compile-time constant expressions.
- `random` uses a **non-cryptographic** pseudo-random number generator. It is
  not the full CPython `random` API (`shuffle`, `sample`, distributions, etc.).
  Seed it explicitly for repeatable results.
- DOS filesystem names are limited by the native DOS/Watcom interfaces
  (normally 8.3 under DOS 6.22); `os.path` is not implemented.
  `os.stat` returns a 10-element stat tuple, but POSIX metadata fields are
  not necessarily meaningful on DOS.
- `time` uses the DOS wall clock and BIOS ticks, which have approximately
  **55 ms** resolution. `ticks_ms` wraps each DOS day, and `ticks_diff`
  handles that wrap for sufficiently short intervals. Date/time timezone
  conversion depends on the DOS C runtime, not a zone-information database.
  Dates after the 32-bit `time_t` limit may not work.
- This is not the complete CPython standard library. The existing 48 KB
  Python heap and 16-bit real-mode memory restrictions still apply.

The new `tests/LIBTEST.PY` exercises representative functionality from all
four modules, including DOS directory/file operations, seeded random sequences,
mathematical functions, and BIOS-tick sleeps. The DOSBox test runner includes
it, but the automatic GitHub Actions workflow remains **build/package only**.
A successful CI build is not a claim that these APIs have been exercised on
the physical Tandy.


## Built-in `datetime` (no shim file)

Py86 registers a small **native C `datetime` module**. The PythonClock source
remains exactly as originally written: `import datetime` and
`datetime.datetime.now()` work without `datetime.py` on the DOS drive.
It also provides `datetime.datetime.today()`, and a constructor supporting
`year, month, day, hour, minute, second, microsecond` with positional or
keyword arguments. Objects have read-only fields; DOS time supplies hundredths
of a second for `microsecond`. Timezone conversion, formatting methods,
`timedelta`, and date arithmetic are not yet implemented.

The DOSBox `CLOCKAPI.PY` test exercises the built-in constructor and clock
and the harness explicitly removes stale `datetime.py` from the test stage.


## Built-in json, errno, re, and hashlib (16-bit DOS)

The following modules are included directly in PY86.EXE with the other native
modules (no additional .PY files are required):

- `json`: `loads()` and `dumps()` handle strings, numbers, lists, dicts,
  booleans, and null. `load()`/`dump()` require a Python stream object;
  conventional Python `open()` is not yet available in this port.
- `errno`: DOS-compatible integer error constants such as `ENOENT`,
  `EEXIST`, and `EINVAL`.
- `re`: MicroPython's lightweight regex engine with `match`, `search`,
  `compile`, `sub`, groups, and spans. It is not full CPython regex syntax.
- `hashlib`: Native SHA-256 with `hashlib.sha256(data)`, `update()`, and
  `digest()`. SHA-1, MD5, and CPython's full hash API aren't included.

The compatibility patch `compat-extra-libs-v1.24.1.patch` fixes 16-bit
compiler limitations (flexible array members, JSON C initializers, and the
SHA-256 32-bit word type) against the pinned MicroPython v1.24.1 source.
Open Watcom's `-zt=256` flag moves larger static objects into far data to
keep the 16-bit near-data group below 64 KB without reducing the 48 KB
Python heap or the existing 16 KB C stack.

The `tests/MODTEST.PY` file verifies native imports, JSON round trips,
regular expressions and captures, errno constants, and SHA-256 published
reference digests (including incremental hashing). GitHub Actions now installs
DOSBox and uses `xvfb-run` to execute the actual 8086 DOS executable.
Packaging only proceeds after the DOSBox integration suite passes; on
failure the CI uploads `PY86-test-logs` for debugging. The emulator test is
not a substitute for testing on the real 7 MHz V20.


### SHA-256 on 16-bit DOS: regression correction

The first GitHub DOSBox run after enabling Actions identified a genuine 16-bit
integer-promotion bug in the upstream SHA-256 block reader. Although SHA-256 of
the empty string passed, the `abc` vector failed because `data[j+1] << 16`
shifted a promoted 16-bit integer. The compatibility patch now widens **every**
input byte to `uint32_t` before shifting. The test also covers a full 64-byte
block, in addition to empty and `abc` reference digests.


## Performance baseline (DOSBox, not a real V20 measurement)

Run `python run_bench.py --dosbox /path/to/dosbox --mode baseline` after
building `PY86.EXE`. Tests execute the **real 16-bit DOS executable** in
DOSBox `core=normal, cputype=8086, cycles=fixed 20000`. The BIOS timer's
roughly 55 ms resolution is handled by scaling each loop to at least 450 ms
where possible and reporting three trials with median milliseconds per unit.

`BENCH1.PY` measures local/global integer operations, dictionary lookups,
instance attributes, method calls, module attributes and repeated string
concatenation. `FRAMEBEN.PY` uses the original PythonClock face/hour/minute/
second modules, times its frame computation *without* rendering or sleep, and
leaves all original PythonClock files unchanged.

GitHub Actions uploads the `PY86-baseline` JSON measurements. Compare on the
same DOSBox configuration; the reported speeds are not 7 MHz V20 performance
figures. Run the same scripts on real hardware for definitive speed results.


The frame benchmark launches three fresh Py86 processes and renders two
frames per process. This avoids invalidating measurements by accumulating
long-lived allocations in the 48 KB interpreter heap during calibration.


## Lookup optimization comparison (experimental)

`build.py --lookup-mode` supports `off` (the default production build),
`map` (MicroPython's map lookup cache), `attr` (instance attribute fast path),
and `both`. These flags are applied at C compilation time, not by loading
modules dynamically. Default `PY86.EXE` remains unchanged until measured
correctness and speed justify enabling them.

The `Py86 lookup optimization experiment` GitHub Actions workflow builds
all four configurations using identical pinned MicroPython/Open Watcom versions
and DOSBox CPU settings, runs the existing correctness tests on each, and
measures the same eight benchmarks in each. It uploads JSON measurements and
`lookup-comparison.md`, with speedup percentages compared to the `off`
configuration on that same runner. Clock frame results omit its sleep/printing,
and report time per frame. The experiment only measures simulated 8086 behavior,
so promising variants should also be tested on the physical NEC V20.


### Default optimization decision (DOSBox comparison)

The four-variant DOSBox comparison on the same runner found `map` cache
increased throughput by roughly 10% for global variables, 16.7% for dict
lookups, and 33.3% for instance attributes, with just 320 additional EXE bytes
and no reduction in `gc.mem_free()` in the benchmark. `attr` fast path alone
was less consistent and adding it to `map` did not improve the measured clock
frame workload, so the production default is **`map` only**. Results are
quantized to ~55 ms and are not measurements on a physical NEC V20. The 48 KB
Python heap remains unchanged.

`python build.py --source ... --watcom ...` produces the recommended map-cache
version. Use `--lookup-mode off` for an exact unoptimized comparison, or
`--lookup-mode attr` / `both` for further experiments. CI separately compares
all four modes and publishes `PY86-lookup-comparison`. The main package job
publishes the current production metrics in `PY86-perf-production`.

`LOOKUP.PY` asserts that cached dictionary and attribute lookups continue to
reflect mutations and deletions, and is included in the mandatory DOSBox suite.


## String concatenation and garbage-collection profiling

The `Py86 string and GC profiling experiment` workflow builds two 8086-compatible
executables: the unchanged production engine (`--string-mode original`) and an
experimental one-character ASCII QSTR lookup cache (`--string-mode char-cache`).
Both retain the production map-lookup optimization, 48 KB Python GC heap,
16 KB C stack, source-level Python compatibility, and unmodified PythonClock.

`tests/bench/STRGC.PY` compares string iteration, repeated `str += char`,
`"".join(chars)`, and PythonClock frame assembly. It runs with fresh processes
at `gc.threshold(-1)` (default allocation-failure collection), 4096, 8192, and
16384 byte thresholds. Reports include elapsed duration, free bytes before,
free bytes before/after an explicit GC, and measured explicit-GC duration.
The script does not change production GC settings. A separate
`run_bench.py` run measures the original microbenchmarks and clock frames.

The alternate ASCII cache stores only interned QSTR identifiers, not mutable
strings, and leaves UTF-8 multibyte handling on the original path. The
experimental cache must not become the default without runtime correctness
testing and a measurable improvement. All timings are DOSBox 8086
`cycles=fixed 20000`, quantized to roughly 55 ms by BIOS ticks; they are
not physical V20 benchmarks.
