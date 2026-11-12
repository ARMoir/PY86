# Native DOS open() coverage. All paths are 8.3-compatible.
import os

with open("P86TXT.TXT", "w") as f:
    assert f.write("alpha\nbeta\n") == 11
    assert f.flush() is None
    assert not f.closed
assert f.closed
with open("P86TXT.TXT", "r") as f:
    assert f.readline() == "alpha\n"
    assert f.tell() > 0
    assert f.readline() == "beta\n"
    assert f.readline() == ""
    f.seek(0)
    assert f.read() == "alpha\nbeta\n"
print("PASS dos_text_open")

with open("P86BIN.DAT", "wb") as f:
    assert f.write(b"\x00\xff\x03abc") == 6
with open("P86BIN.DAT", "rb") as f:
    assert f.read(6) == b"\x00\xff\x03abc"
    f.seek(2)
    assert f.read(1) == b"\x03"
    assert f.read(12) == b"abc"
    assert f.read(1) == b""
print("PASS dos_binary_open")

with open("P86TXT.TXT", "a") as f:
    f.write("last\n")
with open("P86TXT.TXT", "r") as f:
    lines = [line for line in f]
    assert lines == ["alpha\n", "beta\n", "last\n"]
assert f.closed
print("PASS dos_context_manager")

try:
    open("MISSING.ZZZ", "r")
except OSError:
    pass
else:
    assert False

for mode in ("q", "rbx", "rbb", ""):
    try:
        open("P86TXT.TXT", mode)
    except ValueError:
        pass
    else:
        assert False
os.remove("P86TXT.TXT")
os.remove("P86BIN.DAT")
print("PASS dos_open_errors")
