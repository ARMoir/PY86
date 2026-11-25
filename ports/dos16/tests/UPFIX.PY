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


cases = {'eval': eval_fix, 'array': array_fix, 'bytes': bytes_fix}
if len(sys.argv) > 1:
    print('BEGIN upstream_' + sys.argv[1])
    cases[sys.argv[1]]()
else:
    for name in ('eval', 'array', 'bytes'):
        cases[name]()
    print('PASS upstream_fixes_complete')
