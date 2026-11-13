"""Resolve only the known DOS16 three-way GC conflicts, then opt in safely.

The source merge must already have been produced by incremental_gc_lab.py.
Nothing here touches the master branch. The patch remains EXPERIMENTAL.
"""
import argparse
import json
import subprocess
from pathlib import Path

PORT = Path(__file__).resolve().parent
EVIDENCE = PORT / "build" / "incremental-gc"


def once(s, old, new, name):
    n = s.count(old)
    if n != 1:
        raise RuntimeError("Cannot resolve " + name + ": found " + str(n))
    return s.replace(old, new, 1)


def check_clean(s, name):
    if "<<<<<<< " in s or ">>>>>>> " in s or "\n=======\n" in s:
        raise RuntimeError("Unresolved conflict in " + name)


def resolve(source):
    conflict_file = EVIDENCE / "threeway-conflicts.json"
    info = json.loads(conflict_file.read_text())
    if info["automatic_merge"]:
        raise RuntimeError("Source already merged; manual validation required")
    names = info["unmerged_paths"]
    if names != ["py/gc.c", "py/objset.c"]:
        raise RuntimeError("Unexpected three-way conflicts: " + str(names))
    gcpath = source / "py" / "gc.c"
    setpath = source / "py" / "objset.c"
    gc = gcpath.read_text()
    sets = setpath.read_text()

    # Preserve the original DOS16 overlapping far-pointer scan: pointers are
    # 4 bytes, but valid C stack and object fields may be two-byte aligned.
    gc = once(gc, """<<<<<<< ours
        for (size_t i = (n_blocks * BYTES_PER_BLOCK - sizeof(void *)) / 2 + 1; i > 0; i--, ptrs = (void **)((char *)ptrs + 2)) {
=======
        for (size_t i = n_blocks * (BYTES_PER_BLOCK / sizeof(void *)); i > 0; i--, ptrs++) {
>>>>>>> theirs""", """        for (size_t i = (n_blocks * BYTES_PER_BLOCK - sizeof(void *)) / 2 + 1; i > 0; i--, ptrs = (void **)((char *)ptrs + 2)) {""", "gc.c far-pointer scan")

    sets = once(sets, """<<<<<<< ours
    if (update) {
        m_del(mp_obj_t, self->set.table, self->set.alloc);
        self->set.alloc = out->set.alloc;
        self->set.used = out->set.used;
        self->set.table = out->set.table;
=======
    for (size_t i = start; i < n_args; i++) {
        if (MP_OBJ_FROM_PTR(in_ptr) != args[i]) {
            mp_obj_set_t *out_ptr = set_intersect_one(&in_ptr->set, args[i]);
            m_del(mp_obj_t, in_ptr->set.table, in_ptr->set.alloc);
            in_ptr->set.alloc = out_ptr->set.alloc;
            in_ptr->set.used = out_ptr->set.used;
            GC_WB_PTR(out_ptr->set.table); // table buffer moved into a live set
            in_ptr->set.table = out_ptr->set.table;
        }
>>>>>>> theirs""", """    if (update) {
        m_del(mp_obj_t, self->set.table, self->set.alloc);
        self->set.alloc = out->set.alloc;
        self->set.used = out->set.used;
        GC_WB_PTR(out->set.table); // new table pointer installed on live set
        self->set.table = out->set.table;""", "objset.c mutator")
    check_clean(gc, "gc.c")
    check_clean(sets, "objset.c")

    # The fork doubled ATB metadata (4-bit allocation entries), while the
    # DOS 1.29 baseline still computes the allocation-table width for 2-bit.
    # Correct the non-finaliser case before attempting any runtime tests.
    gc = once(gc,
              "(total_byte_len - ALLOC_TABLE_GAP_BYTE) / (1 + MP_BITS_PER_BYTE / 2 * BYTES_PER_BLOCK)",
              "(total_byte_len - ALLOC_TABLE_GAP_BYTE) / (1 + BLOCKS_PER_ATB * BYTES_PER_BLOCK)",
              "4-bit heap ATB sizing")

    # The 1.29 DOS root helper must respect gc_inc_mark_only while the tri-
    # colour mark is in progress. Reuse the core's barrier-aware root scanner
    # on every two-byte-aligned candidate; never recurse from a gray root.
    start = gc.index("void py86_gc_collect_root_words(void *start, size_t bytes) {")
    end = gc.index("\n// Take the given block as the topmost", start)
    gc = gc[:start] + """void py86_gc_collect_root_words(void *start, size_t bytes) {
    byte *p = (byte *)start;
    for (; bytes >= sizeof(void *); bytes -= 2, p += 2) {
        gc_collect_root((void **)p, 1);
    }
}
""" + gc[end:]

    # Incremental gray scanning must also examine overlapping 4-byte far
    # pointer windows at 2-byte stride, not just 4-byte aligned fields.
    gc = once(gc,
              "    size_t n_words = n_blocks * WORDS_PER_BLOCK;",
              "    size_t n_words = (n_blocks * BYTES_PER_BLOCK - sizeof(void *)) / 2 + 1;",
              "incremental scan window count")
    gc = once(gc,
              "    for (size_t i = 0; i < n_words; i++, ptrs++) {",
              "    for (size_t i = 0; i < n_words; i++, ptrs = (void **)((byte *)ptrs + 2)) {",
              "incremental scan 2-byte stride")

    # In the fork the clock helpers exist only if port provides a us timer,
    # but gc_inc_step_inner refers to gc_inc_now_us unconditionally.  DOS16
    # initially uses fixed word budgets and avoids a costly BIOS clock read.
    gc = once(gc,
              "#else\nstatic inline bool gc_inc_due(void) {\n    return true;\n}",
              "#else\nstatic inline uint32_t gc_inc_now_us(void) { return 0; }\nstatic inline bool gc_inc_due(void) {\n    return true;\n}",
              "no-high-resolution-timer fallback")

    gcpath.write_text(gc)
    setpath.write_text(sets)
    staged = subprocess.run(["git", "-C", str(source), "add", "py/gc.c",
                             "py/objset.c"], capture_output=True, text=True)
    if staged.returncode:
        raise RuntimeError(staged.stderr)
    unresolved = subprocess.check_output(["git", "-C", str(source),
                                           "ls-files", "--unmerged"], text=True)
    if unresolved.strip():
        raise RuntimeError("Rebase still unresolved: " + unresolved)
    report = {
        "fork_core_threeway_resolved": True,
        "merged_conflicts": names,
        "dos_changes": [
            "preserve overlapping far-pointer stack and object scanning",
            "preserve original set intersection and add write barrier",
            "correct 4-bit ATB heap sizing",
            "mark-only-aware 2-byte conservative GC roots",
            "incremental gray scan 2-byte pointer windows",
            "timer-free allocation-budget stepping",
        ],
        "collector_enabled": False,
        "status": "core source resolved; compilation and pointer-write audit required",
    }
    (EVIDENCE / "rebase-resolution.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


def enable(source):
    gc = source / "py" / "gc.c"
    if "gc_inc_scan_chain(" not in gc.read_text():
        raise RuntimeError("Fork incremental GC implementation missing")
    config_file = PORT / "port" / "mpconfigport.h"
    config = config_file.read_text()
    if "MICROPY_GC_INCREMENTAL" in config:
        raise RuntimeError("Already enabled or unexpected config")
    config = """/* GC experiment only: run bounded slices on allocations.
 * There is no microsecond DOS clock; the fork uses word budgets instead. */
#define MICROPY_GC_INCREMENTAL (1)
#define MICROPY_ALLOC_GC_STACK_SIZE (128)
#define MICROPY_GC_INCR_TRIGGER_BLOCKS (192)
#define MICROPY_GC_INCR_SLICE_WORDS (48)
#define MICROPY_GC_INCR_SWEEP_SLICE_BLOCKS (96)
#define MICROPY_GC_USTIME_AVAILABLE (0)
void py86_gc_port_stack_roots(void);
#define MICROPY_GC_PORT_STACK_ROOTS() py86_gc_port_stack_roots()
""" + config
    config_file.write_text(config)

    main_file = PORT / "port" / "main.c"
    main = main_file.read_text()
    anchor = "void gc_collect(void) {"
    hook = """/* On incremental collection, expose C stack/register roots without
 * forcing an ordinary full gc.collect(). The mark-only core root scanner
 * handles 2-byte-aligned 4-byte far pointer windows. */
extern void py86_gc_collect_root_words(void *start, size_t bytes);
void py86_gc_port_stack_roots(void) {
    jmp_buf regs;
    char *p;
    setjmp(regs);
    p = (char *)&regs;
    if (p < stack_top) {
        py86_gc_collect_root_words(p, (size_t)(stack_top - p));
    }
}

"""
    main = once(main, anchor, hook + anchor, "DOS stack-root collector")
    main = once(main,
                "    gc_collect_start();",
                """    // Do not interleave the explicit collector with an unfinished cycle.
    if (gc_incremental_active()) {
        gc_incremental_complete();
    }
    gc_collect_start();""", "completion before explicit collection")
    main_file.write_text(main)
    report = {
        "full_incremental_experimental": True,
        "slice_words": 48,
        "sweep_blocks": 96,
        "mark_stack_entries": 128,
        "heap_gc_threshold_blocks": 192,
        "microsecond_timer": False,
        "warnings": [
            "No bounded wall-clock guarantee on 7 MHz V20",
            "C write-barrier coverage still requires native audit",
            "Physical hardware testing is prohibited until DOSBox stress passes",
        ],
    }
    (EVIDENCE / "incremental-config.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--mode", choices=("resolve", "enable"), required=True)
    a = parser.parse_args()
    source = a.source.resolve()
    if a.mode == "resolve":
        resolve(source)
    else:
        enable(source)


if __name__ == "__main__":
    main()
