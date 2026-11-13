"""Package *qualified* Py86 DOS16 A/D GC builds and test the actual DOS kit.

Only snapshots that have a PASS DOSBox regression report are allowed.
A complete incremental collector is deliberately excluded: its GC_WB
write-barrier and far-pointer audits are not complete.
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[2]
PORT = ROOT / "ports" / "dos16"
OUT = PORT / "build" / "incremental-gc"
KIT = OUT / "TANDYGC"
ZIP = OUT / "TANDYGC.zip"
FILES = {
    "RUN48.BAT": PORT / "hardware_gc" / "RUN48.BAT",
    "README.TXT": PORT / "hardware_gc" / "README.TXT",
    "GCBENCH.PY": PORT / "tests" / "bench" / "GCBENCH.PY",
    "BENCH1.PY": PORT / "tests" / "bench" / "BENCH1.PY",
    "GCINCR.PY": PORT / "tests" / "GCINCR.PY",
    "SNAKE.PY": PORT / "examples" / "SNAKE.PY",
}


def package():
    OUT.mkdir(parents=True, exist_ok=True)
    ZIP.unlink(missing_ok=True)
    shutil.rmtree(KIT, ignore_errors=True)
    KIT.mkdir()
    builds = {"A86.EXE": OUT / "baseline", "D86.EXE": OUT / "data"}
    info = {}
    for output, folder in builds.items():
        meta = folder / "test-results.json"
        exe = folder / "PY86.EXE"
        bench = folder / "benchmark.json"
        if not (meta.is_file() and exe.is_file() and bench.is_file()):
            raise RuntimeError("Missing qualified build " + str(folder))
        tests = json.loads(meta.read_text())
        if tests.get("batch_result") != "PASS":
            raise RuntimeError("Failed DOSBox regression: " + str(folder))
        benchmark = json.loads(bench.read_text())
        if benchmark.get("heap_request") != "48000":
            raise RuntimeError("Hardware test kit demands 48000-byte qualification")
        shutil.copy2(exe, KIT / output)
        info[output] = {
            "sha256": hashlib.sha256(exe.read_bytes()).hexdigest(),
            "bytes": exe.stat().st_size,
            "dosbox_regressions": "PASS",
            "emulator": benchmark["environment"],
            "heap_request": benchmark["heap_request"],
        }
    for name, source in FILES.items():
        if len(Path(name).stem) > 8 or len(Path(name).suffix) > 4:
            raise RuntimeError("DOS 8.3 violation: " + name)
        if not source.is_file():
            raise RuntimeError("Missing kit source: " + str(source))
        shutil.copy2(source, KIT / name)
    (KIT / "BUILD.JSN").write_text(json.dumps(info, indent=2) + "\n")
    (KIT / "SHA256.TXT").write_text("\r\n".join(
        item["sha256"] + "  " + name
        for name, item in info.items()) + "\r\n")
    with ZipFile(ZIP, "w", compression=ZIP_DEFLATED) as z:
        for item in sorted(KIT.iterdir()):
            z.write(item, item.name)
    with ZipFile(ZIP) as z:
        bad = z.testzip()
        if bad:
            raise RuntimeError("Corrupt kit entry: " + bad)
    print("PASS qualified baseline/data-only Tandy kit:", ZIP,
          "bytes:", ZIP.stat().st_size)


def verify(dosbox, timeout):
    if not KIT.joinpath("A86.EXE").exists() or not KIT.joinpath("D86.EXE").exists():
        raise RuntimeError("Package kit before testing it")
    for name in ("RESULT.TXT", "A1.TXT", "D1.TXT", "A2.TXT", "D2.TXT",
                 "ACPU.TXT", "DCPU.TXT", "ACHK.TXT", "DCHK.TXT",
                 "ASNK.TXT", "DSNK.TXT"):
        (KIT / name).unlink(missing_ok=True)
    conf = OUT / "tandy-kit-dosbox.conf"
    conf.write_text(
        "[sdl]\nfullscreen=false\n[dosbox]\nmemsize=1\n"
        "[cpu]\ncore=normal\ncpu_cycles=20000\n"
        '[autoexec]\nmount c "' + str(KIT) + '"\nc:\ncall RUN48.BAT\nexit\n')
    environment = dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy")
    with (OUT / "tandy-kit-dosbox.log").open("w") as log:
        p = subprocess.run([dosbox, "--conf", str(conf), "--noprimaryconf",
                            "--nolocalconf"], env=environment,
                           stdout=log, stderr=subprocess.STDOUT, timeout=timeout)
    if p.returncode:
        raise RuntimeError("DOSBox did not exit successfully")
    if not (KIT / "RESULT.TXT").exists() or (KIT / "RESULT.TXT").read_text().strip() != "PASS":
        raise RuntimeError("Hardware batch failed its emulator check")
    for key, token in (
        ("ACHK.TXT", "PASS incremental_gc_mutations"),
        ("DCHK.TXT", "PASS incremental_gc_mutations"),
        ("ASNK.TXT", "PASS snake_logic"),
        ("DSNK.TXT", "PASS snake_logic"),
        ("A1.TXT", "PASS gcbench"),
        ("A2.TXT", "PASS gcbench"),
        ("D1.TXT", "PASS gcbench"),
        ("D2.TXT", "PASS gcbench"),
        ("ACPU.TXT", "PASS microbench"),
        ("DCPU.TXT", "PASS microbench"),
    ):
        content = (KIT / key).read_text(errors="replace")
        if token not in content or "Traceback" in content:
            raise RuntimeError("Bad/missing DOS test output " + key)
    checksums = {}
    for name in ("gc_raw", "gc_refs"):
        values = []
        for key in ("A1.TXT", "A2.TXT", "D1.TXT", "D2.TXT"):
            for line in (KIT / key).read_text().splitlines():
                parts = line.split()
                if len(parts) == 6 and parts[0:2] == ["BENCH", name]:
                    values.append((int(parts[4]), int(parts[5])))
        if len(values) != 12 or len({checksum for _, checksum in values}) != 1:
            raise RuntimeError("GC benchmark trial count or checksum mismatch: " + name)
        checksums[name] = {
            "samples": len(values),
            "checksum": values[0][1],
            "times_ms": [elapsed for elapsed, _ in values],
        }
    (OUT / "tandy-kit-dosbox-verification.json").write_text(json.dumps({
        "status": "PASS", "environment": "DOSBox Staging 0.83, fixed 20000 cycles",
        "hardware_qualified": False, "checksum_validation": checksums,
    }, indent=2) + "\n")
    print("PASS actual RUN48.BAT in DOSBox, 24 checksum-verified GC benchmark samples")


def main():
    p = argparse.ArgumentParser()
    cmd = p.add_subparsers(dest="mode", required=True)
    cmd.add_parser("package")
    v = cmd.add_parser("verify")
    v.add_argument("--dosbox", required=True)
    v.add_argument("--timeout", type=int, default=360)
    a = p.parse_args()
    if a.mode == "package":
        package()
    else:
        verify(a.dosbox, a.timeout)


if __name__ == "__main__":
    main()
