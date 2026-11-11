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

# One isolated sample per interpreter invocation avoids accumulating dynamic
# qstrs/references over many frames in Py86's tiny 48KB heap. The DOSBox
# harness launches a fresh PY86.EXE three times and records every trial.
gc.collect()
print("MEM", gc.mem_free(), gc.mem_alloc())
t0 = time.ticks_ms()
result = render(2)
dt = time.ticks_diff(time.ticks_ms(), t0)
print("BENCH", "clock_frame", 0, 2, dt, result)
print("PASS framebench")
