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

## Converting PyPI packages for Py86 (host-side `py86pkg`)

The experimental **[py86pkg converter](../../tools/py86pkg/README.md)** lives
in the same GitHub repository at [`tools/py86pkg/py86pkg.py`](../../tools/py86pkg/py86pkg.py).
It runs with Python 3.10+ on a **modern PC**, not under MS-DOS. It is entirely
separate from the 16-bit Py86 interpreter and does **not** change the
`PY86.EXE` build, runtime performance, or DOS memory usage.

From the **repository root** on the modern PC, convert a PyPI package by name
or URL:

```sh
python tools/py86pkg/py86pkg.py convert https://pypi.org/project/roman/5.2/ --library-only --output ROMAN.ZIP
# Or inspect a local source directory instead of downloading from PyPI:
python tools/py86pkg/py86pkg.py convert --source path/to/library --output PY86PKG.ZIP
```

The converter downloads and verifies the source distribution, performs
conservative source transformations (including stripping type annotations
and lowering supported modern syntax), and writes a ZIP containing the
converted Python files, `REPORT.JSON`, and `README.TXT`. **Always check the
report**: exit code 0 means *no statically detected blockers*, not proven DOS
compatibility; exit code 2 means some manual porting is still required.
An individual source file must fit Py86's 24,000-byte loading limit, and
DOS 8.3 filenames and runtime heap availability still matter.

The pinned **roman 5.2** example uses `--library-only` because the package's
`argparse`-based command-line interface is not supported by Py86. This mode
omits the CLI entrypoints and emits a single DOS-compatible `ROMAN.PY`.
Extract `ROMAN.PY` from `ROMAN.ZIP` onto the DOS/CF drive alongside
`PY86.EXE`. Then try:

```bat
PY86 -c "import roman; print(roman.toRoman(2026))"
REM Expected: MMXXVI
PY86 -c "import roman; print(roman.fromRoman('XLII'))"
REM Expected: 42
```

The [`py86pkg` GitHub Actions workflow](../../.github/workflows/py86pkg.yml)
performs automated host-side converter tests **and** an end-to-end test that
downloads roman 5.2 from PyPI, converts it, builds the real 16-bit `PY86.EXE`,
and executes Roman numeral round-trip and validation tests in **DOSBox
Staging**. The successful reference run is
[GitHub Actions run 43040390458](https://github.com/ARMoir/micropython/actions/runs/43040390458).
DOSBox success is not a substitute for testing on the physical Tandy V20.

Other packages may require manual changes or may be impossible to use with
current Py86 APIs, its memory limits, or native extension restrictions.
The tool does not currently install and convert dependencies recursively.
See the [converter documentation](../../tools/py86pkg/README.md) for its
supported transformations, limitations, and command options.

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
under `tests/pythonclock/`. The DOSBox runner still tests the original
implementation by generating a two-tick `CLKTEST.PY` from its `Clock.py` in
a temporary test folder. The checked-in original sources are never modified.

**The downloadable ZIP now uses a different, optimized clock** assembled into
one generated `CLOCK.PY`. The packager extracts the original face/hand positions
from those checked-in sources and verifies the generated mapping against
the original before packaging. This only changes the bundled release, not
the original PythonClock code.

Native support is provided by a small, registered DOS-backed `os` module
(`os.name == "dos"`, `os.system("cls")` via BIOS video; other commands use
COMMAND.COM through the C runtime) and `time` module (`sleep()` via BIOS timer
and `localtime()` via DOS date/time). A native, registered `datetime` module (`port/moddatetime.c`) supplies
`datetime.datetime.now()`, `today()`, a validated constructor, and the basic
date/time fields. It is built into `PY86.EXE` rather than loaded from a `.PY`
file. It is **not** CPython's full `datetime` module; no timezone support,
date arithmetic, or `timedelta` are implemented. `time.localtime()` takes no positional argument, and sleep
is quantized to BIOS ticks (about 55 ms) with a one-hour call limit.

For the optimized release clock, extract `PY86.EXE`, `CLOCK.PY`, and
`RUNCLK.BAT` from the versioned release ZIP into one DOS directory. No
`datetime.py`, `face.py`, `hour.py`, `minute.py`, or `second.py` is needed.
Then run:

```bat
C:\>RUNCLK
```

To run the original five-file PythonClock instead, use the unchanged files
in `tests/pythonclock/` and invoke `PY86 Clock.py` after copying them to DOS.

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
patch, rebuilds `PY86.EXE`, and packages the generated single-file clock
and feature showcase.

In the **Actions** tab, open the latest **Py86 DOS + PythonClock package** run
and download the **PY86** artifact. GitHub downloads it as **PY86.zip**.
The ZIP has everything at its root (no extra directory or nested ZIP):

- `PY86.EXE` (newly compiled 16-bit DOS interpreter)
- `CLOCK.PY` (optimized single-file derivative of the original PythonClock)
- `DEMO.PY` (self-checking feature showcase and diagnostic logger)
- `RUNCLK.BAT` (starts the optimized clock with flicker-reducing cursor home)
- `RUNTEST.BAT` (runs the feature demo; writes `PY86.LOG`)
- `README.TXT` (DOS startup instructions)

Extract these files into one folder on the DOS/CF drive, then run `RUNCLK`
(or `PY86 CLOCK.PY`). The main build workflow retains the **PY86** Actions
artifact for compatibility. It also publishes a **versioned GitHub Release**
after its interpreter build, DOSBox tests, and packaging succeed. A release
contains the standalone, flat `PY86-<version>.zip` archive.
DOSBox Staging checks the actual 16-bit executable, but is not an exact
8086 CPU simulation or a substitute for testing on a physical V20.


## Automatic build versions and GitHub Releases

Every successful run of the main
[Py86 DOS + PythonClock package](../../.github/workflows/py86-package.yml)
workflow (branch push or manual dispatch) creates a GitHub
[Release](https://github.com/ARMoir/micropython/releases) with a
downloadable DOS-ready ZIP.

Versions use **`0.YY.MM.N`**, for example `0.26.11.42`:

- `YY` and `MM` are the UTC year and month of the build.
- `N` is the increasing GitHub Actions run number for the main workflow.
  It never resets at the start of a month, preventing duplicate tags.
- The tag is `v0.YY.MM.N` and the attached file is `PY86-0.YY.MM.N.zip`.
- `PY86 -V`, `PY86 --version`, the interactive startup banner, and the
  included `README.TXT` report the **same version embedded at compile time**.
- A manual/local build without `PY86_VERSION` is marked with a development
  suffix `.0`, using the local UTC year/month. To specify a local build
  number, set the `PY86_VERSION` environment variable before `build.py`.

The main build validates the DOS executable, runs the complete DOSBox
Staging test suite and benchmarks, and only then publishes the Release.
Failed builds do not create releases. The existing Actions `PY86` artifact
remains available. The converter workflow (`py86pkg`) is **paused for
automatic triggers** and can still be run manually from Actions.

**Installation:** download the newest versioned ZIP from Releases, extract
the files together to a DOS/CF card, and run `PY86 -V` to confirm the
embedded version. `RUNCLK` starts the optimized one-file PythonClock.

## Flicker-free clock redraw on slow DOS hardware

The original PythonClock invokes `os.system("cls")` after displaying each
frame. On a 7 MHz 8086/V20-class machine, recomputing the next frame can
take multiple seconds, leaving the screen blank after an ordinary clear.

Use **`RUNCLK.BAT`**, which clears the DOS screen once (`CLS`) and then
starts `PY86 --home-cls CLOCK.PY`. In this
opt-in mode, `os.system("cls")` homes the BIOS text cursor to row 0, column 0
**without clearing the previous clock**. The next full-sized frame overwrites
the old one; the five original PythonClock source files remain unchanged
in the repository.

The packaged clock also reduces its **own computation**: it runs from a
single `CLOCK.PY`, uses native `time.localtime()` rather than allocating a
new `datetime` object every second, generates the ASCII face only once,
recomputes hour/minute hand overlays only when the minute changes, and uses
a fast join or a single-character splice for the blinking second marker.
The generated face and hand positions are checked against all 1,440
hour/minute combinations from the original functions. This is a design
optimization, not a measured speedup on physical 7 MHz V20 hardware.

Plain `PY86 CLOCK.PY` retains normal `cls` clearing behavior, so other programs
aren't affected. Cursor-home mode is intended for fixed-size full-screen text
programs; differing line lengths or stray output may leave old characters.
The mode assumes a DOS BIOS-compatible text console.


## Full feature showcase and persistent DOS test log

The downloadable release includes **`DEMO.PY`** and **`RUNTEST.BAT`**
beside `PY86.EXE` and the one-file `CLOCK.PY`. Run from DOS:

```bat
C:\>RUNTEST
REM or: PY86 DEMO.PY
TYPE PY86.LOG
```

The demo first shows **native Py86 startup timing**, measured from the
earliest C `main()` instruction to completion of MicroPython initialization
(`time.init_ms()`), then to the first executed Python statements
(`time.startup_ms()`). These values are calculated on the DOS computer
using the approximately **55 ms BIOS timer** and are printed onscreen and
saved to `PY86.LOG`. The second figure includes source parsing, compilation
and initial dispatch; the delta approximates those phases.

**Important:** DOS `COMMAND.COM` and the MZ executable loader operate before
C `main()`, so this measurement does not include the entire time between
typing `RUNTEST` and seeing its first output. It does give us a repeatable
interpreter-startup baseline on the physical V20. Startup does not run on
every frame or every test, and the timer adds no continuing per-bytecode cost.
To measure full shell-to-first-output delay, an external DOS launcher timer
would be required.

In addition to the full screen transcript in `PY86.LOG`, the showcase appends
a line to **`PY86TIME.CSV`** on every run. Its columns are
`date,time,version,init_ms,first_python_ms,dispatch_ms`. This is an
**append-only** 8.3-compatible CSV that survives subsequent runs and is useful
for comparing versions and hardware configurations. The version is read from
the adjacent release `README.TXT` (or `unknown` if unavailable). The
startup timer is sampled before file I/O; CSV writing does not distort it.
`PY86.LOG` remains a fresh per-run screen transcript.

The demo also prints formatted ASCII sections and PASS/FAIL results for **19
feature groups**: integer/big-integer and floating/complex arithmetic,
Unicode/strings, lists/dicts/sets/tuples/comprehensions, classes,
generators, closures, exceptions, the `math`, `random`, `datetime`,
`time`, `re`, `json`, `hashlib`, `errno`, `os` and `gc` modules,
real DOS file I/O, and script arguments. It also shows BIOS-tick timings,
DOS date/time and remaining heap.

Each feature group is now a **live executable example** rather than just a
PASS/FAIL label. It shows the Python operation and the *actual value computed
by Py86*, then prints the check result and elapsed time. For example:

```text
  Integer arithmetic and big ints
    >>> -7 // 3
    output: -3
    >>> 1000000 * 1000000
    output: 1000000000000
  [PASS] Integer arithmetic and big ints

  math
    >>> math.sqrt(144)
    output: 12.0
    >>> math.factorial(5)
    output: 120
  [PASS] math
```

Other examples show live JSON serialization, pattern matches, a SHA-256
digest, object methods and generators, DOS time, file operations and memory
usage. The displayed results are generated by the test, not prewritten
example output. The **complete screen transcript** is also written to
**`PY86.LOG`** in the current directory and reset at the start of each run.

This is a representative, user-facing demonstration, **not** a claim that
all CPython APIs are implemented. It exits with a nonzero DOS errorlevel
if any group fails. The main GitHub Actions DOSBox suite runs both this
program and a bounded two-frame test of the generated `CLOCK.PY`, requires
19 PASS entries, verifies that both the screen and log contain the
executed operations and outputs, and checks that the two transcripts match.
The original five-file clock integration test remains in CI as well.

The generator is [`gen_clock.py`](gen_clock.py), and the user-facing
showcase source is [`examples/DEMO.PY`](examples/DEMO.PY). The
original `tests/pythonclock/` sources remain untouched.

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
strings, and leaves UTF-8 multibyte handling on the original path.
A second opt-in optimization, `--string-mode lazy-hash`, avoids eagerly
re-hashing intermediate concatenated strings that are never used as dictionary
keys. A hash value of zero already means "not computed" in MicroPython; the
new `runtime.c` fast path memoizes the hash upon its first request. This
preserves equality, hashing and dictionary-key semantics. `both` tests the
two changes together. The combined version passed the DOSBox correctness suite and delivered a
measured speed improvement, so it is now the production default. Use the
original build mode to reproduce pre-optimization behavior. All timings are DOSBox 8086
`cycles=fixed 20000`, quantized to roughly 55 ms by BIOS ticks; they are
not physical V20 benchmarks.


**Profiling isolation:** The first full-in-one-process run hit the 48 KB
heap after repeated concatenation (though all original interpreter and
module tests passed). The profile now runs split/concat/join and the three
clock-frame samples in separate Py86 interpreter processes per GC threshold.
It still records three consecutive concatenation trials within one process,
including reclaimed memory, to expose heap retention without contaminating
the subsequent clock benchmark. This changes the benchmark harness only, not
the PythonClock sources or production interpreter.


### Optional lazy hashing of temporary strings

`--string-mode lazy-hash` experimentally changes the MicroPython v1.24.1
string constructor to store a zero (uncomputed) hash for new strings, avoiding
an entire eager hash pass over each intermediate result during repeated
`str += char`. When a string or bytes object is later hashed for a dictionary,
`runtime.c` computes and memoizes its hash on first use. `STRHASH.PY`
verifies equality, Unicode, bytes and dictionary-key behavior for every
variant. The `--string-mode both` build combines lazy hashing with the ASCII
QSTR cache. Both optimizations are enabled by default. Use `--string-mode original`
to turn them off, or the individual modes to isolate their effects.


### Default string optimizations (measured)

The four-mode DOSBox comparison showed **25% higher throughput for repeated
string concatenation** with deferred hash calculation, and roughly **14%
higher throughput** for the PythonClock frame benchmark when lazy hashing
and ASCII character QSTR caching are combined. Python GC heap is unchanged;
the combined executable is 32 bytes larger than the unoptimized version.
Production builds use `--string-mode both`; `original` restores the old
behavior, `char-cache` and `lazy-hash` isolate changes.

The GC experiments favored the existing allocation-failure policy for speed.
More frequent collections provided more post-collection free heap but slowed
execution, so the default GC threshold is unchanged. See `PERFORMANCE.md`.
The costly four-configuration profile is manually dispatched, while normal
push CI continues to execute all correctness tests and a production benchmark.


## 16-bit VM dispatch and segmented memory experiments

The `build.py --vm-mode` option permits a controlled comparison of six
8086-compatible builds: `baseline` (production, -ot and -zt=256),
`fast-decode` (fast one-byte variable-length operand decode), `compiler`
(Open Watcom -oi -ol -oe -oh), `far128` (-zt=128),
`near384` (-zt=384), and `combined` (fast decode plus compiler flags,
at the normal -zt=256 threshold). These options do not require a 286,
change the 48 KB GC heap, or alter PythonClock's sources.

`MICROPY_OPT_COMPUTED_GOTO` uses GCC's labels-as-values extension and is not
supported by the Open Watcom C16 compiler; Py86 retains its portable
`switch` VM dispatch. The experiment measures actual Python opcode
execution, ordinary library workloads and PythonClock frame computation.
It compiles every variant, runs the full DOSBox correctness suite, and
uploads linker maps to inspect the 16-bit default data-group size.
The 64 KB near-data limit means some higher -zt thresholds may not link.
All results are DOSBox emulator comparisons, not 7 MHz V20 measurements;
production remains on baseline flags until a candidate is verified.


### Isolating Watcom optimization options

The first six-build VM experiment confirmed `-oi -ol -oe -oh` together
improved Python function-call throughput by about 17.6% and bound-method
calls by about 15.4%, although PythonClock was unchanged. More aggressive
far data placement (128-byte threshold) reduced DGROUP from 61,536 to
58,400 bytes but slowed dictionary and attribute lookups by around 14%; a
384-byte near threshold made no measurable difference. One-byte-specialized
operand decoding slowed instance attribute reads and increased the VM code
size, so it is not enabled. The standard compiler remains `-ot -zt=256`.

The follow-up Watcom-isolation experiment tests `--vm-mode inline` (`-oe`),
`intrinsic` (`-oi`), `loop` (`-ol`), `reopt` (`-oh`) and `compiler`
(all four), each against baseline with the same regression tests and opcode
benchmarks. Its purpose is to isolate the call-speedup from the 4.7 KB
executable growth before selecting any production compiler flag.


### VM and near/far memory results

Two complete DOSBox studies compared six variants each. `-zt=128` reduced
near/static data use from 61,536 to 58,400 bytes but slowed dictionary and
instance attribute reads by around 14%. Increasing the threshold to 384
bytes had no effect. A fast one-byte operand decoder did not improve the VM.

The `-ol` loop optimization improved function and bound-method throughput
by about 15–18% in DOSBox, but increased the executable by 2,656 bytes and
slowed one instance-attribute workload. All four compiler optimization flags
together delivered comparable call gains without a measured attribute loss,
but cost 4,672 bytes and did not measurably improve PythonClock.

As a result, the standard interpreter retains its existing Open Watcom flags
and 8086 CPU target. Use `--vm-mode loop` or `--vm-mode compiler` to create
an experimental call-optimized executable; all variants are covered by the
manually dispatched full benchmark workflows. The documented results are
emulator-only; the physical 7 MHz V20 is the decisive performance test.
See `PERFORMANCE.md` for full numbers and workflow links.


## Exiting to DOS: exit(), quit(), and sys.exit()

Py86 provides native `exit()` and `quit()` builtins at the interactive
prompt and inside normal Python scripts. They work without loading external
Python modules. Both raise `SystemExit`, so Python code can intercept them
with `except SystemExit` if desired. `import sys; sys.exit(...)` and direct
`raise SystemExit(...)` use the same host exit handling.

```python
exit()       # leave REPL or script, DOS ERRORLEVEL 0
quit()       # same
exit(7)      # DOS ERRORLEVEL 7
import sys
sys.exit(3)  # DOS ERRORLEVEL 3
```

When uncaught, `SystemExit` terminates the Py86 process cleanly without a
traceback. No argument, `None` and integer 0 return ERRORLEVEL 0; numeric
codes use DOS's 8-bit exit status (modulo 256), including negative values.
A nonnumeric value such as `sys.exit('message')` prints the message and
returns ERRORLEVEL 1. Other exceptions still print tracebacks and return
ERRORLEVEL 1 for scripts; the interactive interpreter continues after them.
Ctrl+Z followed by Enter continues to exit the interactive prompt.

The DOSBox integration suite now tests exit/quit/sys.exit in both scripts and
the REPL, exact DOS ERRORLEVEL values, no execution after exit, and caught
SystemExit exceptions. The pinned-source `compat-exit-v1.24.1.patch` only
exposes the Py86 host function in MicroPython's existing builtins table.


Note: Every DOSBox test script must have a DOS 8.3 filename. The runner
validates flat test files and refuses long names instead of letting DOS
silently truncate them (for example `EXCATCH.PY`, not `EXITCATCH.PY`).


## Keyboard interrupt and built-in help

The native DOS host now polls BIOS keyboard input using INT 16h only when
stdin is a console and only once per 256 VM branches. A Ctrl+C key is consumed
and turned into a MicroPython `KeyboardInterrupt` at the VM pending-exception
check. Ordinary keyboard input is left in the BIOS buffer. The DOS SIGINT
handler only sets a flag, with all Python exception handling deferred to a safe
VM boundary. The DOS BIOS-timer `time.sleep()` loop also checks for pending
interrupts. Ctrl+C is expected to recover to the REPL or be catchable in a
Python `try/except KeyboardInterrupt` block. Existing Ctrl+Z, Enter for DOS
REPL exit remains available. Redirected stdin is not polled through BIOS.

`help()` uses MicroPython's native help implementation with a Py86-specific
small welcome message and `help(obj)` support, compiled into the executable.
The DOSBox integration tests cover `help()`, `help(list)`, and a deterministic
pending-keyboard-interrupt injection during an infinite loop and BIOS sleep
(using the test-only `PY86_TEST_CTRLC` DOS environment variable). They do not
substitute for a physical keyboard Ctrl+C test on the actual Tandy V20.


## Reading and writing DOS files with open()

Py86 includes the native `open(path, mode='r')` built-in. It supports DOS
text and binary files, modes `r`, `w`, `a`, optionally `+` and `b` or
`t`, and a file object with `read()`, `readline()`, `readlines()`,
`write()`, `seek()`, `tell()`, `flush()`, and `close()`.
Use `with open(...) as f:` for automatic file closure. Text mode uses
Open Watcom's DOS CRT translation for CRLF. Binary mode preserves bytes.

Example:

```python
with open('NOTES.TXT', 'w') as f:
    f.write('Hello Tandy!\\n')
with open('NOTES.TXT', 'r') as f:
    print(f.read())
```

File handling uses native C `FILE*` and MicroPython stream APIs, rather
than importing external libraries. DOS 8.3 filenames are safest. The current
48 KB Python heap limits how much content can be held in one Python string;
use bounded `read(n)` for large files. Explicitly close open handles when
not using a context manager. Advanced CPython `open()` features such as
encoding conversion, buffering control, `x` exclusive-create mode and
complete `io` module compatibility are not yet implemented.


### DOS file I/O and command-line compatibility additions (Nov 2026)

`open()` file objects now implement `readinto(buffer)` using MicroPython's
existing stream buffer protocol and `writelines(iterable)` using the existing
DOS writer. Neither requires allocating a new Python string per operation.
An alternate C `readline(size=-1)` and native iterator use buffered
Watcom `fgetc` instead of the generic MicroPython stream calls. The DOSBox
A/B test found **no improvement for direct readline() and a 25% slowdown in
the short file-iteration trial**, with only 55ms BIOS timer resolution.
Therefore the **original generic MicroPython reader remains the production
default**. Use `build.py --file-readline-mode fast` to experiment with the
alternative reader; both pass the same text and binary tests.

`help('modules')` lists compiled MicroPython/Py86 modules.
`PY86 -h` / `--help` shows command usage; `PY86 -V` / `--version`
shows the interpreter version and target architecture. Python command
`PY86 -c "code" [arguments...]` now sets `sys.argv[0]` to `-c`, omits
the command string from `sys.argv`, and passes the subsequent arguments.
Running scripts retains `sys.argv[0]` as the script filename. The interactive
REPL sets it to an empty string. A missing `-c` command returns DOS
`ERRORLEVEL 2`. All options retain `--home-cls` compatibility.


## Automatic conventional-memory-aware Python heap sizing

Py86 now attempts a larger single-segment Python heap at startup, starting
at **60,000 bytes** and backing down through 56,000, 52,000, 48,000,
44,000, 40,000, 36,000, 32,000, 28,000 and **24,000 bytes** if a suitable
allocation is not available. This uses the Open Watcom large-model *far*
heap, not a 64 KB static near-DGROUP allocation. Each candidate is checked
against the 16-bit far-pointer offset boundary (guarded at 0xFFF0) and must
leave a testable 32 KB contiguous native allocation for DOS and source I/O.
All heap allocations still remain in one 64 KB-addressable segment.

The default mode is automatic, and prints no additional text when running
a normal Python script. From DOS:

```bat
PY86 --heap-info
REM Example on a machine with enough free memory:
REM heap_bytes=60000 gc_total=... gc_free=... mode=auto
SET PY86_HEAP=48000
PY86 --heap-info
SET PY86_HEAP=
SET PY86_HEAP_MAX=32000
PY86 --heap-info
SET PY86_HEAP_MAX=
```

`PY86_HEAP` requests an exact heap size, `PY86_HEAP_MAX` caps automatic
selection. Accepted numeric values are 24,000 through 60,000, multiples
of 16. Invalid or unallocatable sizes return DOS `ERRORLEVEL 2`.
Python still uses `gc.mem_free()` / `gc.mem_alloc()` to inspect usable
GC memory. `heap_bytes` is the raw far allocation including MicroPython's
allocation bitmap; `gc_total` is usable GC pool after its metadata.
The 32 KB native headroom probe is freed after selection and does not
reserve that amount against later DOS allocations.

This is **not** a multi-segment Python heap, does not consume EMS/XMS, and
cannot give a 286 with more RAM a >64 KB Python heap. Enlarging beyond
60 KB requires first validating split-GC root tracking and segmented
pointer arithmetic, then a separate multi-block allocator design.

The DOSBox integration suite checks forced 24K, 48K and 60K modes,
32K auto caps, invalid input, GC allocations and roots. The real V20
should still be used to verify native-memory margins and performance.


### Verified adaptive heap results

The initial DOSBox validation selected a **60,000-byte** raw far heap with
**58,912 GC bytes free** immediately after startup, compared to
**47,136 free** using the prior fixed 48,000-byte setting. All existing
PythonClock and library tests passed. The fixed-versus-auto benchmarking
showed mixed instruction-level performance, not a reliable speed improvement;
the benefit is principally **25% more live Python storage** in the tested
DOSBox configuration. See `PERFORMANCE.md` for the full comparison.

To test the selection on a real DOS machine run `PY86 --heap-info`.
For conservative operation use `SET PY86_HEAP=48000`; restore adaptive
operation with `SET PY86_HEAP=`. This preserves the original proven size
without rebuilding. A low-memory DOS installation may select a smaller heap.
