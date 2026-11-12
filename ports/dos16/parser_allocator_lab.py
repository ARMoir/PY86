"""Install an opt-in parser-node arena into a SEPARATE patched MicroPython checkout.

Usage:
    python parser_allocator_lab.py patch-source /tmp/pinned-micropython

The default interpreter keeps MicroPython v1.24.1's original parser allocator.
Only builds with -dPY86_PARSER_ALLOC_MODE=1..4 select the alternate allocator.

1 = fixed 512-byte parse-node blocks
2 = fixed 1024-byte parse-node blocks
3 = fixed 2048-byte parse-node blocks
4 = geometric in-place chunk growth, 256-byte initial blocks

All modes preserve the lifetime and layout of MicroPython parse-tree nodes.
No grammar or bytecode format is changed.
"""
import argparse
from pathlib import Path

MARKER = "PY86_PARSER_ALLOC_MODE"
START = "static void *parser_alloc(parser_t *parser, size_t num_bytes) {"
END = "\n#if MICROPY_COMP_CONST_TUPLE\nstatic void parser_free_parse_node_struct("

# The geometric variant retains MicroPython's allow_move=false behavior.
# Moving an existing parse chunk would invalidate AST node pointers.
ALTERNATE_ALLOCATOR = r"""
#if defined(PY86_PARSER_ALLOC_MODE) && (PY86_PARSER_ALLOC_MODE != 0)
static void *parser_alloc(parser_t *parser, size_t num_bytes) {
    mp_parse_chunk_t *chunk = parser->cur_chunk;
    size_t capacity;

    #if PY86_PARSER_ALLOC_MODE == 1
    capacity = 512;
    #elif PY86_PARSER_ALLOC_MODE == 2
    capacity = 1024;
    #elif PY86_PARSER_ALLOC_MODE == 3
    capacity = 2048;
    #elif PY86_PARSER_ALLOC_MODE == 4
    capacity = 256;
    #else
    #error Unrecognized PY86_PARSER_ALLOC_MODE
    #endif

    if (chunk != NULL && num_bytes > chunk->alloc - chunk->union_.used) {
        #if PY86_PARSER_ALLOC_MODE == 4
        /* Grow in place by roughly 50% instead of rechecking the GC
         * allocation map for every individual syntax-tree node. */
        size_t wanted = chunk->union_.used + num_bytes;
        size_t extra = chunk->alloc / 2;
        size_t grown;
        mp_parse_chunk_t *new_data;
        if (extra < 128) {
            extra = 128;
        }
        grown = chunk->alloc + extra;
        if (grown < wanted) {
            grown = wanted;
        }
        if (grown <= 4096) {
            new_data = (mp_parse_chunk_t *)m_renew_maybe(byte, chunk,
                sizeof(mp_parse_chunk_t) + chunk->alloc,
                sizeof(mp_parse_chunk_t) + grown, false);
            if (new_data != NULL) {
                chunk = new_data;
                chunk->alloc = grown;
                parser->cur_chunk = chunk;
            }
        }
        #endif
        if (num_bytes > chunk->alloc - chunk->union_.used) {
            /* Completed chunks are linked into the parse tree exactly as
             * in upstream MicroPython. The old block is never moved. */
            chunk->union_.next = parser->tree.chunk;
            parser->tree.chunk = chunk;
            chunk = NULL;
        }
    }

    if (chunk == NULL) {
        if (capacity < num_bytes) {
            capacity = num_bytes;
        }
        chunk = (mp_parse_chunk_t *)m_new(byte, sizeof(mp_parse_chunk_t) + capacity);
        chunk->alloc = capacity;
        chunk->union_.used = 0;
        parser->cur_chunk = chunk;
    }

    byte *ret = chunk->data + chunk->union_.used;
    chunk->union_.used += num_bytes;
    return ret;
}
#else
"""

def patch_source(root: Path) -> None:
    path = root / "py" / "parse.c"
    if not path.exists():
        raise SystemExit("Expected patched MicroPython v1.24.1 py/parse.c")
    before = path.read_text()
    if MARKER in before:
        if "#else\n" + START in before and "#endif\n" + END in before:
            print("Parser allocator already instrumented in isolated source")
            return
        raise SystemExit("Partial parser allocator patch; refusing to proceed")
    if before.count(START) != 1 or before.count(END) != 1:
        raise SystemExit("Unexpected MicroPython v1.24.1 parser allocation function")
    pos = before.index(START)
    end = before.index(END, pos)
    if end < pos:
        raise SystemExit("Cannot locate parser allocator boundary")
    original = before[pos:end]
    if "m_renew_maybe" not in original or "parser->cur_chunk" not in original:
        raise SystemExit("Unexpected upstream parser allocator; review necessary")
    after = (before[:pos] + ALTERNATE_ALLOCATOR.lstrip("\n") + original
             + "#endif\n" + before[end:])
    path.write_text(after)
    print("Opt-in parser allocator installed in isolated MicroPython checkout")

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("patch-source",))
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    patch_source(args.source.resolve())

if __name__ == "__main__":
    main()
