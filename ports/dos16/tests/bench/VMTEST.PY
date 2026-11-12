# VM decode, dispatch and branch microbenchmarks. 8086-compatible Python.
import gc
import time
VM_GLOBAL = 9
def vm_load(n):
    x = 7
    y = 0
    for i in range(n):
        y = x
    return y
def vm_branch(n):
    count = 0
    for i in range(n):
        if i & 1:
            count += 1
    return count
def vm_unit():
    return 1
def vm_call(n):
    count = 0
    for i in range(n):
        count += vm_unit()
    return count
def vm_global(n):
    count = 0
    for i in range(n):
        count += VM_GLOBAL
    return count
def vm_tuple(n):
    a, b = 5, 8
    result = 0
    for i in range(n):
        a, b = b, a
        result = a + b
    return result
def bench(name, fn, count):
    for trial in range(3):
        gc.collect()
        start = time.ticks_ms()
        result = fn(count)
        ms = time.ticks_diff(time.ticks_ms(), start)
        print("BENCH", name, trial, count, ms, result)
print("MEM", gc.mem_free(), gc.mem_alloc())
bench("vm_load", vm_load, 24000)
bench("vm_branch", vm_branch, 16000)
bench("vm_call", vm_call, 2400)
bench("vm_global", vm_global, 14000)
bench("vm_tuple", vm_tuple, 14000)
print("PASS vmbench")
