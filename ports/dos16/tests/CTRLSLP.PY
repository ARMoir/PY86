# Test that a sleeping DOS program can still receive Ctrl+C.
import time
try:
    time.sleep(20)
except KeyboardInterrupt:
    print("PASS ctrlc_sleep_interrupt")
else:
    raise AssertionError("Ctrl+C did not interrupt sleep")
