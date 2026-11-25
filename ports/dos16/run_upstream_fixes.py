"""Native DOS tests for upstream fixes, including a negative-control mode."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent
CASES = {'eval': 'upstream_eval', 'array': 'upstream_bytearray', 'bytes': 'upstream_bytes'}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--dosbox', required=True)
    p.add_argument('--expect-unfixed', action='store_true')
    p.add_argument('--json-only', action='store_true')
    a = p.parse_args()
    if a.expect_unfixed and a.json_only:
        p.error('negative controls and JSON baseline are separate')
    label = 'unfixed' if a.expect_unfixed else ('json-baseline' if a.json_only else 'fixed')
    cases = dict(CASES) if a.expect_unfixed else ({'json': 'upstream_json'} if a.json_only else dict(CASES, json='upstream_json'))
    out = ROOT / 'build' / ('upstream-' + label)
    results = []
    for heap in ((48000,) if a.expect_unfixed or a.json_only else (24000, 48000, 60000)):
        stage = out / ('H' + str(heap))
        stage.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / 'build/py86.exe', stage / 'PY86.EXE')
        shutil.copy2(ROOT / 'tests/UPFIX.PY', stage / 'UPFIX.PY')
        lines = ['@echo off', 'set PY86_PROFILE=', 'set PY86_HEAP=' + str(heap)]
        for i, name in enumerate(cases):
            for suffix in ('.OUT', '.RES'):
                (stage / (name.upper() + suffix)).unlink(missing_ok=True)
            lines += ['py86 UPFIX.PY ' + name + ' > ' + name.upper() + '.OUT',
                      'if errorlevel 1 goto fail' + str(i),
                      'echo PASS > ' + name.upper() + '.RES', 'goto next' + str(i),
                      ':fail' + str(i), 'echo FAIL > ' + name.upper() + '.RES', ':next' + str(i)]
        (stage / 'CHECK.BAT').write_bytes(('\r\n'.join(lines) + '\r\n').encode('ascii'))
        conf = stage / 'dosbox.conf'
        conf.write_text('[sdl]\nfullscreen=false\n[dosbox]\nmemsize=1\n[cpu]\ncore=normal\ncpu_cycles=20000\n[autoexec]\nmount c "' + str(stage) + '"\nc:\ncall CHECK.BAT\nexit\n')
        options = {}
        if os.name == 'nt':
            startup = subprocess.STARTUPINFO()
            startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            options['startupinfo'] = startup
        with (stage / 'emulator.log').open('w') as log:
            subprocess.run([a.dosbox, '--conf', str(conf), '--noprimaryconf', '--nolocalconf'],
                           stdout=log, stderr=log, timeout=180, check=True, **options)
        for name, marker in cases.items():
            status = (stage / (name.upper() + '.RES')).read_text().strip()
            output = (stage / (name.upper() + '.OUT')).read_text(errors='replace')
            if a.expect_unfixed:
                # On 16-bit DOS the old parser/allocation bug can terminate
                # without a Python traceback. Require proof that this specific
                # case started, a nonzero exit, and no success marker.
                passed = status == 'FAIL' and 'BEGIN upstream_' + name in output and 'PASS ' + marker not in output
            else:
                passed = status == 'PASS' and 'PASS ' + marker in output and 'Traceback' not in output
            record = {'heap': heap, 'case': name, 'passed': passed, 'exit_status': status}
            if name == 'json' and passed:
                timings = [line.split()[1] for line in output.splitlines() if line.startswith('JSON_MS ')]
                if len(timings) != 1:
                    raise RuntimeError('Missing or ambiguous JSON benchmark result')
                record['json_ms'] = int(timings[0])
            results.append(record)
            if not passed:
                print(name, repr(output))
    (out / 'results.json').write_text(json.dumps(results, indent=2))
    print(json.dumps(results, indent=2))
    if not all(r['passed'] for r in results):
        raise SystemExit('Upstream ' + label + ' regression check failed')
    print('PASS upstream ' + label + ': ' + str(len(results)) + ' native checks')


if __name__ == '__main__':
    main()
