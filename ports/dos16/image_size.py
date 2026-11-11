"""Inspect DOS MZ image size, relocations, and verified DOSBox startup."""
import json
from pathlib import Path
import re
import struct
import sys

def analyze(name, image):
    data = Path(image).read_bytes()
    if len(data) < 28 or data[:2] != b"MZ":
        raise ValueError("Not a DOS MZ image: " + str(image))
    fields = struct.unpack_from("<14H", data)
    header = fields[4] * 16
    if not (28 <= header <= len(data)):
        raise ValueError("Invalid MZ header length")
    result = {"variant": name, "file_bytes": len(data),
              "header_bytes": header, "image_bytes": len(data) - header,
              "relocations": fields[3], "relocation_bytes": fields[3] * 4,
              "min_alloc_paragraphs": fields[5],
              "max_alloc_paragraphs": fields[6]}
    print(json.dumps(result, indent=2))
    return result

def startup(report, record):
    obj = json.loads(Path(report).read_text())
    if obj.get("batch_result") != "PASS" or obj.get("missing") or obj.get("unexpected_errors"):
        raise ValueError("DOSBox test did not pass, cannot accept candidate")
    match = re.search(r"Full child launch: (\d+) ms", obj.get("feature_demo_log", ""))
    if match is None:
        raise ValueError("Missing native DOS launch timing")
    info = json.loads(Path(record).read_text())
    info["launch_ms_dosbox"] = int(match.group(1))
    info["verified_dosbox"] = True
    Path(record).write_text(json.dumps(info, indent=2))
    print(json.dumps(info, indent=2))

def summary(folder):
    variants = []
    for file in sorted(Path(folder).glob("*.json")):
        if file.stem.endswith("-test") or file.stem == "summary":
            continue
        obj = json.loads(file.read_text())
        if "file_bytes" in obj:
            variants.append(obj)
    reference = next((x for x in variants if x["variant"] == "speed"), None)
    for x in variants:
        if reference:
            delta = reference["file_bytes"] - x["file_bytes"]
            x["bytes_saved"] = delta
            x["percent_smaller"] = round(delta * 100 / reference["file_bytes"], 2)
        print(json.dumps(x, indent=2))
    (Path(folder) / "summary.json").write_text(json.dumps(variants, indent=2))

if __name__ == "__main__":
    command = sys.argv[1]
    if command == "summary":
        summary(sys.argv[2])
    elif command == "startup":
        startup(sys.argv[2], sys.argv[3])
    else:
        Path(sys.argv[3]).write_text(json.dumps(analyze(command, sys.argv[2]), indent=2))
