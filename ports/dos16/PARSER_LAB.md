# Py86 fast parser experiment: 8086/V20 build and testing

This is an isolated A/B study. It does not modify the normal production
PY86.EXE, Python grammar or bytecode format, and all candidates execute
ordinary .PY source files without a precompilation step.

## Why focus on parsing?

The real Tandy 1000 EX at 7 MHz showed approximately 61.57 seconds of
parsing and 18.79 seconds of bytecode generation for the 19-feature DEMO.PY.
Compiler-only Watcom optimization reduced parsing to about 60.31 seconds.
These measurements were repeated twice per build.

In MicroPython v1.24.1, the parser allocates AST nodes in chunks, normally
starting from a small 16-byte allocation and trying in-place growth on
every capacity shortage. The study compares this policy with preallocated
fixed-size blocks and geometric growth.

## Implemented alternatives

All use Open Watcom 8086 code generation, a separate pinned v1.24.1 source
checkout, and the existing .PY parser/bytecode format.

| Variant | Parser allocator | Compiler-only Watcom flags |
| --- | --- | --- |
| base | Original | Standard |
| all | Original | -oi -ol -oe -oh |
| p512 | 512-byte fixed blocks | Standard |
| p1k | 1024-byte fixed blocks | Standard |
| p2k | 2048-byte fixed blocks | Standard |
| geo | 256-byte start, ~50% in-place growth to 4K | Standard |
| p1ka | 1024-byte blocks | -oi -ol -oe -oh |
| p2ka | 2048-byte blocks | -oi -ol -oe -oh |

The parser_allocator_lab.py patcher is opt-in, and applies only to a
temporary checkout after prepare_source.py. The default build still uses
the original parser. Fixed blocks never move existing nodes, and completed
blocks are linked into the normal syntax-tree allocation list.

Build on a modern host with Python 3 and Open Watcom:

    python ports/dos16/prepare_source.py --source /tmp/mp124
    python ports/dos16/parser_allocator_lab.py patch-source /tmp/mp124
    python ports/dos16/build.py --source /tmp/mp124 --watcom /tmp/ow --profile-compile --parser-alloc-mode block1024

## Required correctness and performance tests

The independent py86-parser-lab.yml GitHub Actions workflow requires each
variant to pass all existing DOSBox integration tests, two DEMO.PY source
compilation profiles (19/19 feature checks), ONECLK.PY and SHOW.PY, plus the
new 100-statement PARSST.PY syntax-tree stress test. It records per-stage
P86PROF BIOS-tick timings, executable size, free GC heap, and linker maps.
Failed variants are excluded from the DOS test archive.

DOSBox results are an initial screening only. Timing granularity is about
55ms, and the normal 8086 emulator is not identical to the NEC V20.

## Physical Tandy 1000 EX / CF card testing

1. Download the successful parser-lab GitHub Actions artifact, then extract
   its nested PY86-PARSER-LAB.zip into your existing C:\PY86 directory.
   Your existing PY86.EXE and .PY scripts are not replaced.
2. Run RUNPB (parser baseline). This runs DEMO.PY and the included PARSST.PY
   at a fixed 48 KB heap. It saves PBAS.LOG and SBAS.LOG.
3. Run RUNPA (the previous compiler-only optimization). It saves PALL.LOG
   and SALL.LOG. Confirm that all 19 features and parser stress pass.
4. Test the fastest candidate selected by DOSBox measurements, using
   RUN512, RUN1K, RUN2K, RUNGEO, RUN1KA or RUN2KA. A candidate absent
   from the ZIP did not pass the automated tests.
5. Alternate baseline and candidate for THREE runs each, SIX total.
   For example: RUNPB, RUN1K, RUNPB, RUN1K, RUNPB, RUN1K.
   Each RUN*.BAT overwrites its own .LOG. Copy or rename each LOG after
   a run (e.g. PBAS.LOG to BASE1.LOG; P1K.LOG to CAND1.LOG) before
   starting the same batch again. Preserve corresponding S*.LOG files
   if checking the separate parser-stress workload.
6. Upload six DEMO run logs. Compare the median values of read_ms,
   lexer_ms, parse_ms and compile_ms, and keep exec_ms and gc_free for
   regression checks. The meaningful metric is the sum of the four
   startup fields, not a single timer tick.
7. On the best passing candidate, separately measure the first face
   rendered by the ORIGINAL CLOCK.PY, three alternating runs per build:

       P86PBASE --home-cls CLOCK.PY
       P86P1K --home-cls CLOCK.PY

   Substitute the correct candidate executable. Time the first face with
   a stopwatch, including DOS EXE loading; P86PROF excludes that loader.

Do not replace production PY86.EXE unless the candidate consistently
improves physical startup, passes every feature test, and retains acceptable
free heap and normal Python execution speed. A ~3 second or larger
repeatable parser reduction (5%) would be worth considering; small
emulator-only changes are not enough.

If no memory-allocation strategy produces a clear gain, next investigate
the parser's rule-stack loop, token processing and identifier (qstr)
interning. No bytecode cache is introduced by this experiment.
