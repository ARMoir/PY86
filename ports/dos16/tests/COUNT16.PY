# Exactly 65,536 integer increments, from -32768 through 32767.
# Measures only the loop with DOS BIOS ticks (~55 ms resolution).
# Run on hardware: PY86 COUNT16.PY (no display I/O inside timed section).
import time

value = -32768
started = time.ticks_ms()
while value <= 32767:
    value += 1
elapsed = time.ticks_diff(time.ticks_ms(), started)
assert value == 32768
assert elapsed >= 0
print("COUNT16 iterations=65536 elapsed_ms=" + str(elapsed))
print("PASS count16")
