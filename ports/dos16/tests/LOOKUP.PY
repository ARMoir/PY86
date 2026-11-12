# Verify map lookup caching retains Python dict / instance semantics.
import gc
import os

data = {"value": 1, "other": 5}
for n in range(100):
    data["value"] = n
    assert data["value"] == n
    assert data["other"] == 5
data["new"] = 91
assert data["new"] == 91
del data["other"]
assert "other" not in data

class Probe:
    def __init__(self):
        self.value = 1

    def get(self):
        return self.value

p = Probe()
for n in range(100):
    p.value = n
    assert p.value == n
    assert p.get() == n
p.extra = "abc"
assert p.extra == "abc"
del p.extra
assert not hasattr(p, "extra")
assert os.name == "dos"
gc.collect()
print("PASS lookup_cache_correctness")
