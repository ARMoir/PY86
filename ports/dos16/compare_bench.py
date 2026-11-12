"""Compare Py86 lookup variants against the same-run unmodified baseline."""
import json
from pathlib import Path
import statistics

BUILD = Path(__file__).resolve().parent / "build"
MODES = ("off", "map", "attr", "both")
reports = {}
for mode in MODES:
    p = BUILD / ("benchmark-" + mode + ".json")
    if not p.is_file():
        raise SystemExit("Missing metric report: " + str(p))
    reports[mode] = json.loads(p.read_text())
    if set(reports[mode]["summary"]) != set(reports["off"]["summary"] if "off" in reports else reports[mode]["summary"]):
        raise SystemExit("Benchmark labels differ for " + mode)

baseline = reports["off"]
names = list(baseline["summary"])
header = "| Benchmark | Baseline ms/op | Map cache | Attr fast path | Both |\n"
separator = "|---|---:|---:|---:|---:|\n"
rows = [header, separator]
for name in names:
    base = baseline["summary"][name]["ms_per_op"]
    values = []
    for mode in MODES[1:]:
        experiment = reports[mode]["summary"][name]
        if experiment["checksums"] != baseline["summary"][name]["checksums"]:
            raise SystemExit("Checksum discrepancy for " + name + " in " + mode)
        ms = experiment["ms_per_op"]
        values.append("{:+.1f}%".format((base / ms - 1) * 100))
    rows.append("| {} | {:.4f} | {} | {} | {} |\n".format(name, base, *values))

rows.append("\nValues are throughput improvements relative to baseline. "
            "Positive percentages are faster; negative percentages are slower. "
            "All times are DOSBox 8086 fixed-20000-cycle results, not physical V20 timings.\n\n")
rows.append("| Configuration | EXE bytes | Free heap after import (BENCH1) |\n"
            "|---|---:|---:|\n")
for mode in MODES:
    info = reports[mode]
    rows.append("| {} | {} | {} |\n".format(
        mode, info["executable_bytes"], info["memory"]["BENCH1"]["free"]))

result = "".join(rows)
(BUILD / "lookup-comparison.md").write_text(result)
(BUILD / "lookup-comparison.json").write_text(json.dumps(
    {"environment":baseline["environment"], "modes":list(MODES),
     "results":reports}, indent=2))
print(result)
