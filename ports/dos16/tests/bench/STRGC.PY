# String allocation/GC profile with the unchanged PythonClock renderer.
# Required command: PY86 STRGC.PY [threshold], e.g. -1, 4096, 8192, 16384.
# DOSBox virtual 8086 timing uses ~55 ms-resolution BIOS ticks.
import gc
import sys
import time
import datetime
from face import setface
from hour import sethour
from minute import setminute
from second import setsecond

threshold = int(sys.argv[1]) if len(sys.argv) > 1 else -1
gc.threshold(threshold)
frame = setface()
chars = [ch for ch in frame]

def split_case(count):
    total = 0
    for i in range(count):
        split = [c for c in frame]
        total += len(split)
    return total

def concat_case(count):
    total = 0
    for i in range(count):
        display = ""
        for c in chars:
            display += c
        total += len(display)
    return total

def join_case(count):
    total = 0
    for i in range(count):
        display = "".join(chars)
        total += len(display)
    return total

def clock_case(count):
    total = 0
    for i in range(count):
        string = setface()
        cells = [c for c in string]
        now = datetime.datetime.now()
        cells = sethour(now.hour, cells)
        cells = setminute(now.minute, cells)
        cells = setsecond(now.second, now.minute % 10, cells)
        display = ""
        for c in cells:
            display += c
        total += len(display)
    return total

def measure(name, func, count):
    for trial in range(3):
        gc.collect()
        before = gc.mem_free()
        begin = time.ticks_ms()
        check = func(count)
        elapsed = time.ticks_diff(time.ticks_ms(), begin)
        during = gc.mem_free()
        begin = time.ticks_ms()
        gc.collect()
        gc_ms = time.ticks_diff(time.ticks_ms(), begin)
        after = gc.mem_free()
        print("PROFILE", name, trial, count, elapsed, before, during, after, gc_ms, check)

print("CONFIG", threshold, gc.threshold(), gc.mem_free(), gc.mem_alloc())
measure("split_chars", split_case, 5)
measure("concat_chars", concat_case, 3)
measure("join_chars", join_case, 10)
measure("clock_frame", clock_case, 2)
print("PASS strgc")
