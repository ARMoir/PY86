"""Stage a flat DOS-ready runtime and create a standalone PY86.zip.

All five PythonClock files are copied without altering their contents.
GitHub Actions uploads the staged directory as artifact "PY86", which is
downloaded by GitHub as PY86.zip (avoiding a nested ZIP inside a ZIP).
"""
from pathlib import Path
import shutil
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parent
DEST = ROOT / "dist"
STAGE = DEST / "PY86"
ARCHIVE = DEST / "PY86.zip"

INPUTS = {
    "PY86.EXE": ROOT / "build" / "py86.exe",
    "Clock.py": ROOT / "tests" / "pythonclock" / "Clock.py",
    "face.py": ROOT / "tests" / "pythonclock" / "face.py",
    "hour.py": ROOT / "tests" / "pythonclock" / "hour.py",
    "minute.py": ROOT / "tests" / "pythonclock" / "minute.py",
    "second.py": ROOT / "tests" / "pythonclock" / "second.py",
}

README = (
    "Py86 0.1: Python 3 for 16-bit DOS\r\n"
    "PythonClock (original source) is included.\r\n"
    "\r\n"
    "Copy all files to the same directory on your DOS drive.\r\n"
    "Run: RUNCLK\r\n"
    "Or:  PY86 --home-cls CLOCK.PY\r\n"
    "Start the interactive prompt with: PY86\r\n"
    "Normal PY86 CLOCK.PY still uses ordinary screen clearing.\r\n"
    "The --home-cls mode leaves the previous clock visible while\r\n"
    "Python prepares the next frame, then overwrites it.\r\n"
    "\r\n"
    "Requires a PC-compatible DOS computer with enough conventional RAM.\r\n"
    "For the clock, set the system date/time correctly in DOS.\r\n"
    "datetime is built into PY86.EXE; no datetime.py required.\r\n"
    "\r\n"
    "Experimental interpreter, based on MicroPython 1.24.1.\r\n"
    "Not a complete implementation of CPython 3.x.\r\n"
)
RUNCLK = "@echo off\r\nPY86 --home-cls CLOCK.PY\r\n"

def main():
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
    (STAGE / "README.TXT").write_bytes(README.encode("ascii"))
    if ARCHIVE.exists():
        ARCHIVE.unlink()
    with ZipFile(ARCHIVE, "w", ZIP_DEFLATED, compresslevel=9) as z:
        for file in sorted(STAGE.iterdir()):
            z.write(file, file.name)
    with ZipFile(ARCHIVE) as z:
        expected = set(INPUTS) | {"RUNCLK.BAT", "README.TXT"}
        if set(z.namelist()) != expected or z.testzip() is not None:
            raise SystemExit("PY86.zip contents failed verification")
    print(f"Packaged {ARCHIVE} ({ARCHIVE.stat().st_size} bytes)")
    print("Contents: " + ", ".join(sorted(expected)))


if __name__ == "__main__":
    main()
