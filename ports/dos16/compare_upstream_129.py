"""Audit v1.29.0 compatibility with pinned 1.24.1 DOS port adaptations.

Read only: records whether each patch applies. Never silently drops a
compatibility modification or auto-merges incompatible VM/GC changes.
"""
import argparse
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PATCHES = (
    "compat-v1.24.1.patch",
    "compat-extra-libs-v1.24.1.patch",
    "compat-strcache-v1.24.1.patch",
    "compat-lazyhash-v1.24.1.patch",
    "compat-vmdecode-v1.24.1.patch",
    "compat-exit-v1.24.1.patch",
)
PINNED_129 = "0fd6c573ea815774668bbb16b8e197c8822368b2"

def check(source: Path, report: Path):
    def git(*args):
        return subprocess.run(["git", *map(str, args)], cwd=source,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True)
    revision = git("rev-parse", "HEAD")
    if revision.returncode or revision.stdout.strip() != PINNED_129:
        raise SystemExit("Expected exactly upstream MicroPython v1.29.0 at " + PINNED_129)
    items = []
    for name in PATCHES:
        patch = ROOT / name
        result = git("apply", "--check", str(patch))
        entry = {
            "patch": name,
            "clean": result.returncode == 0,
            "diagnostic": (result.stderr or result.stdout)[-12000:],
        }
        items.append(entry)
        print(("CLEAN  " if entry["clean"] else "REBASE ") + name)
        if not entry["clean"]:
            print(entry["diagnostic"][:1800])
    output = {
        "upstream_version": "v1.29.0",
        "upstream_commit": PINNED_129,
        "all_patches_apply": all(p["clean"] for p in items),
        "patches": items,
        "explanation": "Patch check is independent, not cumulative. Even all clean requires full 8086 build and DOSBox tests.",
    }
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(output, indent=2) + "\n")
    print("Compatibility audit report:", report)
    return 0

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    args = p.parse_args()
    raise SystemExit(check(args.source.resolve(), args.report.resolve()))
