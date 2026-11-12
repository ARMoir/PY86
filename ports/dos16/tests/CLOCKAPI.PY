# Quick checks for DOS-backed standard library APIs.
import os
import time
import datetime
# Native PY86 startup timestamps use DOS BIOS ticks and are visible to scripts.
init_ms = time.init_ms()
startup_ms = time.startup_ms()
assert 0 <= init_ms <= startup_ms
print('PASS startup_timing')
assert os.name == 'dos'
t = time.localtime()
assert len(t) == 9
assert 1980 <= t[0] <= 2099
assert 1 <= t[1] <= 12
assert 1 <= t[2] <= 31
assert 0 <= t[3] <= 23
assert 0 <= t[4] <= 59
assert 0 <= t[5] <= 59
assert 0 <= t[6] <= 6
assert 1 <= t[7] <= 366
assert t[8] == -1
now = datetime.datetime.now()
assert now.year == t[0]
assert 0 <= now.hour <= 23
assert 0 <= now.minute <= 59
assert 0 <= now.second <= 59
assert now.microsecond >= 0 and now.microsecond < 1000000
assert datetime.datetime(2024, 2, 29, 12, 34, 56, 123456).microsecond == 123456
assert datetime.datetime(year=2026, month=11, day=10).hour == 0
assert isinstance(datetime.datetime.today(), datetime.datetime)
try:
    datetime.datetime(2025, 2, 29)
except ValueError:
    pass
else:
    raise AssertionError('invalid date accepted')
print('PASS datetime_builtin')
print('PASS dos_datetime')
time.sleep(0.02)
print('PASS dos_sleep')
assert os.system('cls') == 0
print('PASS dos_cls')
