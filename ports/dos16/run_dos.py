"""Run DOS smoke/feature tests with an installed DOSBox (not hardware validation)."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import json
root = Path(__file__).resolve().parent
p = argparse.ArgumentParser()
p.add_argument('--dosbox', required=True)
p.add_argument('--timeout', type=int, default=120)
a = p.parse_args()
stage = root / 'dos-test'
stage.mkdir(exist_ok=True)
for f in (root / 'tests').iterdir():
    if f.is_file():
        # DOSBox mounts a DOS 8.3 filesystem: long names are truncated,
        # causing false FileNotFound failures during the DOS test batch.
        if len(f.stem) > 8 or len(f.suffix.lstrip('.')) > 3:
            raise SystemExit('DOS test filename exceeds 8.3: ' + f.name)
        shutil.copy2(f, stage / f.name)
shutil.copy2(root / 'build/py86.exe', stage / 'PY86.EXE')
# Ensure the built-in datetime module is tested without the old shim.
for f in (root / 'stdlib').glob('*.py'):
    if f.name.lower() != 'datetime.py':
        shutil.copy2(f, stage / f.name)
(stage / 'datetime.py').unlink(missing_ok=True)
for f in (root / 'tests/pythonclock').glob('*.py'):
    shutil.copy2(f, stage / f.name)
clock_src = (root / 'tests/pythonclock/Clock.py').read_text()
if clock_src.count('while True:') != 1:
    raise SystemExit('Unexpected PythonClock main loop; update bounded test generation')
# Only the staged integration copy has a finite loop. The source app is untouched.
(stage / 'CLKTEST.PY').write_text(
    clock_src.replace('while True:', 'for py86_test_tick in range(2):'),
    encoding='utf-8')
for f in stage.glob('*.OUT'):
    f.unlink()
(stage / 'RESULT.TXT').unlink(missing_ok=True)
conf = root / 'build/dosbox.conf'
conf.write_text('[sdl]\nfullscreen=false\noutput=surface\n[dosbox]\nmemsize=1\n'
                '[cpu]\ncore=normal\ncputype=8086\ncycles=fixed 20000\n'
                '[autoexec]\nmount c "' + str(stage) + '"\nc:\ncall RUN.BAT\nexit\n')
runner_opts = {}
if os.name == 'nt':
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 0
    runner_opts['startupinfo'] = startup
with (root / 'build/emulator.log').open('w') as log:
    subprocess.run([a.dosbox, '-conf', str(conf), '-noconsole'], timeout=a.timeout,
                   stdout=log, stderr=log, **runner_opts)
result = (stage / 'RESULT.TXT').read_text().strip() if (stage / 'RESULT.TXT').exists() else 'NO RESULT'
logs = {f.name: f.read_text(errors='replace') for f in stage.glob('*.OUT')}
required = {'SMOKE.OUT': ['PASS smoke'], 'METHOD.OUT': ['PASS methods'],
            'CORE.OUT': ['PASS numeric', 'PASS unicode', 'PASS control', 'PASS functions',
                         'PASS exceptions', 'PASS containers', 'PASS classes_generators',
                         'PASS imports', 'PASS core_complete'],
            'CLOCKAPI.OUT': ['PASS datetime_builtin', 'PASS dos_datetime', 'PASS dos_sleep', 'PASS dos_cls'],
            'LIBTEST.OUT': ['PASS math', 'PASS random', 'PASS os', 'PASS time'],
            'MODTEST.OUT': ['PASS errno', 'PASS json', 'PASS re', 'PASS hashlib',
                            'PASS native_modules_complete'],
            'LOOKUP.OUT': ['PASS lookup_cache_correctness'],
            'STRHASH.OUT': ['PASS lazy_hash_correctness'],
            'CLOCK.OUT': ['   ~-------------~'],
            'GC.OUT': ['PASS gc_roots'], 'INPUT.OUT': ['PASS input'],
            'REPL.OUT': ['Py86 0.1', '>>> 3', '42', 'PASS repl_recovery', 'ValueError: repl recovery'],
            'ERROR.OUT': ['ValueError: intentional exit-code test'],
            'EXCATCH.OUT': ['PASS exit_can_be_caught'],
            'EXIT0.OUT': ['PASS exit0_before'],
            'QUIT0.OUT': ['PASS quit0_before'],
            'SYSEX0.OUT': ['PASS sys_exit0_before'],
            'SYSEX7.OUT': ['PASS sys_exit7_before'],
            'SYSEX9.OUT': ['PASS system_exit9_before'],
            'SYSEXTXT.OUT': ['PASS sys_exit_message_before', 'PASS custom_exit_message'],
            'REPLEX.OUT': ['PASS repl_exit_before'],
            'REPLCODE.OUT': ['PASS repl_exit_code_before']}
missing = [f + ': ' + token for f, tokens in required.items() for token in tokens
           if token not in logs.get(f, '')]
if any('FAIL ' in logs.get(name, '') for name in
       ('EXIT0.OUT', 'QUIT0.OUT', 'SYSEX0.OUT', 'SYSEX7.OUT',
        'SYSEX9.OUT', 'SYSEXTXT.OUT', 'REPLEX.OUT', 'REPLCODE.OUT')):
    missing.append('exit tests: Python continued running after SystemExit')
if logs.get('CLOCK.OUT', '').count('~-------------~') < 2:
    missing.append('CLOCK.OUT: fewer than two rendered clock faces')
unexpected = [f for f, content in logs.items()
              if ('Traceback' in content and f not in ('REPL.OUT', 'ERROR.OUT'))
              or (f == 'REPL.OUT' and any(x in content for x in ('SyntaxError', 'IndentationError', 'NameError')))]
report = {'environment': 'DOSBox built-in DOS; not DOS 6.22 or physical V20',
          'batch_result': result, 'missing': missing, 'unexpected_errors': unexpected, 'logs': logs}
(root / 'build/test-results.json').write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
raise SystemExit(0 if result == 'PASS' and not missing and not unexpected else 1)
