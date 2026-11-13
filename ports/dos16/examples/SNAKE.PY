"""Py86 Snake. Arrow keys or WASD, P pauses, Q/Esc quits.
Small, incremental text updates for 8086/V20-class DOS systems.
"""
import sys
import random
import curses

def next_body(body, dx, dy, food, width, height):
    x, y = body[0]
    head = (x + dx, y + dy)
    grow = head == food
    if head[0] < 1 or head[0] > width or head[1] < 1 or head[1] > height:
        return None, False
    # A move into the vacating tail square is legal unless eating.
    if head in (body if grow else body[:-1]):
        return None, False
    return [head] + (body if grow else body[:-1]), grow

def place_food(body, width, height):
    if len(body) == width * height:
        return None
    while True:
        pos = (random.randint(1, width), random.randint(1, height))
        if pos not in body:
            return pos

def selftest():
    body = [(5, 5), (4, 5), (3, 5)]
    out, grow = next_body(body, 1, 0, (9, 9), 20, 10)
    assert out == [(6, 5), (5, 5), (4, 5)] and not grow
    out, grow = next_body(body, 1, 0, (6, 5), 20, 10)
    assert len(out) == 4 and grow
    assert next_body(body, -1, 0, (9, 9), 20, 10)[0] is None
    assert next_body([(1, 1)], -1, 0, (9, 9), 20, 10)[0] is None
    # Tail square is allowed as it moves away.
    assert next_body([(3, 3), (3, 4), (2, 4), (2, 3)], -1, 0,
                     (8, 8), 20, 10)[0] is not None
    print("PASS snake_logic")

def play():
    screen = curses.initscr()
    try:
        curses.curs_set(0)
        screen.keypad(True)
        rows, cols = screen.getmaxyx()
        width = min(38, cols - 4)
        height = min(16, rows - 6)
        if width < 12 or height < 8:
            raise ValueError("Snake needs a larger text display")
        screen.clear()
        screen.addstr(0, 1, "Py86 SNAKE  Arrows/WASD: steer  P: pause  Q: quit")
        screen.addstr(1, 1, "+" + "-" * width + "+")
        screen.addstr(height + 2, 1, "+" + "-" * width + "+")
        for y in range(1, height + 1):
            screen.addch(y + 1, 1, "|")
            screen.addch(y + 1, width + 2, "|")
        body = [(width // 2, height // 2),
                (width // 2 - 1, height // 2),
                (width // 2 - 2, height // 2)]
        dx, dy = 1, 0
        food = place_food(body, width, height)
        screen.addstr(height + 4, 2, "Score: 0")
        for x, y in body[1:]:
            screen.addch(y + 1, x + 1, "o")
        screen.addch(body[0][1] + 1, body[0][0] + 1, "@")
        screen.addch(food[1] + 1, food[0] + 1, "*")
        screen.refresh()
        score = 0
        screen.timeout(190)
        while True:
            key = screen.getch()
            if key in (ord("q"), ord("Q"), 27, 3):
                break
            if key in (ord("p"), ord("P")):
                screen.addstr(height + 4, 16, "PAUSED")
                screen.refresh()
                screen.timeout(-1)
                while screen.getch() not in (ord("p"), ord("P"), ord("q"), ord("Q"), 27):
                    pass
                screen.timeout(190)
                screen.addstr(height + 4, 16, "      ")
                screen.refresh()
                continue
            if key in (curses.KEY_UP, ord("w"), ord("W")) and dy != 1:
                dx, dy = 0, -1
            elif key in (curses.KEY_DOWN, ord("s"), ord("S")) and dy != -1:
                dx, dy = 0, 1
            elif key in (curses.KEY_LEFT, ord("a"), ord("A")) and dx != 1:
                dx, dy = -1, 0
            elif key in (curses.KEY_RIGHT, ord("d"), ord("D")) and dx != -1:
                dx, dy = 1, 0
            old_head = body[0]
            old_tail = body[-1]
            updated, grow = next_body(body, dx, dy, food, width, height)
            if updated is None:
                screen.addstr(height + 4, 16, "GAME OVER")
                screen.refresh()
                screen.timeout(-1)
                screen.getch()
                break
            body = updated
            if not grow:
                screen.addch(old_tail[1] + 1, old_tail[0] + 1, " ")
            else:
                score += 1
                screen.addstr(height + 4, 2, "Score: " + str(score) + "   ")
            screen.addch(old_head[1] + 1, old_head[0] + 1, "o")
            screen.addch(body[0][1] + 1, body[0][0] + 1, "@")
            if grow:
                food = place_food(body, width, height)
                if food is None:
                    screen.addstr(height + 4, 16, "YOU WIN!")
                    screen.refresh()
                    screen.timeout(-1)
                    screen.getch()
                    break
                screen.addch(food[1] + 1, food[0] + 1, "*")
            screen.refresh()
    finally:
        curses.endwin()

if "--selftest" in sys.argv:
    selftest()
else:
    play()
