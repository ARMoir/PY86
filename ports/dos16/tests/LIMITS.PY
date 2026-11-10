# Known upstream MicroPython difference, not a passing CPython feature.
try:
    'abc'[::-1]
except NotImplementedError:
    print('KNOWN unsupported str slice step')
else:
    print('SUPPORTED str slice step')
