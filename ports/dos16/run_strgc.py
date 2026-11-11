"""Profile Python string operations and GC at different collection thresholds.

Executes the real Py86 16-bit EXE in DOSBox 8086. Results are emulator-only.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import statistics
import subprocess

ROOT = Path(__file__).resolve().parent
THRESHOLDS = (-1, 4096, 8192, 16384)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dosbox", required=True)
    parser.add_argument("--mode", required=True)
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()
    stage = ROOT / "strgc-test"
    stage.mkdir(exist_ok=True)
    build = ROOT / "build"
    shutil.copy2(build / "py86.exe", stage / "PY86.EXE")
    shutil.copy2(ROOT / "tests/bench/STRGC.PY", stage / "STRGC.PY")
    for f in (ROOT / "tests/pythonclock").glob("*.py"):
        shutil.copy2(f, stage / f.name)
    # Each threshold has its own fresh Py86 process to isolate heap history.
    bat = ["@echo off"]
    for idx, threshold in enumerate(THRESHOLDS):
        (stage / ("S%d.OUT" % idx)).unlink(missing_ok=True)
        bat += ["PY86 STRGC.PY %d > S%d.OUT" % (threshold, idx),
                "if errorlevel 1 goto fail"]
    bat += ["echo PASS > STRGC.RES", "goto end", ":fail",
            "echo FAIL > STRGC.RES", ":end"]
    (stage / "STRGC.RES").unlink(missing_ok=True)
    (stage / "STRGC.BAT").write_bytes(("\r\n".join(bat) + "\r\n").encode("ascii"))
    conf = build / "strgc-dosbox.conf"
    conf.write_text(
        "[sdl]\nfullscreen=false\noutput=surface\n"
        "[dosbox]\nmemsize=1\n[cpu]\ncore=normal\n"
        "cputype=8086\ncycles=fixed 20000\n"
        '[autoexec]\nmount c "' + str(stage) + '"\nc:\ncall STRGC.BAT\nexit\n'
    )
    opts = {}
    if os.name == "nt":
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = 0
        opts["startupinfo"] = startup
    with (build / "strgc-emulator.log").open("w") as log:
        subprocess.run([args.dosbox, "-conf", str(conf), "-noconsole"],
                       timeout=args.timeout, stdout=log, stderr=log, **opts)
    checks = {}
    runs = {}
    raw = {}
    for idx, threshold in enumerate(THRESHOLDS):
        content = (stage / ("S%d.OUT" % idx)).read_text(errors="replace")
        raw[threshold] = content
        if "PASS strgc" not in content or "Traceback" in content:
            raise SystemExit("Failed threshold %d:\n%s" % (threshold, content))
        entries = {}
        for line in content.splitlines():
            fields = line.strip().split()
            if len(fields) == 10 and fields[0] == "PROFILE":
                _, name, trial, count, elapsed, before, during, after, gc_ms, check = fields
                entries.setdefault(name, []).append({
                    "trial": int(trial), "count": int(count), "ms": int(elapsed),
                    "before": int(before), "during": int(during),
                    "after": int(after), "gc_ms": int(gc_ms), "check": int(check)
                })
            elif len(fields) == 5 and fields[0] == "CONFIG":
                checks[threshold] = [int(v) for v in fields[1:]]
        if len(entries) != 4 or any(len(v) != 3 for v in entries.values()):
            raise SystemExit("Missing profile data for %d: %r" % (threshold, entries))
        if checks.get(threshold, [None,None])[1] != threshold:
            raise SystemExit("GC threshold did not take effect for %d" % threshold)
        runs[threshold] = entries
    result = (stage / "STRGC.RES").read_text().strip() if (stage / "STRGC.RES").exists() else "NO RESULT"
    if result != "PASS":
        raise SystemExit("DOSBox STRGC batch: " + result)
    summary = {}
    for threshold, tests in runs.items():
        summary[threshold] = {}
        for name, entries in tests.items():
            summary[threshold][name] = {
                "ms_per_unit": statistics.median(x["ms"]/x["count"] for x in entries),
                "gc_ms": statistics.median(x["gc_ms"] for x in entries),
                "allocated_before_collect": statistics.median(x["before"] - x["during"] for x in entries),
                "free_reclaimed": statistics.median(x["after"] - x["during"] for x in entries),
                "free_after_collect": statistics.median(x["after"] for x in entries),
                "checksum": entries[0]["check"],
            }
    report = {
        "mode": args.mode, "environment": "DOSBox normal 8086 fixed 20000 cycles",
        "executable_bytes": (build / "py86.exe").stat().st_size,
        "threshold_bytes": THRESHOLDS, "config": checks,
        "summary": summary, "trials": runs,
        "disclaimer": "BIOS tick ~55ms; timings are emulator relative, not V20 hardware speed"
    }
    (build / ("strgc-" + args.mode + ".json")).write_text(json.dumps(report, indent=2))
    print(json.dumps({"mode": args.mode, "summary": summary}, indent=2))
    print("PASS strgc_profile")

if __name__ == "__main__":
    main()
