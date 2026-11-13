# Py86 V20 parser/runtime/GC isolation experiment

The Tandy 1000 EX real-hardware measurements showed a 1 KB parser allocator
combined with compiler-only Watcom flags (1KA) reduced DEMO.PY startup
from about 80.56 seconds to 77.79 seconds, but DEMO.PY execution averaged
about 3.4 seconds slower. PythonClock first-face timing was BASE 22 seconds
and 1KA 21 seconds on a single run. These observations motivate a
controlled factorial study rather than prematurely changing production.

## Experimental variables

Four opt-in 16-bit 8086 executables make a 2x2 comparison:

| EXE | Parser allocation | Compiler flags |
|---|---|---|
| P86RBAS.EXE | Original MicroPython chunks | Original |
| P86RALL.EXE | Original | -oi -ol -oe -oh only in lexer/parser/compiler sources |
| P86R1K.EXE | Fixed 1024-byte AST chunks | Original |
| P86R1KA.EXE | Fixed 1024-byte AST chunks | Compiler-only optimizations |

This separates the effect of the allocator from the compiler options.
All continue to compile ordinary original .PY source, no .mpy or cache.
Production PY86.EXE, Python sources, and VM dispatch code are unchanged.

These test executables add opt-in runtime instrumentation, activated with
PY86_PROFILE=1:

    P86PROF read_ms=... lexer_ms=... parse_ms=... compile_ms=... exec_ms=... gc_free=...
    P86RUNT gc_calls=... gc_ms=... free_pre=... free_post=... prep_ms=... forced_gc_ms=...

P86RUNT reports collections during script execution only, time spent in
those collections, GC free space before execution, space after optional
collection, and the explicit preparation/collection time (excluded from
exec_ms). This distinguishes garbage-collection time from non-GC Python
execution time and shows whether fewer free blocks could explain a slowdown.

For any of the four EXEs, the optional DOS environment variable
PY86_PREEXEC_GC=1 forces exactly one GC sweep between bytecode compilation
and Python execution. This is a diagnostic intervention, not a production
setting; prep_ms includes its cost. With that variable absent, no extra
collection is performed. Compiled function roots remain live during GC.

## Validation via GitHub Actions

The standalone py86-runtime-gc-lab.yml workflow checks each build:

1. Native Open Watcom -0 8086 compilation in an isolated pinned 1.24.1 source.
2. The complete existing DOSBox regression suite, including syntax errors,
   imports, exceptions, GC behavior, file I/O, and 19-feature DEMO.PY.
3. With pre-execution GC disabled, two full original DEMO.PY runs, ONECLK.PY,
   SHOW.PY, PARSST.PY, and a deterministic VM-only RUNTST.PY benchmark.
4. The same profiles with pre-execution GC enabled. Each must pass.
5. Every profile must contain exactly one P86PROF and P86RUNT record.
6. Only after all 8 variant/toggle combinations pass, create the hardware ZIP.

The release pipeline still packages the original PY86.EXE with unchanged
defaults. The profiler is not added to production builds.

## Physical NEC V20 test protocol

Extract PY86-RUNTIME-LAB.zip into the DOS directory already containing
DEMO.PY and CLOCK.PY. Test scripts use DOS 8.3 names and a 48 KB fixed GC
heap so automatic heap sizing cannot skew comparisons. No existing files
are overwritten except test output logs.

### First, fast diagnosis

Run RUN4.BAT. It executes the same DEMO.PY, deterministic runtime-only
RUNTST.PY and parser-stress PARSST.PY once under each of the four builds.
It writes B0.LOG (BASE), A0.LOG (compiler flags only), K0.LOG (1KB only),
X0.LOG (both), and VM/stress logs VB/VA/VK/VX and SB/SA/SK/SX.

All demo outputs must say 19 passed, 0 failed; runtime stress must pass.
Check P86RUNT: if GC time rises on 1KA but not on BASE or ALL, investigate
GC/heap fragmentation. If runtime stress slows on the original parser
with compiler flags (ALL), suspect compiler flags rather than allocation.
If only 1KB builds slow, suspect memory layout or allocation side effects.

### Then, repeat the four-way test

Run RUN12.BAT for three alternating rounds:

    BASE, ALL, 1K, 1KA,
    BASE, ALL, 1K, 1KA,
    BASE, ALL, 1K, 1KA

Twelve uniquely named results B1-B3.LOG, A1-A3.LOG, K1-K3.LOG and
X1-X3.LOG are preserved automatically in a single run.
Compare medians of startup_ms, exec_ms, gc_calls/gc_ms and gc_free.

### Finally, isolate a one-time GC before execution

Run RUNGCT.BAT: it alternates 1KA without and with forced pre-execution
garbage collection three times each. Output XN1-XN3.LOG and XG1-XG3.LOG.
Distinguish actual Python exec_ms from the collection overhead:
include prep_ms in the end-to-end cost, or a seemingly faster run could
hide an expensive forced GC.

Test the actual original CLOCK.PY without any source modifications:

    P86RBAS --home-cls CLOCK.PY
    P86R1KA --home-cls CLOCK.PY

Measure time to first clock face in 3 alternating runs of each.
Clock first-face timing includes the DOS loader, whereas P86PROF starts
inside the executable after DOS loads it. This is independent of the
DEMO.PY comparison. The previous 22 vs 21-second observations were single
runs and do not establish a robust 1-second gain yet.

## Decision

The best build must keep the 19/19 feature result and both stress tests,
improve startup *on the physical V20*, avoid execution slowdowns and
meaningful reductions in free heap, and not become slower overall after
including pre-execution GC cost. If no candidate succeeds, keep the
original BASE and focus the next optimization on parser rule dispatch,
tokens and qstr interning rather than larger parse blocks.
