"""Apply the archived Watcom adaptations to a *separate* v1.24.1 checkout."""
import argparse
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
PINNED_SHA = "ecfdd5d6f9be971852003c2049600dc7b3e2a838"


def git(*args, cwd=None):
    return subprocess.run(["git", *map(str, args)], cwd=cwd, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True,
                        help="Separate MicroPython v1.24.1 checkout to patch")
    args = parser.parse_args()
    source = args.source.resolve()
    if not (source / "py" / "py.mk").is_file() or not (source / ".git").exists():
        parser.error("--source must point at a MicroPython Git checkout")
    sha = git("rev-parse", "HEAD", cwd=source)
    if sha.returncode or sha.stdout.strip() != PINNED_SHA:
        parser.error("source HEAD must be pinned to v1.24.1 / " + PINNED_SHA)
    # Reproducible, idempotent core and optional-module 16-bit adaptations.
    for patch_name in ("compat-v1.24.1.patch", "compat-extra-libs-v1.24.1.patch",
                       "compat-strcache-v1.24.1.patch", "compat-lazyhash-v1.24.1.patch"):
        patch = HERE / patch_name
        if not patch.is_file():
            parser.error("missing " + str(patch))
        if git("apply", "--reverse", "--check", patch, cwd=source).returncode == 0:
            print("Already applied: " + patch_name)
            continue
        check = git("apply", "--check", patch, cwd=source)
        if check.returncode:
            sys.stderr.write(check.stderr)
            parser.error("patch does not apply cleanly: " + patch_name)
        apply = git("apply", patch, cwd=source)
        if apply.returncode:
            sys.stderr.write(apply.stderr)
            return apply.returncode
        print("Applied " + patch_name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
