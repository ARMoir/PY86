"""Gate Py86 master releases on data-aware GC reference integrity at 3 heap sizes.

Runs the *actual release executable* in DOSBox Staging. No test-only flags,
no changes to normal Python/bytecode handling and no use of incremental GC.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess

PORT = Path(__file__).resolve().parent
ROOT = PORT / "build" / "release-data-gc-tests"
HEAPS = (24000, 32000, 48000)
TESTS = (
    ("GCINCR.PY", "MUT.OUT", "PASS incremental_gc_mutations"),
    ("EXTGC.PY", "EXT.OUT", "PASS extgc"),
    ("SNAKE.PY --selftest", "SNAKE.OUT", "PASS snake_logic"),
)

def run_heap(heap, dosbox, timeout):
    stage = ROOT / ("H" + str(heap))
    stage.mkdir(parents=True, exist_ok=True)
    shutil.copy2(PORT / "build" / "py86.exe", stage / "PY86.EXE")
    for name in ("GCINCR.PY", "EXTGC.PY"):
        shutil.copy2(PORT / "tests" / name, stage / name)
    shutil.copy2(PORT / "examples" / "SNAKE.PY", stage / "SNAKE.PY")
    lines = [
        "@echo off", "set PY86_HEAP=" + str(heap), "set PY86_HEAP_MAX=",
        "PY86 --heap-info > HEAP.OUT", "if errorlevel 1 goto fail",
    ]
    for command, logfile, _ in TESTS:
        lines += ["PY86 " + command + " > " + logfile, "if errorlevel 1 goto fail"]
    lines += ["echo PASS > RESULT.TXT", "goto end", ":fail",
              "echo FAIL > RESULT.TXT", ":end", ""]
    (stage / "RUNGCT.BAT").write_bytes("\r\n".join(lines).encode("ascii"))
    for name in ("HEAP.OUT", "RESULT.TXT", *(t[1] for t in TESTS)):
        (stage / name).unlink(missing_ok=True)
    config = stage / "dosbox.conf"
    config.write_text(
        "[sdl]\nfullscreen=false\n[dosbox]\nmemsize=1\n"
        "[cpu]\ncore=normal\ncpu_cycles=20000\n"
        '[autoexec]\nmount c "' + str(stage) + '"\nc:\ncall RUNGCT.BAT\nexit\n'
    )
    env = dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy")
    with (stage / "dosbox.log").open("w") as f:
        result = subprocess.run(
            [dosbox, "--conf", str(config), "--noprimaryconf", "--nolocalconf"],
            env=env, stdout=f, stderr=subprocess.STDOUT, timeout=timeout,
            check=False,
        )
    report = {"heap": heap, "emulator_exit_code": result.returncode}
    actual_result = stage / "RESULT.TXT"
    report["batch"] = actual_result.read_text(errors="replace").strip() if actual_result.exists() else "MISSING"
    info = stage / "HEAP.OUT"
    report["heap_info"] = info.read_text(errors="replace").strip() if info.exists() else "MISSING"
    report["tests"] = {}
    for command, logfile, marker in TESTS:
        source = stage / logfile
        data = source.read_text(errors="replace") if source.exists() else ""
        report["tests"][logfile] = {
            "pass": marker in data and "Traceback" not in data,
            "output": data[-1500:],
        }
    report["pass"] = (
        result.returncode == 0 and report["batch"] == "PASS"
        and ("heap_bytes=" + str(heap) + " ") in report["heap_info"]
        and all(t["pass"] for t in report["tests"].values())
    )
    return report

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dosbox", required=True)
    p.add_argument("--timeout", type=int, default=360)
    args = p.parse_args()
    ROOT.mkdir(parents=True, exist_ok=True)
    results = []
    for heap in HEAPS:
        print("Validating production data-aware GC at", heap, "bytes", flush=True)
        try:
            row = run_heap(heap, args.dosbox, args.timeout)
        except Exception as exc:
            row = {"heap": heap, "pass": False, "exception": repr(exc)}
        results.append(row)
        print("Result", heap, "PASS" if row["pass"] else "FAIL", flush=True)
    complete = all(x["pass"] for x in results)
    (ROOT / "result.json").write_text(json.dumps({
        "collector": "data-aware conservative GC, not incremental",
        "environment": "DOSBox Staging fixed 20000 cycles, not physical V20",
        "all_passed": complete,
        "tests": results,
    }, indent=2) + "\n")
    if not complete:
        raise SystemExit("STOP RELEASE: GC stress failure; see build/release-data-gc-tests/result.json")
    print("PASS production data-aware GC, all 24/32/48KB stress and mutation tests")

if __name__ == "__main__":
    main()
