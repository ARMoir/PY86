# Py86 — Python 3 for 16-bit DOS

**Py86** is an independent, DOS-focused port of [MicroPython](https://micropython.org/). It brings a useful subset of the Python 3 language and built-in modules to **real-mode 16-bit MS-DOS**, including 8086, 8088 and NEC V20 systems such as the **Tandy 1000 EX**.

This repository is maintained as a **standalone Py86 project**, not as an upstream MicroPython contribution. It is **not an official MicroPython distribution** and is not full desktop CPython. The interpreter is based on pinned **MicroPython 1.29.0**, with DOS-specific adaptations and Open Watcom 16-bit code generation.

## Project status — feature-complete (November 15, 2026)

**Py86 has met its original goal:** a useful Python 3-compatible interpreter running under real-mode 16-bit DOS on 8086/8088/NEC V20-class machines, demonstrated on a 7 MHz Tandy 1000 EX.

**Upstream maintenance (November 24, 2026):** [PR #3](https://github.com/ARMoir/PY86/pull/3) synchronized the repository with 58 upstream MicroPython commits and brought the fork to zero commits behind upstream at the time of the merge. The production runtime remains pinned to MicroPython 1.29.0, with three targeted correctness backports and the faster JSON string serializer. See the [upstream reconciliation notes](ports/dos16/UPSTREAM_SYNC.md) for details.

**Maintenance mode:** the planned feature-development phase is complete. Future changes are intended for reproducible builds, regression fixes, documentation, and carefully scoped hardware-compatibility issues. There is no planned work toward full CPython compatibility, an `.mpy` loader, threading/`asyncio`, or a new GC architecture.

**Validation scope:** the release pipeline runs DOSBox Staging integration tests, VM diagnostics, and GC stress checks; core operation, PythonClock, Snake, and GC performance have real-Tandy evidence. Not every bundled module or heap size has been independently validated on every physical system. This is a practical vintage-computing port, not a hardened runtime for untrusted bytecode.

## Get Py86

**[Download the latest tested DOS release](https://github.com/ARMoir/PY86/releases/latest)**

Extract the versioned ZIP into a directory on a DOS disk or XT-IDE CompactFlash card. From the DOS prompt:

```bat
PY86 -V
PY86
PY86 DEMO.PY
RUNTEST
RUNCLK
RUNSNAKE
```

Run your own script with `PY86 SCRIPT.PY`; type `help()` inside the interactive interpreter. `Ctrl+Z` exits the console. Releases include the executable, DOS batch launchers, PythonClock, a feature showcase, and Snake. No Windows, Python installation, or network access is needed on the DOS computer.

Py86's Python compatibility is a practical **subset**: many Python 3 constructs work, but CPython packages requiring native extensions, threading, unrestricted memory, or operating-system services are not automatically supported. The port currently runs `.PY` source; precompiled `.mpy` execution is **not** enabled.

## Current implementation

- **CPU and environment:** 8086/8088/NEC V20, 16-bit real-mode DOS, Open Watcom C16 large memory model. The primary physical test machine is a 7 MHz NEC V20 Tandy 1000 EX with XT-IDE/CF.
- **Python engine:** pinned MicroPython 1.29.0 with a 1 KiB parser arena and targeted compiler optimizations; DOS-native terminal, file, time, and text-mode `curses` support; interactive Tab completion; bundled `math`, `random`, `os`, `time`, `datetime`, `json`, `re`, `hashlib`, and `gc` features (availability and coverage vary).
- **Default garbage collector:** the tested **data-aware conservative GC** skips scanning known pointer-free raw strings and bytearrays using a bounded 512-byte side bitmap. It retains the 2-bit allocation table, overlapping 16-bit far-pointer root scanning, and safe fallbacks. This is **not incremental GC**.
- **Upstream backports:** optimized JSON string serialization using contiguous runs of unescaped bytes; corrected malformed `eval()` input and `bytearray()` / `bytes()` construction from integer / string subclasses. Geometric string-buffer growth remains disabled in the production runtime.
- **Packaging:** the `master` branch runs DOSBox integration checks, VM-corruption checks, and 24/32/48 KB GC mutation/reallocation stress tests and upstream correctness/JSON checks at 24/48/60 KB before publishing a versioned release. After a verified release, the workflow retains only the latest release and tag.

### JSON serialization performance (DOSBox Staging)

| Workload | Original | Optimized | Speedup |
|---|---:|---:|---:|
| 30 JSON serializations of a 1,024-character ASCII string, 48,000-byte heap | 549 ms | 55 ms | ~10× |

The [validation run](https://github.com/ARMoir/PY86/actions/runs/45535284125) passed all three negative controls, 12 native correctness checks, integration tests, VM diagnostics and data-aware GC stress checks. The JSON timing uses the coarse DOS BIOS clock in DOSBox Staging and is specific to this workload; it has not yet been measured on the physical Tandy.

### Real-hardware evidence

On the Tandy 1000 EX, the data-aware GC reduced a raw-buffer GC benchmark from **15.60 s to 4.83 s** (3.23× faster) and a reference-heavy GC benchmark from **37.95 s to 16.75 s** (2.27× faster). Snake gameplay was perceptibly smoother, while opening Snake remained approximately **34 seconds** under both collectors. The GC comparisons were made with a 48 KiB Python heap; results are specific to this hardware and workload. Other heap sizes have been validated in DOSBox, not yet independently on every physical 8086/V20 machine.

## Repository layout

| Location | Purpose |
|---|---|
| [`ports/dos16/`](ports/dos16/) | The Py86 host, DOS runtime, build scripts, tests, packaging and detailed [technical README](ports/dos16/README.md) |
| [`py/`](py/) | Synchronized upstream MicroPython core reference; production uses a separate pinned checkout |
| [`extmod/`](extmod/) and [`shared/`](shared/) | MicroPython reusable modules and core support code |
| [`lib/`](lib/) | Retained third-party dependencies and upstream source support |
| [`tests/`](tests/) and [`tools/`](tools/) | Core compatibility tests, developer tooling and the [Py86 package converter](tools/py86pkg/README.md) |
| [`docs/`](docs/) and [`mpy-cross/`](mpy-cross/) | General MicroPython language/core reference and tooling; `mpy-cross` does **not** imply `.mpy` loading works in Py86 |
| [`.github/workflows/py86-package.yml`](.github/workflows/py86-package.yml) | Default `master` release build, regression gates and versioned ZIP |

This repository deliberately removes upstream microcontroller/other-platform ports, board-specific drivers, firmware examples, board documentation, and upstream-only GitHub automation. **The MicroPython core source and useful shared infrastructure remain intact.**

### Building

Builds are currently driven by GitHub Actions. Select **[Py86 1.29.0 1KA data-aware GC master release](https://github.com/ARMoir/PY86/actions/workflows/py86-package.yml)** in the Actions tab, or push to `master` to run the gated release pipeline. The workflow checks out the pinned upstream MicroPython **v1.29.0** source separately, applies the Py86 16-bit compatibility patches, 1 KiB parser changes, GC root batching, data-aware GC patch and selected upstream correctness/JSON backports, and compiles with the pinned Open Watcom toolchain.

The release and test pipeline uses an isolated upstream checkout; the local `py/` tree is retained for core code reference and future development. More detailed build parameters, tests, memory constraints and experimental context are in [`ports/dos16/README.md`](ports/dos16/README.md).

## Project scope

Py86 is developed independently for vintage DOS hardware. There is **no plan to submit this port upstream**, and unrelated upstream board firmware or hardware targets are not part of this project's roadmap. Historical optimization experiments and their results remain in the repository where they are useful to Py86.

The full incremental tri-color GC experiment and `.mpy` bytecode loader are **not** part of the production build. The current release intentionally favors tested behavior and backward-compatible Python source execution.

## Credits and licenses

Py86 is derived from the [MicroPython project](https://github.com/micropython/micropython) by Damien P. George and contributors. Its core is based on MicroPython 1.29.0 and is subject to the original [MIT licensing and third-party notices](LICENSE). See [ACKNOWLEDGEMENTS](ACKNOWLEDGEMENTS) and the relevant source files for contributor and third-party attribution. Py86 modifications retain their applicable notices.
