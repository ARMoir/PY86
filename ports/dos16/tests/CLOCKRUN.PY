# Import the unchanged PythonClock source but stop after its first refresh.
# This exercises imports, ASCII rendering, the DOS date/time bridge, and sleep.
import time

_real_sleep = time.sleep

def stop_after_first_frame(seconds):
    assert seconds == 1
    print('PASS clock_first_frame')
    raise SystemExit

time.sleep = stop_after_first_frame
try:
    import Clock
except SystemExit:
    pass
finally:
    time.sleep = _real_sleep
print('PASS clock_original')
