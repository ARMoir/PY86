"""Experimental MicroPython 1.29.0 DOS port patch preparation.

Never alters the pinned 1.24.1 checkout. This first-stage script applies
v1.24.1 adaptations where safe and records rejected hunks for review.
It does NOT claim compatibility until all rejects and tests are resolved.
"""
import argparse
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
SHA = "0fd6c573ea815774668bbb16b8e197c8822368b2"
PATCHES = (
    "compat-v1.24.1.patch",
    "compat-extra-libs-v1.24.1.patch",
    "compat-strcache-v1.24.1.patch",
    "compat-lazyhash-v1.24.1.patch",
    "compat-vmdecode-v1.24.1.patch",
    "compat-exit-v1.24.1.patch",
)

def execute(args, cwd):
    return subprocess.run(["git", *map(str, args)], cwd=cwd, capture_output=True, text=True)

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--report-dir", type=Path, required=True)
    p.add_argument("--allow-rejects", action="store_true")
    args=p.parse_args()
    source=args.source.resolve()
    out=args.report_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    rev=execute(["rev-parse","HEAD"],source)
    if rev.returncode != 0 or rev.stdout.strip() != SHA:
        raise SystemExit("Source must be pinned to MicroPython 1.29.0 "+SHA)
    entries=[]
    # Applying old core patch with rejects keeps every clean hunk, and
    # leaves explicit .rej files for each incompatible 1.29.0 context.
    for name in PATCHES:
        patch=HERE/name
        run=execute(["apply","--reject","--whitespace=nowarn",str(patch)],source)
        entries.append({"name":name,"exit":run.returncode,"diagnostic":run.stderr[-15000:]})
        print("PATCH",name,"exit",run.returncode,flush=True)
        print(run.stderr[-6500:],flush=True)
    rejects={}
    for path in sorted(source.rglob("*.rej")):
        name=str(path.relative_to(source))
        content=path.read_text(errors="replace")
        rejects[name]=content
        target=out/"rejects"/name
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(content)
        print("UNRESOLVED",name,len(content),"bytes")
    data={"version":"1.29.0","sha":SHA,"patches":entries,
          "rejects":{k:len(v) for k,v in rejects.items()},
          "all_resolved":len(rejects)==0 and all(x["exit"]==0 for x in entries)}
    (out/"patch-report.json").write_text(json.dumps(data,indent=2))
    (out/"patch-report.txt").write_text(
        "\n".join([("OK " if i["exit"]==0 else "REBASE ")+i["name"] for i in entries]+
                  ["", "Rejected hunk files:"]+[f"{k}: {len(v)} bytes" for k,v in rejects])+"\n")
    if not data["all_resolved"] and not args.allow_rejects:
        raise SystemExit("Unresolved 1.29.0 compatibility changes; not safe to ship")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
