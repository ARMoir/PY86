"""Build a DOS 8.3 Tandy A/B package from ONLY passing parser-lab binaries."""
from pathlib import Path
import json
import zipfile

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "build"
LAB = BUILD / "parser-lab"
DIST = ROOT / "dist"
DIST.mkdir(exist_ok=True)

MODES = {
    "base": ("P86PBASE.EXE", "RUNPB.BAT", "PBAS.LOG", "SBAS.LOG"),
    "all": ("P86PALL.EXE", "RUNPA.BAT", "PALL.LOG", "SALL.LOG"),
    "p512": ("P86P512.EXE", "RUN512.BAT", "P512.LOG", "S512.LOG"),
    "p1k": ("P86P1K.EXE", "RUN1K.BAT", "P1K.LOG", "S1K.LOG"),
    "p2k": ("P86P2K.EXE", "RUN2K.BAT", "P2K.LOG", "S2K.LOG"),
    "geo": ("P86PGEO.EXE", "RUNGEO.BAT", "PGEO.LOG", "SGEO.LOG"),
    "p1ka": ("P86P1KA.EXE", "RUN1KA.BAT", "P1KA.LOG", "S1KA.LOG"),
    "p2ka": ("P86P2KA.EXE", "RUN2KA.BAT", "P2KA.LOG", "S2KA.LOG"),
}

def bat(exe: str, demo_log: str, stress_log: str) -> str:
    stem = exe[:-4]
    return ("\r\n".join([
        "@echo off",
        "set PY86_PROFILE=1",
        "set PY86_HEAP=48000",
        stem + " DEMO.PY > " + demo_log,
        "if errorlevel 1 goto fail",
        stem + " PARSST.PY > " + stress_log,
        "if errorlevel 1 goto fail",
        'FIND "P86PROF" ' + demo_log,
        'FIND "P86PROF" ' + stress_log,
        "goto done",
        ":fail",
        "echo PARSER TEST FAILED - inspect logs",
        ":done",
        "set PY86_HEAP=",
        "set PY86_PROFILE=",
        ""
    ]))

def main():
    verified = {}
    for mode, info in MODES.items():
        file = LAB / ("PY86-" + mode + ".EXE")
        profile = BUILD / ("compile-profile-parser-" + mode + ".json")
        if not (file.is_file() and profile.is_file()):
            continue
        p = json.loads(profile.read_text())
        if p["mode"] != "parser-" + mode or "PSTRES.OUT" not in p["samples"]:
            raise SystemExit("Missing passing parser stress proof for " + mode)
        verified[mode] = (file, p, info)
    if "base" not in verified:
        raise SystemExit("Parser baseline not verified; refusing to package")
    docs = [
        "PY86 .PY PARSER PERFORMANCE LAB - TANDY 1000 EX / NEC V20",
        "",
        "EXPERIMENTAL: standard PY86.EXE is not overwritten.",
        "All executables, batch files and log files have DOS 8.3 names.",
        "Run inside your existing C:\\PY86 folder (must contain DEMO.PY).",
        "PARSST.PY is included and tests 100 syntax-tree assignments.",
        "",
        "START: RUNPB baseline, then candidate selected by emulator results.",
        "RUNPA = previous compiler-only optimization (the first comparator).",
        "RUN512 / RUN1K / RUN2K = fixed parser-node allocation blocks.",
        "RUNGEO = geometric in-place growth of parser blocks.",
        "RUN1KA / RUN2KA = fixed blocks plus compiler-only -oi/-ol/-oe/-oh.",
        "A missing batch means that candidate failed DOSBox validation.",
        "",
        "Every RUN*.BAT runs DEMO.PY and PARSST.PY, printing P86PROF times",
        "and saving complete logs. Check 19/19 passes and parser_stress PASS.",
        "The scripts overwrite their own logs. Preserve results after each.",
        "Alternate baseline and candidate three times each (six trials).",
        "COMPARE: read_ms + lexer_ms + parse_ms + compile_ms (milliseconds).",
        "Note exec_ms and gc_free too; reject a gain that reduces stability.",
        "Report or upload all six DEMO logs with distinct 8.3 names.",
        "",
        "Additional check: time the first CLOCK.PY face with the same .PY:",
        "P86PBASE --home-cls CLOCK.PY",
        "versus the best candidate's EXE with --home-cls CLOCK.PY.",
        "Repeat three times each, alternating. No .MPY required.",
        "",
        "Measured emulator timing granularity ~55 ms. Real V20 data wins.",
        "Do not replace PY86.EXE based only on DOSBox performance.",
    ]
    dst = DIST / "PY86-PARSER-LAB.zip"
    with zipfile.ZipFile(dst, "w", compression=zipfile.ZIP_DEFLATED) as zipfile_out:
        zipfile_out.writestr("README.TXT", "\r\n".join(docs) + "\r\n")
        zipfile_out.write(ROOT / "tests" / "PARSST.PY", "PARSST.PY")
        for mode, (executable, _, (exe, bat_name, demo_log, stress_log)) in verified.items():
            zipfile_out.write(executable, exe)
            zipfile_out.writestr(bat_name, bat(exe, demo_log, stress_log))
    with zipfile.ZipFile(dst) as z:
        err = z.testzip()
        if err is not None:
            raise SystemExit("Invalid DOS test archive entry: " + err)
    print("PASS created", dst, "with", len(verified), "DOSBox-verified parser modes")
    print("Archive size", dst.stat().st_size)

if __name__ == "__main__":
    main()
