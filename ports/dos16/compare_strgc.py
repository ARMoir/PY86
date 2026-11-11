"""Compare stock and ASCII-qstr-cache builds using DOSBox outputs."""
import json
from pathlib import Path

build = Path(__file__).resolve().parent / "build"
a = json.loads((build / "benchmark-s-original.json").read_text())
b = json.loads((build / "benchmark-s-charcache.json").read_text())
pa = json.loads((build / "strgc-s-original.json").read_text())
pb = json.loads((build / "strgc-s-charcache.json").read_text())
lines = [
    "# Py86 string/GC experiment (DOSBox 8086 fixed 20000 cycles)",
    "",
    "| Microbenchmark | Original ms/unit | ASCII cache ms/unit | Cache throughput change |",
    "|---|---:|---:|---:|",
]
for name, orig in a["summary"].items():
    opt = b["summary"][name]
    if opt["checksums"] != orig["checksums"]:
        raise SystemExit("Different output for " + name)
    base = orig["ms_per_op"]
    new = opt["ms_per_op"]
    lines.append("| %s | %.3f | %.3f | %+.1f%% |" %
                 (name, base, new, (base/new-1)*100))
lines += ["", "| GC threshold | Operation | Original ms/unit | Cache ms/unit | Throughput change |", "|---|---|---:|---:|---:|"]
for t in pa["threshold_bytes"]:
    for name, orig in pa["summary"][str(t)].items():
        opt = pb["summary"][str(t)][name]
        if opt["checksum"] != orig["checksum"]:
            raise SystemExit("Profile output difference for %s %s" % (t, name))
        old = orig["ms_per_unit"]
        new = opt["ms_per_unit"]
        lines.append("| %s | %s | %.3f | %.3f | %+.1f%% |" %
                     (t, name, old, new, (old/new-1)*100 if new else 0))
lines += ["", "EXE bytes: original %d, cache %d." %
          (a["executable_bytes"], b["executable_bytes"]),
          "Bench Python GC heap free: original %d, cache %d." %
          (a["memory"]["BENCH1"]["free"],b["memory"]["BENCH1"]["free"]),
          "",
          "Warning: approx. 55 ms BIOS tick resolution; clock-frame differences",
          "smaller than one tick are not meaningful. DOSBox is not the physical V20.",
          "The one-character cache is an experiment and is OFF in production until",
          "correctness and measured gains justify enabling it.",
          ""]
out = "\n".join(lines)
(build / "strgc-comparison.md").write_text(out)
print(out)
