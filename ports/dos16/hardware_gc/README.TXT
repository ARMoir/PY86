PY86 / TANDY 1000 EX - GC COMPARISON KIT
=========================================
EXPERIMENTAL DATA-AWARE GC - NOT A PRODUCTION RELEASE

Contents: A86.EXE (original collector), D86.EXE (data-aware
collector), RUN48.BAT, GCBENCH.PY, BENCH1.PY, GCINCR.PY,
SNAKE.PY and evidence hashes.

1. Extract the entire ZIP into one directory on the Tandy CF
   card, for example C:\\GCTEST. Keep your known-good normal
   Py86 installation intact elsewhere.
2. Boot MS-DOS normally. At C:\\GCTEST run: RUN48
3. After completion, inspect RESULT.TXT. It must say PASS.
   In A1.TXT / A2.TXT and D1.TXT / D2.TXT, compare the
   BENCH gc_raw and BENCH gc_refs lines. The last numeric
   field is an integrity checksum and must be identical.
   Lower time (ms) is better.
4. Check ACPU.TXT / DCPU.TXT for normal-language speed.
   Check AHEAP.TXT and DHEAP.TXT for GC heap sizes.
5. Optional interactive responsiveness: run
      A86 SNAKE.PY
      D86 SNAKE.PY
   Compare input responsiveness and pauses on the same
   hardware. Use Q to exit; keep runs comparable.
6. Copy all *.TXT files back to the PC and share them for
   review. Do not replace your normal interpreter with D86.

The batch runs baseline and data-aware GC in A,D,D,A order,
with independent interpreter launches and three internal
timing trials per GC workload per launch. CPU tests run once
per build, each containing three internal trials. This is
a 48,000-byte heap comparison; timings use the approx.
55ms DOS BIOS tick, so single-tick differences are noise.
Use medians, not one result. Identical checksums are required.

IF A TEST CRASHES: stop; do not interpret partial output
as a pass. Report which step last printed and the newest
log file. No incremental tri-color build is included until
it passes DOSBox and a write-barrier/far-pointer audit.

Technical provenance, automation and DOSBox evidence:
https://github.com/ARMoir/micropython/tree/experiment/incremental-gc-bench
