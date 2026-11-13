"""Isolated Py86 GC fork feasibility and benchmark evidence collector.

No modification of master, no unsafe deployment claims.
"""
import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

PORT = Path(__file__).resolve().parents[2] / "ports" / "dos16"
OUT = PORT / "build" / "incremental-gc"
CORE = "0fd6c573ea815774668bbb16b8e197c8822368b2"
FORK = "6b9ed5871b52fd68debe5866af9a41333b828e73"
FORK_BASE = "970468103d5ce776d092a1eb84e3bdf2ab5a3b0b"


def run(*args):
    return subprocess.run([str(a) for a in args], text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


def git_sha(path, ref="HEAD"):
    p = run("git", "-C", path, "rev-parse", ref)
    if p.returncode:
        raise RuntimeError(p.stdout)
    return p.stdout.strip()


def prepare(source, fork):
    OUT.mkdir(parents=True, exist_ok=True)
    for path, ref, value in ((source, "HEAD", CORE), (fork, "HEAD", FORK),
                             (fork, "origin/master", FORK_BASE)):
        actual = git_sha(path, ref)
        if actual != value:
            raise RuntimeError("Unexpected source revision " + actual)
    diff = run("git", "-C", fork, "diff", "--binary",
               "origin/master", "HEAD", "--", "py/")
    if diff.returncode or not diff.stdout or "diff --git a/py/gc.c" not in diff.stdout:
        raise RuntimeError("Expected complete upstream GC source diff")
    patch = OUT / "raspy135-incremental-py.patch"
    patch.write_text(diff.stdout)
    changed = run("git", "-C", fork, "diff", "--name-only",
                  "origin/master", "HEAD", "--", "py/")
    files = changed.stdout.splitlines()
    test = run("git", "-C", source, "apply", "--check", patch)
    (OUT / "patch-check.log").write_text(test.stdout or ("PASS\n" if test.returncode == 0 else "UNKNOWN\n"))
    ready = test.returncode == 0
    if ready:
        applied = run("git", "-C", source, "apply", patch)
        (OUT / "patch-apply.log").write_text(applied.stdout)
        ready = applied.returncode == 0
    else:
        # Reject collection happens only on the disposable candidate checkout.
        rejected = run("git", "-C", source, "apply", "--reject", "--whitespace=nowarn", patch)
        (OUT / "patch-reject.log").write_text(rejected.stdout)
        for path in source.rglob("*.rej"):
            target = OUT / "rejects" / path.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
    report = {
        "baseline_core": CORE,
        "fork": "raspy135/micropython:gc-incremental",
        "fork_head": FORK,
        "fork_base": FORK_BASE,
        "changed_core_files": files,
        "patch_sha256": hashlib.sha256(patch.read_bytes()).hexdigest(),
        "patch_applicable": ready,
        "candidate": "ready for compilation and DOS tests" if ready
                     else "NOT PORTED: incompatible core hunks; no candidate timings",
        "warnings": [
            "ESP32/Unix code is not a validated 16-bit DOS collector.",
            "Even a clean patch needs a complete pointer-write barrier audit.",
            "DOSBox performance is not physical NEC V20 performance.",
        ],
    }
    (OUT / "compatibility.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


def snapshot(label):
    dest = OUT / label
    dest.mkdir(parents=True, exist_ok=True)
    required = {
        "PY86.EXE": PORT / "build" / "py86.exe",
        "py86.map": PORT / "build" / "py86.map",
        "test-results.json": PORT / "build" / "test-results.json",
        "benchmark.json": PORT / "build" / ("benchmark-incremental-" + label + ".json"),
        "runtime-profile.json": PORT / "build" / ("compile-profile-incremental-" + label + ".json"),
    }
    for name, src in required.items():
        if not src.is_file():
            raise RuntimeError("Missing required experimental evidence " + str(src))
        shutil.copy2(src, dest / name)
    report = json.loads((dest / "test-results.json").read_text())
    if report.get("batch_result") != "PASS":
        raise RuntimeError("DOSBox regression failed on " + label)
    for name in ("GC.OUT", "GCINCR.OUT", "ROBUST.OUT", "RUNTST.OUT"):
        src = PORT / "dos-test" / name
        if src.exists():
            shutil.copy2(src, dest / name)
    print("Saved verified " + label + " test and benchmark evidence")


def summary():
    OUT.mkdir(parents=True, exist_ok=True)
    status_file = OUT / "compatibility.json"
    status = json.loads(status_file.read_text()) if status_file.exists() else {}
    data = {"status": "baseline not measured", "candidate_applicable": status.get("patch_applicable"),
            "hardware_validated": False, "measurements": {}}
    for name in ("baseline", "data", "candidate"):
        dest = OUT / name
        bench = dest / "benchmark.json"
        prof = dest / "runtime-profile.json"
        if bench.is_file() and prof.is_file():
            b = json.loads(bench.read_text())
            p = json.loads(prof.read_text())
            data["measurements"][name] = {
                "executable_bytes": b["executable_bytes"],
                "heap_bytes": b["python_heap_bytes"],
                "gc_free_on_startup": b["gc_free_on_startup"],
                "bench_median_ms": {k: v["median_ms"] for k, v in b["summary"].items()},
                "runtime_gc": {k: v.get("runtime", {}) for k, v in p["samples"].items()},
            }
    if "candidate" in data["measurements"]:
        data["status"] = "both versions measured; candidate still requires GC barrier audit"
    elif "data" in data["measurements"]:
        data["status"] = "baseline and data-only GC measured; incremental fork NOT PORTED"
    elif "baseline" in data["measurements"]:
        data["status"] = "baseline measured; incremental candidate NOT qualified"
    lines = ["# Py86 incremental GC A/B lab", "",
             "Upstream reference: https://github.com/raspy135/micropython/tree/gc-incremental",
             "", "Production master is unchanged. No release is created.",
             "", "**" + data["status"] + "**", ""]
    if status.get("patch_applicable") is False:
        lines.extend(["Core patch conflict: see patch-check.log and rejects/.",
                      "Never count partial patching as an incremental-GC result.", ""])
    lines.extend(["| Workload | Baseline ms | Data-only ms | Incremental ms | Data/baseline |",
                  "|---|---:|---:|---:|---:|"])
    b = data["measurements"].get("baseline", {}).get("bench_median_ms", {})
    d = data["measurements"].get("data", {}).get("bench_median_ms", {})
    c = data["measurements"].get("candidate", {}).get("bench_median_ms", {})
    for key in sorted(set(b) | set(d) | set(c)):
        x, z, y = b.get(key), d.get(key), c.get(key)
        ratio = "{:.3f}x".format(z / x) if x and z else "n/a"
        lines.append("| {} | {} | {} | {} | {} |".format(
            key, x if x is not None else "-", z if z is not None else "-",
            y if y is not None else "-", ratio))
    lines.extend(["", "DOSBox Staging fixed 20000-cycle emulator, BIOS ~55ms tick.",
                  "Not a real Tandy V20 result; incremental GC is not certified for hardware.", ""])
    (OUT / "summary.json").write_text(json.dumps(data, indent=2) + "\n")
    (OUT / "SUMMARY.md").write_text("\n".join(lines))
    print("\n".join(lines))


def main():
    cli = argparse.ArgumentParser()
    subs = cli.add_subparsers(dest="command", required=True)
    prep = subs.add_parser("prepare")
    prep.add_argument("--source", type=Path, required=True)
    prep.add_argument("--fork", type=Path, required=True)
    snap = subs.add_parser("snapshot")
    snap.add_argument("--label", choices=("baseline", "data", "candidate"), required=True)
    subs.add_parser("summary")
    a = cli.parse_args()
    if a.command == "prepare":
        prepare(a.source.resolve(), a.fork.resolve())
    elif a.command == "snapshot":
        snapshot(a.label)
    else:
        summary()


if __name__ == "__main__":
    main()
