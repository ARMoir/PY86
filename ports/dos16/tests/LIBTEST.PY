# Core math/random/DOS os/time regression tests, runnable by Py86 in DOSBox.
import math
import random
import os
import time

assert abs(math.pi - 3.141592653589793) < 0.0000001
assert abs(math.e - 2.718281828459045) < 0.0000001
assert math.sqrt(81) == 9
assert abs(math.sin(math.pi / 2) - 1) < 0.000001
assert math.factorial(6) == 720
assert math.isclose(1.0, 1.0000000001)
print('PASS math')

random.seed(1234)
a = random.getrandbits(32)
b = random.getrandbits(32)
random.seed(1234)
assert a == random.getrandbits(32)
assert b == random.getrandbits(32)
for i in range(12):
    assert 0 <= random.randrange(10) < 10
    assert random.randrange(2, 12, 2) in (2, 4, 6, 8, 10)
    assert 2 <= random.randint(2, 5) <= 5
    assert random.choice((2, 4, 6)) in (2, 4, 6)
    assert 0 <= random.random() < 1
    assert -1 <= random.uniform(-1, 1) <= 1
random.seed(None)
print('PASS random')

assert os.name == 'dos'
assert os.sep == '\\'
cwd = os.getcwd()
assert len(cwd) > 0
assert 'CORE.PY' in [x.upper() for x in os.listdir()]
assert os.stat('CORE.PY')[6] > 0
os.mkdir('P86DIR')
assert 'P86DIR' in [x.upper() for x in os.listdir()]
os.chdir('P86DIR')
assert 'P86DIR' in os.getcwd().upper()
os.chdir('..')
os.rmdir('P86DIR')
os.rename('P86TMP.TXT', 'P86DST.TXT')
assert os.stat('P86DST.TXT')[6] > 0
os.remove('P86DST.TXT')
print('PASS os')

now = time.time()
assert now > 0
t = time.localtime()
assert len(t) == 9
assert 1 <= t[1] <= 12
assert 0 <= t[3] <= 23
assert len(time.localtime(now)) == 9
before = time.ticks_ms()
time.sleep_ms(70)
after = time.ticks_ms()
assert time.ticks_diff(after, before) >= 0
time.sleep(0.01)
print('PASS time')
