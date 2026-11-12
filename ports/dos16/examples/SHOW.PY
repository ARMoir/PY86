# Py86 one-screen real-hardware showcase. Plain DOS 80x25, 8.3 filename.
# Deliberately 23 lines maximum; no ANSI colors or terminal dependencies.
import math
import re
import json
import hashlib
import gc

count = 0


def example(code, value, expected):
    global count
    # The output below comes from the live computation, not sample text.
    assert value == expected
    print('>>> ' + code)
    print('    ' + repr(value))
    count += 1


class Counter:
    def __init__(self, value):
        self.value = value

    def step(self):
        self.value += 1
        return self.value


print('+--------------------------------------------------------------------+')
print('| PY86  /  PYTHON 3 FOR 16-BIT DOS    |  7 MHz TANDY 1000 EX / V20 |')
print('+--------------------------------------------------------------------+')
print('')
example('[n*n for n in range(6)]  # comprehensions',
        [n*n for n in range(6)], [0, 1, 4, 9, 16, 25])
example('(1+2j) * (1-2j)  # complex arithmetic',
        (1 + 2j) * (1 - 2j), 5)
example('Counter(41).step()  # classes + methods',
        Counter(41).step(), 42)
example('math.factorial(7)  # math',
        math.factorial(7), 5040)
example("re.search('[0-9]+', 'TANDY86').group(0)  # regex",
        re.search('[0-9]+', 'TANDY86').group(0), '86')
example("json.loads('{\"n\":86}')['n']  # JSON",
        json.loads('{"n":86}')['n'], 86)
example("hashlib.sha256(b'abc').digest()[:4]  # SHA-256",
        hashlib.sha256(b'abc').digest()[:4], b'\xba\x78\x16\xbf')
free = gc.mem_free()
assert free > 0
example('gc.mem_free() > 0  # garbage collector', free > 0, True)
print('+--------------------------------------------------------------------+')
print('[PASS] %d LIVE EXAMPLES  |  MICRO PYTHON 1.24.1  |  REAL-MODE DOS' % count)
print('Source: github.com/ARMoir/micropython')
