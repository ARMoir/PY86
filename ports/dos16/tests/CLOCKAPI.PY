# Quick checks for DOS-backed standard library APIs.
import os
import time
import datetime
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
print('PASS dos_datetime')
time.sleep(0.02)
print('PASS dos_sleep')
assert os.system('cls') == 0
print('PASS dos_cls')
