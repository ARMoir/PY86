"""Apply the previously qualified P29OPT 1KA GC root-batching patch for releases.

Edits only the isolated pinned MicroPython checkout and the ephemeral runner
copy of ports/dos16/port/main.c. Never modifies production checkout sources
in Git history. Fail closed if either upstream source has drifted.
"""
import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PORT = ROOT / "ports" / "dos16"
sys.path.insert(0, str(ROOT / "tools" / "py86pkg"))
from gc129_lab import patch_gc, patch_main

UPSTREAM_SHA = "0fd6c573ea815774668bbb16b8e197c8822368b2"

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=True)
    args=p.parse_args()
    source=args.source.resolve()
    sha=subprocess.check_output(
        ["git","-C",str(source),"rev-parse","HEAD"],text=True
    ).strip()
    if sha != UPSTREAM_SHA:
        raise SystemExit("Refusing to patch unexpected MicroPython core "+sha)
    gc_file=source/"py"/"gc.c"
    main_file=PORT/"port"/"main.c"
    original_gc=gc_file.read_text()
    original_main=main_file.read_text()
    if "py86_gc_collect_root_words" in original_gc or "py86_gc_collect_root_words" in original_main:
        raise SystemExit("GC batching source already patched; refusing ambiguous double patch")
    new_gc=patch_gc(original_gc.replace("\r\n","\n"))
    new_main=patch_main(original_main.replace("\r\n","\n"))
    if new_gc==original_gc or new_main==original_main:
        raise SystemExit("Expected both GC and DOS root-scan changes")
    if new_gc.count("void py86_gc_collect_root_words(")!=2:
        raise SystemExit("GC root helper signature not as expected")
    gc_file.write_text(new_gc)
    main_file.write_text(new_main)
    out=PORT/"build"/"release-gc-source.txt"
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(
        "PY86_GC129_APPLIED\n"
        "upstream="+sha+"\n"
        "gc_sha256="+hashlib.sha256(new_gc.encode()).hexdigest()+"\n"
        "main_sha256="+hashlib.sha256(new_main.encode()).hexdigest()+"\n"
    )
    print("Applied qualified 1.29.0 GC root batching to ephemeral release build")
    print(out.read_text())

if __name__=="__main__":
    main()
