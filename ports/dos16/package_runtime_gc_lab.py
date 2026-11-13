"""Create verified DOS 8.3 runtime A/B package, preserving production PY86.EXE."""
from pathlib import Path
import zipfile
import json

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "build"
LAB = BUILD / "runtime-lab"
DIST = ROOT / "dist"
DIST.mkdir(exist_ok=True)
MODES = {
    "base": "P86RBAS",
    "all": "P86RALL",
    "p1k": "P86R1K",
    "p1ka": "P86R1KA",
}
SCRIPT_LINES = [
    "PY86 V20 PARSER COMPILER AND GC DIAGNOSTIC",
    "",
    "Opt-in builds only; your PY86.EXE and all .PY files are preserved.",
    "Unpack into the same DOS directory as DEMO.PY and CLOCK.PY.",
    "First run RUN4.BAT for one 4-way BASE/ALL/1K/1KA comparison.",
    "For reliable measurements run RUN12.BAT: three rounds of each",
    "variant, uniquely named B1-B3.LOG / A1-A3.LOG / K1-K3.LOG",
    "/ X1-X3.LOG. Each batch saves DEMO execution and GC diagnostics.",
    "Run RUNGCT.BAT for a controlled 1KA no-GC vs forced pre-GC",
    "alternating experiment. It saves XN1/XG1/XN2/XG2.LOG.",
    "",
    "Every DEMO must say 19 passed, zero failed. Look for both",
    "P86PROF (read/lexer/parse/compile/exec) and P86RUNT",
    "(gc_calls/gc_ms/free_pre/free_post/prep_ms/forced_gc_ms).",
    "preexec_gc enabled only in G runs; its prep time is outside exec_ms.",
    "RUN4 and RUN12 also test unmodified Python via the included",
    "RUNTST.PY deterministic VM benchmark and PARSST.PY syntax stress.",
    "Use FIND P86RUNT filename.LOG or view with EDIT.",
    "Scripts overwrite their own named outputs on subsequent calls.",
    "All tests use a fixed 48KB GC heap and 8086-compatible executables.",
    "Clock-face benchmark (unchanged CLOCK.PY) is separate:",
    "P86RBAS --home-cls CLOCK.PY",
    "P86R1KA --home-cls CLOCK.PY",
    "Compare three alternating runs with a stopwatch.",
    "",
    "No production changes and no .mpy precompilation required.",
]

def batch(lines):
    return ("\r\n".join(["@echo off",
                        "set PY86_PROFILE=1",
                        "set PY86_HEAP=48000",
                        "set PY86_PREEXEC_GC="] + lines +
                       [":done", "set PY86_HEAP=", "set PY86_PROFILE=",
                        "set PY86_PREEXEC_GC=", "goto end",
                        ":fail", "echo FAIL - inspect most recent log",
                        "set PY86_HEAP=", "set PY86_PROFILE=",
                        "set PY86_PREEXEC_GC=", ":end", ""]))

def command(exe, script, out, gc=False):
    result = ["set PY86_PREEXEC_GC=" + ("1" if gc else ""),
              exe + " " + script + " > " + out,
              "if errorlevel 1 goto fail"]
    return result

def main():
    for mode in MODES:
        executable = LAB / ("PY86-" + mode + ".EXE")
        for state in ("on", "off"):
            path = BUILD / ("compile-profile-runtime-" + mode + "-" + state + ".json")
            if not executable.is_file() or not path.is_file():
                raise SystemExit("Not fully verified in DOSBox: " + mode + "/" + state)
            report = json.loads(path.read_text())
            assert report["mode"] == "runtime-" + mode + "-" + state
            assert "RUNTST.OUT" in report["samples"]
    scripts = {}
    single=[]
    for mode, letter in (("base", "B"), ("all", "A"),
                         ("p1k", "K"), ("p1ka", "X")):
        single += command(MODES[mode], "DEMO.PY", letter + "0.LOG")
        single += command(MODES[mode], "RUNTST.PY", "V" + letter + ".LOG")
        single += command(MODES[mode], "PARSST.PY", "S" + letter + ".LOG")
    single += ["echo PASS four-way parser compiler GC comparison", "goto done"]
    scripts["RUN4.BAT"] = batch(single)
    repeated=[]
    for n in (1,2,3):
        for mode, letter in (("base", "B"), ("all", "A"),
                             ("p1k", "K"), ("p1ka", "X")):
            repeated += command(MODES[mode], "DEMO.PY", letter + str(n) + ".LOG")
    repeated += ["echo PASS twelve alternating DEMO runs", "goto done"]
    scripts["RUN12.BAT"] = batch(repeated)
    gc_test=[]
    for n in (1,2,3):
        gc_test += command(MODES["p1ka"], "DEMO.PY", "XN" + str(n) + ".LOG", gc=False)
        gc_test += command(MODES["p1ka"], "DEMO.PY", "XG" + str(n) + ".LOG", gc=True)
    gc_test += ["echo PASS forced GC alternating comparison", "goto done"]
    scripts["RUNGCT.BAT"] = batch(gc_test)
    target = DIST / "PY86-RUNTIME-LAB.zip"
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("README.TXT", "\r\n".join(SCRIPT_LINES) + "\r\n")
        for name in ("RUNTST.PY", "PARSST.PY"):
            z.write(ROOT / "tests" / name, name)
        for mode, stem in MODES.items():
            z.write(LAB / ("PY86-" + mode + ".EXE"), stem + ".EXE")
        for name, content in scripts.items():
            z.writestr(name, content)
    with zipfile.ZipFile(target) as z:
        assert z.testzip() is None
        assert all(name in z.namelist() for name in (
            "RUN4.BAT", "RUN12.BAT", "RUNGCT.BAT",
            "P86RBAS.EXE", "P86RALL.EXE", "P86R1K.EXE", "P86R1KA.EXE"))
    print("PASS verified DOS experiment ZIP", target, target.stat().st_size, "bytes")

if __name__ == "__main__":
    main()
