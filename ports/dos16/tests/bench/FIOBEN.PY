# File-I/O speed test for real Py86.exe in DOSBox (not a 7 MHz V20 claim).
# Each launch runs one independent trial for stable 48 KB heap behavior.
import sys
import gc
import time
import os

phase = sys.argv[1]
line = "abcdefghij" * 3 + "\n"
count = 64
passes = 4
with open("FIOBEN.TXT", "w") as f:
    assert f.writelines([line] * count) is None

gc.collect()
start = time.ticks_ms()
total = 0
for rep in range(passes):
    with open("FIOBEN.TXT", "rb" if phase == "readinto" else "r") as f:
        if phase == "line":
            while True:
                value = f.readline()
                if not value:
                    break
                total += len(value)
        elif phase == "iter":
            for value in f:
                total += len(value)
        elif phase == "readinto":
            buf = bytearray(128)
            while True:
                n = f.readinto(buf)
                if n == 0:
                    break
                total += n
        else:
            raise ValueError("unknown phase")
ms = time.ticks_diff(time.ticks_ms(), start)
os.remove("FIOBEN.TXT")
assert total == count * passes * (32 if phase == "readinto" else 31)
print("BENCH", phase, count * passes, ms, total)
print("PASS filebench")
