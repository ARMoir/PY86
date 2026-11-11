"""Stage a flat DOS-ready runtime and create a standalone PY86.zip.

The original PythonClock sources remain untouched in the repository.
The release includes a generated optimized standalone CLOCK.PY and a
self-checking DEMO.PY; both are tested under the real DOS interpreter.
"""
from pathlib import Path
import shutil
from zipfile import ZipFile, ZIP_DEFLATED
from gen_clock import generate as generate_clock

ROOT = Path(__file__).resolve().parent
DEST = ROOT / "dist"
STAGE = DEST / "PY86"
ARCHIVE = DEST / "PY86.zip"

INPUTS = {
    "PY86.EXE": ROOT / "build" / "py86.exe",
    "PY86P.EXE": ROOT / "build" / "py86p.exe",
    "START86.EXE": ROOT / "build" / "start86.exe",
    "CLOCK.PY": ROOT / "build" / "CLOCK.PY",
    "DEMO.PY": ROOT / "examples" / "DEMO.PY",
}

VERSION = (ROOT / "build" / "py86-version.txt").read_text(encoding="ascii").strip()
README = (
    f"Py86 {VERSION}: Python 3 for 16-bit DOS\r\n"
    "Optimized one-file PythonClock and feature demo included.\r\n"
    "Original PythonClock files are unchanged in the GitHub repository.\r\n"
    "\r\n"
    "COPY ALL FILES TO ONE DIRECTORY ON YOUR DOS DRIVE.\r\n"
    "PY86 -V      Display the version embedded in PY86.EXE\r\n"
    "RUNCLK       Optimized single-file analog clock (CLOCK.PY)\r\n"
    "RUNTEST      Run feature showcase directly (DEMO.PY)\r\n"
    "RUNPCLK      Clock using smaller compressed PY86P.EXE\r\n"
    "RUNPTEST     Feature showcase using compressed interpreter\r\n"
    "RUNLOAD      Optional timing test via START86 launcher\r\n"
    "START86 PY86 DEMO.PY   Optional full child EXE-load timing\r\n"
    "PY86         Start the interactive interpreter\r\n"
    "PY86 DEMO.PY Run feature tests without the batch script\r\n"
    "\r\n"
    "The demo shows results on screen and saves PY86.LOG.\r\n"
    "RUNTEST starts PY86 directly, with no extra DOS loader.\r\n"
    "PY86P.EXE is UPX-packed for 8086-compatible DOS use.\r\n"
    "The smaller file may or may not start faster on real hardware.\r\n"
    "Use RUNPCLK or RUNPTEST to try it without renaming files.\r\n"
    "START86/RUNLOAD are optional timing tools.\r\n"
    "History is saved in PY86TIME.CSV (LOADTIME.CSV with RUNLOAD).\r\n"
    "The log is overwritten on each demo run. Failed tests exit nonzero.\r\n"
    "The clock uses time.localtime(), cached hands, and fast rendering.\r\n"
    "RUNCLK uses --home-cls to minimize redraw blanking.\r\n"
    "Stop the clock with Ctrl+C. The DOS system clock sets its time.\r\n"
    "Normal PY86 CLOCK.PY uses standard CLS instead.\r\n"
    "\r\n"
    "On slow machines, tests may take some time.\r\n"
    "Requires DOS-compatible conventional memory and an 8086/V20 CPU.\r\n"
    "Experimental MicroPython 1.24.1 DOS port; not full CPython.\r\n"
)
RUNCLK = "@echo off\r\ncls\r\nPY86 --home-cls CLOCK.PY\r\n"
RUNTEST = "@echo off\r\ncls\r\nPY86 DEMO.PY\r\nif errorlevel 1 echo Demo failed; inspect PY86.LOG\r\n"
RUNLOAD = "@echo off\r\ncls\r\nSTART86 PY86 DEMO.PY\r\nif errorlevel 1 echo Demo failed; inspect PY86.LOG\r\n"
RUNPCLK = "@echo off\r\ncls\r\nPY86P --home-cls CLOCK.PY\r\n"
RUNPTEST = "@echo off\r\ncls\r\nPY86P DEMO.PY\r\nif errorlevel 1 echo Demo failed; inspect PY86.LOG\r\n"


def main():
    generate_clock(ROOT / "build" / "CLOCK.PY")
    missing = [str(src) for src in INPUTS.values() if not src.is_file()]
    if missing:
        raise SystemExit("Missing required Py86/clock files:\n" + "\n".join(missing))
    if (ROOT / "build" / "py86.exe").read_bytes()[:2] != b"MZ":
        raise SystemExit("build/py86.exe is not a DOS MZ executable")
    if STAGE.exists():
        shutil.rmtree(STAGE)
    STAGE.mkdir(parents=True)
    for name, src in INPUTS.items():
        shutil.copyfile(src, STAGE / name)
    (STAGE / "RUNCLK.BAT").write_bytes(RUNCLK.encode("ascii"))
    (STAGE / "RUNTEST.BAT").write_bytes(RUNTEST.encode("ascii"))
    (STAGE / "RUNLOAD.BAT").write_bytes(RUNLOAD.encode("ascii"))
    (STAGE / "RUNPCLK.BAT").write_bytes(RUNPCLK.encode("ascii"))
    (STAGE / "RUNPTEST.BAT").write_bytes(RUNPTEST.encode("ascii"))
    (STAGE / "README.TXT").write_bytes(README.encode("ascii"))
    if ARCHIVE.exists():
        ARCHIVE.unlink()
    with ZipFile(ARCHIVE, "w", ZIP_DEFLATED, compresslevel=9) as z:
        for file in sorted(STAGE.iterdir()):
            z.write(file, file.name)
    with ZipFile(ARCHIVE) as z:
        expected = set(INPUTS) | {"RUNCLK.BAT", "RUNTEST.BAT", "RUNLOAD.BAT",
                                  "RUNPCLK.BAT", "RUNPTEST.BAT", "README.TXT"}
        if set(z.namelist()) != expected or z.testzip() is not None:
            raise SystemExit("PY86.zip contents failed verification")
    print(f"Packaged {ARCHIVE} ({ARCHIVE.stat().st_size} bytes)")
    print("Contents: " + ", ".join(sorted(expected)))


if __name__ == "__main__":
    main()
