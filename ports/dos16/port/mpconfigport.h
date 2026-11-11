#include <stdint.h>
#include <stdlib.h>
#include <time.h>
/* Native standard-library modules, built into PY86.EXE for fast DOS execution. */
/* Host-provided CPython-style exit()/quit() builtins.
 * py86_builtin_exit_obj is declared to modbuiltins.c by compat-exit patch. */
#define MICROPY_PORT_BUILTINS \
    { MP_ROM_QSTR(MP_QSTR_exit), MP_ROM_PTR(&py86_builtin_exit_obj) }, \
    { MP_ROM_QSTR(MP_QSTR_quit), MP_ROM_PTR(&py86_builtin_exit_obj) },
#define MICROPY_PY_JSON (1)
#define MICROPY_PY_ERRNO (1)
#define MICROPY_PY_RE (1)
#define MICROPY_PY_RE_MATCH_GROUPS (1)
#define MICROPY_PY_RE_MATCH_SPAN_START_END (1)
#define MICROPY_PY_RE_SUB (1)
#define MICROPY_PY_HASHLIB (1)
#define MICROPY_PY_HASHLIB_SHA256 (1)
#define MICROPY_PY_HASHLIB_MD5 (0)
#define MICROPY_PY_HASHLIB_SHA1 (0)
/* DOSBox A/B comparison: map cache gave faster dict/globals/instance lookups
 * at +320 EXE bytes and unchanged 48KB GC heap. Keep attr fast path off. */
#ifndef MICROPY_OPT_MAP_LOOKUP_CACHE
#define MICROPY_OPT_MAP_LOOKUP_CACHE (1)
#endif
#ifndef MICROPY_OPT_LOAD_ATTR_FAST_PATH
#define MICROPY_OPT_LOAD_ATTR_FAST_PATH (0)
#endif
#define MICROPY_PY_RANDOM (1)
#define MICROPY_PY_RANDOM_EXTRA_FUNCS (1)
#define MICROPY_MODULE_BUILTIN_INIT (1)
#define MICROPY_PY_MATH_CONSTANTS (0) /* Watcom C16 NAN/INFINITY are not compile-time constants */
#define MICROPY_PY_MATH_ISCLOSE (1)
#define MICROPY_PY_MATH_FACTORIAL (1)
#define MICROPY_PY_RANDOM_SEED_INIT_FUNC ((unsigned long)time(NULL))
#include <limits.h>
#define MICROPY_CONFIG_ROM_LEVEL (MICROPY_CONFIG_ROM_LEVEL_CORE_FEATURES)
#define MICROPY_OBJ_REPR (MICROPY_OBJ_REPR_B)
#define MICROPY_ENABLE_COMPILER (1)
#define MICROPY_ENABLE_GC (1)
#define MICROPY_GC_STACK_ENTRY_TYPE unsigned short
#define MICROPY_NLR_SETJMP (1)
#define MICROPY_NO_ALLOCA (1)
#define MICROPY_HELPER_REPL (1)
#define MICROPY_ENABLE_EXTERNAL_IMPORT (1)
#define MICROPY_READER_POSIX (0)
#define MICROPY_READER_VFS (0)
#define MICROPY_ENABLE_SOURCE_LINE (1)
#define MICROPY_ERROR_REPORTING (MICROPY_ERROR_REPORTING_NORMAL)
#define MICROPY_ROM_TEXT_COMPRESSION (0)
#define MICROPY_LONGINT_IMPL (MICROPY_LONGINT_IMPL_MPZ)
#define MPZ_DIG_SIZE (8)
#define MICROPY_FLOAT_IMPL (MICROPY_FLOAT_IMPL_DOUBLE)
#define MICROPY_PY_BUILTINS_COMPLEX (1)
#define MICROPY_PY_BUILTINS_STR_UNICODE (1)
#define MICROPY_PY_BUILTINS_INPUT (1)
#define MICROPY_PY_BUILTINS_HELP (1)
#define MICROPY_PY_BUILTINS_HELP_TEXT py86_help_text
#define MICROPY_PY_BUILTINS_HELP_MODULES (0)
#define MICROPY_KBD_EXCEPTION (1)
#define MICROPY_VM_HOOK_LOOP py86_vm_hook_loop();
void py86_vm_hook_loop(void);
#define MICROPY_PY_SYS (1)
#define MICROPY_PY_SYS_PATH (1)
#define MICROPY_PY_SYS_ARGV (1)
#define MICROPY_PY_SYS_EXIT (1)
#define MICROPY_PY_GC (1)
#define MICROPY_PY_IO (0)
#define MICROPY_CPYTHON_COMPAT (1)
#define MICROPY_PY___FILE__ (1)
#define MICROPY_PY_MATH (1)
#define MICROPY_ALLOC_PATH_MAX (128)
#define MICROPY_ALLOC_PARSE_CHUNK_INIT (16)
#define MICROPY_STACK_CHECK (1)
#define MICROPY_USE_INTERNAL_ERRNO (1)
#define MICROPY_QSTR_BYTES_IN_HASH (1)
#define MICROPY_QSTR_BYTES_IN_LEN (1)
#define MP_ENDIANNESS_LITTLE (1)
#define MP_SSIZE_MAX (32767)
#define UINT_FMT "%lu"
#define INT_FMT "%ld"
typedef long mp_int_t;
typedef unsigned long mp_uint_t;
typedef long mp_off_t;
#define NORETURN __declspec(noreturn)
#define MP_WEAK
#define MP_NOINLINE
#define MP_ALWAYSINLINE
#define MP_LIKELY(x) (x)
#define MP_UNLIKELY(x) (x)
#define MICROPY_HW_BOARD_NAME "Py86 16-bit DOS"
#define MICROPY_HW_MCU_NAME "8086/V20"
#define MICROPY_MPHALPORT_H "mphalport.h"
#define MP_STATE_PORT MP_STATE_VM
