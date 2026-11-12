/* Py86 DOS host, MIT license. Experimental MicroPython port. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <setjmp.h>
#include <sys/stat.h>
#include <signal.h>
#include <dos.h>
#include <bios.h>
#include <i86.h>
#include <io.h>
#include "py/compile.h"
#include "py/runtime.h"
#include "py/repl.h"
#include "py/gc.h"
#include "py/stackctrl.h"
#include "py/mperrno.h"
#include "py/objlist.h"
#include "py/builtin.h"
#include "py86-version.h"
#if defined(PY86_UPSTREAM_129)
#define PY86_MP_VERSION "1.29.0"
#else
#define PY86_MP_VERSION "1.24.1"
#endif

/* From moddostime.c: opt-in cursor-home behavior for interactive redraws. */
extern void py86_set_home_cls(int enabled);
extern void py86_startup_begin(void);
extern void py86_startup_initialized(void);

static char *stack_top;
static void *heap;
static int py86_exit_requested;

/* Opt-in profiling uses BIOS ticks, keeping the normal build unchanged.
 * No output is emitted until a script has finished executing. */
#if defined(PY86_COMPILE_PROFILE)
static int py86_profile_enabled;
static unsigned long py86_profile_read_ms;
#if defined(PY86_RUNTIME_PROFILE)
static unsigned long py86_gc_runtime_ms;
static unsigned py86_gc_runtime_calls;
#endif
static unsigned long py86_profile_ticks(void) {
    union REGS in_regs, out_regs;
    memset(&in_regs, 0, sizeof(in_regs));
    in_regs.h.ah = 0;
    int86(0x1a, &in_regs, &out_regs);
    return ((unsigned long)out_regs.x.cx << 16) | out_regs.x.dx;
}
static unsigned long py86_profile_elapsed(unsigned long from, unsigned long to) {
    unsigned long ticks = to >= from ? to - from : 1573040UL - from + to;
    return ticks * 55UL - ticks * 75UL / 1000UL;
}
#endif

/* Single-segment GC heap selection.  Open Watcom -ml malloc() uses its
 * far heap, but ordinary far pointers cannot wrap their 16-bit offsets.
 * The larger multi-segment case needs a separate split-GC project.
 *
 * Auto tries from 60,000 down to 24,000 bytes.  Verify that each candidate
 * fits before offset 0xfff0 and that a separate 32 KiB native malloc still
 * succeeds (e.g. when reading/parsing Python source or DOS files).
 *
 * PY86_HEAP=48000 requests one exact heap size and errors if unavailable.
 * PY86_HEAP_MAX=32000 caps automatic selection for small machines/tests.
 */
#define PY86_HEAP_MIN 24000U
#define PY86_HEAP_MAX 60000U
#define PY86_HEAP_STEP 4000U
#define PY86_NATIVE_HEADROOM 32768U
static unsigned py86_heap_bytes;
static int py86_heap_fixed;

static int py86_heap_parse(const char *s, unsigned *value) {
    char *end;
    unsigned long n;
    if (s == NULL || s[0] == '\0') return 0;
    n = strtoul(s, &end, 10);
    if (*end != '\0' || end == s ||
        n < PY86_HEAP_MIN || n > PY86_HEAP_MAX ||
        ((unsigned)n & 15U) != 0) {
        return -1;
    }
    *value = (unsigned)n;
    return 1;
}

static int py86_heap_try(unsigned bytes) {
    void *p;
    void *reserve;
    /* One contiguous object and one 16-bit far-pointer address space. */
    p = malloc(bytes);
    if (p == NULL) return 0;
    if ((unsigned long)FP_OFF(p) + (unsigned long)bytes > 65520UL) {
        free(p);
        return 0;
    }
    reserve = malloc(PY86_NATIVE_HEADROOM);
    if (reserve == NULL) {
        free(p);
        return 0;
    }
    free(reserve);
    heap = p;
    py86_heap_bytes = bytes;
    return 1;
}

static int py86_heap_allocate(void) {
    const char *setting = getenv("PY86_HEAP");
    const char *cap_setting = getenv("PY86_HEAP_MAX");
    unsigned requested = 0;
    unsigned ceiling = PY86_HEAP_MAX;
    unsigned candidate;
    int parse;

    parse = py86_heap_parse(cap_setting, &ceiling);
    if (parse < 0) {
        fputs("PY86_HEAP_MAX requires 24000..60000 bytes, multiple of 16\n", stderr);
        return 0;
    }
    if (setting && setting[0] && strcmp(setting, "auto") != 0) {
        parse = py86_heap_parse(setting, &requested);
        if (parse != 1) {
            fputs("PY86_HEAP requires auto or 24000..60000 bytes, multiple of 16\n", stderr);
            return 0;
        }
        py86_heap_fixed = 1;
        if (py86_heap_try(requested)) return 1;
        fprintf(stderr, "Cannot allocate %u-byte Python heap with native headroom\n", requested);
        return 0;
    }
    for (candidate = PY86_HEAP_MAX; candidate >= PY86_HEAP_MIN;
         candidate -= PY86_HEAP_STEP) {
        if (candidate <= ceiling && py86_heap_try(candidate)) {
            return 1;
        }
    }
    fputs("Cannot allocate a safe 24000-byte Python heap with native headroom\n", stderr);
    return 0;
}

/* Keyboard interrupt support: SIGINT is deferred to safe VM boundaries. */
const char py86_help_text[] =
    "Py86: Python 3 for 16-bit DOS (MicroPython " PY86_MP_VERSION ")\n"
    "Commands: help(), help(obj), exit(), quit(), input(), print()\n"
    "Modules: os, sys, time, datetime, math, random, json, re, hashlib, gc, errno\n"
    "Run: PY86 SCRIPT.PY or PY86 for the interactive prompt.\n"
    "Ctrl+C interrupts a running program; Ctrl+Z then Enter exits the REPL.\n"
    "For built-in object information, use help(obj).\n"
    "Type help('modules') to list the available built-in modules.\n";

/* Signal handler only records a flag; MicroPython exceptions are scheduled
 * later in the VM, never from an asynchronous DOS signal handler. */
static volatile sig_atomic_t py86_ctrl_c_flag;
static unsigned short py86_vm_branches;
static int py86_console_input;
static int py86_test_ctrl_c;
static int py86_interrupt_char = 3;

/* Supports MicroPython's micropython.kbd_intr(char) API.  -1 disables
 * translation, matching the standard port convention. */
void mp_hal_set_interrupt_char(int c) {
    py86_interrupt_char = c;
}

static void py86_sigint(int signal_number) {
    (void)signal_number;
    py86_ctrl_c_flag = 1;
    signal(SIGINT, py86_sigint);
}

/* Called at branches, not per bytecode.  BIOS keyboard polling is gated to
 * a real console and limited to once per 256 branches to protect the V20.
 * BIOS INT 16h peeks without swallowing ordinary pending input; Ctrl+C
 * alone is removed and turned into a catchable KeyboardInterrupt. */
void py86_vm_hook_loop(void) {
    if (++py86_vm_branches != 0) {
        if ((py86_vm_branches & 255U) != 0) {
            if (!py86_ctrl_c_flag) return;
        }
    }
    if (py86_test_ctrl_c && py86_vm_branches >= 256U) {
        py86_test_ctrl_c = 0;
        py86_ctrl_c_flag = 1;
    }
    if (py86_console_input && ((py86_vm_branches & 255U) == 0U)) {
        unsigned short key = _bios_keybrd(_KEYBRD_READY);
        if (py86_interrupt_char >= 0 && (key & 0xff) == (unsigned)py86_interrupt_char) {
            (void)_bios_keybrd(_KEYBRD_READ);
            py86_ctrl_c_flag = 1;
        }
    }
    if (py86_ctrl_c_flag) {
        py86_ctrl_c_flag = 0;
        if (py86_interrupt_char >= 0) mp_sched_keyboard_interrupt();
    }
}

/* CPython-style convenience functions: both signal SystemExit.
 * This is a C builtin, so it also works when no Python stdlib is installed. */
static mp_obj_t py86_builtin_exit(size_t n_args, const mp_obj_t *args) {
    if (n_args == 0) {
        mp_raise_type(&mp_type_SystemExit);
    }
    mp_raise_type_arg(&mp_type_SystemExit, args[0]);
}
MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(py86_builtin_exit_obj, 0, 1, py86_builtin_exit);

int mp_hal_stdin_rx_chr(void) {
    int c = getchar();
    return c == EOF ? 4 : c == '\n' ? '\r' : c;
}
mp_uint_t mp_hal_stdout_tx_strn(const char *s, size_t n) { return fwrite(s, 1, n, stdout); }
void mp_hal_stdout_tx_strn_cooked(const char *s, size_t n) { mp_hal_stdout_tx_strn(s, n); }
void mp_hal_stdout_tx_str(const char *s) { mp_hal_stdout_tx_strn(s, strlen(s)); }

void gc_collect(void) {
    jmp_buf regs;
    char *p;
    #if defined(PY86_RUNTIME_PROFILE)
    unsigned long gc_begin = py86_profile_enabled ? py86_profile_ticks() : 0;
    #endif
    /* Watcom stack entries are only 2-byte aligned; far roots are 4 bytes.
       setjmp spills the callee-saved registers before scanning SS==DGROUP. */
    setjmp(regs);
    gc_collect_start();
    for (p = (char *)&regs; p + sizeof(void *) <= stack_top; p += 2) {
        void *root;
        memcpy(&root, p, sizeof(root));
        gc_collect_root(&root, 1);
    }
    gc_collect_end();
    #if defined(PY86_RUNTIME_PROFILE)
    if (py86_profile_enabled) {
        py86_gc_runtime_ms += py86_profile_elapsed(gc_begin, py86_profile_ticks());
        ++py86_gc_runtime_calls;
    }
    #endif
}

mp_import_stat_t mp_import_stat(const char *path) {
    struct stat s;
    if (stat(path, &s)) return MP_IMPORT_STAT_NO_EXIST;
    return (s.st_mode & S_IFDIR) ? MP_IMPORT_STAT_DIR : MP_IMPORT_STAT_FILE;
}

mp_lexer_t *mp_lexer_new_from_file(qstr filename) {
    const char *path = qstr_str(filename);
    FILE *f;
    long len;
    char *buf;
    #if defined(PY86_COMPILE_PROFILE)
    unsigned long io_start = py86_profile_ticks();
    #endif
    f = fopen(path, "rb");
    if (!f) mp_raise_OSError(MP_ENOENT);
    if (fseek(f, 0, SEEK_END) || (len = ftell(f)) < 0 || len > 24000L) {
        fclose(f); mp_raise_OSError(MP_EFBIG);
    }
    rewind(f);
    #if defined(PY86_SOURCE_DIRECT)
    /* Experimental single-copy path: allocate the final lexer-owned GC
     * buffer directly.  A local exception guard closes the DOS descriptor
     * even if m_new() fails. The reader frees the buffer after parsing. */
    {
        nlr_buf_t nlr;
        if (nlr_push(&nlr) == 0) {
            buf = m_new(char, (size_t)len + 1);
            if (fread(buf, 1, (size_t)len, f) != (size_t)len) {
                fclose(f);
                m_del(char, buf, (size_t)len + 1);
                nlr_pop();
                mp_raise_OSError(MP_EIO);
            }
            fclose(f);
            buf[len] = 0;
            #if defined(PY86_COMPILE_PROFILE)
            py86_profile_read_ms = py86_profile_elapsed(io_start, py86_profile_ticks());
            #endif
            nlr_pop();
            return mp_lexer_new_from_str_len(filename, buf, (size_t)len, (size_t)len + 1);
        }
        fclose(f);
        nlr_jump(nlr.ret_val);
    }
    #else
    /* Production loader intentionally unchanged. */
    buf = malloc((size_t)len + 1);
    if (!buf) { fclose(f); mp_raise_msg(&mp_type_MemoryError, MP_ERROR_TEXT("source buffer")); }
    if (fread(buf, 1, (size_t)len, f) != (size_t)len) {
        free(buf); fclose(f); mp_raise_OSError(MP_EIO);
    }
    fclose(f);
    #if defined(PY86_COMPILE_PROFILE)
    py86_profile_read_ms = py86_profile_elapsed(io_start, py86_profile_ticks());
    #endif
    buf[len] = 0;
    {
        nlr_buf_t nlr;
        if (nlr_push(&nlr) == 0) {
            char *copy = m_new(char, (size_t)len + 1);
            memcpy(copy, buf, (size_t)len + 1);
            free(buf);
            nlr_pop();
            return mp_lexer_new_from_str_len(filename, copy, (size_t)len, (size_t)len + 1);
        }
        free(buf);
        nlr_jump(nlr.ret_val);
    }
    #endif
}

/* Fault injection exists ONLY in the isolated, non-release PY86F.EXE.
 * The production PY86.EXE compiles none of this code.  Never run this test
 * binary on physical DOS hardware: an invalid instruction pointer can hang,
 * corrupt memory, or crash DOS.  DOSBox runs one case per disposable session.
 */
#if defined(PY86_TEST_VMFAULT)
#include "py/objfun.h"
#include "py/bc.h"
#include "py/bc0.h"
static int py86_vm_fault_inject(mp_obj_t object) {
    const char *mode = getenv("PY86_VMFAULT");
    mp_obj_fun_bc_t *fun;
    const byte *cursor;
    byte *opcode;
    if (mode == NULL || *mode == '\0') return 0;
    if (mp_obj_get_type(object) != &mp_type_fun_bc) {
        fputs("VMFAULT ERROR: expected a bytecode function\n", stderr);
        return -1;
    }
    fun = MP_OBJ_TO_PTR(object);
    if (strcmp(mode, "bad-pointer") == 0) {
        /* Deliberately corrupt the compiled function's bytecode pointer. */
        fun->bytecode = (const byte *)MK_FP(0, 0);
    } else if (strcmp(mode, "bad-opcode") == 0 ||
               strcmp(mode, "bad-jump") == 0) {
        /* Leave the prelude and constant table intact.  Only damage the
         * executable bytecode, not unrelated memory in the injector. */
        cursor = fun->bytecode;
        MP_BC_PRELUDE_SIG_DECODE(cursor);
        MP_BC_PRELUDE_SIZE_DECODE(cursor);
        opcode = (byte *)(cursor + n_info + n_cell);
        if (strcmp(mode, "bad-opcode") == 0) {
            opcode[0] = 0; /* Reserved opcode: should raise an exception. */
        } else {
            /* Valid JUMP with a corrupt ~16K forward destination.
             * There is no per-instruction IP bounds guard in the VM. */
            opcode[0] = MP_BC_JUMP;
            opcode[1] = 0xbf;
            opcode[2] = 0xff;
        }
    } else {
        fputs("VMFAULT ERROR: invalid fault name\n", stderr);
        return -1;
    }
    printf("VMFAULT INJECTED %s\n", mode);
    fflush(stdout);
    return 0;
}
#endif

static int execute(const char *source, int file, mp_parse_input_kind_t kind) {
    nlr_buf_t nlr;
    #if defined(PY86_COMPILE_PROFILE)
    unsigned long t0 = 0, t1 = 0, t2 = 0, t3 = 0, t4 = 0;
    unsigned long read_ms = 0;
    #if defined(PY86_RUNTIME_PROFILE)
    unsigned long prep_ms = 0;
    unsigned long forced_gc_ms = 0;
    unsigned pre_gc_free = 0;
    unsigned post_gc_free = 0;
    unsigned runtime_gc_calls = 0;
    unsigned long runtime_gc_ms = 0;
    #endif
    py86_profile_enabled = getenv("PY86_PROFILE") != NULL;
    if (py86_profile_enabled) {
        py86_profile_read_ms = 0;
        t0 = py86_profile_ticks();
    }
    #endif
    if (nlr_push(&nlr) == 0) {
        mp_lexer_t *lex = file ? mp_lexer_new_from_file(qstr_from_str(source)) :
            mp_lexer_new_from_str_len(MP_QSTR__lt_stdin_gt_, source, strlen(source), 0);
        qstr name = lex->source_name;
        #if defined(PY86_COMPILE_PROFILE)
        if (py86_profile_enabled) {
            t1 = py86_profile_ticks();
            read_ms = file ? py86_profile_read_ms : 0;
        }
        #endif
        mp_parse_tree_t tree = mp_parse(lex, kind);
        #if defined(PY86_COMPILE_PROFILE)
        if (py86_profile_enabled) t2 = py86_profile_ticks();
        #endif
        mp_obj_t fun = mp_compile(&tree, name, kind == MP_PARSE_SINGLE_INPUT);
        #if defined(PY86_COMPILE_PROFILE)
        if (py86_profile_enabled) t3 = py86_profile_ticks();
        #endif
        #if defined(PY86_RUNTIME_PROFILE)
        if (py86_profile_enabled) {
            gc_info_t pre;
            unsigned long prep_begin = py86_profile_ticks();
            gc_info(&pre);
            pre_gc_free = (unsigned)pre.free;
            /* Optional pre-execution GC: does not affect parsing or
             * bytecode. The compiled function stays rooted on the stack. */
            if (getenv("PY86_PREEXEC_GC") != NULL) {
                unsigned long collect_begin = py86_profile_ticks();
                gc_collect();
                forced_gc_ms = py86_profile_elapsed(collect_begin, py86_profile_ticks());
            }
            gc_info(&pre);
            post_gc_free = (unsigned)pre.free;
            prep_ms = py86_profile_elapsed(prep_begin, py86_profile_ticks());
            /* Count only collections performed while Python executes. */
            py86_gc_runtime_calls = 0;
            py86_gc_runtime_ms = 0;
        }
        #endif
        #if defined(PY86_TEST_VMFAULT)
        if (py86_vm_fault_inject(fun) != 0) {
            nlr_pop();
            return 4;
        }
        #endif
        #if defined(PY86_RUNTIME_PROFILE)
        if (py86_profile_enabled) {
            /* Exclude deliberate preparation/GC overhead from exec_ms.
             * P86RUNT reports prep_ms so full duration remains measurable. */
            t3 = py86_profile_ticks();
        }
        #endif
        mp_call_function_0(fun);
        #if defined(PY86_RUNTIME_PROFILE)
        if (py86_profile_enabled) {
            runtime_gc_calls = py86_gc_runtime_calls;
            runtime_gc_ms = py86_gc_runtime_ms;
        }
        #endif
        nlr_pop();
        #if defined(PY86_COMPILE_PROFILE)
        if (py86_profile_enabled) {
            gc_info_t gi;
            t4 = py86_profile_ticks();
            gc_info(&gi);
            printf("P86PROF read_ms=%lu lexer_ms=%lu parse_ms=%lu compile_ms=%lu exec_ms=%lu gc_free=%u\n",
                read_ms,
                py86_profile_elapsed(t0, t1) - read_ms,
                py86_profile_elapsed(t1, t2),
                py86_profile_elapsed(t2, t3),
                py86_profile_elapsed(t3, t4),
                (unsigned)gi.free);
            #if defined(PY86_RUNTIME_PROFILE)
            printf("P86RUNT gc_calls=%u gc_ms=%lu free_pre=%u free_post=%u prep_ms=%lu forced_gc_ms=%lu\n",
                runtime_gc_calls, runtime_gc_ms, pre_gc_free, post_gc_free,
                prep_ms, forced_gc_ms);
            #endif
        }
        #endif
        return 0;
    }
    {
        mp_obj_t exception = (mp_obj_t)nlr.ret_val;
        if (mp_obj_exception_match(exception, MP_OBJ_FROM_PTR(&mp_type_SystemExit))) {
            mp_obj_t value = mp_obj_exception_get_value(exception);
            py86_exit_requested = 1;
            /* DOS ERRORLEVEL is an 8-bit process return status. */
            if (value == mp_const_none) {
                return 0;
            }
            if (mp_obj_is_integer(value)) {
                return (int)(unsigned char)mp_obj_get_int_truncated(value);
            }
            /* Match sys.exit("message"): print the message and exit 1,
             * rather than treating SystemExit as a Python traceback. */
            mp_obj_print_helper(&mp_plat_print, value, PRINT_STR);
            mp_print_str(&mp_plat_print, "\n");
            return 1;
        }
        mp_obj_print_exception(&mp_plat_print, exception);
        return 1;
    }
}

int main(int argc, char **argv) {
    int dummy;
    int result = 0;
    int first_arg = 1;
    char line[256];
    static char source[2048];
    /* Sample the BIOS clock before heap selection and VM initialization. */
    py86_startup_begin();
    setvbuf(stdout, NULL, _IONBF, 0);
    setvbuf(stderr, NULL, _IONBF, 0);
    stack_top = (char *)&dummy;
    mp_stack_ctrl_init();
    mp_stack_set_limit(10000);
    if (!py86_heap_allocate()) return 2;
    gc_init(heap, (char *)heap + py86_heap_bytes);
    mp_init();
    py86_startup_initialized();
    py86_console_input = isatty(0);
    py86_test_ctrl_c = getenv("PY86_TEST_CTRLC") != NULL;
    signal(SIGINT, py86_sigint);
    /* Command switches must be handled before sys.argv is populated.
     * -c consumes a Python code argument but must not place it in sys.argv.
     * The -h/-V paths return without loading/running any user Python.
     * --home-cls is retained as a DOS-specific pre-command switch. */
    /* Keep ordinary cls behavior by default. --home-cls is useful for
       fixed-width full-frame text apps such as the unchanged PythonClock. */
    if (argc > 1 && strcmp(argv[1], "--home-cls") == 0) {
        first_arg = 2;
        py86_set_home_cls(1);
    }
    if (argc > first_arg && strcmp(argv[first_arg], "--heap-info") == 0) {
        gc_info_t info;
        gc_info(&info);
        printf("heap_bytes=%u gc_total=%u gc_free=%u mode=%s\n",
               py86_heap_bytes, (unsigned)info.total, (unsigned)info.free,
               py86_heap_fixed ? "fixed" : "auto");
        goto done;
    }
    if (argc > first_arg &&
        (strcmp(argv[first_arg], "-h") == 0 ||
         strcmp(argv[first_arg], "--help") == 0)) {
        puts("Usage: PY86 [--home-cls] [script.py [args...]]");
        puts("       PY86 [--home-cls] -c \"code\" [args...]");
        puts("       PY86 --heap-info");
        puts("       PY86 -h | --help | -V | --version");
        puts("Environment: PY86_HEAP=auto|24000..60000");
        puts("             PY86_HEAP_MAX=24000..60000 (auto limit)");
        puts("No script starts the interactive interpreter.");
        puts("Ctrl+C interrupts Python; Ctrl+Z then Enter exits the prompt.");
        goto done;
    }
    if (argc > first_arg &&
        (strcmp(argv[first_arg], "-V") == 0 ||
         strcmp(argv[first_arg], "--version") == 0)) {
        puts("Py86 " PY86_VERSION " (MicroPython " PY86_MP_VERSION ", 16-bit DOS, 8086/V20)");
        goto done;
    }
    if (argc > first_arg && strcmp(argv[first_arg], "-c") == 0) {
        if (first_arg + 1 >= argc) {
            fputs("PY86: -c requires a Python command\n", stderr);
            result = 2;
            goto done;
        }
        mp_obj_list_append(mp_sys_path, MP_OBJ_NEW_QSTR(MP_QSTR_));
        mp_obj_list_append(mp_sys_argv, mp_obj_new_str("-c", 2));
        for (dummy = first_arg + 2; dummy < argc; ++dummy)
            mp_obj_list_append(mp_sys_argv, mp_obj_new_str(argv[dummy], strlen(argv[dummy])));
        result = execute(argv[first_arg + 1], 0, MP_PARSE_FILE_INPUT);
    } else if (argc > first_arg) {
        mp_obj_list_append(mp_sys_path, MP_OBJ_NEW_QSTR(MP_QSTR_));
        for (dummy = first_arg; dummy < argc; ++dummy)
            mp_obj_list_append(mp_sys_argv, mp_obj_new_str(argv[dummy], strlen(argv[dummy])));
        result = execute(argv[first_arg], 1, MP_PARSE_FILE_INPUT);
    } else {
        mp_obj_list_append(mp_sys_path, MP_OBJ_NEW_QSTR(MP_QSTR_));
        mp_obj_list_append(mp_sys_argv, mp_obj_new_str("", 0));
        puts("Py86 " PY86_VERSION " (experimental) - Python 3 for 16-bit DOS");
        puts("Based on MicroPython " PY86_MP_VERSION);
        puts("Blank line ends a block; Ctrl-Z then Enter exits.");
        for (;;) {
            source[0] = 0;
            fputs(">>> ", stdout); fflush(stdout);
            if (!fgets(line, sizeof(line), stdin)) {
                if (py86_ctrl_c_flag) {
                    py86_ctrl_c_flag = 0;
                    clearerr(stdin);
                    puts("KeyboardInterrupt");
                    continue;
                }
                break;
            }
            if ((unsigned char)line[0] == 3 || py86_ctrl_c_flag) {
                py86_ctrl_c_flag = 0;
                puts("KeyboardInterrupt");
                continue;
            }
            line[strcspn(line, "\r\n")] = 0;
            strcpy(source, line);
            while (mp_repl_continue_with_input(source)) {
                fputs("... ", stdout); fflush(stdout);
                if (!fgets(line, sizeof(line), stdin)) break;
                line[strcspn(line, "\r\n")] = 0;
                if (!line[0]) break;
                if (strlen(source) + strlen(line) + 1 >= sizeof(source)) {
                    puts("REPL input exceeds 2047 bytes"); source[0] = 0; break;
                }
                strcat(source, "\n"); strcat(source, line);
            }
            if (source[0]) {
                int step_result = execute(source, 0, MP_PARSE_SINGLE_INPUT);
                if (py86_exit_requested) {
                    result = step_result;
                    break;
                }
            }
        }
    }
done:
    signal(SIGINT, SIG_DFL);
    mp_deinit();
    free(heap);
    return result;
}

void nlr_jump_fail(void *val) { fputs("Fatal uncaught Python exception\n", stderr); exit(3); }
