"""Apply the hardware-qualified Py86 1.29.0 data-aware garbage collector.

Inspired by raspy135's GC_ALLOC_FLAG_IS_DATA/scan-skipping work. Unlike the
full fork, the production data-aware collector retains the production 2-bit allocation table and
uses a *bounded 512-byte side bitmap* for non-pointer allocation heads. No
write barriers or incremental marking are enabled here. Production default after physical Tandy 1000 EX A/B.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PORT = ROOT / "ports" / "dos16"
FILES = ("py/gc.c", "py/gc.h", "py/malloc.c", "py/misc.h",
         "py/vstr.c", "py/objstr.c", "py/objarray.c")


def replace(text, before, after, name):
    matches = text.count(before)
    if matches != 1:
        raise RuntimeError("Expected exactly one " + name + " anchor, found " + str(matches))
    return text.replace(before, after, 1)


def patch_gc(s):
    location = "// Static functions for individual steps of the GC mark/sweep sequence"
    helper = r"""
// Py86 data-aware GC. 512 bytes cover up to 4096 GC blocks.
// If a heap is too big, scanning safely falls back to conservative mode.
// Each bit belongs to a HEAD allocation, and new heads always overwrite it.
// Dead heads do not need eager clearing: the ATB guards all accesses.
#define PY86_GC_DATA_MAP_BYTES (512)
static uint8_t py86_gc_data_bits[PY86_GC_DATA_MAP_BYTES];
static size_t py86_gc_data_blocks;

static bool py86_gc_data_test(size_t block) {
    return block < py86_gc_data_blocks
        && (py86_gc_data_bits[block >> 3] & (1 << (block & 7))) != 0;
}

static void py86_gc_data_set(size_t block, bool data) {
    if (block < py86_gc_data_blocks) {
        uint8_t *slot = &py86_gc_data_bits[block >> 3];
        uint8_t mask = (uint8_t)(1 << (block & 7));
        if (data) {
            *slot |= mask;
        } else {
            *slot &= (uint8_t)~mask;
        }
    }
}

"""
    s = replace(s, location, helper + location, "data GC bitmap")
    s = replace(s,
                "    gc_setup_area(&MP_STATE_MEM(area), start, end);",
                """    gc_setup_area(&MP_STATE_MEM(area), start, end);
    // The side bitmap never consumes GC heap blocks. Disable tagging above
    // its capacity instead of indexing beyond the static near-data array.
    py86_gc_data_blocks = MP_STATE_MEM(area).gc_alloc_table_byte_len * BLOCKS_PER_ATB;
    if (py86_gc_data_blocks > PY86_GC_DATA_MAP_BYTES * 8) {
        py86_gc_data_blocks = 0;
    }
    memset(py86_gc_data_bits, 0, sizeof(py86_gc_data_bits));""", "gc_init")
    s = replace(s,
                "        // work out number of consecutive blocks in the chain starting with this one",
                """        // Raw byte buffers cannot contain live mp_obj_t pointers.
        // Keep the HEAD marked but do not conservatively scan its bytes.
        if (!py86_gc_data_test(block)) {
        // work out number of consecutive blocks in the chain starting with this one""",
                "mark subtree start")
    s = replace(s,
                "        // Are there any blocks on the stack?",
                """        }

        // Are there any blocks on the stack?""", "mark subtree end")
    s = replace(s, "    ATB_FREE_TO_HEAD(area, start_block);",
                """    ATB_FREE_TO_HEAD(area, start_block);
    py86_gc_data_set(start_block, (alloc_flags & GC_ALLOC_FLAG_IS_DATA) != 0);""",
                "allocation head")
    s = replace(s, "    size_t block = BLOCK_FROM_PTR(area, ptr);\n    assert(ATB_GET_KIND(area, block) == AT_HEAD);\n\n    // compute number of new blocks",
                """    size_t block = BLOCK_FROM_PTR(area, ptr);
    assert(ATB_GET_KIND(area, block) == AT_HEAD);
    bool py86_realloc_is_data = py86_gc_data_test(block);

    // compute number of new blocks""", "realloc original type")
    s = replace(s,
                "    void *ptr_out = gc_alloc(n_bytes, ftb_state);",
                """    void *ptr_out = gc_alloc(n_bytes,
        (ftb_state ? GC_ALLOC_FLAG_HAS_FINALISER : 0)
        | (py86_realloc_is_data ? GC_ALLOC_FLAG_IS_DATA : 0));""",
                "moved realloc preserves data flag")
    return s


def patch_header(s):
    return replace(s, "    GC_ALLOC_FLAG_HAS_FINALISER = 1,",
                   "    GC_ALLOC_FLAG_HAS_FINALISER = 1,\n    GC_ALLOC_FLAG_IS_DATA = 2,",
                   "new GC allocation flag")


def patch_malloc(s):
    anchor = "void *m_malloc(size_t num_bytes) {"
    func = r"""// Raw buffers: matches the fork's data-only allocation intent, but keeps
// memory accounting identical to m_malloc in the production DOS16 build.
void *m_malloc_data(size_t num_bytes) {
    #if MICROPY_ENABLE_GC
    void *ptr = gc_alloc(num_bytes, GC_ALLOC_FLAG_IS_DATA);
    #else
    void *ptr = malloc(num_bytes);
    #endif
    if (ptr == NULL && num_bytes != 0) {
        m_malloc_fail(num_bytes);
    }
    #if MICROPY_MEM_STATS
    MP_STATE_MEM(total_bytes_allocated) += num_bytes;
    MP_STATE_MEM(current_bytes_allocated) += num_bytes;
    UPDATE_PEAK();
    #endif
    return ptr;
}

"""
    return replace(s, anchor, func + anchor, "raw malloc helper")


def patch_misc(s):
    anchor = "#define m_new(type, num) ((type *)(m_malloc(sizeof(type) * (num))))"
    return replace(s, anchor, anchor + """
// Only use for buffers that cannot contain Python object references.
#define m_new_data(type, num) ((type *)(m_malloc_data(sizeof(type) * (num))))
void *m_malloc_data(size_t num_bytes);""", "raw data macro")


def patch_objarray(s):
    return replace(s, "    o->items = m_new(byte, typecode_size * o->len);",
                   """    // Object arrays can hold pointers; ONLY bytearray uses raw-data tagging.
    o->items = (typecode == BYTEARRAY_TYPECODE)
        ? m_new_data(byte, typecode_size * o->len)
        : m_new(byte, typecode_size * o->len);""", "bytearray raw buffer")


def patch_objstr(s):
    return replace(s, "    byte *p = m_new(byte, len + 1);",
                   "    byte *p = m_new_data(byte, len + 1);",
                   "string raw buffer")


def patch_vstr(s):
    return replace(s, "    vstr->buf = m_new(char, vstr->alloc);",
                   "    vstr->buf = m_new_data(char, vstr->alloc);",
                   "vstr raw buffer")


PATCHES = {
    "py/gc.c": patch_gc, "py/gc.h": patch_header,
    "py/malloc.c": patch_malloc, "py/misc.h": patch_misc,
    "py/vstr.c": patch_vstr, "py/objstr.c": patch_objstr,
    "py/objarray.c": patch_objarray,
}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=True)
    a = p.parse_args()
    source = a.source.resolve()
    # The patch was qualified against the exact pinned MicroPython core.
    import subprocess
    upstream_sha = subprocess.check_output(
        ["git", "-C", str(source), "rev-parse", "HEAD"], text=True
    ).strip()
    if upstream_sha != "0fd6c573ea815774668bbb16b8e197c8822368b2":
        raise RuntimeError("Refusing data-aware GC patch for unexpected core: " + upstream_sha)
    originals = {name: (source / name).read_text()
                 for name in FILES}
    patched = {name: PATCHES[name](originals[name]) for name in FILES}
    for name in FILES:
        if patched[name] == originals[name]:
            raise RuntimeError("No modifications to " + name)
    for name in FILES:
        (source / name).write_text(patched[name])
    report = {
        "collector": "production data-aware GC (NOT incremental GC)",
        "upstream_idea": "raspy135/micropython gc-incremental",
        "implementation": "2-bit ATB unchanged; 512-byte bounded head bitmap",
        "qualification": "DOSBox regression 24/32/48KB and physical Tandy 1000 EX 48KB A/B",
        "files": {n: hashlib.sha256(patched[n].encode()).hexdigest()
                  for n in FILES},
        "data_buffers": ["vstr", "mp_obj_str bytes", "bytearray"],
        "cautions": [
            "Pointer-containing arrays remain conservatively scanned",
            "Realloc preserves the head's data flag when moved",
            "No incremental mark/sweep or GC_WB enabled",
            "A passing emulator run does not certify physical Tandy hardware",
        ],
    }
    out = source / "py86-data-gc.json"
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
