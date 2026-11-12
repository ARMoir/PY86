# Deterministic runtime benchmark: deliberately no file I/O in timed loops.
# Exercises dict lookup, instance attribute load, integer ops and bytecode VM.
import gc

class Counter:
    def __init__(self, value):
        self.value = value

def run_loop(n):
    table = {"value": 3}
    counter = Counter(4)
    result = 0
    for i in range(n):
        result += table["value"] + counter.value + (i & 7)
    return result

# 1200 is divisible by eight; 150 full repetitions of 0..7.
assert run_loop(1200) == 12600
for run in range(3):
    assert run_loop(1200) == 12600
print("PASS runtime_stress")
