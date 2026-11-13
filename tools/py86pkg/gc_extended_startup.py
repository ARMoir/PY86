"""Extended DOSBox qualification plus native Snake startup phase profiler.

Baseline and data-aware GC, fixed 24/32/48 KB heaps, independent processes.
The same original Snake source is run in --selftest mode so it terminates;
this is a compilation/import proxy, not a frame-visible or DOS-loader timer.
"""
import argparse
import json
import os
import re
import shutil
import statistics
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "ports" / "dos16"
OUT = ROOT / "build" / "gc-extended"
GC = ROOT / "build" / "incremental-gc"
PROF = re.compile(r"^P86PROF read_ms=(\d+) lexer_ms=(\d+) parse_ms=(\d+) compile_ms=(\d+) exec_ms=(\d+) gc_free=(\d+)$", re.M)
FIELDS = ("read_ms", "lexer_ms", "parse_ms", "compile_ms", "exec_ms", "gc_free")
TESTS = (
    ("EXTGC.PY", "EXTGC.OUT", "PASS extgc"),
    ("GCINCR.PY", "GCINCR.OUT", "PASS incremental_gc_mutations"),
    ("SNAKE.PY --selftest", "SNAKE.OUT", "PASS snake_logic"),
    ("SNKMIN.PY --selftest", "SNKMIN.OUT", "PASS snake_logic"),
    ("MINIMAL.PY", "MINIMAL.OUT", "START_INIT"),
)

def short_snake(src):
    """Only remove comments, empty lines and its module docstring; no gameplay edits."""
    if not src.startswith('"""'):
        raise RuntimeError("Snake module docstring changed")
    close = src.find('"""', 3)
    if close < 0:
        raise RuntimeError("Snake docstring unterminated")
    src = src[close + 3:]
    return "\n".join(
        line.rstrip() for line in src.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ) + "\n"

def write_stage(stage, exe, heap):
    stage.mkdir(parents=True, exist_ok=True)
    shutil.copy2(exe, stage / "PY86.EXE")
    for name in ("EXTGC.PY", "GCINCR.PY"):
        shutil.copy2(ROOT / "tests" / name, stage / name)
    snake = (ROOT / "examples" / "SNAKE.PY").read_text()
    (stage / "SNAKE.PY").write_text(snake)
    (stage / "SNKMIN.PY").write_text(short_snake(snake))
    (stage / "MINIMAL.PY").write_text(
        'import time\nprint("START_INIT", time.init_ms())\n'
        'print("START_RUN", time.startup_ms())\n')
    commands = ["@echo off", "set PY86_HEAP=" + str(heap),
                "set PY86_HEAP_MAX=", "set PY86_PROFILE=1"]
    commands.extend(["PY86 --heap-info > HEAP.OUT", "if errorlevel 1 goto fail"])
    for cmd, out, _ in TESTS:
        commands.extend(["PY86 " + cmd + " > " + out, "if errorlevel 1 goto fail"])
    commands.extend(["echo PASS > DONE.TXT", "goto end",
                     ":fail", "echo FAIL > DONE.TXT", ":end", ""])
    (stage / "RUN.BAT").write_bytes("\r\n".join(commands).encode("ascii"))
    for name in ["HEAP.OUT", "DONE.TXT", *(x[1] for x in TESTS)]:
        (stage / name).unlink(missing_ok=True)

def measure(mode, heap, dosbox, timeout):
    stage = OUT / (mode + str(heap))
    exe = GC / mode / "PY86.EXE"
    assert exe.exists(), "Missing verified build: " + str(exe)
    write_stage(stage, exe, heap)
    conf = stage / "run.conf"
    conf.write_text(
        "[sdl]\nfullscreen=false\n[dosbox]\nmemsize=1\n"
        "[cpu]\ncore=normal\ncpu_cycles=20000\n"
        '[autoexec]\nmount c "' + str(stage) + '"\nc:\ncall RUN.BAT\nexit\n')
    env = dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy")
    with (stage / "dosbox.log").open("w") as out:
        subprocess.run([dosbox, "--conf", str(conf), "--noprimaryconf",
                        "--nolocalconf"], env=env, stdout=out,
                       stderr=subprocess.STDOUT, timeout=timeout, check=True)
    row = {"mode": mode, "heap_request": heap, "tests": {}}
    row["batch"] = (stage / "DONE.TXT").read_text().strip() if (stage / "DONE.TXT").exists() else "MISSING"
    heaptext = (stage / "HEAP.OUT").read_text(errors="replace") if (stage / "HEAP.OUT").exists() else ""
    row["heap_report"] = heaptext.strip()
    for cmd, name, marker in TESTS:
        text = (stage / name).read_text(errors="replace") if (stage / name).exists() else ""
        found = PROF.findall(text)
        row["tests"][name] = {"passed": marker in text and "Traceback" not in text,
                              "profile": dict(zip(FIELDS, [int(v) for v in found[0]])) if len(found) == 1 else None,
                              "output": text[-2000:]}
    row["pass"] = row["batch"] == "PASS" and all(item["passed"] and item["profile"]
                         for item in row["tests"].values()) and "heap_bytes=" + str(heap) in heaptext
    return row

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dosbox", required=True)
    p.add_argument("--timeout", type=int, default=360)
    a = p.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    results = []
    for heap in (48000, 32000, 24000):
        for mode in ("baseline", "data"):
            print("Running", mode, heap, flush=True)
            try:
                result = measure(mode, heap, a.dosbox, a.timeout)
                results.append(result)
                print("Result", mode, heap, "PASS" if result["pass"] else "FAIL",
                      flush=True)
            except Exception as exc:
                results.append({"mode": mode, "heap_request": heap,
                                "pass": False, "error": repr(exc)})
                print("FAIL:", exc, flush=True)
    (OUT / "extended-results.json").write_text(json.dumps({
        "environment": "DOSBox Staging v0.83.0 fixed 20000 cycles; not hardware",
        "sources": ["Production GC", "Data-aware GC experimental 512-byte bitmap"],
        "results": results, "all_passed": all(x["pass"] for x in results),
        "caution": "Snake selftest excludes screen drawing; P86PROF excludes DOS loader",
    }, indent=2) + "\n")
    # Human summary can be inspected without rerunning the emulator.
    lines = ["# Extended GC and Snake startup lab", "",
             "DOSBox Staging fixed 20000 cycles; BIOS-tick resolution ~55 ms.",
             "P86PROF stages: read, lexer, parse, compile, exec; excludes DOS EXE load.",
             "Snake --selftest exits before curses screen drawing, so it isolates",
             "parsing and interpreter-side imports, not time to first screen.",
             "", "| Variant | Heap | Extended GC | Mutations | Snake | Trimmed Snake |",
             "|---|---:|---|---|---|---|"]
    for x in results:
        tests = x.get("tests", {})
        lines.append("| {} | {} | {} | {} | {} | {} |".format(
            x["mode"], x["heap_request"], *(
                "PASS" if tests.get(n, {}).get("passed") else "FAIL"
                for n in ("EXTGC.OUT", "GCINCR.OUT", "SNAKE.OUT", "SNKMIN.OUT"))))
    lines.extend(["", "| Variant | Heap | Snake read | lexer | parse | compile | exec |",
                  "|---|---:|---:|---:|---:|---:|---:|"])
    for x in results:
        prof = x.get("tests", {}).get("SNAKE.OUT", {}).get("profile") or {}
        lines.append("| {} | {} | {} | {} | {} | {} | {} |".format(
            x["mode"], x["heap_request"], *(prof.get(k, "-")
                 for k in ("read_ms", "lexer_ms", "parse_ms", "compile_ms", "exec_ms"))))
    lines.extend(["", "Files: extended-results.json and per-run DOSBox output.", ""])
    (OUT / "SUMMARY.md").write_text("\n".join(lines))
    if not all(x["pass"] for x in results):
        raise SystemExit("At least one extended DOSBox case FAILED; see uploaded evidence")
    print("PASS all extended GC/24KB/32KB/48KB Snake and safety tests")

if __name__ == "__main__":
    main()
