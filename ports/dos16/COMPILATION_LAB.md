# Py86 source compilation experiment and real-hardware test plan

This is an opt-in source compilation study. All candidates compile and execute
the original unchanged .PY files at runtime. No .mpy files or bytecode cache
are required. The production Py86 interpreter retains the original compiler
and file loader.

## Why this experiment matters

Three BASE runs on the 7 MHz NEC V20 Tandy 1000 EX averaged 78.378 seconds
from native C main to the first Python statement of DEMO.PY. Three HOT runs
averaged 78.983 seconds. Both completed all 19 feature checks.
The earlier hybrid near-data optimization had no significant overall benefit.

## Compilation stages and profiling

Build the experimental executable with --profile-compile and set
PY86_PROFILE=1 under DOS. A completed source script emits a line such as:

    P86PROF read_ms=0 lexer_ms=0 parse_ms=1099 compile_ms=330 exec_ms=...
    
The fields mean:
- read_ms: time spent in DOS fopen, read and close
- lexer_ms: time to get the first token, excluding the file read
- parse_ms: MicroPython syntax-tree generation
- compile_ms: generation of bytecode from that syntax tree
- exec_ms: Python script execution, including any file I/O or sleep
- gc_free: remaining Python GC heap at the end of the script

The BIOS timer resolution is approximately 55 milliseconds. The source file
read/lexer timing can therefore appear as zero in DOSBox. The total reported
time starts after the DOS MZ executable has loaded, consistent with
time.startup_ms from the interpreter.

## Eight tested build variants

| Variant | Build option | Description |
| --- | --- | --- |
| baseline | --profile-compile | Production compiler settings plus timing |
| chunk32 | --parse-chunk 32 | Parser initial chunks of 32 bytes |
| chunk64 | --parse-chunk 64 | Parser initial chunks of 64 bytes |
| chunk128 | --parse-chunk 128 | Parser initial chunks of 128 bytes |
| loop | --compile-opt loop | Open Watcom -ol only on lexer, parser, compiler, emitter, qstr |
| intrinsic | --compile-opt intrinsic | Open Watcom -oi only on those source files |
| all | --compile-opt all | Open Watcom -oi, -ol, -oe, -oh on those source files |
| direct | --source-loader direct | Read directly into GC-managed lexer input, skipping malloc + memcpy |

All builds retain the 16-bit 8086-compatible -0 target, the same Python
features, and the standard bytecode interpreter. Defaults are parse chunk 16,
compiler-opt baseline, and source-loader original. No experiment is promoted
automatically to the standard release.

The GitHub Actions workflow py86-compile-lab.yml uses pinned MicroPython
1.24.1, Open Watcom and DOSBox Staging, and requires every candidate to:
1. Compile and link.
2. Pass the full DOSBox compatibility suite, including malformed Python
   input, exceptions, filesystem I/O, imports, GC and the feature demo.
3. Complete two independent DEMO.PY compilation profiles.
4. Run ONECLK.PY and SHOW.PY as real unchanged Python source.

Every verified candidate is saved as a standalone DOS 8.3 executable. The
workflow creates PY86-COMPILE-LAB.zip containing only candidates that pass
all tests. This is a GitHub Actions artifact, not a normal production release.

## V20 physical hardware validation

1. Back up PY86.EXE and preserve your current original .PY scripts.
   Extract PY86-COMPILE-LAB.zip in the same directory as DEMO.PY. This does
   not overwrite PY86.EXE.
2. Run RUNB.BAT for the experimental baseline. Verify 19 tests passed and
   failed 0. Note the P86PROF line in BTEST.LOG. Batch files explicitly use
   PY86_HEAP=48000 to keep the GC allocation consistent.
3. Compare the best emulator candidate, initially RUNA.BAT for the compiler
   all-flags build. Its result is saved in ATEST.LOG. Available alternate
   scripts (if their candidates passed): RUN32, RUN64, RUN128, RUNL, RUNI,
   and RUND. Each runs actual DEMO.PY and writes a distinct .LOG.
4. Alternate RUNB and the candidate three times each. Save results from
   every trial before the batch overwrites its log, and compare medians
   of read_ms + lexer_ms + parse_ms + compile_ms.
5. Independently measure first clock-face wall time for each candidate
   against the baseline on the very same CLOCK.PY script. For example,
   P86BASE --home-cls CLOCK.PY and P86ALL --home-cls CLOCK.PY.
   Alternate each three times and use a stopwatch.
6. Verify SHOW.PY and external import tests, and check that memory
   allocation and output match the unmodified production executable.
7. Do not adopt a candidate unless the real V20 shows repeatable improvement
   beyond normal timing variation with no compatibility regression.

If a candidate hangs or crashes, revert immediately to production PY86.EXE,
which is intentionally unchanged.

## Later possible work

A transparent on-disk bytecode cache may ultimately eliminate most repeat
compilation, while preserving .PY as the source of truth. That is a separate
project involving validation of bytecode serialization, version/source
invalidation, 16-bit pointers, and crash safety. It is not part of this
no-cache speed experiment.
