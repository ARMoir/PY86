"""Enable completion of Python builtins in the pinned MicroPython 1.29 REPL.

Upstream mp_repl_autocomplete() already implements variable, attribute and
module completion.  Its test_qstr() checks __main__ attributes but does not
fall back to the builtin globals map, unlike normal Python name lookup.
This source patch enables that fallback only for Py86, with no new cache
or memory allocation.  Runs against an isolated pinned upstream checkout.
"""
from pathlib import Path
import argparse
import subprocess

SHA = "0fd6c573ea815774668bbb16b8e197c8822368b2"
OLD = """        mp_load_method_protected(obj, name, dest, true);
        return dest[0] != MP_OBJ_NULL;"""
NEW = """        mp_load_method_protected(obj, name, dest, true);
        #if defined(PY86_DOS_COMPLETE_BUILTINS)
        if (dest[0] == MP_OBJ_NULL && obj == MP_OBJ_FROM_PTR(&mp_module___main__)) {
            // Match Python's main-module -> builtins name resolution for Tab.
            if (MP_STATE_VM(mp_module_builtins_override_dict) != NULL
                && mp_map_lookup(
                    &MP_STATE_VM(mp_module_builtins_override_dict)->map,
                    MP_OBJ_NEW_QSTR(name), MP_MAP_LOOKUP) != NULL) {
                return true;
            }
            if (mp_map_lookup((mp_map_t *)&mp_module_builtins_globals.map,
                MP_OBJ_NEW_QSTR(name), MP_MAP_LOOKUP) != NULL) {
                return true;
            }
        }
        #endif
        return dest[0] != MP_OBJ_NULL;"""

def main():
    a = argparse.ArgumentParser()
    a.add_argument("--source", type=Path, required=True)
    args = a.parse_args()
    root = args.source.resolve()
    sha = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"],
                                  text=True).strip()
    if sha != SHA:
        raise SystemExit("Unexpected MicroPython checkout: " + sha)
    f = root / "py/repl.c"
    code = f.read_text()
    if code.count(OLD) != 1 or "PY86_DOS_COMPLETE_BUILTINS" in code:
        raise SystemExit("Upstream REPL source drift or already patched")
    f.write_text(code.replace(OLD, NEW, 1))
    print("PASS: mp_repl_autocomplete now includes builtin globals in Py86")

if __name__ == "__main__":
    main()
