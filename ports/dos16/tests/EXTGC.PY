# Extended GC regression for 8086/V20 Py86.
# Validate live object graphs, bytearray resizing, reclaiming and long cycles.
import gc

guard = bytearray(b"PY86GUARD")
parents = []
for turn in range(20):
    holder = [[], {}, turn]
    for i in range(20):
        buf = bytearray(30)
        buf[0] = i + 1
        buf[-1] = turn
        buf.extend(bytearray(24))
        pair = [i, buf]
        holder[0].append(pair)
        if i % 4 == 0:
            holder[1][i] = pair
    parents.append(holder)
    if len(parents) > 2:
        parents.pop(0)
    gc.collect()
    assert bytes(guard) == b"PY86GUARD"
    for pair in holder[0]:
        assert pair[1][0] == pair[0] + 1
        assert pair[1][29] == turn
        assert len(pair[1]) == 54
    for index in holder[1]:
        assert holder[1][index] is holder[0][index]
    # Reassign young references into older reachable objects.
    holder[1]["next"] = [turn, str(turn)]
    gc.collect()
    assert holder[1]["next"][1] == str(turn)

# Reallocation must not lose the data-only bit for bytes buffers.
buf = bytearray(b"X")
for n in range(30):
    buf.extend(bytearray(29))
    buf[0] = 88
    gc.collect()
    assert buf[0] == 88
    assert len(buf) == 1 + (n + 1) * 29
parents = []
gc.collect()
assert bytes(guard) == b"PY86GUARD"
print("PASS extgc", gc.mem_free(), gc.mem_alloc())
