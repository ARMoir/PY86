"""Run repeatable Py86 benchmarks using the built DOS EXE in DOSBox.

This is an emulator-relative performance comparison, not a V20 timing claim.
The DOSBox CPU configuration is pinned to 8086, fixed 20000 cycles.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import statistics
import subprocess

ROOT = Path(__file__).resolve().parent

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dosbox", required=True)
    p.add_argument("--emulator", choices=("classic", "staging"), default="classic")
    p.add_argument("--mode", default="baseline")
    p.add_argument("--timeout", type=int, default=220)
    p.add_argument("--vm-tests", action="store_true", help="Include dispatch microbenchmarks")
    p.add_argument("--heap", default="auto",
                   choices=("auto", "24000", "32000", "48000", "60000"),
                   help="PY86_HEAP used for comparison (default: auto)")
    args = p.parse_args()

    build = ROOT / "build"
    stage = ROOT / "bench-test"
    stage.mkdir(exist_ok=True)
    for f in (ROOT / "tests" / "bench").glob("*.PY"):
        shutil.copy2(f, stage / f.name)
    for f in (ROOT / "tests" / "pythonclock").glob("*.py"):
        shutil.copy2(f, stage / f.name)
    shutil.copy2(build / "py86.exe", stage / "PY86.EXE")
    vm_commands = (b"PY86 VMTEST.PY > VMTEST.OUT\r\n"
                   b"if errorlevel 1 goto fail\r\n") if args.vm_tests else b""
    # Set the heap for the entire DOS batch, including --heap-info and
    # the individual independent Py86 benchmark processes.
    heap_cmd = ("set PY86_HEAP=" + ("" if args.heap == "auto" else args.heap) +
                "\r\nset PY86_HEAP_MAX=\r\n").encode("ascii")
    (stage / "BENCH.BAT").write_bytes(
        b"@echo off\r\n" +
        heap_cmd +
        b"PY86 --heap-info > HEAPINFO.OUT\r\n"
        b"if errorlevel 1 goto fail\r\n"
        b"PY86 BENCH1.PY > BENCH1.OUT\r\n"
        b"if errorlevel 1 goto fail\r\n"
        + vm_commands +
        b"PY86 FRAMEBEN.PY > FRAMEBEN.OUT\r\n"
        b"if errorlevel 1 goto fail\r\n"
        b"PY86 FRAMEBEN.PY >> FRAMEBEN.OUT\r\n"
        b"if errorlevel 1 goto fail\r\n"
        b"PY86 FRAMEBEN.PY >> FRAMEBEN.OUT\r\n"
        b"if errorlevel 1 goto fail\r\n"
        b"echo PASS > BENCH.RES\r\n"
        b"goto done\r\n"
        b":fail\r\necho FAIL > BENCH.RES\r\n"
        b":done\r\n"
    )
    for name in ("BENCH1.OUT", "VMTEST.OUT", "FRAMEBEN.OUT",
                 "HEAPINFO.OUT", "BENCH.RES"):
        (stage / name).unlink(missing_ok=True)

    conf = build / "bench-dosbox.conf"
    video = ("[sdl]\nfullscreen=false\n" if args.emulator == "staging"
             else "[sdl]\nfullscreen=false\noutput=surface\n")
    cpu = ("core=normal\ncpu_cycles=20000\n" if args.emulator == "staging"
           else "core=normal\ncputype=8086\ncycles=fixed 20000\n")
    conf.write_text(
        video + "[dosbox]\nmemsize=1\n[cpu]\n" + cpu +
        '[autoexec]\nmount c "' + str(stage) + '"\nc:\ncall BENCH.BAT\nexit\n'
    )
    opts = {}
    if os.name == "nt":
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = 0
        opts["startupinfo"] = startup
    with (build / "bench-emulator.log").open("w") as log:
        subprocess.run(
            ([args.dosbox, "--conf", str(conf), "--noprimaryconf", "--nolocalconf"]
             if args.emulator == "staging" else
             [args.dosbox, "-conf", str(conf), "-noconsole"]),
            timeout=args.timeout, stdout=log, stderr=log, **opts,
        )

    parsed = {}
    memories = {}
    logs = {}
    for script in (("BENCH1", "VMTEST", "FRAMEBEN") if args.vm_tests
                   else ("BENCH1", "FRAMEBEN")):
        contents = (stage / (script + ".OUT")).read_text(errors="replace")
        logs[script] = contents
        parsed[script] = {}
        for line in contents.splitlines():
            fields = line.strip().split()
            if not fields:
                continue
            if fields[0] == "MEM" and len(fields) == 3:
                memories[script] = {"free": int(fields[1]), "allocated": int(fields[2])}
            if fields[0] == "BENCH" and len(fields) == 6:
                _, name, trial, count, ms, check = fields
                existing = parsed[script].setdefault(name, [])
                existing.append({
                    "trial": len(existing) if script == "FRAMEBEN" else int(trial),
                    "count": int(count),
                    "ms": int(ms), "checksum": int(check),
                })

    summary = {}
    for workloads in parsed.values():
        for name, runs in workloads.items():
            if len(runs) != 3 or any(x["ms"] <= 0 or x["count"] <= 0 for x in runs):
                raise SystemExit("Bad or missing benchmark trials for " + name)
            if len({x["checksum"] for x in runs}) != 1:
                raise SystemExit("Nondeterministic checksums for " + name)
            summary[name] = {
                "ms_per_op": statistics.median(x["ms"] / x["count"] for x in runs),
                "count": runs[0]["count"],
                "median_ms": statistics.median(x["ms"] for x in runs),
                "checksums": runs[0]["checksum"],
            }
    expected = {"local_int", "global_int", "dict_lookup", "instance_attr",
                "bound_method", "module_attr", "concat", "clock_frame"}
    if args.vm_tests:
        expected.update(("vm_load", "vm_branch", "vm_call", "vm_global", "vm_tuple"))
    result = (stage / "BENCH.RES").read_text().strip() if (stage / "BENCH.RES").exists() else "NO RESULT"
    if result != "PASS" or set(summary) != expected or any("Traceback" in text for text in logs.values()):
        print(json.dumps({"status": result, "raw": logs, "summary": summary}, indent=2))
        raise SystemExit("Py86 benchmark failed")

    info = (stage / "HEAPINFO.OUT").read_text().strip() if (stage / "HEAPINFO.OUT").exists() else ""
    info_fields = {}
    for field in info.split():
        if "=" in field:
            k, v = field.split("=", 1)
            info_fields[k] = v
    try:
        heap_bytes = int(info_fields["heap_bytes"])
        gc_total = int(info_fields["gc_total"])
        gc_free = int(info_fields["gc_free"])
    except (KeyError, ValueError):
        raise SystemExit("Bad PY86 --heap-info output: " + info)
    if not (24000 <= heap_bytes <= 60000):
        raise SystemExit("Selected heap outside expected 16-bit single-segment bounds")
    if args.heap != "auto" and heap_bytes != int(args.heap):
        raise SystemExit("Requested heap size was not selected")
    report = {
        "mode": args.mode,
        "environment": ("DOSBox Staging real-mode 20000 cycles, BIOS ~55ms tick"
                        if args.emulator == "staging" else
                        "DOSBox 0.74, 8086, fixed 20000 cycles, BIOS ~55ms tick"),
        "disclaimer": "Relative DOSBox results, not physical V20 clock speed",
        "executable_bytes": (build / "py86.exe").stat().st_size,
        "heap_request": args.heap,
        "python_heap_bytes": heap_bytes,
        "gc_total_bytes": gc_total,
        "gc_free_on_startup": gc_free,
        "heap_info": info_fields,
        "vm_tests": args.vm_tests,
        "memory": memories,
        "summary": summary,
        "trials": parsed,
    }
    output = build / ("benchmark-" + args.mode + ".json")
    output.write_text(json.dumps(report, indent=2))
    print(json.dumps({"mode": args.mode, "exe_bytes": report["executable_bytes"],
                      "memory": memories, "summary": summary}, indent=2))
    print("PASS benchmark")

if __name__ == "__main__":
    main()
