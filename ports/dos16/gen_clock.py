"""Generate a single-file, clock-only optimized DOS script from checked-in PythonClock.

Only trusted repository sources are evaluated to extract the original artwork
and hand coordinates. The source files in tests/pythonclock are NEVER altered.
The derived CLOCK.PY is generated into build/ for the release package.
"""
import argparse
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCES = ROOT / "tests" / "pythonclock"
OUTPUT = ROOT / "build" / "CLOCK.PY"


def original_parts():
    ns = {}
    # These are trusted, checked-in functions, not third-party input.
    for filename in ("face.py", "hour.py", "minute.py", "second.py"):
        source = (SOURCES / filename).read_text(encoding="utf-8")
        exec(compile(source, str(SOURCES / filename), "exec"), ns)
    return ns


def edits(face, invoke):
    chars = list(face)
    result = invoke(chars)
    assert result is chars, "Unexpected original hand contract"
    return tuple((i, val) for i, val in enumerate(chars) if val != face[i])


def source_from_original():
    parts = original_parts()
    face = parts["setface"]()
    assert face.count("\n") == 13 and all(len(x) == 22 for x in face.splitlines()), (
        "Original clock face layout changed; review the generated renderer")
    hours = tuple(edits(face, lambda buf, h=h: parts["sethour"](h, buf))
                  for h in range(12))
    minutes = tuple(edits(face, lambda buf, m=m: parts["setminute"](m, buf))
                    for m in range(0, 60, 5))
    stars = []
    for minute_digit in range(10):
        overlay = edits(face, lambda buf, m=minute_digit:
                        parts["setsecond"](0, m, buf))
        assert len(overlay) == 1 and overlay[0][1] == "*", (
            "Original second marker changed; review clock generator")
        stars.append(overlay[0][0])

    # Confirm that the combined overlays match the original functions at
    # every minute of the day, with both second-marker states.
    for hour in range(24):
        for minute in range(60):
            for second in (0, 1):
                expected = list(face)
                parts["sethour"](hour, expected)
                parts["setminute"](minute, expected)
                parts["setsecond"](second, minute % 10, expected)
                got = list(face)
                for where, char in hours[hour % 12]:
                    got[where] = char
                for where, char in minutes[minute // 5]:
                    got[where] = char
                if second == 0:
                    got[stars[minute % 10]] = "*"
                assert got == expected, "Clock parity mismatch at %02d:%02d:%02d" % (
                    hour, minute, second)

    face_literals = "\n".join("    " + repr(line + "\n")
                              for line in face.splitlines())
    hour_literals = "\n".join("    " + repr(h) + "," for h in hours)
    minute_literals = "\n".join("    " + repr(m) + "," for m in minutes)
    header = (
        "# GENERATED from original PythonClock face/hour/minute/second files.\n"
        "# Original sources remain untouched. Single-file optimized DOS version.\n"
        "# Face/hand overlays verified against original at all 1440 minute marks.\n"
        "import os\n"
        "import time\n\n"
        "FACE = (\n" + face_literals + "\n)\n"
        "HOURS = (\n" + hour_literals + "\n)\n"
        "MINUTES = (\n" + minute_literals + "\n)\n"
        "STARS = " + repr(tuple(stars)) + "\n\n"
    )
    engine = '''def paint(buf, coords):
    for pos, symbol in coords:
        buf[pos] = symbol


def render(hour, minute, second):
    # Render one exact original-compatible frame without moving the cursor.
    buf = list(FACE)
    paint(buf, HOURS[hour % 12])
    paint(buf, MINUTES[minute // 5])
    if second % 2 == 0:
        buf[STARS[minute % 10]] = '*'
    return ''.join(buf)


def run(frames=0, pause=1):
    # 0 frames means continuous operation; use run(2, 0) for test mode.
    # Native localtime() avoids creating a datetime object every frame.
    last_hour_minute = None
    hands = ''
    count = 0
    while True:
        current = time.localtime()
        hour = current[3]
        minute = current[4]
        second = current[5]
        hour_minute = hour * 60 + minute
        if hour_minute != last_hour_minute:
            # Build hands only when the minute changes.
            buf = list(FACE)
            paint(buf, HOURS[hour % 12])
            paint(buf, MINUTES[minute // 5])
            hands = ''.join(buf)
            last_hour_minute = hour_minute
        if second % 2 == 0:
            spot = STARS[minute % 10]
            screen = hands[:spot] + '*' + hands[spot + 1:]
        else:
            screen = hands
        print(screen)
        count += 1
        if frames and count >= frames:
            break
        if pause:
            time.sleep(pause)
        # RUNCLK uses --home-cls, leaving the old face on screen until
        # the new face is printed. Ordinary PY86 CLOCK.PY still clears.
        os.system('cls')


if __name__ == '__main__':
    run()
'''
    code = header + engine
    ast.parse(code, filename="CLOCK.PY")
    if len(code.encode("utf-8")) > 24000:
        raise ValueError("CLOCK.PY exceeds the Py86 24KB source limit")
    return code


def generate(output=OUTPUT):
    code = source_from_original()
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(code.encode("ascii"))
    print("Generated optimized CLOCK.PY (%d bytes) from untouched PythonClock sources"
          % len(code))
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    generate(args.output)
