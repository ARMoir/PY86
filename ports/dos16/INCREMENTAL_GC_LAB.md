# Py86 incremental GC lab (experimental)

This branch is an isolated, reproducible assessment of the
[raspy135 incremental GC fork](https://github.com/raspy135/micropython/tree/gc-incremental).
Production master and its automatic releases are not modified.

## Fixed source revisions

- Base MicroPython 1.29.0: 0fd6c573ea815774668bbb16b8e197c8822368b2
- Fork incremental GC head: 6b9ed5871b52fd68debe5866af9a41333b828e73
- Fork comparison base: 970468103d5ce776d092a1eb84e3bdf2ab5a3b0b

The fork supports Unix and ESP32; it has not been ported or certified for
Py86's segmented 16-bit address space. The core diff modifies numerous
files, including GC layout, pointer-stores and write barriers. The port
cannot safely use only the new gc.c without the related updates.

## Automated experiment

GitHub Actions workflow: .github/workflows/py86-incremental-gc.yml

Pushes on experiment/incremental-gc-bench run a branch-only lab:

1. Clone pinned MicroPython and fork revisions.
2. Apply the existing verified Py86 production 1.29.0 adaptations,
   1KB parser, batched GC root traversal and REPL autocomplete.
3. Build the baseline with the production compiler and memory options.
4. Run the complete DOSBox regression suite, including the extra
   mutation-stress test GCINCR.PY, and the existing allocation/VM/frame
   benchmark plus RUNTST.PY runtime GC instrumentation.
5. Reconstruct the exact full fork py/ diff from its pinned base.
   Check/apply that diff to a disposable copy of the already patched core.
6. If *all* hunks apply, compile the candidate and run precisely the
   same DOSBox tests and benchmarks; otherwise, retain rejected hunks
   and explicitly record that the fork is NOT PORTED.
7. Upload a summary, machine-readable performance data, run logs and
   reject diagnostics as a 30-day workflow artifact.

The workflow never publishes or overwrites a release, and the experiment
has no push permission to master. It is deliberately allowed to report
a successful baseline with an incompatible experimental source; this is
a compatibility finding, NOT a successful incremental GC benchmark.

## Evaluation criteria

Compare interpreter binary size, 48KB heap startup free bytes,
median operations per workload, GC calls, GC timing and total runtime.
Do not interpret comparisons until the candidate actually builds and
passes the same tests. DOSBox fixed-cycle emulation and 55ms BIOS-tick
timings cannot establish maximum 20us pauses or physical V20 performance.

Before ever considering an incremental candidate hardware-safe, complete
a far-pointer root and heap alignment audit; review every GC_WB mutation
site (including native modules); test repeated allocations, appends,
reassignments, finalisers, memory pressure, exception paths, GC-stack
overflow and GC enabled/disabled transitions. Test on physical V20 with
the known-good release available for recovery.

The fork is MIT-licensed. This lab records its exact provenance, and
does not copy unrelated ESP32/Unix port code into the release branch.

## Verified data-only GC candidate (November 13, 2026)

The first phase successfully compiles and passes the complete DOSBox
regression suite including live-reference mutation tests. The data-only
prototype is applied to a second disposable copy of the same production
Py86 core using \`prepare_data_gc_lab.py\`; it is **not** the incremental
collector and does **not** enable tri-color marking or write barriers.

It retains the existing 2-bit allocation table and adds a bounded 512-byte
side bitmap for allocations whose data cannot hold Python pointers
(bytearray, strings and vstr raw buffers). Moving reallocations preserve
the raw-data tag. The bitmap safely disables itself for oversized heaps.

The measured run
[43461667372](https://github.com/ARMoir/micropython/actions/runs/43461667372)
reported the following DOSBox Staging fixed-cycle medians:

| Workload | Production baseline | Data-only prototype |
|---|---:|---:|
| 32 GCs, 16 live 768-byte raw buffers | 220 ms | 110 ms |
| 32 GCs, same buffers plus 64 pointer-rich lists | 605 ms | 329 ms |
| 600 string concatenations | 494 ms | 439 ms |
| 12,800 local integer additions | 440 ms | 494 ms |
| Executable size | 362,706 bytes | 363,762 bytes |

This is encouraging, but DOS timing is quantized to ~55 ms; these
measurements do **not** establish stable 2x gains on actual 7 MHz V20
hardware. No general interpreter speed improvement is claimed.
Physical testing, more trials, and broader data workloads are still
required before considering a release.

The fork's full incremental collector still cannot be safely applied
to the DOS16-modified 1.29.0 core. The lab records raw rejected hunks
and, separately, performs a three-way source rebase diagnostic to
identify which overlapping changes need manual integration. **No
incremental binary is built unless all source and port correctness
gates are met.**

