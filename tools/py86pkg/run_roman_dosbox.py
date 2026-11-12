"""Run converted PyPI roman 5.2 using a real 16-bit Py86 executable in DOSBox."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import zipfile

ROMAN_TEST = """import gc
import roman
print('PASS roman_import')
cases = ((0, 'N'), (1, 'I'), (4, 'IV'), (9, 'IX'),
         (42, 'XLII'), (49, 'XLIX'), (99, 'XCIX'),
         (2026, 'MMXXVI'), (1994, 'MCMXCIV'), (3999, 'MMMCMXCIX'),
         (4999, 'MMMMCMXCIX'))
for value, numeral in cases:
    got = roman.toRoman(value)
    assert got == numeral, (value, got, numeral)
    assert roman.fromRoman(numeral) == value
    assert roman.fromRoman(numeral.lower()) == value
print('PASS roman_roundtrip')
for bad in ('', 'ABC', 'IIIIII', 'VX', 'IM'):
    try:
        roman.fromRoman(bad)
    except roman.InvalidRomanNumeralError:
        pass
    else:
        raise AssertionError('accepted invalid Roman numeral')
print('PASS roman_invalid')
for bad in (-1, 5000):
    try:
        roman.toRoman(bad)
    except roman.OutOfRangeError:
        pass
    else:
        raise AssertionError('accepted out-of-range value')
print('PASS roman_bounds')
assert gc.mem_free() > 0
print('PASS roman')
"""

def check_archive(archive, stage):
    with zipfile.ZipFile(archive) as z:
        if "roman.py" not in z.namelist():
            raise ValueError("Expected flattened roman.py in converted library-only ZIP")
        report = json.loads(z.read("REPORT.JSON"))
        if report.get("package") != "roman" or report.get("version") != "5.2":
            raise ValueError("Converted package is not roman 5.2")
        if report.get("status") != "candidate_untested_on_dos":
            raise ValueError("Conversion blockers: " + str(report.get("issues")))
        if any(x["severity"] == "error" for x in report["issues"]):
            raise ValueError("Conversion has errors")
        (stage / "ROMAN.PY").write_bytes(z.read("roman.py"))
    return report

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archive", type=Path, required=True)
    p.add_argument("--py86", type=Path, required=True)
    p.add_argument("--dosbox", required=True)
    p.add_argument("--emulator", choices=("classic", "staging"), default="classic")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--timeout", type=int, default=300)
    args = p.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    stage = args.out / "stage"
    stage.mkdir(exist_ok=True)
    outcome = {"environment": "DOSBox " + args.emulator + ", real Py86 DOS binary",
               "passed": False, "batch_result": "NOT RUN", "stdout": ""}
    try:
        shutil.copyfile(args.py86, stage / "PY86.EXE")
        outcome["conversion"] = check_archive(args.archive, stage)
        (stage / "TESTROM.PY").write_text(ROMAN_TEST, encoding="ascii")
        (stage / "RUN.BAT").write_text(
            "@echo off\n"
            "PY86 TESTROM.PY > ROMAN.OUT\n"
            "if errorlevel 1 goto fail\n"
            "echo PASS > RESULT.TXT\n"
            "goto done\n"
            ":fail\n"
            "echo FAIL > RESULT.TXT\n"
            ":done\n",
            encoding="ascii",
        )
        conf = args.out / "dosbox.conf"
        # Staging is a real-mode x86 emulator, but no longer offers an
        # exact 8086 cputype. Classic DOSBox retains the 8086 setting.
        cpu = ("core=normal\ncpu_cycles=20000\n" if args.emulator == "staging"
               else "core=normal\ncputype=8086\ncycles=fixed 20000\n")
        video = ("[sdl]\nfullscreen=false\n" if args.emulator == "staging"
                 else "[sdl]\nfullscreen=false\noutput=surface\n")
        conf.write_text(
            video + "[dosbox]\nmemsize=1\n[cpu]\n" + cpu +
            "[autoexec]\nmount c \"" + str(stage.resolve()) + "\"\n"
            "c:\ncall RUN.BAT\nexit\n", encoding="ascii",
        )
        options = {}
        if os.name == "nt":
            startup = subprocess.STARTUPINFO()
            startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startup.wShowWindow = 0
            options["startupinfo"] = startup
        with (args.out / "emulator.log").open("w") as log:
            proc = subprocess.run(
                ([args.dosbox, "--conf", str(conf), "--noprimaryconf", "--nolocalconf"]
                 if args.emulator == "staging" else
                 [args.dosbox, "-conf", str(conf), "-noconsole"]),
                stdout=log, stderr=subprocess.STDOUT, timeout=args.timeout,
                check=False, **options)
        outf = stage / "ROMAN.OUT"
        outcome["stdout"] = outf.read_text(errors="replace") if outf.exists() else ""
        batch = stage / "RESULT.TXT"
        outcome["batch_result"] = batch.read_text(errors="replace").strip() if batch.exists() else "MISSING"
        required = ["PASS roman_import", "PASS roman_roundtrip",
                    "PASS roman_invalid", "PASS roman_bounds", "PASS roman"]
        outcome["missing"] = [x for x in required if x not in outcome["stdout"]]
        outcome["exit_status"] = proc.returncode
        outcome["passed"] = (proc.returncode == 0 and outcome["batch_result"] == "PASS"
                             and not outcome["missing"]
                             and "Traceback" not in outcome["stdout"])
    except (OSError, ValueError, zipfile.BadZipFile, subprocess.TimeoutExpired) as exc:
        outcome["error"] = str(exc)
    finally:
        (args.out / "roman-dosbox-report.json").write_text(json.dumps(outcome, indent=2))
        print(json.dumps(outcome, indent=2))
    return 0 if outcome["passed"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
