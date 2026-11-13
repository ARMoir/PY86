/* Minimal native curses for Py86 real-mode DOS.
 * ASCII text screens and BIOS keyboard only. No ncurses or ANSI.SYS dependency.
 * Open Watcom 16-bit / 8086 compatible. MIT license.
 */
#include <stdlib.h>
#include <string.h>
#include <dos.h>
#include <bios.h>
#include <i86.h>
#include "py/runtime.h"

#define PY86_ROWS 25
#define PY86_MAX_COLS 80
#define PY86_MAX_CELLS (PY86_ROWS * PY86_MAX_COLS)
#define PY86_DAY_TICKS 1573040UL

#define PY86_KEY_DOWN 258
#define PY86_KEY_UP 259
#define PY86_KEY_LEFT 260
#define PY86_KEY_RIGHT 261

typedef struct _py86_curses_screen_t {
    mp_obj_base_t base;
} py86_curses_screen_t;

static const mp_obj_type_t py86_curses_screen_type;
static py86_curses_screen_t py86_screen = {{&py86_curses_screen_type}};
static unsigned short *py86_cells;
static unsigned char *py86_dirty;
static unsigned py86_cols = 80;
static unsigned py86_page;
static unsigned py86_cursor_y, py86_cursor_x;
static unsigned char py86_original_cursor_start = 6;
static unsigned char py86_original_cursor_end = 7;
static int py86_active;
static int py86_timeout_ms = -1;

/* Preserve the video page and mode. BIOS calls also work on Tandy and CGA.
 * We deliberately avoid writing to an assumed B800 segment. */
static void py86_video(unsigned ax, unsigned bx, unsigned cx, unsigned dx) {
    union REGS in_regs, out_regs;
    memset(&in_regs, 0, sizeof(in_regs));
    in_regs.x.ax = ax;
    in_regs.x.bx = bx;
    in_regs.x.cx = cx;
    in_regs.x.dx = dx;
    int86(0x10, &in_regs, &out_regs);
}

static unsigned long py86_ticks(void) {
    union REGS in_regs, out_regs;
    memset(&in_regs, 0, sizeof(in_regs));
    in_regs.h.ah = 0;
    int86(0x1a, &in_regs, &out_regs);
    return ((unsigned long)out_regs.x.cx << 16) | out_regs.x.dx;
}

static void py86_require_active(void) {
    if (!py86_active) {
        mp_raise_ValueError(MP_ERROR_TEXT("call curses.initscr() first"));
    }
}

static void py86_clear_video(void) {
    py86_video(0x0600, 0x0700, 0, (24U << 8) | (py86_cols - 1));
    py86_video(0x0200, py86_page << 8, 0, 0);
}

static void py86_put(unsigned y, unsigned x, unsigned char ch) {
    unsigned index;
    if (y >= PY86_ROWS || x >= py86_cols) return;
    index = y * py86_cols + x;
    if (py86_cells[index] != (unsigned short)(0x0700U | ch)) {
        py86_cells[index] = (unsigned short)(0x0700U | ch);
        py86_dirty[index] = 1;
    }
}

static mp_obj_t py86_curses_initscr(void) {
    union REGS in_regs, out_regs;
    unsigned size;
    unsigned i;
    unsigned char mode;
    if (py86_active) return MP_OBJ_FROM_PTR(&py86_screen);
    memset(&in_regs, 0, sizeof(in_regs));
    in_regs.h.ah = 0x0f;
    int86(0x10, &in_regs, &out_regs);
    mode = out_regs.h.al;
    if (!((mode <= 3) || mode == 7)) {
        mp_raise_ValueError(MP_ERROR_TEXT("curses requires DOS text mode"));
    }
    py86_cols = out_regs.h.ah;
    py86_page = out_regs.h.bh;
    if (py86_cols == 0 || py86_cols > PY86_MAX_COLS) {
        mp_raise_ValueError(MP_ERROR_TEXT("unsupported text width"));
    }
    size = py86_cols * PY86_ROWS;
    py86_cells = (unsigned short *)malloc(size * sizeof(unsigned short));
    py86_dirty = (unsigned char *)malloc(size);
    if (py86_cells == NULL || py86_dirty == NULL) {
        free(py86_cells);
        free(py86_dirty);
        py86_cells = NULL;
        py86_dirty = NULL;
        mp_raise_msg(&mp_type_MemoryError, MP_ERROR_TEXT("curses screen buffer"));
    }
    /* Read current cursor style so endwin can restore DOS's normal cursor. */
    memset(&in_regs, 0, sizeof(in_regs));
    in_regs.h.ah = 3;
    in_regs.h.bh = (unsigned char)py86_page;
    int86(0x10, &in_regs, &out_regs);
    py86_original_cursor_start = out_regs.h.ch;
    py86_original_cursor_end = out_regs.h.cl;
    for (i = 0; i < size; ++i) {
        py86_cells[i] = 0x0720;
        py86_dirty[i] = 0;
    }
    py86_cursor_y = py86_cursor_x = 0;
    py86_timeout_ms = -1;
    py86_active = 1;
    py86_clear_video();
    return MP_OBJ_FROM_PTR(&py86_screen);
}
static MP_DEFINE_CONST_FUN_OBJ_0(py86_curses_initscr_obj, py86_curses_initscr);

static mp_obj_t py86_curses_endwin(void) {
    if (py86_active) {
        py86_video(0x0100, 0,
            ((unsigned)py86_original_cursor_start << 8) | py86_original_cursor_end, 0);
        py86_video(0x0200, py86_page << 8, 0, (24U << 8));
        free(py86_cells);
        free(py86_dirty);
        py86_cells = NULL;
        py86_dirty = NULL;
        py86_active = 0;
    }
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_0(py86_curses_endwin_obj, py86_curses_endwin);

static mp_obj_t py86_curses_curs_set(mp_obj_t visibility) {
    int show = mp_obj_get_int(visibility);
    py86_require_active();
    if (show < 0 || show > 2) mp_raise_ValueError(MP_ERROR_TEXT("cursor visibility 0..2"));
    if (show == 0) {
        py86_video(0x0100, 0, 0x2000, 0);
    } else {
        py86_video(0x0100, 0, ((unsigned)py86_original_cursor_start << 8) |
            py86_original_cursor_end, 0);
    }
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(py86_curses_curs_set_obj, py86_curses_curs_set);

static mp_obj_t py86_screen_getmaxyx(mp_obj_t self) {
    mp_obj_t dims[2];
    (void)self;
    py86_require_active();
    dims[0] = MP_OBJ_NEW_SMALL_INT(PY86_ROWS);
    dims[1] = mp_obj_new_int(py86_cols);
    return mp_obj_new_tuple(2, dims);
}
static MP_DEFINE_CONST_FUN_OBJ_1(py86_screen_getmaxyx_obj, py86_screen_getmaxyx);

static mp_obj_t py86_screen_clear(mp_obj_t self) {
    unsigned i, size;
    (void)self;
    py86_require_active();
    size = PY86_ROWS * py86_cols;
    for (i = 0; i < size; ++i) {
        py86_cells[i] = 0x0720;
        py86_dirty[i] = 0;
    }
    py86_cursor_y = py86_cursor_x = 0;
    py86_clear_video();
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(py86_screen_clear_obj, py86_screen_clear);

static mp_obj_t py86_screen_move(mp_obj_t self, mp_obj_t y, mp_obj_t x) {
    mp_int_t row = mp_obj_get_int(y), col = mp_obj_get_int(x);
    (void)self;
    py86_require_active();
    if (row < 0 || row >= PY86_ROWS || col < 0 || col >= (mp_int_t)py86_cols)
        mp_raise_ValueError(MP_ERROR_TEXT("cursor outside screen"));
    py86_cursor_y = (unsigned)row;
    py86_cursor_x = (unsigned)col;
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_3(py86_screen_move_obj, py86_screen_move);

static void py86_pos(size_t n_args, const mp_obj_t *args, unsigned *row, unsigned *col) {
    mp_int_t y, x;
    if (n_args == 4) {
        y = mp_obj_get_int(args[1]);
        x = mp_obj_get_int(args[2]);
    } else {
        y = py86_cursor_y;
        x = py86_cursor_x;
    }
    if (y < 0 || y >= PY86_ROWS || x < 0 || x >= (mp_int_t)py86_cols)
        mp_raise_ValueError(MP_ERROR_TEXT("text outside screen"));
    *row = (unsigned)y;
    *col = (unsigned)x;
}

static mp_obj_t py86_screen_addstr(size_t n_args, const mp_obj_t *args) {
    const char *s;
    size_t len, i;
    unsigned row, col;
    py86_require_active();
    if (n_args != 2 && n_args != 4) mp_raise_TypeError(MP_ERROR_TEXT("addstr(text) or addstr(y,x,text)"));
    py86_pos(n_args, args, &row, &col);
    s = mp_obj_str_get_data(args[n_args - 1], &len);
    for (i = 0; i < len && col < py86_cols; ++i) {
        if (s[i] == '\n') {
            ++row;
            col = 0;
            if (row >= PY86_ROWS) break;
        } else {
            py86_put(row, col++, (unsigned char)s[i]);
        }
    }
    py86_cursor_y = row < PY86_ROWS ? row : PY86_ROWS - 1;
    py86_cursor_x = col < py86_cols ? col : py86_cols - 1;
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(py86_screen_addstr_obj, 2, 4, py86_screen_addstr);

static mp_obj_t py86_screen_addch(size_t n_args, const mp_obj_t *args) {
    unsigned row, col;
    unsigned char ch;
    mp_obj_t v;
    py86_require_active();
    if (n_args != 2 && n_args != 4) mp_raise_TypeError(MP_ERROR_TEXT("addch(ch) or addch(y,x,ch)"));
    py86_pos(n_args, args, &row, &col);
    v = args[n_args - 1];
    if (mp_obj_is_int(v)) {
        ch = (unsigned char)mp_obj_get_int(v);
    } else {
        size_t len;
        const char *s = mp_obj_str_get_data(v, &len);
        if (len != 1) mp_raise_ValueError(MP_ERROR_TEXT("addch requires one character"));
        ch = (unsigned char)s[0];
    }
    py86_put(row, col, ch);
    py86_cursor_y = row;
    py86_cursor_x = col + 1 < py86_cols ? col + 1 : col;
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(py86_screen_addch_obj, 2, 4, py86_screen_addch);

static mp_obj_t py86_screen_refresh(mp_obj_t self) {
    unsigned row, col, index;
    (void)self;
    py86_require_active();
    for (row = 0; row < PY86_ROWS; ++row) {
        for (col = 0; col < py86_cols; ++col) {
            index = row * py86_cols + col;
            if (py86_dirty[index]) {
                unsigned short cell = py86_cells[index];
                py86_video(0x0200, py86_page << 8, 0, (row << 8) | col);
                py86_video(0x0900 | (cell & 255U),
                    (py86_page << 8) | (cell >> 8), 1, 0);
                py86_dirty[index] = 0;
            }
        }
    }
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(py86_screen_refresh_obj, py86_screen_refresh);

/* BIOS keyboard does not echo. Scan codes are translated to CPython key values. */
static mp_obj_t py86_screen_getch(mp_obj_t self) {
    unsigned short key = 0;
    unsigned long start, ticks, elapsed, max_ticks;
    (void)self;
    py86_require_active();
    if (py86_timeout_ms < 0) {
        key = _bios_keybrd(_KEYBRD_READ);
    } else if (py86_timeout_ms == 0) {
        if (!_bios_keybrd(_KEYBRD_READY)) return MP_OBJ_NEW_SMALL_INT(-1);
        key = _bios_keybrd(_KEYBRD_READ);
    } else {
        max_ticks = ((unsigned long)py86_timeout_ms + 54UL) / 55UL;
        start = py86_ticks();
        for (;;) {
            if (_bios_keybrd(_KEYBRD_READY)) {
                key = _bios_keybrd(_KEYBRD_READ);
                break;
            }
            ticks = py86_ticks();
            elapsed = ticks >= start ? ticks - start : PY86_DAY_TICKS - start + ticks;
            if (elapsed >= max_ticks) return MP_OBJ_NEW_SMALL_INT(-1);
        }
    }
    if ((key & 255U) == 0 || (key & 255U) == 0xe0) {
        switch (key >> 8) {
            case 0x48: return MP_OBJ_NEW_SMALL_INT(PY86_KEY_UP);
            case 0x50: return MP_OBJ_NEW_SMALL_INT(PY86_KEY_DOWN);
            case 0x4b: return MP_OBJ_NEW_SMALL_INT(PY86_KEY_LEFT);
            case 0x4d: return MP_OBJ_NEW_SMALL_INT(PY86_KEY_RIGHT);
            default: return MP_OBJ_NEW_SMALL_INT(-1);
        }
    }
    return MP_OBJ_NEW_SMALL_INT(key & 255U);
}
static MP_DEFINE_CONST_FUN_OBJ_1(py86_screen_getch_obj, py86_screen_getch);

static mp_obj_t py86_screen_nodelay(mp_obj_t self, mp_obj_t enabled) {
    (void)self;
    py86_require_active();
    py86_timeout_ms = mp_obj_is_true(enabled) ? 0 : -1;
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_2(py86_screen_nodelay_obj, py86_screen_nodelay);

static mp_obj_t py86_screen_timeout(mp_obj_t self, mp_obj_t milliseconds) {
    mp_int_t ms = mp_obj_get_int(milliseconds);
    (void)self;
    py86_require_active();
    if (ms > 60000) mp_raise_ValueError(MP_ERROR_TEXT("timeout must be <=60000 ms"));
    py86_timeout_ms = ms < 0 ? -1 : (int)ms;
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_2(py86_screen_timeout_obj, py86_screen_timeout);

static mp_obj_t py86_screen_keypad(mp_obj_t self, mp_obj_t enabled) {
    (void)self;
    (void)enabled; /* BIOS arrow-key decoding is always enabled. */
    py86_require_active();
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_2(py86_screen_keypad_obj, py86_screen_keypad);

static const mp_rom_map_elem_t py86_screen_locals_table[] = {
    { MP_ROM_QSTR(MP_QSTR_getmaxyx), MP_ROM_PTR(&py86_screen_getmaxyx_obj) },
    { MP_ROM_QSTR(MP_QSTR_clear), MP_ROM_PTR(&py86_screen_clear_obj) },
    { MP_ROM_QSTR(MP_QSTR_erase), MP_ROM_PTR(&py86_screen_clear_obj) },
    { MP_ROM_QSTR(MP_QSTR_move), MP_ROM_PTR(&py86_screen_move_obj) },
    { MP_ROM_QSTR(MP_QSTR_addch), MP_ROM_PTR(&py86_screen_addch_obj) },
    { MP_ROM_QSTR(MP_QSTR_addstr), MP_ROM_PTR(&py86_screen_addstr_obj) },
    { MP_ROM_QSTR(MP_QSTR_refresh), MP_ROM_PTR(&py86_screen_refresh_obj) },
    { MP_ROM_QSTR(MP_QSTR_getch), MP_ROM_PTR(&py86_screen_getch_obj) },
    { MP_ROM_QSTR(MP_QSTR_nodelay), MP_ROM_PTR(&py86_screen_nodelay_obj) },
    { MP_ROM_QSTR(MP_QSTR_timeout), MP_ROM_PTR(&py86_screen_timeout_obj) },
    { MP_ROM_QSTR(MP_QSTR_keypad), MP_ROM_PTR(&py86_screen_keypad_obj) },
};
static MP_DEFINE_CONST_DICT(py86_screen_locals, py86_screen_locals_table);

static MP_DEFINE_CONST_OBJ_TYPE(
    py86_curses_screen_type,
    MP_QSTR_window,
    MP_TYPE_FLAG_NONE,
    locals_dict, &py86_screen_locals
    );

static const mp_rom_map_elem_t py86_curses_globals_table[] = {
    { MP_ROM_QSTR(MP_QSTR___name__), MP_ROM_QSTR(MP_QSTR_curses) },
    { MP_ROM_QSTR(MP_QSTR_initscr), MP_ROM_PTR(&py86_curses_initscr_obj) },
    { MP_ROM_QSTR(MP_QSTR_endwin), MP_ROM_PTR(&py86_curses_endwin_obj) },
    { MP_ROM_QSTR(MP_QSTR_curs_set), MP_ROM_PTR(&py86_curses_curs_set_obj) },
    { MP_ROM_QSTR(MP_QSTR_KEY_UP), MP_ROM_INT(PY86_KEY_UP) },
    { MP_ROM_QSTR(MP_QSTR_KEY_DOWN), MP_ROM_INT(PY86_KEY_DOWN) },
    { MP_ROM_QSTR(MP_QSTR_KEY_LEFT), MP_ROM_INT(PY86_KEY_LEFT) },
    { MP_ROM_QSTR(MP_QSTR_KEY_RIGHT), MP_ROM_INT(PY86_KEY_RIGHT) },
};
static MP_DEFINE_CONST_DICT(py86_curses_globals, py86_curses_globals_table);
const mp_obj_module_t py86_curses_module = {
    .base = { &mp_type_module },
    .globals = (mp_obj_dict_t *)&py86_curses_globals,
};
MP_REGISTER_MODULE(MP_QSTR_curses, py86_curses_module);
