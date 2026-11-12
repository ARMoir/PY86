"""Package verified native 8086 Py86 v1.24.1 / v1.29.0 A/B builds.
Produces a DOS 8.3-compatible ZIP for use on an existing bootable CF disk.
The bootable image step is independent and uses only FreeDOS, not MS-DOS.
"""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import json
import shutil

ROOT=Path(__file__).resolve().parent
LAB=ROOT/"build"/"upstream-129"
DIST=ROOT/"dist"
STAGE=ROOT/"dos-test"
DIST.mkdir(exist_ok=True)
VARIANTS=(
    ("24base","P24BASE.EXE","B"),
    ("24opt","P24OPT.EXE","O"),
    ("29base","P29BASE.EXE","N"),
    ("29opt","P29OPT.EXE","P"),
)
FIXTURES=("DEMO.PY","CLOCK.PY","PARSST.PY","RUNTST.PY")
README=(
"PY86 MICROPYTHON UPSTREAM 1.24.1 VS 1.29.0 / NEC V20 LAB",
"",
"Independent experimental 16-bit DOS EXEs. Production PY86.EXE is safe.",
"Unzip into a folder on an EXISTING bootable DOS or CF drive.",
"Every interpreter executes unchanged ordinary .PY source files.",
"",
"P24BASE.EXE: MicroPython 1.24.1 original parser and C compiler",
"P24OPT.EXE: MicroPython 1.24.1 1KB parser and compiler switches",
"P29BASE.EXE: MicroPython 1.29.0 original parser and compiler",
"P29OPT.EXE: MicroPython 1.29.0 1KB parser and compiler switches",
"",
"RUN4.BAT: 4 one-off A/B demos plus a 29-base parser and VM stress.",
"RUN12.BAT: 12 alternating DEMO.PY benchmarks, 3 each configuration.",
"          Output B1-3.LOG, O1-3.LOG, N1-3.LOG, P1-3.LOG.",
"RUN29.BAT: 3 alternating comparisons of v1.29 BASE and 1KB-ALL.",
"          Output NB1-3.LOG and NO1-3.LOG.",
"RUNVER.BAT: display each interpreter version.",
"CLK24B/CLK24O/CLK29B/CLK29O.BAT: original PythonClock manual test.",
"Stop the Clock with Ctrl+C. Time to first face by stopwatch.",
"",
"All benchmark scripts set PY86_PROFILE=1 and PY86_HEAP=48000.",
"Each log records P86PROF phase times and P86RUNT GC diagnostics.",
"Check every DEMO.PY reports 19 passed, 0 failed.",
"RUN12 and RUN29 preserve their own logs, but rerunning them overwrites.",
"No result is considered a speedup until confirmed on the 7MHz NEC V20.",
"",
"If you use a separate experimental FreeDOS raw CF image, first back",
"up your current card: writing a raw IMG WILL ERASE the entire target.",
"Never write a ZIP directly to a CF card: extract to your existing DOS.",
)

def bat(lines):
    return ("\r\n".join(["@echo off","set PY86_HEAP=48000",
                        "set PY86_PROFILE=1","set PY86_PREEXEC_GC="]+lines+[
                        "goto done",":fail","echo TEST FAILED! Inspect last LOG.",
                        ":done","set PY86_HEAP=","set PY86_PROFILE=",
                        "set PY86_PREEXEC_GC=",""])+"\r\n").encode("ascii")

def exec_lines(exe, script, output):
    return [exe+" "+script+" > "+output,"if errorlevel 1 goto fail"]

def main():
    for key,exe,_ in VARIANTS:
        f=LAB/exe
        p=LAB/(key+"-profile.json")
        t=LAB/(key+"-regression.json")
        if not (f.is_file() and p.is_file() and t.is_file()):
            raise SystemExit("Unverified upstream A/B test build "+key)
        report=json.loads(p.read_text())
        assert report.get("mode")=="upstream-"+key
        assert "RUNTST.OUT" in report.get("samples",{})
        assert "PSTRES.OUT" in report.get("samples",{})
    missing=[p for p in FIXTURES if not (STAGE/p).is_file()]
    if missing:
        raise SystemExit("Unstaged .PY test fixtures: "+repr(missing))
    scripts={}
    one=[]
    for key,exe,letter in VARIANTS:
        one+=exec_lines(exe,"DEMO.PY",letter+"0.LOG")
    one+=exec_lines("P29BASE.EXE","PARSST.PY","PSTRESS.LOG")
    one+=exec_lines("P29BASE.EXE","RUNTST.PY","VSTRESS.LOG")
    one+=["echo PASS four-way upstream A-B demonstration"]
    scripts["RUN4.BAT"]=bat(one)
    repeated=[]
    for n in (1,2,3):
        for key,exe,letter in VARIANTS:
            repeated+=exec_lines(exe,"DEMO.PY",letter+str(n)+".LOG")
    repeated+=["echo PASS 12 alternating 1.24 vs 1.29 tests"]
    scripts["RUN12.BAT"]=bat(repeated)
    narrow=[]
    for n in (1,2,3):
        narrow+=exec_lines("P29BASE.EXE","DEMO.PY","NB"+str(n)+".LOG")
        narrow+=exec_lines("P29OPT.EXE","DEMO.PY","NO"+str(n)+".LOG")
    narrow+=["echo PASS 6 alternating 1.29 parser tests"]
    scripts["RUN29.BAT"]=bat(narrow)
    scripts["RUNVER.BAT"]=bat([v[1]+" -V" for v in VARIANTS]+[
        "echo MicroPython core versions displayed above"])
    for key,exe,letter in VARIANTS:
        name="CLK"+("24" if key.startswith("24") else "29")+("B" if key.endswith("base") else "O")+".BAT"
        scripts[name]=bat([exe+" --home-cls CLOCK.PY"])
    test_files={}
    for p in STAGE.glob("*.PY"):
        if len(p.stem)<=8 and len(p.suffix)==3:
            test_files[p.name.upper()]=p.read_bytes()
    for name,contents in scripts.items():
        test_files[name]=contents
    for key,exe,_ in VARIANTS:
        test_files[exe]=(LAB/exe).read_bytes()
    test_files["README.TXT"]=("\r\n".join(README)+"\r\n").encode("ascii")
    out=DIST/"PY86-UPSTREAM-129-LAB.zip"
    with ZipFile(out,"w",ZIP_DEFLATED,compresslevel=9) as z:
        for name,content in sorted(test_files.items()):
            z.writestr(name,content)
    with ZipFile(out) as z:
        assert z.testzip() is None
        for n in ("RUN4.BAT","RUN12.BAT","RUN29.BAT","P29BASE.EXE","P29OPT.EXE","DEMO.PY","CLOCK.PY"):
            assert n in z.namelist(),n
    print("PASS verified",out,"files",len(test_files),"bytes",out.stat().st_size)
    return out

if __name__=="__main__":
    main()
