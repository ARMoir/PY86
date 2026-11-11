# Integration harness injects a deferred Ctrl+C after 256 VM branches.
count = 0
try:
    while True:
        count += 1
except KeyboardInterrupt:
    assert count > 0
    print("PASS ctrlc_keyboard_interrupt")
else:
    raise AssertionError("Ctrl+C was not delivered")
