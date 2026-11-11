import sys
try:
    exit(2)
except SystemExit as e:
    assert e.args[0] == 2
else:
    assert False
try:
    quit(3)
except SystemExit as e:
    assert e.args[0] == 3
else:
    assert False
try:
    sys.exit(4)
except SystemExit as e:
    assert e.args[0] == 4
else:
    assert False
print("PASS exit_can_be_caught")
