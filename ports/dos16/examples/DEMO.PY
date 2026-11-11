# PY86 full feature showcase. ASCII-only output is readable on DOS 6.22.
# All results are written to PY86.LOG as well as to the console.
# This is a runnable example, not a replacement for the deeper CI test suite.
import time
# Capture startup immediately at the first executed Python statements.
# C main() -> native VM initialization and C main() -> first Python code.
# DOS MZ loading / COMMAND.COM execution before C main is not included.
STARTUP_MS = time.startup_ms()
INIT_MS = time.init_ms()
LAUNCH_MS = time.launch_ms()
import sys
import os
import gc

PASSED = 0
FAILED = 0
LOG = None


def show(message):
    print(message)
    if LOG is not None:
        LOG.write(message + '\n')
        LOG.flush()


def example(code, output):
    # Print the actual value computed by the test, not a canned result.
    # Both lines go to the DOS screen and to PY86.LOG.
    show('    >>> ' + code)
    show('    output: ' + repr(output))


def append_startup_history():
    # Append-only DOS 8.3 CSV retains comparisons between different releases.
    # Native timings were sampled before imports/logging, so file I/O does
    # not inflate the measured startup times.
    timestamp = time.localtime()
    version = 'unknown'
    try:
        with open('README.TXT', 'r') as info:
            first = info.readline().split()
            if len(first) >= 2 and first[0] == 'Py86':
                version = first[1].rstrip(':')
    except OSError:
        pass
    filename = 'PY86TIME.CSV'
    try:
        with open(filename, 'r') as previous:
            has_header = bool(previous.readline())
    except OSError:
        has_header = False
    try:
        with open(filename, 'a') as history:
            if not has_header:
                history.write('date,time,version,init_ms,first_python_ms,dispatch_ms\n')
            history.write('%04d-%02d-%02d,%02d:%02d:%02d,%s,%d,%d,%d\n' %
                          (timestamp[0], timestamp[1], timestamp[2],
                           timestamp[3], timestamp[4], timestamp[5],
                           version, INIT_MS, STARTUP_MS, STARTUP_MS - INIT_MS))
        show('  Startup history appended to ' + filename)
        if LAUNCH_MS is not None:
            # Keep the original CSV schema intact across version upgrades.
            full_name = 'LOADTIME.CSV'
            try:
                with open(full_name, 'r') as previous:
                    exists = bool(previous.readline())
            except OSError:
                exists = False
            with open(full_name, 'a') as log:
                if not exists:
                    log.write('date,time,version,full_launch_ms\n')
                log.write('%04d-%02d-%02d,%02d:%02d:%02d,%s,%d\n' %
                          (timestamp[0], timestamp[1], timestamp[2],
                           timestamp[3], timestamp[4], timestamp[5],
                           version, LAUNCH_MS))
            show('  Full DOS launch appended to ' + full_name)
    except OSError as error:
        show('  Startup CSV not writable: ' + str(error))


def line():
    show('+----------------------------------------------------------+')


def banner(title):
    line()
    show('| %-56s |' % title)
    line()


def check(label, func):
    global PASSED, FAILED
    show('')
    show('  ' + label.upper())
    start = time.ticks_ms()
    try:
        func()
        elapsed = time.ticks_diff(time.ticks_ms(), start)
        PASSED += 1
        show('  [PASS] %-33s %5d ms' % (label, elapsed))
    except Exception as error:
        FAILED += 1
        show('  [FAIL] %s' % label)
        show('         %s: %s' % (type(error).__name__, str(error)))
    gc.collect()


def integers():
    assert -7 // 3 == -3
    assert 10 % 3 == 1
    assert 1000000 * 1000000 == 1000000000000
    assert 2 ** 10 == 1024
    example('-7 // 3', -7 // 3)
    example('1000000 * 1000000', 1000000 * 1000000)


def floats_complex():
    assert 1.25 + 2.5 == 3.75
    assert (1 + 2j) * (1 - 2j) == 5
    example('1.25 + 2.5', 1.25 + 2.5)
    example('(1+2j) * (1-2j)', (1 + 2j) * (1 - 2j))


def text_unicode():
    assert 'DOS'.lower() == 'dos'
    assert '-'.join(('PY', '86')) == 'PY-86'
    assert 'abcdef'[1:4] == 'bcd'
    assert '\u03a9' != 'A'
    assert len('\u03a9') == 1
    example("'abcdef'[1:4]", 'abcdef'[1:4])
    example("ord('\\u03a9')", ord('\u03a9'))


def containers():
    squares = [i * i for i in range(6)]
    assert squares == [0, 1, 4, 9, 16, 25]
    mapping = {'name': 'PY86', 'value': 86}
    assert mapping['value'] == 86
    assert set((1, 1, 2, 3)) == {1, 2, 3}
    assert tuple(squares[:2]) == (0, 1)
    example('[i*i for i in range(6)]', squares)
    example("mapping['value']", mapping['value'])


def classes_generators():
    class Ticker:
        def __init__(self, value):
            self.value = value

        def step(self):
            self.value += 1
            return self.value

    thing = Ticker(41)
    assert thing.step() == 42
    g = (n * n for n in range(3))
    assert next(g) == 0 and next(g) == 1 and next(g) == 4
    example('Ticker(41).step()', thing.value)
    example('next(n*n for n in range(3))', next(n * n for n in range(3)))


def functions_closure():
    def multiplier(factor):
        def mul(value):
            return value * factor
        return mul
    assert multiplier(7)(6) == 42
    def collect(*args, **kwargs):
        return (len(args), kwargs['a'])
    assert collect(1, 2, a=3) == (2, 3)
    example('multiplier(7)(6)', multiplier(7)(6))
    example('collect(1, 2, a=3)', collect(1, 2, a=3))


def exceptions():
    state = []
    try:
        try:
            raise ValueError('expected')
        except ValueError as error:
            assert str(error) == 'expected'
            state.append('caught')
    finally:
        state.append('finally')
    assert state == ['caught', 'finally']
    example("catch ValueError('expected') + finally", state)


def math_module():
    import math
    assert math.sqrt(144) == 12.0
    assert math.factorial(5) == 120
    assert math.isclose(math.sin(math.pi / 2), 1.0)
    example('math.sqrt(144)', math.sqrt(144))
    example('math.factorial(5)', math.factorial(5))


def random_module():
    import random
    random.seed(86)
    n = random.randint(1, 100)
    assert 1 <= n <= 100
    assert random.choice((3, 7, 11)) in (3, 7, 11)
    example('random.seed(86); random.randint(1,100)', n)


def datetime_module():
    import datetime
    now = datetime.datetime.now()
    assert 1 <= now.month <= 12 and 0 <= now.hour <= 23
    fixed = datetime.datetime(2026, 11, 11, 9, 30, 5)
    assert fixed.year == 2026 and fixed.minute == 30
    example('datetime.datetime.now()', '%04d-%02d-%02d %02d:%02d:%02d' %
            (now.year, now.month, now.day, now.hour, now.minute, now.second))


def time_module():
    t = time.localtime()
    assert len(t) >= 6 and 1 <= t[1] <= 12
    assert 0 <= t[5] <= 59
    start = time.ticks_ms()
    time.sleep_ms(60)
    assert time.ticks_diff(time.ticks_ms(), start) >= 0
    example('time.localtime()[:6]', t[:6])
    example('ticks elapsed after sleep_ms(60)',
            time.ticks_diff(time.ticks_ms(), start))


def regex_module():
    import re
    assert re.match('a+b', 'aaabc').group(0) == 'aaab'
    assert re.search('[0-9]+', 'DOS86PY').group(0) == '86'
    assert re.compile('(ab)+').match('ababX').group(0) == 'abab'
    example("re.search('[0-9]+','DOS86PY').group(0)",
            re.search('[0-9]+', 'DOS86PY').group(0))


def json_module():
    import json
    data = {'platform': 'dos', 'values': [1, 2, 3], 'ok': True}
    encoded = json.dumps(data)
    assert json.loads(encoded) == data
    example('json.dumps(data)', encoded)
    example('json.loads(encoded)["values"]', json.loads(encoded)['values'])


def sha256_module():
    import hashlib
    digest = hashlib.sha256(b'abc').digest()
    assert len(digest) == 32
    assert digest[:4] == b'\xba\x78\x16\xbf'
    h = hashlib.sha256()
    h.update(b'a')
    h.update(b'bc')
    assert h.digest() == digest
    hexdigest = ''.join('%02x' % n for n in digest)
    example("sha256(b'abc').digest() as hex", hexdigest)


def errno_module():
    import errno
    assert errno.ENOENT > 0 and errno.EEXIST > 0 and errno.EINVAL > 0
    example('errno.ENOENT', errno.ENOENT)
    example('errno.EINVAL', errno.EINVAL)


def filesystem():
    filename = 'P86D.TXT'
    renamed = 'P86E.TXT'
    for candidate in (filename, renamed):
        try:
            os.remove(candidate)
        except OSError:
            pass
    with open(filename, 'w') as f:
        f.writelines(('alpha\n', 'beta\n'))
    with open(filename, 'r') as f:
        assert f.readline().strip() == 'alpha'
        assert f.readline().strip() == 'beta'
    with open(filename, 'rb') as f:
        data = bytearray(4)
        count = f.readinto(data)
        assert count == 4 and bytes(data) == b'alph'
    assert len(os.stat(filename)) == 10
    os.rename(filename, renamed)
    assert renamed in os.listdir()
    os.remove(renamed)
    example("readinto(bytearray(4)) from P86D.TXT", bytes(data))
    example("os.rename('P86D.TXT','P86E.TXT')", 'renamed and removed')


def os_module():
    assert os.name == 'dos'
    path = os.getcwd()
    assert len(path) >= 1
    assert os.sep in ('\\', '/')
    example('os.name', os.name)
    example('os.getcwd()', path)


def gc_module():
    before = gc.mem_free()
    gc.collect()
    after = gc.mem_free()
    assert before > 0 and after > 0
    example('gc.mem_free() after collect()', after)


def command_line():
    assert len(sys.argv) >= 1
    example('sys.argv', sys.argv)


def main():
    global LOG
    started = time.ticks_ms()
    LOG = open('PY86.LOG', 'w')
    try:
        banner('PY86 / 16-BIT DOS FEATURE SHOWCASE')
        show('Platform: %s  |  Interpreter: MicroPython DOS port' % os.name)
        show('Result log: PY86.LOG (saved on current DOS drive)')
        show('The commands and outputs below are executed live by PY86.')
        show('Each >>> line shows the operation; output is the real result.')
        show('')
        banner('INTERPRETER STARTUP')
        example('time.init_ms()  # C main to VM ready', INIT_MS)
        example('time.startup_ms()  # C main to first Python', STARTUP_MS)
        assert INIT_MS >= 0 and STARTUP_MS >= INIT_MS
        show('  Native VM startup: %d ms' % INIT_MS)
        show('  First Python code: %d ms' % STARTUP_MS)
        show('  Source parse/dispatch: approx %d ms' %
             (STARTUP_MS - INIT_MS))
        show('  BIOS timer resolution: about 55 ms')
        if LAUNCH_MS is None:
            show('  Full EXE-load timing: unavailable (run RUNTEST)')
        else:
            example('time.launch_ms()  # before EXE load to Python', LAUNCH_MS)
            assert LAUNCH_MS >= STARTUP_MS
            show('  Full child launch: %d ms' % LAUNCH_MS)
            show('  DOS EXE load / launcher: approx %d ms' %
                 (LAUNCH_MS - STARTUP_MS))
        show('  Native times exclude the DOS loader unless START86 is used.')
        append_startup_history()
        show('')
        banner('LANGUAGE AND OBJECTS')
        check('Integer arithmetic and big ints', integers)
        check('Floating point and complex', floats_complex)
        check('String and Unicode support', text_unicode)
        check('Lists, tuples, dicts and sets', containers)
        check('Classes and generators', classes_generators)
        check('Functions and closures', functions_closure)
        check('Exception handling', exceptions)
        banner('BUILT-IN MODULES')
        check('math', math_module)
        check('random', random_module)
        check('datetime', datetime_module)
        check('time', time_module)
        check('re', regex_module)
        check('json', json_module)
        check('hashlib (SHA-256)', sha256_module)
        check('errno', errno_module)
        check('os', os_module)
        check('gc', gc_module)
        banner('DOS INTEGRATION')
        check('File I/O and filesystem', filesystem)
        check('Command-line arguments', command_line)
        banner('SUMMARY')
        show('Tests passed: %d   failed: %d   total: %d' %
             (PASSED, FAILED, PASSED + FAILED))
        show('Elapsed: %d ms' % time.ticks_diff(time.ticks_ms(), started))
        show('Final free heap: %d bytes' % gc.mem_free())
        show('All commands, real outputs and results saved in PY86.LOG')
        show('PASS feature_demo_complete' if FAILED == 0 else
             'FAIL feature_demo_incomplete')
        line()
    finally:
        LOG.close()
        LOG = None
    if FAILED:
        sys.exit(1)


main()
