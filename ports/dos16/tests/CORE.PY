assert 7 // 3 == 2
assert -7 // 3 == -3
assert -7 % 3 == 2
assert 7 / 2 == 3.5
assert 2 ** 100 == 1267650600228229401496703205376
assert (2 ** 100 + 1) - 2 ** 100 == 1
assert abs((1 + 2j) * (1 - 2j) - 5) < 0.00001
assert True + True == 2
assert None is None
print('PASS numeric')
s = 'caf\u00e9 \U0001f600'
assert len(s) == 6
assert ord(s[3]) == 233
assert ord(s[5]) == 128512
assert s.encode('utf-8').decode('utf-8') == s
assert s[3:4] == '\u00e9'
assert isinstance(b'x', bytes) and isinstance('x', str)
print('PASS unicode')
x = []
for i in range(8):
    if i == 2:
        continue
    if i == 6:
        break
    x.append(i)
assert x == [0, 1, 3, 4, 5]
n = 3
while n:
    n -= 1
else:
    x.append(9)
assert x[-1] == 9
print('PASS control')
def outer(x):
    def inner(y=3, *args, **kwargs):
        return x + y + sum(args) + kwargs.get('z', 0)
    return inner
assert outer(5)(4, 6, z=7) == 22
assert outer(5)() == 8
print('PASS functions')
try:
    try:
        raise ValueError('expected')
    finally:
        n = 42
except ValueError as e:
    assert str(e) == 'expected'
assert n == 42
try:
    1 / 0
except ZeroDivisionError:
    pass
else:
    raise AssertionError('division must raise')
print('PASS exceptions')
a = [i * i for i in range(5)]
assert a == [0, 1, 4, 9, 16]
assert a[1:4] == [1, 4, 9]
d = {'a': 1, 'b': 2}
assert sorted(d.keys()) == ['a', 'b']
assert (1, 2) + (3,) == (1, 2, 3)
assert {1, 2, 2} == {2, 1}
assert {i: i + 1 for i in range(3)}[2] == 3
print('PASS containers')
def gen():
    yield 1
    yield 2
assert list(gen()) == [1, 2]
class A:
    def __init__(self, x):
        self.x = x
    def add(self, n):
        return self.x + n
assert A(7).add(4) == 11
print('PASS classes_generators')
import HELPER
from HELPER import twice
assert twice(21) == 42
assert HELPER.VALUE == 'imported'
print('PASS imports')
print('PASS core_complete')
