"""Isolated, test-only Py86 bytecode fault experiments in disposable DOSBox.

Normal PY86.EXE has no injection facility.  Never run PY86F.EXE on actual DOS
hardware or on a mounted real drive.  Each fault gets a fresh DOSBox instance.
Dangerous fault outcomes are characterized, not asserted to be crash-proof.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent
CASES = ("normal", "bad-opcode", "bad-jump", "bad-pointer")

def run_case(dosbox, emulator, seconds, name):
    stage = ROOT / "fault-test" / name
    stage.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "build" / "py86f.exe", stage / "PY86F.EXE")
    shutil.copy2(ROOT / "tests" / "FAULTSRC.PY", stage / "FAULTSRC.PY")
    for filename in ("OUT.TXT", "CODE.TXT", "DONE.TXT"):
        (stage / filename).unlink(missing_ok=True)
    env_line = "" if name == "normal" else "set PY86_VMFAULT=" + name + "\r\n"
    batch = ("@echo off\r\n" + env_line +
             "PY86F FAULTSRC.PY > OUT.TXT\r\n" +
             "if errorlevel 1 echo NONZERO > CODE.TXT\r\n" +
             "if not errorlevel 1 echo ZERO > CODE.TXT\r\n" +
             "echo COMPLETE > DONE.TXT\r\n")
    (stage / "CASE.BAT").write_bytes(batch.encode("ascii"))
    video = "[sdl]\nfullscreen=false\n" if emulator == "staging" else (
        "[sdl]\nfullscreen=false\noutput=surface\n")
    cpu = ("core=normal\ncpu_cycles=20000\n" if emulator == "staging" else
           "core=normal\ncputype=8086\ncycles=fixed 20000\n")
    conf = ROOT / "build" / ("fault-" + name + ".conf")
    conf.write_text(video + "[dosbox]\nmemsize=1\n[cpu]\n" + cpu +
                    '[autoexec]\nmount c "' + str(stage) +
                    '"\nc:\ncall CASE.BAT\nexit\n')
    opts = {}
    if os.name == "nt":
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = 0
        opts["startupinfo"] = startup
    argv = ([dosbox, "--conf", str(conf), "--noprimaryconf", "--nolocalconf"]
            if emulator == "staging" else
            [dosbox, "-conf", str(conf), "-noconsole"])
    timed_out = False
    returncode = None
    with (ROOT / "build" / ("fault-" + name + ".log")).open("w") as log:
        try:
            result = subprocess.run(argv, timeout=seconds, stdout=log, stderr=log,
                                    **opts)
            returncode = result.returncode
        except subprocess.TimeoutExpired:
            timed_out = True
    output = (stage / "OUT.TXT").read_text(errors="replace") if (
        stage / "OUT.TXT").is_file() else ""
    code = (stage / "CODE.TXT").read_text(errors="replace").strip() if (
        stage / "CODE.TXT").is_file() else "MISSING"
    done = (stage / "DONE.TXT").exists()
    injected = "VMFAULT INJECTED " + name in output
    if timed_out:
        outcome = "timeout (possible invalid-bytecode loop)"
    elif not done:
        outcome = "abnormal termination (possible DOS/VM crash)"
    elif "PASS unmodified_fault_source" in output:
        outcome = "normal Python code executed"
    elif "Traceback" in output:
        outcome = "handled Python exception"
    elif code == "NONZERO":
        outcome = "nonzero DOS return without Python traceback"
    else:
        outcome = "unexpected exit or output"
    return {"case": name, "injected": injected, "emulator_returncode": returncode,
            "timeout": timed_out, "batch_completed": done, "dos_status": code,
            "outcome": outcome, "output": output}

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dosbox", required=True)
    p.add_argument("--emulator", choices=("classic", "staging"), default="staging")
    p.add_argument("--timeout", type=int, default=35, help="Per-case timeout")
    args = p.parse_args()
    if not (ROOT / "build" / "py86f.exe").is_file():
        raise SystemExit("Test-only PY86F.EXE is missing: build with --vm-fault-probe")
    results = [run_case(args.dosbox, args.emulator, args.timeout, name)
               for name in CASES]
    baseline, reserved = results[:2]
    errors = []
    if (baseline["timeout"] or not baseline["batch_completed"] or
            baseline["dos_status"] != "ZERO" or
            "PASS unmodified_fault_source" not in baseline["output"]):
        errors.append("Test-enabled binary does not execute unmodified bytecode")
    if (reserved["timeout"] or not reserved["batch_completed"] or
            reserved["dos_status"] != "NONZERO" or
            not reserved["injected"] or
            "opcode" not in reserved["output"].lower() or
            "PASS unmodified_fault_source" in reserved["output"]):
        errors.append("Reserved-opcode error was not handled cleanly")
    for row in results[2:]:
        if not row["injected"]:
            errors.append(row["case"] + ": fault was not injected")
        if "PASS unmodified_fault_source" in row["output"]:
            errors.append(row["case"] + ": damaged bytecode executed the original script")
    report = {
        "environment": "isolated DOSBox, never physical Tandy / production EXE",
        "warning": "Corrupt jump/pointer outcomes are diagnostic only; this suite does not prove the VM is bounds-safe.",
        "baseline_and_reserved_opcode_must_pass": True,
        "dangerous_cases_are_report_only": True,
        "cases": results,
        "errors": errors,
    }
    (ROOT / "build" / "vm-fault-results.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    if errors:
        raise SystemExit(1)

if __name__ == "__main__":
    main()
