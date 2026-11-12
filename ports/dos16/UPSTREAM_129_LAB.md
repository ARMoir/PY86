# Py86 NEC V20: MicroPython 1.24.1 vs 1.29.0

The normal production PY86.EXE stays on MicroPython 1.24.1.
These are independently compiled experimental 8086/V20 DOS executables.

Four 8086 configurations use an identical -zt=128 near-data threshold
so the comparison remains fair. This differs from the earlier production
-zt=256 setting; do not directly compare these experimental clock speeds
to the former production benchmark without accounting for the layout.

| Executable | Upstream core | Parser | Watcom compiler flags |
|---|---|---|---|
| P24BASE.EXE | 1.24.1 | Original | Original |
| P24OPT.EXE | 1.24.1 | Fixed 1 KB | -oi -ol -oe -oh on parser/compiler |
| P29BASE.EXE | 1.29.0 | Original | Original |
| P29OPT.EXE | 1.29.0 | Fixed 1 KB | -oi -ol -oe -oh on parser/compiler |

v1.29.0 is pinned to commit 0fd6c573ea815774668bbb16b8e197c8822368b2.
v1.24.1 is pinned to commit ecfdd5d6f9be971852003c2049600dc7b3e2a838.
The original Python syntax, modules, and benchmark scripts are unchanged.

The 1.29 adaptation rebases ten source conflicts, including gc.c,
formatfloat.c, objint.c, runtime.h, stream.c, lexer.c and vm.c. Only
the isolated upstream checkout is modified. The core patches for optional
modules, string cache, lazy hashing, VM decode and exit compatibility are
reapplied separately; the original MicroPython license is respected.

## Automated qualification

Each executable must pass the full 8086 DOSBox regression suite, the
19-feature DEMO.PY twice, ONECLK.PY, SHOW.PY, parser stress PARSST.PY
and runtime stress RUNTST.PY. Native P86PROF and P86RUNT lines capture
source read, lexer, parse, compile, execution, GC activity and heap usage.

Only four passing builds are packaged. A successful DOSBox result does
not prove real-hardware stability, compatibility or performance.

## Testing on an original Tandy 1000 EX

The safest initial approach is to unzip PY86-UPSTREAM-129-LAB.zip
into an existing DOS folder on the CF drive; do not replace PY86.EXE.

RUNVER displays each core version.
RUN4 runs the four 19-feature demos once, creating
B0.LOG = 1.24 BASE; O0.LOG = 1.24 1KA;
N0.LOG = 1.29 BASE; P0.LOG = 1.29 1KA.
It also exercises 1.29 parser/VM stress scripts.

Only after RUN4 passes (19/19 every time) run RUN12, which alternates
B,O,N,P three times. Results B1-B3.LOG, O1-O3.LOG, N1-N3.LOG and
P1-P3.LOG are preserved automatically. Upload all 12 logs to compare
median compilation and execution times, GC and memory. RUN29 compares
only 1.29 BASE vs 1KA for 3 runs each (NB1-NB3, NO1-NO3).

Use CLK24B, CLK24O, CLK29B, CLK29O for original CLOCK.PY face timing,
three alternating measurements each. Record first-face stopwatch time,
including DOS executable loading. Stop the clock with Ctrl+C.

## Optional 16 MB FreeDOS image

The optional FreeDOS image build packages a 16MB bootable FAT16 CF
raw image for XT-IDE. It uses GPL/BSD-licensed FreeDOS boot components,
not Microsoft DOS. Boot behavior must be confirmed on the physical Tandy.

WARNING: Writing a raw IMG ERASES the whole target CF card. Back up
your existing card and use a spare. For a safe comparison, copy the
ZIP files to your existing working DOS environment instead.
