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


## String concatenation, QSTR caching, and garbage collection (2026-11-10)

The pinned-v1.24.1 string constructor eagerly re-hashed every newly allocated
intermediate string even when it was never used as a dictionary key.
`compat-lazyhash-v1.24.1.patch` stores zero (uncomputed) until first `hash()`,
when the runtime computes and memoizes the result. It preserves equality,
dictionary-key semantics, string immutability, Unicode and byte strings;
`STRHASH.PY` explicitly tests these properties. The ASCII-QSTR cache avoids
repeated intern-pool lookups when iterating one-byte ASCII strings and leaves
non-ASCII paths unchanged.

The [four-mode DOSBox comparison](https://github.com/ARMoir/micropython/actions/runs/42945176395)
passed the full regression suite. Fixed DOSBox 8086 at 20,000 cycles:

| Workload | Baseline | Combined (char cache + lazy hashing) | Gain |
| --- | ---: | ---: | ---: |
| Repeated concatenation, ms/add | 0.917 | approx. 0.734 | **25% higher throughput** |
| Isolated two-frame PythonClock, ms/frame | 219.5 | approx. 192.5 | **14% higher throughput** |
| GC clock profile, ms/frame | 247 | approx. 192.5 | 28.3% higher throughput |
| String splitting, default GC threshold | 22 ms per split | 22 ms per split | no measurable improvement in combined run |

The ASCII cache alone improved the dedicated split benchmark by about 2× at
the default threshold (22 to 11 ms per split), and often by 3× at more
aggressive GC thresholds, but the **combined** build showed no split speedup
at the default GC threshold in this run. Short splits cross only one or
two BIOS ticks, so those individual samples are highly quantized. The
measured gains in long concatenation and the overall clock workload are
more useful than any single short splitting measurement.

The BIOS clock resolves about 55 ms and the two-frame results should not be
overinterpreted. These are *not* physical 7 MHz V20 timings. The combined EXE
was 334,618 bytes vs. 334,586 bytes baseline, both with 44,624 free Python GC
heap bytes at BENCH1 startup.

`gc.threshold(-1)`, 4096, 8192 and 16384 were profiled. Frequent proactive
collections could leave more free Python heap after concatenation (roughly
32 KB at the default vs 37 KB using 8192) but slowed the workload (roughly
18% with 8192 on baseline). The **default GC threshold is unchanged** for speed;
applications can select `gc.threshold(n)` if memory headroom matters more.
PythonClock source remains unmodified.

Production build defaults to `--lookup-mode map --string-mode both`. The
comparison harness retains all individual flags. The expensive four-way
string and GC workflow is now manually dispatched; ordinary pushes still
run the full DOSBox correctness suite and production benchmark.


## 8086 bytecode dispatch and segmented-memory study (2026-11-10)

[Six-way complete DOSBox VM experiment](https://github.com/ARMoir/micropython/actions/runs/42948965948)
compared baseline (`-ot -zt=256`), a new single-byte variable-length-operand
fast path, `-oi -ol -oe -oh` compiler flags, `-zt=128` to move more static
data into far segments, `-zt=384` to keep more static data near, and a
combined decode/compiler build. All **six passed** the full DOSBox correctness
suite and opcode-specific benchmark, with no changed Python semantics.

| Main result | Baseline | Candidate | Consequence |
| --- | ---: | ---: | --- |
| `DGROUP` (near/static data bytes) | 61,536 | 58,400 with `-zt=128` | Saves 3,136 near bytes but ~14% slower dict/instance reads |
| `DGROUP`, `-zt=384` | 61,536 | 61,536 | No objects moved; no measured benefit |
| VM code size (bytes) | 7,842 | 8,312 with fast operand decoder | Adds 470 bytes, no overall improvement |
| Python call throughput | baseline | +17.6% with compiler flags | Useful for call-heavy programs |
| Bound-method throughput | baseline | +15.4% with compiler flags | Useful for call-heavy programs |
| Clock frame benchmark | 192 ms/frame | 192 ms/frame with compiler flags | No observed change |
| Python GC heap free | 45,488 | 45,488 in every variant | No measured heap change |

The fixed-cycle DOSBox 8086 timing is not physical V20 speed. The VM fast
operand decoder worsened a benchmark of instance attributes by approximately
14%, so it remains off. The near/far tradeoff demonstrates that indiscriminate
movement of static tables can degrade hot object lookups. The normal
`-zt=256` remains the best balanced value tested. `DGROUP` has about
4,000 bytes of headroom before its 64 KB size limit, not counting the
separately allocated 48 KB Python GC heap. The MicroPython VM uses portable
C `switch` bytecode dispatch. The GCC computed-goto extension is not
supported by Open Watcom C16 and cannot be enabled as a portable switch.

### Isolating Open Watcom compiler switches

[Six additional complete DOSBox runs](https://github.com/ARMoir/micropython/actions/runs/42949869932)
individually tested `-oe` (inline functions), `-oi` (intrinsics),
`-ol` (loop optimizations), `-oh` (extra passes), and all combined, each
against the same fixed baseline. Every build and regression suite passed.

| Compiler setting | EXE size | Python calls | Bound methods | Instance attributes | PythonClock |
| --- | ---: | ---: | ---: | ---: | ---: |
| Baseline `-ot` | 334,618 bytes | baseline | baseline | baseline | baseline |
| Inline `-oe` | 335,978 bytes | −0.1% | 0% | −14.3% | 0% |
| Intrinsics `-oi` | 335,178 bytes | +5.2% | 0% | −14.1% | −0.3% |
| Loop `-ol` | 337,274 bytes | **+17.6%** | **+15.4%** | −14.1% | +16.7% |
| Extra `-oh` | 334,730 bytes | +11.0% | +7.2% | −14.1% | 0% |
| All four | 339,290 bytes | **+17.6%** | **+15.4%** | 0% | 0% |

Positive percentages indicate higher throughput, not reduction in elapsed
time; +17.6% throughput means approximately 15% less elapsed time. Individual
measurements are quantized by the ~55 ms BIOS tick. In particular, the
clock-frame +16.7% figure arises from a short two-frame test and should
not be interpreted as a confirmed 16.7% speedup on hardware.

**Decision:** No global compiler or near/far change is justified yet. For
some call-heavy programs, `--vm-mode loop` and `--vm-mode compiler` are
promising optional builds, but each has code-size or performance tradeoffs.
Keep the default `--vm-mode baseline` and target CPU `-0`, preserving the
single executable on 8086, NEC V20 and 286 machines. Future work could mark
specific *cold* static tables as far rather than penalizing all object lookups
with a blanket `-zt=128`. The comparison workflows remain manually
dispatchable and upload linker maps for analysis. Validate on the physical
V20 before changing the production default.


## DOS file-line reading, readinto(), and CLI compatibility (2026-11-11)

After adding native DOS-backed `readinto(buffer)` and `writelines(iterable)`,
MicroPython's default generic `readline()` was compared against an optional
C `fgetc` implementation. The [successful A/B DOSBox experiment](https://github.com/ARMoir/micropython/actions/runs/43019197338)
built each configuration with otherwise identical settings, ran the entire
8086 correctness suite, and measured three independent file-reading trials.

| Benchmark | Generic ms/line | Native ms/line | Outcome |
| --- | ---: | ---: | --- |
| `file.readline()` | 0.6445 | 0.6445 | **No measurable improvement** |
| `for line in file` | 0.6445 | 0.8594 | **Native ~25% lower throughput** |
| `readinto()` (control) | 0.2109 | 0.0000 | Too short for 55ms timer; no meaningful inference |

Generic executable was 342,028 bytes, alternative native 342,492 bytes.
Those results were measured using DOSBox 8086 fixed 20,000 cycles, not the
physical 7 MHz NEC V20; short trials are quantized to 55ms timer ticks.
There is no evidence yet to promote the native reader, so the production
build **retains the generic default**. Both modes are selectable with
`--file-readline-mode generic|fast`; the expensive comparison workflow is
manually dispatched. The new `readinto` and `writelines` APIs are available
in both builds and passed DOSBox functional tests.

Py86 also now enables `help('modules')`, adds `-h/--help`, `-V/--version`,
and corrects `sys.argv` handling of `-c 'code' [args...]`. These changes
are covered by DOSBox command-line, module-help, and script argument tests.


## Adaptive single-segment Python heap (November 2026)

The previous Py86 startup unconditionally requested `malloc(48000)`.
Open Watcom's large-data-model `malloc()` uses the far heap; ordinary
far pointers cannot carry arithmetic across a 64 KB offset boundary.
A safe first stage now tries **60,000 down to 24,000 bytes**, in 4 KB
steps, chooses the first candidate which fits within one offset range,
and checks a temporary **32 KB additional native malloc** for source file
and DOS runtime headroom. A user may request an exact size using the
`PY86_HEAP` DOS environment variable or cap automatic sizing using
`PY86_HEAP_MAX`. The `PY86 --heap-info` command prints actual allocated
raw heap bytes and usable GC pool/free bytes. All these settings leave the
8086 instruction target, Open Watcom large memory model, and current VM,
GC root scanning, Python libraries, and 16 KB C stack unchanged.

This improves flexibility on machines with different *free conventional
memory*; it does not grant access to memory above the 1 MB real-mode
address limit or remove the ~64 KB single-allocation limit. Heap sizes
and usable Python free memory must be checked using the actual EXE
under DOSBox and preferably on the real NEC V20. Benchmarking at 48K
and automatic sizes is a separate comparison, not a CPU-clock claim.
