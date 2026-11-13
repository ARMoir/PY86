"""Package only successfully validated experimental 8086 DOS builds.

No production PY86.EXE is replaced, and all executable names are DOS 8.3.
Use after the GitHub Actions build + full DOSBox test + native profile loop.
"""
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / 'build'
LAB = BUILD / 'compile-lab'
DIST = ROOT / 'dist'
DIST.mkdir(exist_ok=True)
mapping = {
    'baseline': ('P86BASE.EXE', 'RUNB.BAT', 'BTEST.LOG'),
    'chunk32': ('P86P32.EXE', 'RUN32.BAT', 'P32.LOG'),
    'chunk64': ('P86P64.EXE', 'RUN64.BAT', 'P64.LOG'),
    'chunk128': ('P86P128.EXE', 'RUN128.BAT', 'P128.LOG'),
    'loop': ('P86LOOP.EXE', 'RUNL.BAT', 'LTEST.LOG'),
    'intrinsic': ('P86INTR.EXE', 'RUNI.BAT', 'ITEST.LOG'),
    'all': ('P86ALL.EXE', 'RUNA.BAT', 'ATEST.LOG'),
    'direct': ('P86DIR.EXE', 'RUND.BAT', 'DTEST.LOG'),
}
readme = [
    'PY86 8086 .PY COMPILATION LAB - PHYSICAL TANDY TESTS', '',
    'EXPERIMENTAL executables. Existing PY86.EXE is not overwritten.',
    'All files use DOS 8.3 naming. Run from the directory containing DEMO.PY.',
    'The full feature demo must show 19 passed and zero failed.',
    'Each RUN*.BAT executes a real .PY file with a 48KB fixed GC heap.',
    'A native P86PROF line is written to the output .LOG file after completion.',
    '',
    'For each candidate, run its batch file 3 times, alternating with RUNB.',
    'View timing summary with FIND "P86PROF" <file.LOG> (or EDIT file.LOG).',
    'Read_ms: DOS source read/open; lexer_ms: lexer setup;',
    'parse_ms: parse syntax tree; compile_ms: emit bytecode;',
    'exec_ms: 19-feature DEMO runtime; gc_free: free GC bytes.',
    'A BIOS tick is ~55ms; small differences are noise on V20.',
    'time.startup_ms includes source parsing/compilation but excludes MZ load.',
    'Keep measuring clock face wall time separately with existing RUNCLK.',
    'Report median of 3 runs for both total startup and first clock face.',
    '',
    'If a variant crashes, stop testing it and keep production PY86.EXE.',
    'No .mpy cache is required and no original Python source is modified.',
]
out = DIST / 'PY86-COMPILE-LAB.zip'
count = 0
with zipfile.ZipFile(out, 'w', compression=zipfile.ZIP_DEFLATED) as z:
    for name, text in [('README.TXT', '\r\n'.join(readme) + '\r\n')]:
        z.writestr(name, text)
    for key, (exe, bat, logfile) in mapping.items():
        source_exe = LAB / ('PY86-' + key + '.EXE')
        proof = BUILD / ('compile-profile-' + key + '.json')
        if not (source_exe.is_file() and proof.is_file()):
            continue
        count += 1
        z.write(source_exe, exe)
        content = ('@echo off\r\n'
                   'set PY86_PROFILE=1\r\n'
                   'set PY86_HEAP=48000\r\n'
                   + exe[:-4] + ' DEMO.PY > ' + logfile + '\r\n'
                   'if errorlevel 1 echo PY86 EXPERIMENT FAILED\r\n'
                   'set PY86_HEAP=\r\n'
                   'set PY86_PROFILE=\r\n'
                   'FIND "P86PROF" ' + logfile + '\r\n'
                   'echo Results saved in ' + logfile + '\r\n')
        z.writestr(bat, content)
if count < 1:
    raise SystemExit('No validated experimental executables to package')
with zipfile.ZipFile(out) as z:
    assert z.testzip() is None
print('PASS built', out, 'with', count, 'validated variants, production unaffected')
