# Py86 Performance Baseline and Lookup Optimization Experiment

Date: 2026-11-10 (US Eastern). Platform: Open Watcom 16-bit DOS executable
running under DOSBox 0.74, `cputype=8086`, `core=normal`,
`cycles=fixed 20000`. These are **not measurements on the physical 7 MHz
NEC V20**. The underlying BIOS timer resolves about 55 ms, so small differences
and results based on only two PythonClock frames should not be overinterpreted.

## Reproducible baseline

The production interpreter before lookup optimization was built with
`--lookup-mode off`; to reproduce:
```
python ports/dos16/build.py --source <micropython-v1.24.1> --watcom <watcom> --lookup-mode off
python ports/dos16/run_bench.py --dosbox <dosbox> --mode off
```
Build source: MicroPython v1.24.1 pinned SHA
`ecfdd5d6f9be971852003c2049600dc7b3e2a838` and the Py86 DOS patches.
The CI workflow also compiles `map`, `attr`, and `both` using identical
runtime settings. It runs the existing correctness regression suite on each.

## Side-by-side results

Measured in [successful GitHub Actions run 42941753002](https://github.com/ARMoir/micropython/actions/runs/42941753002).
Numbers are medians of three runs, normalized per workload operation.
Positive percentages represent increased operation throughput
(`baseline_ms_per_op / variant_ms_per_op - 1`).

| Workload | Baseline ms/op | Map cache | Attr fast | Both |
| --- | ---: | ---: | ---: | ---: |
| Local integer additions | 0.0344 | 0.0% | +0.2% | 0.0% |
| Global reads and additions | 0.0472 | **+10.0%** | 0.0% | +10.0% |
| Dictionary reads | 0.0602 | **+16.7%** | 0.0% | +16.7% |
| Instance attribute reads | 0.0688 | **+33.3%** | +14.3% | +33.3% |
| Bound Python method calls | 0.5494 | +6.7% | +6.7% | +6.7% |
| Module attribute reads | 0.0772 | 0.0% | -10.0% | +12.3% |
| Repeated string concatenation | 0.9150 | -0.2% | -0.2% | -0.2% |
| PythonClock frame rendering (excluding print and sleep) | **220.0** | +0.2% | +0.2% | 0.0% |

The clock-frame test uses the original, unchanged PythonClock component modules
but renders **two frames per fresh Py86 process**, repeated in three processes.
This reduces memory pressure in the 48 KB heap, but timer resolution means the
fractional differences reported for the clock are not significant.

| Variant | DOS EXE bytes | Python GC heap free at BENCH1 start |
| --- | ---: | ---: |
| off | 334,266 | 44,624 |
| map | 334,586 | 44,624 |
| attr | 334,378 | 44,624 |
| both | 334,698 | 44,624 |

The `gc.mem_free()` metric measures only the MicroPython garbage-collected
heap. It does not measure **all DOS conventional memory** or the static memory
used by the cache.

## Decision

**Enable `MICROPY_OPT_MAP_LOOKUP_CACHE=1` by default** while leaving
`MICROPY_OPT_LOAD_ATTR_FAST_PATH=0`. Map cache yielded the strongest improvements
in dictionary and instance accesses without detectable Python heap loss. Both
features together did not measurably improve PythonClock beyond map cache alone.
The original setting remains available via `build.py --lookup-mode off`.

The 8086 emulator results are a first filter. Benchmarks should be repeated
on the real V20 before attributing specific speedups to the 7 MHz Tandy.
Future interpreter optimizations should preserve Python semantics and use the
same regression tests and benchmark framework.
