"""Compare all Py86 string and GC optimization variants with one baseline."""
import json
from pathlib import Path

build = Path(__file__).resolve().parent / "build"
modes = ("s-original", "s-charcache", "s-lazyhash", "s-both")
bench = {}
profiles = {}
for mode in modes:
    bench[mode] = json.loads((build / ("benchmark-" + mode + ".json")).read_text())
    profiles[mode] = json.loads((build / ("strgc-" + mode + ".json")).read_text())
base = modes[0]
def speedup(old, new):
    return (old / new - 1) * 100 if new else 0

lines = [
    "# Py86 string/GC experiment (DOSBox 8086 fixed 20000 cycles)",
    "",
    "| Microbenchmark | Original ms/unit | ASCII cache | Lazy hash | Both |",
    "|---|---:|---:|---:|---:|",
]
for name, orig in bench[base]["summary"].items():
    other = [bench[m]["summary"][name] for m in modes[1:]]
    if any(x["checksums"] != orig["checksums"] for x in other):
        raise SystemExit("Incorrect result in " + name)
    old = orig["ms_per_op"]
    gains = [speedup(old,x["ms_per_op"]) for x in other]
    lines.append("| %s | %.3f | %+.1f%% | %+.1f%% | %+.1f%% |" %
                 (name, old, *gains))
lines += ["", "| GC threshold | Operation | Original ms/unit | ASCII cache | Lazy hash | Both |",
          "|---|---|---:|---:|---:|---:|"]
for threshold in profiles[base]["threshold_bytes"]:
    key = str(threshold)
    for name, orig in profiles[base]["summary"][key].items():
        other = [profiles[m]["summary"][key][name] for m in modes[1:]]
        if any(x["checksum"] != orig["checksum"] for x in other):
            raise SystemExit("Profile output mismatch: %s %s" % (key,name))
        old = orig["ms_per_unit"]
        gains = [speedup(old,x["ms_per_unit"]) for x in other]
        lines.append("| %s | %s | %.3f | %+.1f%% | %+.1f%% | %+.1f%% |" %
                     (key, name, old, *gains))
lines += ["", "| Mode | EXE bytes | Python GC heap free |",
          "|---|---:|---:|"]
for m in modes:
    lines.append("| %s | %d | %d |" %
                 (m, bench[m]["executable_bytes"], bench[m]["memory"]["BENCH1"]["free"]))
lines += ["",
          "Positive percentages are higher throughput than the unmodified production",
          "interpreter. These are DOSBox 8086 fixed-20000-cycle results, not V20",
          "hardware results. BIOS tick resolution is about 55 ms, so small",
          "differences, especially per-frame timings, are not significant.",
          "All variants must pass the DOSBox regression suite. The experimental",
          "flags remain OFF in the production executable until validated.",
          ""]
out = "\n".join(lines)
(build / "strgc-comparison.md").write_text(out)
print(out)
