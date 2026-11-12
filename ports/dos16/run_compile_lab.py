"""Run native Py86 DOS compilation profiling on unchanged Python scripts."""
from pathlib import Path
import argparse
import json
import os
import re
import statistics
import subprocess

ROOT = Path(__file__).resolve().parent
FIELDS = ('read_ms', 'lexer_ms', 'parse_ms', 'compile_ms', 'exec_ms', 'gc_free')
PROF = re.compile(r'^P86PROF ' + r'\s+'.join(k + r'=(\d+)' for k in FIELDS) + r'\s*$', re.M)

def run():
    p = argparse.ArgumentParser()
    p.add_argument('--dosbox', required=True)
    p.add_argument('--emulator', choices=('classic','staging'), default='staging')
    p.add_argument('--mode', required=True)
    p.add_argument('--timeout', type=int, default=360)
    args = p.parse_args()
    stage = ROOT / 'dos-test'
    build = ROOT / 'build'
    if not all((stage / n).is_file() for n in ('PY86.EXE','DEMO.PY','ONECLK.PY','SHOW.PY')):
        raise SystemExit('Run run_dos.py first to stage full regression fixtures')
    commands = ['@echo off','set PY86_PROFILE=1','set PY86_HEAP=48000',
                'py86 DEMO.PY > PDEM1.OUT','if errorlevel 1 goto fail',
                'py86 DEMO.PY > PDEM2.OUT','if errorlevel 1 goto fail',
                'py86 ONECLK.PY > PCLK.OUT','if errorlevel 1 goto fail',
                'py86 SHOW.PY > PSHOW.OUT','if errorlevel 1 goto fail',
                'echo PASS > PROF.RES','goto done',':fail',
                'echo FAIL > PROF.RES',':done','']
    (stage / 'PROF.BAT').write_bytes(('\r\n'.join(commands)).encode('ascii'))
    for name in ('PDEM1.OUT','PDEM2.OUT','PCLK.OUT','PSHOW.OUT','PROF.RES'):
        (stage / name).unlink(missing_ok=True)
    conf = build / 'compile-profile-dosbox.conf'
    cpu = 'core=normal\ncpu_cycles=20000\n' if args.emulator == 'staging' else 'core=normal\ncputype=8086\ncycles=fixed 20000\n'
    video = '[sdl]\nfullscreen=false\n' if args.emulator == 'staging' else '[sdl]\nfullscreen=false\noutput=surface\n'
    conf.write_text(video + '[dosbox]\nmemsize=1\n[cpu]\n' + cpu +
                    '[autoexec]\nmount c "' + str(stage) + '"\nc:\ncall PROF.BAT\nexit\n')
    opts = {}
    if os.name == 'nt':
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = 0
        opts['startupinfo'] = startup
    command = ([args.dosbox,'--conf',str(conf),'--noprimaryconf','--nolocalconf']
               if args.emulator == 'staging' else [args.dosbox,'-conf',str(conf),'-noconsole'])
    with (build / 'compile-profile-emulator.log').open('w') as log:
        subprocess.run(command, timeout=args.timeout, stdout=log, stderr=log, **opts)
    status = stage / 'PROF.RES'
    if not status.exists() or status.read_text().strip() != 'PASS':
        raise SystemExit('Profiling batch failed: see output and emulator logs')
    results = {}
    for filename in ('PDEM1.OUT','PDEM2.OUT','PCLK.OUT','PSHOW.OUT'):
        output = (stage / filename).read_text(errors='replace')
        matches = list(PROF.finditer(output))
        if len(matches) != 1:
            raise SystemExit('Expected one P86PROF line in ' + filename)
        row = dict(zip(FIELDS, (int(v) for v in matches[0].groups())))
        if filename.startswith('PDEM') and not ('Tests passed: 19' in output and 'failed: 0' in output and 'PASS feature_demo_complete' in output):
            raise SystemExit('Feature demo failed: ' + filename)
        if filename == 'PSHOW.OUT' and '[PASS] 8 LIVE EXAMPLES' not in output:
            raise SystemExit('Showcase failed: ' + filename)
        if 'Traceback' in output:
            raise SystemExit('Traceback: ' + filename)
        row['startup_total_ms'] = sum(row[k] for k in ('read_ms','lexer_ms','parse_ms','compile_ms'))
        results[filename] = row
    demos = [results[x] for x in ('PDEM1.OUT','PDEM2.OUT')]
    metrics = {k: statistics.median(v[k] for v in demos) for k in (*FIELDS,'startup_total_ms')}
    report = {'mode': args.mode, 'environment': 'DOSBox fixed 8086 / 20000 cycles',
              'resolution': 'BIOS approximately 55 ms; not real V20 timing',
              'executable_bytes': (build / 'py86.exe').stat().st_size,
              'demo_median': metrics, 'samples': results}
    (build / ('compile-profile-' + args.mode + '.json')).write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    print('PASS native compilation-stage profile')

if __name__ == '__main__':
    run()
