"""A/B benchmark actual 16-bit DOS executable for file.readline, iteration and readinto."""
import argparse
import json
import os
from pathlib import Path
import shutil
import statistics
import subprocess

ROOT = Path(__file__).resolve().parent
p = argparse.ArgumentParser()
p.add_argument("--dosbox", required=True)
p.add_argument("--mode", required=True)
p.add_argument("--timeout", type=int, default=240)
args = p.parse_args()
stage = ROOT / "filebench-test"
stage.mkdir(exist_ok=True)
build = ROOT / "build"
shutil.copy2(build / "py86.exe", stage / "PY86.EXE")
shutil.copy2(ROOT / "tests" / "bench" / "FIOBEN.PY", stage / "FIOBEN.PY")
commands = ["@echo off"]
labels = {"line": "L", "iter": "I", "readinto": "R"}
for phase in labels:
    for trial in range(3):
        filename = "%s%d.OUT" % (labels[phase], trial)
        (stage / filename).unlink(missing_ok=True)
        commands += ["PY86 FIOBEN.PY %s > %s" % (phase, filename),
                     "if errorlevel 1 goto fail"]
commands += ["echo PASS > FIO.RES", "goto done", ":fail",
             "echo FAIL > FIO.RES", ":done"]
(stage / "FIO.RES").unlink(missing_ok=True)
(stage / "RUNFIO.BAT").write_bytes(("\r\n".join(commands) + "\r\n").encode("ascii"))
conf = build / "filebench-dosbox.conf"
conf.write_text(
    "[sdl]\nfullscreen=false\noutput=surface\n"
    "[dosbox]\nmemsize=1\n"
    "[cpu]\ncore=normal\ncputype=8086\ncycles=fixed 20000\n"
    '[autoexec]\nmount c "' + str(stage) + '"\nc:\ncall RUNFIO.BAT\nexit\n'
)
options = {}
if os.name == "nt":
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 0
    options["startupinfo"] = startup
with (build / "filebench-emulator.log").open("w") as log:
    subprocess.run([args.dosbox, "-conf", str(conf), "-noconsole"],
                   timeout=args.timeout, stdout=log, stderr=log, **options)
result = (stage / "FIO.RES").read_text().strip() if (stage / "FIO.RES").exists() else "NO RESULT"
reports = {}
errors = []
for phase, prefix in labels.items():
    trials = []
    for i in range(3):
        fn = "%s%d.OUT" % (prefix, i)
        contents = (stage / fn).read_text(errors="replace") if (stage / fn).exists() else ""
        parts = next((x.split() for x in contents.splitlines() if x.startswith("BENCH ")), [])
        if (len(parts) != 5 or parts[1] != phase or
                "PASS filebench" not in contents or "Traceback" in contents):
            errors.append("%s: %s" % (fn, contents))
            continue
        trials.append({"count": int(parts[2]), "ms": int(parts[3]),
                       "checksum": int(parts[4])})
    if len(trials) != 3:
        errors.append(phase + " missing trials")
    else:
        if len({(x["count"], x["checksum"]) for x in trials}) != 1:
            errors.append(phase + " inconsistent checksums")
        reports[phase] = {
            "ms_per_line": statistics.median(x["ms"] / x["count"] for x in trials),
            "median_ms": statistics.median(x["ms"] for x in trials),
            "count": trials[0]["count"],
            "checksum": trials[0]["checksum"],
            "trials": trials,
        }
if result != "PASS" or errors:
    raise SystemExit(json.dumps({"batch": result, "errors": errors, "reports": reports}, indent=2))
output = {"mode": args.mode,
          "environment": "DOSBox 8086, core=normal, cycles=fixed 20000, 55ms BIOS timer",
          "exe_bytes": (build / "py86.exe").stat().st_size,
          "summary": reports,
          "disclaimer": "Emulated results only; not physical V20 speed"}
(build / ("filebench-" + args.mode + ".json")).write_text(json.dumps(output, indent=2))
print(json.dumps(output, indent=2))
print("PASS filebench runner")
