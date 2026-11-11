# Py86 interpreter microbenchmarks. No external libraries; works on 8086 DOS.
# Times come from the DOS BIOS tick clock (~55ms resolution).
import gc
import time
import os

CONST = 7

class Probe:
    def __init__(self):
        self.value = 7

    def get(self):
        return self.value

probe = Probe()
mapping = {"value": 7}

def local_int(n):
    total = 0
    for i in range(n):
        total += 7
    return total

def global_int(n):
    total = 0
    for i in range(n):
        total += CONST
    return total

def dict_lookup(n):
    total = 0
    for i in range(n):
        total += mapping["value"]
    return total

def instance_attr(n):
    total = 0
    for i in range(n):
        total += probe.value
    return total

def bound_method(n):
    total = 0
    for i in range(n):
        total += probe.get()
    return total

def module_attr(n):
    total = 0
    for i in range(n):
        if os.name == "dos":
            total += 1
    return total

def concat(n):
    s = ""
    for i in range(n):
        s += "x"
    return len(s)

def benchmark(name, fn, max_n):
    # Auto-calibrate because BIOS ticks are only about 55ms each.
    n = 100
    while True:
        gc.collect()
        t0 = time.ticks_ms()
        check = fn(n)
        dt = time.ticks_diff(time.ticks_ms(), t0)
        if dt >= 450 or n >= max_n:
            break
        n *= 2
        if n > max_n:
            n = max_n
    for trial in range(3):
        gc.collect()
        t0 = time.ticks_ms()
        check = fn(n)
        dt = time.ticks_diff(time.ticks_ms(), t0)
        print("BENCH", name, trial, n, dt, check)

print("MEM", gc.mem_free(), gc.mem_alloc())
benchmark("local_int", local_int, 12800)
benchmark("global_int", global_int, 12800)
benchmark("dict_lookup", dict_lookup, 6400)
benchmark("instance_attr", instance_attr, 6400)
benchmark("bound_method", bound_method, 6400)
benchmark("module_attr", module_attr, 6400)
benchmark("concat", concat, 600)
print("PASS microbench")
