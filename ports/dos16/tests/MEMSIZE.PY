# Keep GC roots valid after selecting an adaptive far-memory segment.
import gc
gc.collect()
total = gc.mem_free() + gc.mem_alloc()
assert 22000 <= total <= 60000
print("PASS heap_gc", total)
blob = bytearray(4096)
for i in range(0, len(blob), 257):
    blob[i] = 123
gc.collect()
assert blob[0] == 123 and blob[257] == 123
print("PASS heap_roots")
