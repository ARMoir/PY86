"""Noninteractive DOSBox check for Py86 built-in curses."""
import curses
assert curses.KEY_UP == 259
assert curses.KEY_DOWN == 258
assert curses.KEY_LEFT == 260
assert curses.KEY_RIGHT == 261
screen = curses.initscr()
try:
    rows, cols = screen.getmaxyx()
    assert rows == 25 and cols in (40, 80)
    screen.clear()
    screen.addstr(1, 2, "curses native screen")
    screen.addch(2, 2, "@")
    screen.move(3, 2)
    screen.addstr("works")
    screen.refresh()
    screen.keypad(True)
    screen.nodelay(True)
    assert screen.getch() == -1
    screen.timeout(0)
    assert screen.getch() == -1
    curses.curs_set(0)
    curses.curs_set(1)
finally:
    curses.endwin()
print("PASS curses_screen")
