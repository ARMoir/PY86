/* Py86 DOS host, MIT license. Experimental MicroPython port. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <setjmp.h>
#include <sys/stat.h>
#include "py/compile.h"
#include "py/runtime.h"
#include "py/repl.h"
#include "py/gc.h"
#include "py/stackctrl.h"
#include "py/mperrno.h"
#include "py/objlist.h"
#include "py/builtin.h"

/* From moddostime.c: opt-in cursor-home behavior for interactive redraws. */
extern void py86_set_home_cls(int enabled);

static char *stack_top;
static void *heap;

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
}

mp_import_stat_t mp_import_stat(const char *path) {
    struct stat s;
    if (stat(path, &s)) return MP_IMPORT_STAT_NO_EXIST;
    return (s.st_mode & S_IFDIR) ? MP_IMPORT_STAT_DIR : MP_IMPORT_STAT_FILE;
}

mp_lexer_t *mp_lexer_new_from_file(qstr filename) {
    const char *path = qstr_str(filename);
    FILE *f = fopen(path, "rb");
    long len;
    char *buf;
    if (!f) mp_raise_OSError(MP_ENOENT);
    if (fseek(f, 0, SEEK_END) || (len = ftell(f)) < 0 || len > 24000L) {
        fclose(f); mp_raise_OSError(MP_EFBIG);
    }
    rewind(f);
    /* Allocate outside GC while reading; release on any allocation exception. */
    buf = malloc((size_t)len + 1);
    if (!buf) { fclose(f); mp_raise_msg(&mp_type_MemoryError, MP_ERROR_TEXT("source buffer")); }
    if (fread(buf, 1, (size_t)len, f) != (size_t)len) {
        free(buf); fclose(f); mp_raise_OSError(MP_EIO);
    }
    fclose(f);
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
}

static int execute(const char *source, int file, mp_parse_input_kind_t kind) {
    nlr_buf_t nlr;
    if (nlr_push(&nlr) == 0) {
        mp_lexer_t *lex = file ? mp_lexer_new_from_file(qstr_from_str(source)) :
            mp_lexer_new_from_str_len(MP_QSTR__lt_stdin_gt_, source, strlen(source), 0);
        qstr name = lex->source_name;
        mp_parse_tree_t tree = mp_parse(lex, kind);
        mp_obj_t fun = mp_compile(&tree, name, kind == MP_PARSE_SINGLE_INPUT);
        mp_call_function_0(fun);
        nlr_pop();
        return 0;
    }
    mp_obj_print_exception(&mp_plat_print, (mp_obj_t)nlr.ret_val);
    return 1;
}

int main(int argc, char **argv) {
    int dummy;
    int result = 0;
    int first_arg = 1;
    char line[256];
    static char source[2048];
    setvbuf(stdout, NULL, _IONBF, 0);
    setvbuf(stderr, NULL, _IONBF, 0);
    stack_top = (char *)&dummy;
    mp_stack_ctrl_init();
    mp_stack_set_limit(10000);
    heap = malloc(48000U);
    if (!heap) { fputs("Cannot allocate 48000-byte Python heap\n", stderr); return 2; }
    gc_init(heap, (char *)heap + 48000U);
    mp_init();
    /* Keep ordinary cls behavior by default. --home-cls is useful for
       fixed-width full-frame text apps such as the unchanged PythonClock. */
    if (argc > 1 && strcmp(argv[1], "--home-cls") == 0) {
        first_arg = 2;
        py86_set_home_cls(1);
    }
    mp_obj_list_append(mp_sys_path, MP_OBJ_NEW_QSTR(MP_QSTR_));
    for (dummy = first_arg; dummy < argc; ++dummy)
        mp_obj_list_append(mp_sys_argv, mp_obj_new_str(argv[dummy], strlen(argv[dummy])));
    if (argc > first_arg) {
        if (argc == first_arg + 2 && strcmp(argv[first_arg], "-c") == 0)
            result = execute(argv[first_arg + 1], 0, MP_PARSE_FILE_INPUT);
        else result = execute(argv[first_arg], 1, MP_PARSE_FILE_INPUT);
    } else {
        puts("Py86 0.1 (experimental) - Python 3 for 16-bit DOS");
        puts("Based on MicroPython 1.24.1");
        puts("Blank line ends a block; Ctrl-Z then Enter exits.");
        for (;;) {
            source[0] = 0;
            fputs(">>> ", stdout); fflush(stdout);
            if (!fgets(line, sizeof(line), stdin)) break;
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
            if (source[0]) execute(source, 0, MP_PARSE_SINGLE_INPUT);
        }
    }
    mp_deinit();
    free(heap);
    return result;
}

void nlr_jump_fail(void *val) { fputs("Fatal uncaught Python exception\n", stderr); exit(3); }
