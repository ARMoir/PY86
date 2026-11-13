# GC-specific fixed-workload benchmark for 16-bit Py86.
# Three independent measured trials per scenario; timers are BIOS-tick based.
# Keeps a significant raw-byte workload live through repeated collections.
import gc
import time

def measure(name, count, check):
    for trial in range(3):
        gc.collect()
        start = time.ticks_ms()
        for n in range(count):
            gc.collect()
        elapsed = time.ticks_diff(time.ticks_ms(), start)
        assert elapsed > 0
        print("BENCH", name, trial, count, elapsed, check)

# Raw allocations have no Python references inside and are eligible for the
# data-aware short circuit. The baseline scans every word of these buffers.
raw = [bytearray(768) for i in range(16)]
for i in range(16):
    raw[i][0] = i + 1
gc.collect()
measure("gc_raw", 32, 136)
assert sum(item[0] for item in raw) == 136

# Pointer-containing Python collections must continue to be scanned.
refs = [[i, i + 1] for i in range(64)]
gc.collect()
measure("gc_refs", 32, 64)
assert len(refs) == 64 and refs[-1][1] == 64
print("PASS gcbench")
