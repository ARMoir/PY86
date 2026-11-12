"""Compare Py86 VM opcode dispatch and 16-bit near/far data experiments."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "build"
MODES = ("baseline", "fast-decode", "compiler", "far128", "near384", "combined")
NAMES = ("vm_load", "vm_branch", "vm_call", "vm_global", "vm_tuple",
         "local_int", "global_int", "dict_lookup", "instance_attr",
         "bound_method", "module_attr", "concat", "clock_frame")
data = {}
for mode in MODES:
    file = BUILD / ("benchmark-vm-" + mode + ".json")
    if file.is_file():
        data[mode] = json.loads(file.read_text())
if "baseline" not in data:
    raise SystemExit("Cannot compare VM variants without a passing baseline")
base = data["baseline"]["summary"]
lines = [
    "# Py86: 8086 bytecode dispatch and memory-access experiment",
    "",
    "All builds retain the **8086** target and 48 KB Python GC heap.",
    "DOSBox normal 8086, 20,000 fixed cycles; these are not real V20 timings.",
    "Three samples per benchmark, BIOS tick resolution approximately 55 ms.",
    "",
    "| Benchmark | Baseline ms/op | Decode fast | Compiler flags | Far data 128 | Near data 384 | Combined |",
    "|---|---:|---:|---:|---:|---:|---:|",
]
for name in NAMES:
    orig = base[name]
    row = [name, "%.4f" % orig["ms_per_op"]]
    for mode in MODES[1:]:
        if mode not in data or name not in data[mode]["summary"]:
            row.append("not built")
            continue
        candidate = data[mode]["summary"][name]
        if orig["count"] == candidate["count"] and orig["checksums"] != candidate["checksums"]:
            raise SystemExit("Benchmark checksum mismatch: %s %s" % (name, mode))
        row.append("%+.1f%%" % ((orig["ms_per_op"] / candidate["ms_per_op"] - 1) * 100))
    lines.append("| " + " | ".join(row) + " |")

lines.extend(("", "| Build mode | EXE bytes | Python GC heap free |",
              "|---|---:|---:|"))
for mode in MODES:
    if mode in data:
        report = data[mode]
        lines.append("| %s | %d | %d |" % (
            mode, report["executable_bytes"], report["memory"]["VMTEST"]["free"]))
    else:
        lines.append("| %s | compile/link/runtime failed (see diagnostics) | - |" % mode)
failures = BUILD / "vm-failures.txt"
if failures.exists():
    lines += ["", "## Candidate build / test failures", "", failures.read_text()]
lines += ["", "Positive percentages mean more operations per unit time relative to baseline.",
          "Small differences, especially PythonClock's two-frame workload, are",
          "limited by coarse DOS BIOS timing. Only consistent gains and passing",
          "functional tests should be considered for the default interpreter.",
          "The experiment has **not** automatically changed production settings.", ""]
text = "\n".join(lines)
(BUILD / "vm-comparison.md").write_text(text)
print(text)
