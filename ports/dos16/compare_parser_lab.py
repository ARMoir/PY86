"""Compare ONLY DOSBox-verified 8086 parser allocator builds."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "build"
OUT = BUILD / "parser-lab"
OUT.mkdir(exist_ok=True)
MODES = ("base", "all", "p512", "p1k", "p2k", "geo", "p1ka", "p2ka")
report = {}
for mode in MODES:
    data_file = BUILD / ("compile-profile-parser-" + mode + ".json")
    if data_file.exists():
        report[mode] = json.loads(data_file.read_text())

lines = [
    "# Py86 8086 parser allocator comparison",
    "",
    "Every PASS candidate compiled unchanged .PY files, passed the entire",
    "DOSBox regression suite, ran two complete 19-feature demos, ONECLK.PY,",
    "SHOW.PY, and a 100-statement parser syntax-tree stress test.",
    "All use 8086 -0 and 48 KB test GC heap. No production build changes.",
    "Times reflect DOSBox Staging 20000-cycle fixed emulator, NOT real V20.",
    "BIOS timing granularity is about 55 ms.",
    "",
    "| Mode | Parse ms | Compile ms | Startup ms | vs base | GC free | Stress parse ms | EXE bytes |",
    "|---|---:|---:|---:|---:|---:|---:|---:|",
]
baseline = report.get("base", {}).get("demo_median", {}).get("startup_total_ms")
for mode in MODES:
    data = report.get(mode)
    if data is None:
        lines.append("| %s | Not verified | - | - | - | - | - | - |" % mode)
        continue
    metrics = data["demo_median"]
    stress = data["samples"].get("PSTRES.OUT")
    if not stress:
        raise SystemExit("Missing mandatory parser stress proof: " + mode)
    rel = (baseline / metrics["startup_total_ms"] - 1) * 100 if baseline else 0.0
    lines.append("| %s | %.0f | %.0f | %.0f | %+.1f%% | %.0f | %d | %d |" % (
        mode, metrics["parse_ms"], metrics["compile_ms"],
        metrics["startup_total_ms"], rel, metrics["gc_free"],
        stress["parse_ms"], data["executable_bytes"]))
failures = OUT / "failures.txt"
if failures.exists():
    lines.extend(("", "## Rejected variants", "", failures.read_text()))
lines.extend(("", "This is an isolated A/B study, not a new production default.",
              "Only consistent physical V20 improvements justify promotion.", ""))
result = "\n".join(lines)
(OUT / "summary.md").write_text(result)
print(result)
