"""Isolated 8086 near/far data experiment. Does not alter production source.

patch-source adds an opt-in near annotation to the separate MicroPython tree.
summary compares only candidates passing complete DOSBox regressions and
checks benchmark results for matching checksums.
"""
import json
from pathlib import Path
import sys

MODES = ("production", "far128", "hotstate", "medium")
WORKLOADS = ("vm_load", "vm_branch", "vm_call", "vm_global", "vm_tuple",
             "local_int", "global_int", "dict_lookup", "instance_attr",
             "bound_method", "module_attr", "concat", "clock_frame")


def patch_source(folder):
    src = Path(folder)
    hpath = src / "py/mpstate.h"
    cpath = src / "py/mpstate.c"
    h = hpath.read_text()
    c = cpath.read_text()
    if "PY86_HOT_STATE_NEAR" in h and "PY86_HOT_STATE_NEAR" in c:
        print("Isolated MicroPython state already instrumented")
        return
    if "PY86_HOT_STATE_NEAR" in h or "PY86_HOT_STATE_NEAR" in c:
        raise SystemExit("Partial near-state patch detected")
    for content, text in ((h, "extern mp_state_ctx_t mp_state_ctx;"),
                          (c, "mp_state_ctx_t mp_state_ctx;")):
        if content.count(text) != 1:
            raise SystemExit("Unexpected MicroPython v1.24.1 state declaration: " + text)
    h = h.replace("extern mp_state_ctx_t mp_state_ctx;",
                  "#ifdef PY86_HOT_STATE_NEAR\n"
                  "extern mp_state_ctx_t __near mp_state_ctx;\n"
                  "#else\n"
                  "extern mp_state_ctx_t mp_state_ctx;\n"
                  "#endif")
    c = c.replace("mp_state_ctx_t mp_state_ctx;",
                  "#ifdef PY86_HOT_STATE_NEAR\n"
                  "mp_state_ctx_t __near mp_state_ctx;\n"
                  "#else\n"
                  "mp_state_ctx_t mp_state_ctx;\n"
                  "#endif")
    hpath.write_text(h)
    cpath.write_text(c)
    print("Patched isolated source; near-state annotations are conditional")


def summary(build_dir):
    build = Path(build_dir)
    dest = build / "memory-lab"
    dest.mkdir(exist_ok=True)
    reports = {}
    for mode in MODES:
        filename = build / ("benchmark-memory-" + mode + ".json")
        if filename.exists():
            reports[mode] = json.loads(filename.read_text())
    lines = ["# Py86 8086 medium versus hybrid near/far experiment", "",
             "DOSBox Staging results, not real 7 MHz V20 timing.",
             "All validated benchmarks use a 48 KB far GC heap.",
             "Production model: Open Watcom large (-ml) with -zt=256.",
             "far128: large model, -zt=128; hotstate: the same layout",
             "with MicroPython's frequently accessed state forced near.",
             "medium: Open Watcom -mm feasibility only.", "",
             "| Model | Full tests and benchmarks | EXE bytes | GC free |",
             "|---|---|---:|---:|"]
    rows = []
    for mode in MODES:
        if mode not in reports:
            lines.append("| %s | Not verified; check diagnostics | - | - |" % mode)
            rows.append({"mode": mode, "status": "not_verified"})
            continue
        report = reports[mode]
        lines.append("| %s | PASS | %d | %d |" %
                     (mode, report["executable_bytes"], report["memory"]["VMTEST"]["free"]))
        rows.append({"mode": mode, "status": "pass", "file_bytes": report["executable_bytes"]})
    if "production" in reports:
        base = reports["production"]["summary"]
        lines.extend(("", "## Relative throughput (positive means faster)", "",
                      "| Workload | Baseline ms/op | far128 | hotstate | medium |",
                      "|---|---:|---:|---:|---:|"))
        for name in WORKLOADS:
            orig = base[name]
            cells = [name, "%.4f" % orig["ms_per_op"]]
            for mode in MODES[1:]:
                if mode not in reports:
                    cells.append("not verified")
                    continue
                cand = reports[mode]["summary"][name]
                if cand["checksums"] != orig["checksums"] or cand["count"] != orig["count"]:
                    raise SystemExit("Mismatched result for %s in %s" % (name, mode))
                cells.append("%+.1f%%" % (
                    100 * (orig["ms_per_op"] / cand["ms_per_op"] - 1)))
            lines.append("| " + " | ".join(cells) + " |")
    failures = dest / "failures.txt"
    if failures.is_file():
        lines.extend(("", "## Failed candidates", "", failures.read_text()))
    lines.extend(("", "The production build is unchanged. Emulator differences",
                  "must be validated on the physical V20 before promotion.", ""))
    result = "\n".join(lines)
    (dest / "summary.md").write_text(result)
    (dest / "summary.json").write_text(json.dumps(rows, indent=2))
    print(result)


if __name__ == "__main__":
    if sys.argv[1] == "patch-source":
        patch_source(sys.argv[2])
    elif sys.argv[1] == "summary":
        summary(sys.argv[2])
    else:
        raise SystemExit("Specify patch-source or summary")
