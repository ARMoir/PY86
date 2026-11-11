# Timing of PythonClock's original rendering operations, without sleep or IO.
# Loads unmodified face.py/hour.py/minute.py/second.py alongside the benchmark.
import gc
import time
import datetime
from face import setface
from hour import sethour
from minute import setminute
from second import setsecond

def render(n):
    last = 0
    for tick in range(n):
        clockstring = setface()
        clockchar = [char for char in clockstring]
        now = datetime.datetime.now()
        hours = now.hour
        minutes = now.minute
        seconds = now.second
        minute = minutes % 10
        clockchar = sethour(hours, clockchar)
        clockchar = setminute(minutes, clockchar)
        clockchar = setsecond(seconds, minute, clockchar)
        display = ""
        for val in clockchar:
            display += val
        last = len(display)
    return last

n = 1
while True:
    gc.collect()
    t0 = time.ticks_ms()
    result = render(n)
    dt = time.ticks_diff(time.ticks_ms(), t0)
    if dt >= 450 or n >= 16:
        break
    n *= 2

print("MEM", gc.mem_free(), gc.mem_alloc())
for trial in range(3):
    gc.collect()
    t0 = time.ticks_ms()
    result = render(n)
    dt = time.ticks_diff(time.ticks_ms(), t0)
    print("BENCH", "clock_frame", trial, n, dt, result)
print("PASS framebench")
