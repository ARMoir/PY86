# Python strings and bytes must retain equality, hashing and identity semantics
# when lazy string hashing is enabled. Also runs on normal production Py86.
import gc

s = ""
for c in "abcdef":
    s += c
assert s == "abcdef"
assert hash(s) == hash("abcdef")
d = {s: 42}
assert d["abcdef"] == 42
for n in range(50):
    assert d[s] == 42

prior = s
s += "!"
assert prior == "abcdef"
assert s == "abcdef!"
assert hash(s) == hash("abcdef!")

k = b""
for c in b"binary":
    k += bytes([c])
assert k == b"binary"
assert hash(k) == hash(b"binary")
bmap = {k: "ok"}
assert bmap[b"binary"] == "ok"

u = ""
for c in "café":
    u += c
assert u == "café"
assert hash(u) == hash("café")
assert {u: 5}["café"] == 5
gc.collect()
print("PASS lazy_hash_correctness")
