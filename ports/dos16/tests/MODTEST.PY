# Py86 native standard-library tests on a DOS 8086/V20 interpreter.
import gc
import json
import errno
import re
import hashlib

assert errno.ENOENT > 0
assert errno.EEXIST > 0
assert errno.EINVAL > 0
print('PASS errno')

obj = json.loads('{"score":42,"ok":true,"nil":null,"items":[1,2,3]}')
assert obj['score'] == 42 and obj['ok'] is True
assert obj['nil'] is None and obj['items'] == [1,2,3]
data = {"name":"Py86", "active":True, "values":[3,2,1]}
assert json.loads(json.dumps(data)) == data
assert json.loads('"escape\\n"') == 'escape\n'
print('PASS json')

assert re.match('a+b', 'aaabc').group(0) == 'aaab'
assert re.search('[0-9]+', 'clock123time').group(0) == '123'
r = re.compile('(ab)+')
assert r.match('ababX').group(0) == 'abab'
m = re.match('(a)(b)', 'abc')
assert m.group(1) == 'a' and m.group(2) == 'b'
assert m.span() == (0, 2)
print('PASS re')

empty = b'\xe3\xb0\xc4\x42\x98\xfc\x1c\x14\x9a\xfb\xf4\xc8\x99\x6f\xb9\x24\x27\xae\x41\xe4\x64\x9b\x93\x4c\xa4\x95\x99\x1b\x78\x52\xb8\x55'
abc = b'\xba\x78\x16\xbf\x8f\x01\xcf\xea\x41\x41\x40\xde\x5d\xae\x22\x23\xb0\x03\x61\xa3\x96\x17\x7a\x9c\xb4\x10\xff\x61\xf2\x00\x15\xad'
assert hashlib.sha256(b'').digest() == empty
assert hashlib.sha256(b'abc').digest() == abc
h = hashlib.sha256()
h.update(b'a')
h.update(b'bc')
assert h.digest() == abc
print('PASS hashlib')

assert gc.mem_free() > 0
print('PASS native_modules_complete')
