"""Compare file-I/O performance between generic and native Py86 line readers."""
import json
from pathlib import Path

build = Path(__file__).resolve().parent / "build"
base = json.loads((build / "filebench-generic.json").read_text())
fast = json.loads((build / "filebench-fast.json").read_text())
rows = [
    "# Py86 native DOS file-reading A/B experiment",
    "",
    "DOSBox 8086, core=normal, fixed 20,000 cycles, approximate 55ms BIOS tick.",
    "Both executables use the same MicroPython and Open Watcom source/settings.",
    "",
    "| Workload | Generic ms/line | Native ms/line | Throughput change |",
    "|---|---:|---:|---:|"
]
for phase in ("line", "iter", "readinto"):
    old = base["summary"][phase]
    new = fast["summary"][phase]
    if (old["checksum"], old["count"]) != (new["checksum"], new["count"]):
        raise SystemExit("Incorrect data returned in " + phase)
    a, b = old["ms_per_line"], new["ms_per_line"]
    pct = (a / b - 1) * 100 if b else 0.0
    rows.append("| %s | %.4f | %.4f | %+.1f%% |" % (phase,a,b,pct))
rows += [
    "",
    "Original executable: %d bytes; native file reader: %d bytes." %
    (base["exe_bytes"], fast["exe_bytes"]),
    "",
    "Positive throughput change means faster. Short runs are quantized by the",
    "DOS BIOS timer; results must be verified on the physical NEC V20.",
    "The readinto workload is a control: its implementation is identical in",
    "both builds, and it may differ slightly due to measurement noise.",
    "",
]
out = "\n".join(rows)
(build / "filebench-comparison.md").write_text(out)
print(out)
