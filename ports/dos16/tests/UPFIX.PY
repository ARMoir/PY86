# Upstream regressions: eval continuation and builtin constructor subclasses.
import gc
import sys


def raises(error, function, *args):
    try:
        function(*args)
    except error:
        return
    raise AssertionError('expected exception')


def eval_fix():
    for text in ('123\\', '123\\\n', '1 + 2\\', '123\\\r\n',
                 '123\\\r', '1 + 2\\\r\n', '1 + 2\\\r'):
        raises(SyntaxError, eval, text)
    for ending in ('\n', '\r\n', '\r'):
        assert eval('1 + \\' + ending + '2') == 3
    assert eval('123') == 123
    assert eval('1, 2') == (1, 2)
    assert eval('lambda x: x + 1')(2) == 3
    namespace = {}
    exec('answer = 42', namespace)
    assert namespace['answer'] == 42
    print('PASS upstream_eval')


def array_fix():
    class MyInt(int):
        pass
    assert bytearray() == bytearray(0)
    assert bytearray([1, 2]) == b'\x01\x02'
    for length in (0, 2, 97):
        data = bytearray(MyInt(length))
        assert len(data) == length
        assert data == bytes(length)
        if length:
            data[-1] = 90
        gc.collect()
        assert len(data) == length
        if length:
            assert data[-1] == 90
    print('PASS upstream_bytearray')


def bytes_fix():
    class MyStr(str):
        pass
    for text in ('', 'abc', '\u03a9'):
        value = MyStr(text)
        raw = bytes(value, 'utf-8')
        gc.collect()
        assert raw == bytes(text, 'utf-8')
        raises(TypeError, bytes, value)
    assert bytes([1, 2]) == b'\x01\x02'
    assert bytes(bytearray(b'abc')) == b'abc'
    print('PASS upstream_bytes')


def json_fix():
    import json
    import time
    assert json.dumps('') == '""'
    assert json.dumps('plain ASCII') == '"plain ASCII"'
    assert json.dumps('a"b\\c\n\r\t') == '"a\\"b\\\\c\\n\\r\\t"'
    for i in range(32):
        value = chr(i)
        encoded = json.dumps(value)
        assert json.loads(encoded) == value
        assert len(encoded) > 3
    for value in ('\u03a9', 'abc\u03a9xyz', '\u03a9"\\\n\u03a9'):
        assert json.loads(json.dumps(value)) == value
    for value in ('x' * 1024, ('a"b\\c\n' * 100), ('x' * 511 + '"' + 'y' * 512)):
        encoded = json.dumps(value)
        gc.collect()
        assert json.loads(encoded) == value
    value = {'key': ['abc', 17, True, None, '\u03a9']}
    assert json.loads(json.dumps(value)) == value
    value = 'abcdefghijklmnopqrstuvwxyz012345' * 32
    gc.collect()
    start = time.ticks_ms()
    for i in range(30):
        encoded = json.dumps(value)
    elapsed = time.ticks_diff(time.ticks_ms(), start)
    assert encoded == '"' + value + '"'
    print('JSON_MS', elapsed)
    print('PASS upstream_json')


cases = {'eval': eval_fix, 'array': array_fix, 'bytes': bytes_fix, 'json': json_fix}
if len(sys.argv) > 1:
    print('BEGIN upstream_' + sys.argv[1])
    cases[sys.argv[1]]()
else:
    for name in ('eval', 'array', 'bytes', 'json'):
        cases[name]()
    print('PASS upstream_fixes_complete')
