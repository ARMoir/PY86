# Targeted DOS file behavior and memory-efficient reuse tests.
import os
buf = bytearray(10)
with open("RDFILE.DAT", "wb") as f:
    assert f.write(b"\x00A\xffB12345") == 9
with open("RDFILE.DAT", "rb") as f:
    n = f.readinto(buf)
    assert n == 9
    assert bytes(buf[:n]) == b"\x00A\xffB12345"
    assert f.readinto(buf) == 0
    f.seek(0)
    n = f.readinto(buf, 4)
    assert n == 4
    assert bytes(buf[:n]) == b"\x00A\xffB"
print("PASS readinto")

with open("RDTEXT.TXT", "w") as f:
    assert f.writelines(["first\n", "second\n", "third\n"]) is None
with open("RDTEXT.TXT", "r") as f:
    assert f.readline(2) == "fi"
    assert f.readline(10) == "rst\n"
    assert f.readline(0) == ""
    assert f.readlines() == ["second\n", "third\n"]
    assert f.readline() == ""
with open("RDFILE.DAT", "ab") as f:
    assert f.writelines((b"\x00", b"\xff")) is None
with open("RDFILE.DAT", "rb") as f:
    f.seek(9)
    assert f.readline() == b"\x00\xff"
    assert f.readline() == b""
with open("RDTEXT.TXT", "a") as f:
    f.writelines(s for s in ["fourth\n", "fifth\n"])
with open("RDTEXT.TXT", "r") as f:
    assert [s for s in f] == ["first\n", "second\n", "third\n", "fourth\n", "fifth\n"]
print("PASS writelines")
print("PASS native_readline")
os.remove("RDFILE.DAT")
os.remove("RDTEXT.TXT")
