"""Run DOS smoke/feature tests with an installed DOSBox (not hardware validation)."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import json
from gen_clock import generate as generate_clock
root = Path(__file__).resolve().parent
p = argparse.ArgumentParser()
p.add_argument('--dosbox', required=True)
p.add_argument('--emulator', choices=('classic', 'staging'), default='classic')
p.add_argument('--core-version', choices=('1.24.1','1.29.0'), default='1.24.1',
               help='Version string expected in the optional 1.29.0 migration test')
p.add_argument('--timeout', type=int, default=120)
p.add_argument('--repl-tab-test', action='store_true',
               help='Native DOSBox test of Tab/keyboard editing with a test-only EXE')
a = p.parse_args()
version = (root / 'build' / 'py86-version.txt').read_text(encoding='ascii').strip()
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
shutil.copy2(root / 'build/start86.exe', stage / 'START86.EXE')
# Ensure the built-in datetime module is tested without the old shim.
for f in (root / 'stdlib').glob('*.py'):
    if f.name.lower() != 'datetime.py':
        shutil.copy2(f, stage / f.name)
(stage / 'datetime.py').unlink(missing_ok=True)
for f in (root / 'tests/pythonclock').glob('*.py'):
    # The original Clock.py would collide with generated CLOCK.PY on DOS.
    # The original CLKTEST.PY still uses the other unchanged modules.
    if f.name.lower() != 'clock.py':
        shutil.copy2(f, stage / f.name)
generate_clock(stage / 'CLOCK.PY')
shutil.copy2(root / 'examples' / 'DEMO.PY', stage / 'DEMO.PY')
shutil.copy2(root / 'examples' / 'SHOW.PY', stage / 'SHOW.PY')
(stage / 'ONECLK.PY').write_text(
    "import clock\n"
    "f = clock.render(12, 0, 0)\n"
    "assert f.count('~-------------~') == 2\n"
    "clock.run(2, 0)\n"
    "print('PASS optimized_clock')\n",
    encoding='ascii')
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

if a.repl_tab_test:
    # Raw DOS key bytes: Tab (09), extended left arrow (00 4B), Ctrl+C (03).
    # The test-mode EXE reads these bytes through the same DOS line editor
    # used by getch() on real hardware; production uses getch() only on TTY.
    (stage / 'REPLTAB.IN').write_bytes(
        b"pri\t('PASS tab_builtin')\r\n"
        b"imp\tos\r\n"
        b"print('PASS tab_import')\r\n"
        b"text = 'hello'\r\n"
        b"print(text.up\t())\r\n"
        b"prit\x00Kn\x00O('PASS tab_cursor')\r\n"
        b"printf\x08('PASS tab_backspace')\r\n"
        b"text.st\t\x03"
        b"print('PASS tab_recovery')\r\n"
        b"exit()\r\n"
    )
    (stage / 'TABCHECK.BAT').write_bytes(
        b"@echo off\r\n"
        b"set PY86_TEST_REPL_KEYS=1\r\n"
        b"py86 < REPLTAB.IN > REPLTAB.OUT\r\n"
        b"set PY86_TEST_REPL_KEYS=\r\n"
        b"if errorlevel 1 goto fail\r\n"
        b"echo PASS > TABRES.TXT\r\n"
        b"goto end\r\n"
        b":fail\r\n"
        b"echo FAIL > TABRES.TXT\r\n"
        b":end\r\n"
    )
    (stage / 'TABRES.TXT').unlink(missing_ok=True)

conf = root / 'build/dosbox.conf'
video = ('[sdl]\nfullscreen=false\n' if a.emulator == 'staging'
         else '[sdl]\nfullscreen=false\noutput=surface\n')
cpu = ('core=normal\ncpu_cycles=20000\n' if a.emulator == 'staging'
       else 'core=normal\ncputype=8086\ncycles=fixed 20000\n')
conf.write_text(video + '[dosbox]\nmemsize=1\n[cpu]\n' + cpu +
                '[autoexec]\nmount c "' + str(stage) + '"\nc:\ncall RUN.BAT\n' +
                ('call TABCHECK.BAT\n' if a.repl_tab_test else '') + 'exit\n')
runner_opts = {}
if os.name == 'nt':
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 0
    runner_opts['startupinfo'] = startup
with (root / 'build/emulator.log').open('w') as log:
    subprocess.run(([a.dosbox, '--conf', str(conf), '--noprimaryconf', '--nolocalconf']
                    if a.emulator == 'staging' else
                    [a.dosbox, '-conf', str(conf), '-noconsole']), timeout=a.timeout,
                   stdout=log, stderr=log, **runner_opts)
result = (stage / 'RESULT.TXT').read_text().strip() if (stage / 'RESULT.TXT').exists() else 'NO RESULT'
logs = {f.name: f.read_text(errors='replace') for f in stage.glob('*.OUT')}
required = {'SMOKE.OUT': ['PASS smoke'], 'METHOD.OUT': ['PASS methods'],
            'CORE.OUT': ['PASS numeric', 'PASS unicode', 'PASS control', 'PASS functions',
                         'PASS exceptions', 'PASS containers', 'PASS classes_generators',
                         'PASS imports', 'PASS core_complete'],
            'CLOCKAPI.OUT': ['PASS startup_timing', 'PASS datetime_builtin', 'PASS dos_datetime', 'PASS dos_sleep', 'PASS dos_cls'],
            'LIBTEST.OUT': ['PASS math', 'PASS random', 'PASS os', 'PASS time'],
            'MODTEST.OUT': ['PASS errno', 'PASS json', 'PASS re', 'PASS hashlib',
                            'PASS native_modules_complete'],
            'LOOKUP.OUT': ['PASS lookup_cache_correctness'],
            'STRHASH.OUT': ['PASS lazy_hash_correctness'],
            'HELP.OUT': ['Py86: Python 3 for 16-bit DOS', 'PASS help_builtin',
                         'Plus any modules on the filesystem'],
            'FILEIO.OUT': ['PASS dos_text_open', 'PASS dos_binary_open',
                           'PASS dos_context_manager', 'PASS dos_open_errors'],
            'FILEMORE.OUT': ['PASS readinto', 'PASS writelines', 'PASS native_readline'],
            'ARGS.OUT': ['PASS script_argv'],
            'CARGS.OUT': ['PASS command_argv'],
            'CLIHELP.OUT': ['Usage: PY86', 'Ctrl+C'],
            'HELPFLAG.OUT': ['Usage: PY86'],
            'VERSION.OUT': ['Py86 ' + version, 'MicroPython ' + a.core_version],
            'VERNAME.OUT': ['Py86 ' + version, 'MicroPython ' + a.core_version],
            'CTRLC.OUT': ['PASS ctrlc_keyboard_interrupt'],
            'CTRLSLP.OUT': ['PASS ctrlc_sleep_interrupt'],
            'CLOCK.OUT': ['   ~-------------~'],
            'ONECLK.OUT': ['PASS optimized_clock', '   ~-------------~'],
            'DEMO.OUT': ['PASS feature_demo_complete', 'Tests passed: 19   failed: 0'],
            'SHOW.OUT': ['PYTHON 3 FOR 16-BIT DOS', '[PASS] 8 LIVE EXAMPLES',
                         'Source: github.com/ARMoir/micropython'],
            'GC.OUT': ['PASS gc_roots'],
            'COUNT16.OUT': ['COUNT16 iterations=65536 elapsed_ms=', 'PASS count16'],
            'ROBUST.OUT': ['PASS buffer_bounds', 'PASS gc_canary', 'PASS robust_complete'],
            'BADSYNT.OUT': ['SyntaxError:'],
            'RECOV.OUT': ['PASS after_parse_error'],
            'MEMSIZE.OUT': ['PASS heap_gc', 'PASS heap_roots'],
            'MEMAUTO.OUT': ['heap_bytes=', 'mode=auto'],
            'MEM48.OUT': ['heap_bytes=48000', 'mode=fixed'],
            'MEM24.OUT': ['heap_bytes=24000', 'mode=fixed'],
            'MEM60.OUT': ['heap_bytes=60000', 'mode=fixed'],
            'MEMCAP.OUT': ['heap_bytes=32000', 'mode=auto'],
            'INPUT.OUT': ['PASS input'],
            'REPL.OUT': ['Py86 ' + version + ' (MicroPython ' + a.core_version + ')',
                         'Python 3 for 16-bit DOS',
                         'Type "help()" for help, "exit()" to quit.',
                         '>>> 3', '42', 'PASS repl_recovery', 'ValueError: repl recovery'],
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

if a.repl_tab_test:
    tab_content = logs.get('REPLTAB.OUT', '')
    needed = (
        "print('PASS tab_builtin')",
        "PASS tab_builtin",
        "import os",
        "PASS tab_import",
        "HELLO",
        "PASS tab_cursor",
        "PASS tab_backspace",
        "startswith",
        "strip",
        "KeyboardInterrupt",
        "PASS tab_recovery",
    )
    for token in needed:
        if token not in tab_content:
            missing.append("REPLTAB.OUT: " + repr(token))
    if 'SyntaxError:' in tab_content or 'NameError:' in tab_content:
        missing.append('REPLTAB.OUT: Python traceback during completion test')
    if not (stage / 'TABRES.TXT').is_file() or (
            stage / 'TABRES.TXT').read_text().strip() != 'PASS':
        missing.append('TABCHECK.BAT: no PASS')

# Ensure CPython-style REPL banner is exact, including blank lines,
# while retaining the release's dynamically stamped Py86 version.
expected_banner = ('Py86 ' + version + ' (MicroPython ' + a.core_version + ')\n'
                   'Python 3 for 16-bit DOS\n'
                   'Type "help()" for help, "exit()" to quit.\n')
if expected_banner not in logs.get('REPL.OUT', '').replace('\r\n', '\n'):
    missing.append('REPL.OUT: incorrect banner or unexpected blank lines')
# The measurement must be produced by DOS PY86, with exactly one well-formed result.
count_lines = [line for line in logs.get('COUNT16.OUT', '').splitlines()
               if line.startswith('COUNT16 iterations=')]
if len(count_lines) != 1:
    missing.append('COUNT16.OUT: missing or duplicate measurement')
else:
    try:
        fields = dict(item.split('=', 1) for item in count_lines[0].split()[1:])
        if int(fields['iterations']) != 65536 or int(fields['elapsed_ms']) < 0:
            missing.append('COUNT16.OUT: invalid count or timing')
    except (KeyError, ValueError):
        missing.append('COUNT16.OUT: malformed result')

if any('FAIL ' in logs.get(name, '') for name in
       ('EXIT0.OUT', 'QUIT0.OUT', 'SYSEX0.OUT', 'SYSEX7.OUT',
        'SYSEX9.OUT', 'SYSEXTXT.OUT', 'REPLEX.OUT', 'REPLCODE.OUT')):
    missing.append('exit tests: Python continued running after SystemExit')
# Verify native DOS heap selection independently of Python-object memory
# and reject forged/success-looking output from a failing startup.
for name, target in (('MEM48.OUT', 48000), ('MEM24.OUT', 24000),
                     ('MEM60.OUT', 60000), ('MEMCAP.OUT', 32000)):
    line = logs.get(name, '').strip()
    if not line.startswith('heap_bytes=' + str(target) + ' '):
        missing.append(name + ': wrong selected heap')
auto = logs.get('MEMAUTO.OUT', '').strip()
if auto.startswith('heap_bytes='):
    try:
        amount = int(auto.split()[0].split('=', 1)[1])
        if not (24000 <= amount <= 60000):
            missing.append('MEMAUTO.OUT: size outside single-segment bounds')
    except (IndexError, ValueError):
        missing.append('MEMAUTO.OUT: invalid size')
if logs.get('CLOCK.OUT', '').count('~-------------~') < 2:
    missing.append('CLOCK.OUT: fewer than two rendered clock faces')
if logs.get('ONECLK.OUT', '').count('~-------------~') < 4:
    missing.append('ONECLK.OUT: fewer than two optimized clock frames')
full_launch_history = stage / 'LOADTIME.CSV'
if not full_launch_history.is_file():
    missing.append('LOADTIME.CSV: no parent-measured DOS load timing')
else:
    try:
        lines = full_launch_history.read_text(errors='replace').splitlines()
        assert lines[0] == 'date,time,version,full_launch_ms'
        assert int(lines[-1].split(',')[-1]) >= 0
    except (AssertionError, ValueError, IndexError):
        missing.append('LOADTIME.CSV: malformed parent DOS launch measurement')
# Enforce actual DOS 80x25 screenshot suitability: 23 visible rows leaves
# a command prompt below the showcase without causing the display to scroll.
show_lines = logs.get('SHOW.OUT', '').splitlines()
if len(show_lines) > 23 or len(show_lines) < 20:
    missing.append('SHOW.OUT: should occupy 20..23 lines on an 80x25 screen')
if any(len(line) > 76 for line in show_lines):
    missing.append('SHOW.OUT: line exceeds 76 columns on 80-column DOS')
if sum(line.startswith('>>> ') for line in show_lines) != 8:
    missing.append('SHOW.OUT: expected exactly 8 live expression lines')
for text_fragment in ('[0, 1, 4, 9, 16, 25]', '(5+0j)', '5040',
                      "'86'", 'True', 'Source: github.com/ARMoir/micropython'):
    if text_fragment not in logs.get('SHOW.OUT', ''):
        missing.append('SHOW.OUT: missing actual result ' + text_fragment)
demo_log = stage / 'PY86.LOG'
history_path = stage / 'PY86TIME.CSV'
if not history_path.is_file():
    missing.append('PY86TIME.CSV: startup history not saved')
else:
    rows = history_path.read_text(errors='replace').splitlines()
    if len(rows) < 2 or rows[0] != 'date,time,version,init_ms,first_python_ms,dispatch_ms':
        missing.append('PY86TIME.CSV: missing startup CSV header or data')
    else:
        try:
            values = rows[-1].split(',')
            boot_ms, first_ms, dispatch_ms = map(int, values[-3:])
            if not 0 <= boot_ms <= first_ms or dispatch_ms != first_ms - boot_ms:
                missing.append('PY86TIME.CSV: inconsistent measured startup values')
        except (ValueError, IndexError):
            missing.append('PY86TIME.CSV: invalid startup timing row')
if not demo_log.is_file():
    missing.append('PY86.LOG: demo did not create its persistent log')
else:
    demo_text = demo_log.read_text(errors='replace')
    if ('PASS feature_demo_complete' not in demo_text or
            demo_text.count('[PASS]') != 19 or '[FAIL]' in demo_text):
        missing.append('PY86.LOG: feature demo results missing or incomplete')
    # Startup timing must be measured by native PY86 code (not host Python).
    for label in ('INTERPRETER STARTUP', 'time.init_ms()', 'time.startup_ms()', 'time.launch_ms()',
                  'Native VM startup:', 'First Python code:', 'Full child launch:',
                  'Source parse/dispatch:', 'DOS EXE load / launcher:',
                  'Native times exclude the DOS loader'):
        if label not in demo_text:
            missing.append('PY86.LOG: missing startup timing ' + label)
    # The showcase must expose the actual operations and their computed
    # results, on BOTH the DOS console and in the persistent log.
    demo_stdout = logs.get('DEMO.OUT', '')
    for name, content in (('DEMO.OUT', demo_stdout), ('PY86.LOG', demo_text)):
        if content.count('    >>> ') < 19 or content.count('    output: ') < 19:
            missing.append(name + ': not enough code-and-result examples')
        for snippet in ('>>> -7 // 3', 'output: -3',
                        '>>> math.sqrt(144)', 'output: 12.0',
                        ">>> re.search(", '>>> json.dumps(data)',
                        ">>> sha256(b'abc')", '>>> os.getcwd()',
                        'Tests passed: 19   failed: 0'):
            if snippet not in content:
                missing.append(name + ': missing showcase example ' + snippet)
    if demo_stdout.splitlines() != demo_text.splitlines():
        missing.append('DEMO.OUT and PY86.LOG transcripts differ')
unexpected = [f for f, content in logs.items()
              if ('Traceback' in content and f not in ('REPL.OUT', 'ERROR.OUT', 'BADSYNT.OUT'))
              or (f == 'REPL.OUT' and any(x in content for x in ('SyntaxError', 'IndentationError', 'NameError')))]
report = {'environment': 'DOSBox ' + a.emulator + ' built-in DOS; not physical V20',
          'version': version,
          'feature_demo_log': demo_log.read_text(errors='replace') if demo_log.is_file() else '',
          'batch_result': result, 'missing': missing, 'unexpected_errors': unexpected, 'logs': logs}
(root / 'build/test-results.json').write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
raise SystemExit(0 if result == 'PASS' and not missing and not unexpected else 1)
