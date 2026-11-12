"""Compare fixed 48 KB and automatic 16-bit Python heap on identical Py86 builds."""
import json
from pathlib import Path

build = Path(__file__).resolve().parent / "build"
a = json.loads((build / "benchmark-heap-48k.json").read_text())
b = json.loads((build / "benchmark-heap-auto.json").read_text())
if a["executable_bytes"] != b["executable_bytes"]:
    raise SystemExit("The benchmark compared different executable files")
if a["python_heap_bytes"] != 48000 or b["python_heap_bytes"] < 24000:
    raise SystemExit("Heap selection did not match benchmark configuration")
rows = [
    "# Py86 automatic single-segment heap A/B",
    "",
    "Identical 8086 DOS executables; only PY86_HEAP=48000 versus automatic sizing differs.",
    "DOSBox normal core, 8086, fixed 20,000 cycles; BIOS clock ~55 ms.",
    "",
    "| Memory | Fixed 48KB | Automatic |",
    "|---|---:|---:|",
    "| Raw allocated GC heap | %d | %d |" %
    (a["python_heap_bytes"], b["python_heap_bytes"]),
    "| GC pool bytes at startup | %d | %d |" %
    (a["gc_total_bytes"], b["gc_total_bytes"]),
    "| GC free bytes at startup | %d | %d |" %
    (a["gc_free_on_startup"], b["gc_free_on_startup"]),
    "| GC free bytes at BENCH1 start | %d | %d |" %
    (a["memory"]["BENCH1"]["free"], b["memory"]["BENCH1"]["free"]),
    "",
    "| Benchmark | 48 KB ms/op | Auto ms/op | Throughput change |",
    "|---|---:|---:|---:|",
]
for name, fixed in a["summary"].items():
    auto = b["summary"][name]
    if fixed["checksums"] != auto["checksums"]:
        raise SystemExit("Different checksums for " + name)
    old, new = fixed["ms_per_op"], auto["ms_per_op"]
    rows.append("| %s | %.4f | %.4f | %+.1f%% |" %
                (name, old, new, 100 * (old/new-1) if new else 0))
rows += ["", "Note: a larger heap increases usable Python object memory but may",
         "also affect GC scanning costs. No physical NEC V20 timings are claimed.",
         "Single-segment far-pointer and native headroom constraints still apply.",
         ""]
out = "\n".join(rows)
(build / "heap-compare.md").write_text(out)
print(out)
