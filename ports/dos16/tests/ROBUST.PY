# Memory-boundary and GC regression tests using only public Python APIs.
# These do NOT inject native memory corruption or malformed VM bytecode.
import gc

def bad_index(container, index):
    try:
        ignored = container[index]
    except IndexError:
        return
    raise AssertionError("read outside buffer accepted")

def bad_write(container, index):
    try:
        container[index] = 123
    except IndexError:
        return
    raise AssertionError("write outside buffer accepted")

# Both ends, empty buffers, positive and negative out-of-range addresses.
for length in (0, 1, 16, 97):
    data = bytearray(length)
    view = memoryview(data)
    raw = bytes(data)
    for index in (-length - 1, length, length + 1000, -length - 1000):
        bad_index(data, index)
        bad_index(view, index)
        bad_index(raw, index)
        bad_write(data, index)
        bad_write(view, index)
    if length:
        data[0] = 165
        data[-1] = 90
        assert data[0] == 90 if length == 1 else data[0] == 165
        assert view[-1] == 90
print("PASS buffer_bounds")

# Object roots and sentinel contents must survive repeated heap pressure.
sentinel = bytearray(b"VMGUARD!")
for n in range(128):
    temp = bytearray(80)
    temp[0] = n % 256
    temp[-1] = (n * 3) % 256
    assert temp[0] == n % 256
    assert temp[-1] == (n * 3) % 256
    if n % 8 == 0:
        gc.collect()
    assert bytes(sentinel) == b"VMGUARD!"
print("PASS gc_canary")
print("PASS robust_complete")
