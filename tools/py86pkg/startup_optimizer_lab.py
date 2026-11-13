"""DOSBox A/B of Py86 ordinary two-copy vs GC-owned direct source loader.

Measure end-to-end DOS-child load using START86 and time.launch_ms(), and
the read/parse/compile/exec breakdown from the existing P86PROF. All test
files have DOS 8.3 filenames. This is NOT physical NEC V20 timing.
"""
import argparse
import json
import os
import re
import shutil
import statistics
import subprocess
from pathlib import Path

PORT = Path(__file__).resolve().parents[2] / "ports" / "dos16"
OUT = PORT / "build" / "startup-lab"
PROF = re.compile(r"^P86PROF read_ms=(\d+) lexer_ms=(\d+) parse_ms=(\d+) compile_ms=(\d+) exec_ms=(\d+) gc_free=(\d+)$", re.M)
FIELDS = ("read_ms", "lexer_ms", "parse_ms", "compile_ms", "exec_ms", "gc_free")

def capture(label):
    OUT.mkdir(parents=True, exist_ok=True)
    exe = PORT / "build" / "py86.exe"
    if not exe.is_file():
        raise RuntimeError("Missing build")
    shutil.copy2(exe, OUT / (label + ".exe"))
    sh = OUT / (label + ".map")
    shutil.copy2(PORT / "build" / "py86.map", sh)

def run_one(label, dosbox):
    stage = OUT / label
    stage.mkdir(parents=True, exist_ok=True)
    shutil.copy2(OUT / (label + ".exe"), stage / "PY86.EXE")
    shutil.copy2(PORT / "build" / "start86.exe", stage / "START86.EXE")
    snake = (PORT / "examples" / "SNAKE.PY").read_text()
    # Same source, same functionality; only extra first-statement timer.
    snake = 'import time\nprint("SNAKE_LAUNCH_MS", time.launch_ms())\n' + snake
    (stage / "SNKLOAD.PY").write_text(snake)
    (stage / "MINIMAL.PY").write_text(
        'import time\nprint("START_INIT_MS",time.init_ms())\n'
        'print("START_RUN_MS",time.startup_ms())\n'
        'print("START_LAUNCH_MS",time.launch_ms())\n')
    lines = ["@echo off", "set PY86_PROFILE=1", "set PY86_HEAP=48000",
             "set PY86_HEAP_MAX="]
    for test in ("MINIMAL", "SNKLOAD"):
        for n in range(3):
            args = " --selftest" if test == "SNKLOAD" else ""
            lines.append("START86 PY86 " + test + ".PY" + args
                         + " > " + test[:3] + str(n) + ".OUT")
            lines.append("if errorlevel 1 goto fail")
    lines += ["echo PASS > RESULT.TXT", "goto done", ":fail",
              "echo FAIL > RESULT.TXT", ":done", ""]
    (stage / "RUN.BAT").write_bytes("\r\n".join(lines).encode("ascii"))
    conf = stage / "startup.conf"
    conf.write_text("[sdl]\nfullscreen=false\n[dosbox]\nmemsize=1\n"
        "[cpu]\ncore=normal\ncpu_cycles=20000\n"
        '[autoexec]\nmount c "' + str(stage) + '"\nc:\ncall RUN.BAT\nexit\n')
    env = dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy")
    with (stage / "dosbox.log").open("w") as log:
        subprocess.run([dosbox,"--conf",str(conf),"--noprimaryconf",
                        "--nolocalconf"],env=env,stdout=log,
                       stderr=subprocess.STDOUT,timeout=360,check=True)
    status = stage / "RESULT.TXT"
    if not status.is_file() or status.read_text().strip() != "PASS":
        raise RuntimeError("DOS batch failed in " + label)
    result = {"mode":label,"executable_bytes":(OUT / (label+".exe")).stat().st_size,
              "tests":{}}
    for typ in ("MINIMAL", "SNKLOAD"):
        rows = []
        for n in range(3):
            path = stage / (typ[:3]+str(n)+".OUT")
            content = path.read_text(errors="replace")
            if "Traceback" in content or (typ=="SNKLOAD" and "PASS snake_logic" not in content):
                raise RuntimeError("Startup test error: " + str(path) + content[-600:])
            prof = PROF.findall(content)
            if len(prof)!=1:
                raise RuntimeError("No P86PROF for "+str(path))
            measures = dict(zip(FIELDS,[int(x) for x in prof[0]]))
            k = "SNAKE_LAUNCH_MS" if typ=="SNKLOAD" else "START_LAUNCH_MS"
            found = re.search(r"^"+k+r" (\d+)$",content,re.M)
            if not found:
                raise RuntimeError("Missing START86 end-to-end timing in "+str(path)+": "+content)
            measures["launch_to_first_python_ms"] = int(found.group(1))
            rows.append(measures)
        result["tests"][typ] = {
            "trials":rows,
            "median":{k:statistics.median(r[k] for r in rows)
                      for k in rows[0]},
        }
    return result

def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="command",required=True)
    one = sub.add_parser("capture")
    one.add_argument("--label",choices=("regular","direct"),required=True)
    test = sub.add_parser("compare")
    test.add_argument("--dosbox",required=True)
    a = p.parse_args()
    if a.command == "capture":
        capture(a.label)
    else:
        rows = [run_one(mode,a.dosbox) for mode in ("regular","direct")]
        out={"environment":"DOSBox Staging 0.83 fixed 20000 cycles",
             "disclaimer":"Emulator/BIOS tick (~55ms), not Tandy physical timing",
             "results":rows}
        OUT.mkdir(parents=True,exist_ok=True)
        (OUT/"startup-comparison.json").write_text(json.dumps(out,indent=2)+"\n")
        for row in rows:
            print(row["mode"], row["tests"]["SNKLOAD"]["median"],
                  "exe_bytes",row["executable_bytes"])
        print("PASS direct-loader vs regular-loader startup A/B")

if __name__ == "__main__":
    main()
