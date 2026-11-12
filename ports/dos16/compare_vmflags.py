"""Compare incremental Open Watcom compiler optimizations for Py86 8086."""
import json
from pathlib import Path

BUILD = Path(__file__).resolve().parent / "build"
MODES = ("baseline", "inline", "intrinsic", "loop", "reopt", "compiler")
NAMES = ("vm_load", "vm_branch", "vm_call", "vm_global", "vm_tuple",
         "local_int", "global_int", "dict_lookup", "instance_attr",
         "bound_method", "module_attr", "concat", "clock_frame")
data = {}
for mode in MODES:
    p = BUILD / ("benchmark-flags-" + mode + ".json")
    if p.is_file():
        data[mode] = json.loads(p.read_text())
if "baseline" not in data:
    raise SystemExit("Missing baseline benchmark")
base = data["baseline"]["summary"]
rows = [
    "# Open Watcom 8086 compiler-flag A/B experiment",
    "",
    "All configurations use -ot, -0, -ml, -zt=256, and all Py86 production features.",
    "Only the additional flags differ. DOSBox 8086, fixed 20,000 cycles.",
    "Times are medians over three samples with ~55 ms BIOS tick resolution.",
    "",
    "| Workload | Baseline ms/op | Inline -oe | Intrinsics -oi | Loops -ol | Extra -oh | All four |",
    "|---|---:|---:|---:|---:|---:|---:|",
]
for name in NAMES:
    entry = base[name]
    values = [name, "%.4f" % entry["ms_per_op"]]
    for mode in MODES[1:]:
        if mode not in data:
            values.append("not built")
            continue
        item = data[mode]["summary"][name]
        if item["count"] == entry["count"] and item["checksums"] != entry["checksums"]:
            raise SystemExit("Different checksum for %s in %s" % (name,mode))
        values.append("%+.1f%%" % ((entry["ms_per_op"] / item["ms_per_op"] - 1) * 100))
    rows.append("| " + " | ".join(values) + " |")
rows += ["", "| Variant | EXE size (bytes) | Free Python GC heap |",
         "|---|---:|---:|"]
for mode in MODES:
    if mode in data:
        item = data[mode]
        rows.append("| %s | %d | %d |" % (
            mode, item["executable_bytes"], item["memory"]["VMTEST"]["free"]))
    else:
        rows.append("| %s | failed validation | - |" % mode)
p=BUILD/"flags-failures.txt"
if p.exists():
    rows += ["", "Failed variants:", p.read_text()]
rows += ["", "Positive percentages are higher throughput; do not treat sub-55ms",
         "clock differences as reliable. These results do not measure the real V20.",
         "The production configuration is not modified automatically.", ""]
result = "\n".join(rows)
(BUILD / "compiler-flags-comparison.md").write_text(result)
print(result)
