# GC stress regression for experimental incremental-GC branch only.
# Repeatedly attach young objects to already live containers.
import gc

class Box:
    def __init__(self, value):
        self.value = value

holder = Box([0, 1, 2])
dictionary = {"live": holder}
links = [holder, dictionary, holder.value]
for n in range(96):
    child = Box([n, str(n), n + 1])
    holder.value = child
    dictionary["live"] = child
    links[n % 3] = child
    for m in range(7):
        scratch = bytearray(48)
        scratch[m] = (n + m) % 256
        assert scratch[m] == (n + m) % 256
    if n % 6 == 0:
        gc.collect()
    assert dictionary["live"] is child
    assert holder.value is child
    assert links[n % 3] is child
    assert child.value == [n, str(n), n + 1]
gc.collect()
assert len(links) == 3 and "live" in dictionary
print("PASS incremental_gc_mutations")
