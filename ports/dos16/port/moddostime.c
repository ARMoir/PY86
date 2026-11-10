/* Py86: minimal DOS-backed os/time support for Python 3 programs.
 * MIT License. BIOS text console and timer; DOS-local wall clock.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <dos.h>
#include <i86.h>

#include "py/runtime.h"
#include "py/objtuple.h"

#define PY86_TICKS_PER_DAY 1573040UL

/* Opt-in interactive text refresh. Normal os.system("cls") still clears. */
static int py86_home_on_cls = 0;
void py86_set_home_cls(int enabled) {
    py86_home_on_cls = enabled;
}

/* Reposition the active text page cursor without erasing existing content. */
static void py86_cursor_home(void) {
    union REGS in_regs;
    union REGS out_regs;
    unsigned char page;
    fflush(stdout);
    memset(&in_regs, 0, sizeof(in_regs));
    in_regs.h.ah = 0x0f;
    int86(0x10, &in_regs, &out_regs);
    page = out_regs.h.bh;
    memset(&in_regs, 0, sizeof(in_regs));
    in_regs.h.ah = 0x02;
    in_regs.h.bh = page;
    in_regs.h.dh = 0;
    in_regs.h.dl = 0;
    int86(0x10, &in_regs, &out_regs);
}

/* BIOS tick count since midnight (INT 1Ah, AH=00h). */
static unsigned long py86_bios_ticks(void) {
    union REGS in_regs;
    union REGS out_regs;
    memset(&in_regs, 0, sizeof(in_regs));
    in_regs.h.ah = 0;
    int86(0x1a, &in_regs, &out_regs);
    return ((unsigned long)out_regs.x.cx << 16) | out_regs.x.dx;
}

/* The original clock calls os.system("cls") once per refresh.
 * Clear the current BIOS text page without invoking another copy of COMMAND.COM.
 */
static void py86_clear_screen(void) {
    union REGS in_regs;
    union REGS out_regs;
    unsigned char columns;
    unsigned char page;
    fflush(stdout);
    memset(&in_regs, 0, sizeof(in_regs));
    in_regs.h.ah = 0x0f;
    int86(0x10, &in_regs, &out_regs);
    columns = out_regs.h.ah;
    page = out_regs.h.bh;
    if (columns == 0) {
        columns = 80;
    }
    memset(&in_regs, 0, sizeof(in_regs));
    in_regs.h.ah = 0x06;
    in_regs.h.al = 0;
    in_regs.h.bh = 0x07;
    in_regs.h.ch = 0;
    in_regs.h.cl = 0;
    in_regs.h.dh = 24;
    in_regs.h.dl = columns - 1;
    int86(0x10, &in_regs, &out_regs);
    memset(&in_regs, 0, sizeof(in_regs));
    in_regs.h.ah = 0x02;
    in_regs.h.bh = page;
    in_regs.h.dh = 0;
    in_regs.h.dl = 0;
    int86(0x10, &in_regs, &out_regs);
}

static mp_obj_t py86_os_system(mp_obj_t command_in) {
    const char *cmd = mp_obj_str_get_str(command_in);
    const char *p = cmd;
    const char *end;
    while (*p == ' ' || *p == '\t') {
        ++p;
    }
    end = p + strlen(p);
    while (end > p && (end[-1] == ' ' || end[-1] == '\t')) {
        --end;
    }
    if (end - p == 3 && tolower((unsigned char)p[0]) == 'c'
        && tolower((unsigned char)p[1]) == 'l'
        && tolower((unsigned char)p[2]) == 's') {
        if (py86_home_on_cls) {
            py86_cursor_home();
        } else {
            py86_clear_screen();
        }
        return MP_OBJ_NEW_SMALL_INT(0);
    }
    /* For other commands preserve os.system semantics if COMMAND.COM fits RAM. */
    return mp_obj_new_int(system(cmd));
}
static MP_DEFINE_CONST_FUN_OBJ_1(py86_os_system_obj, py86_os_system);

static const mp_rom_map_elem_t py86_os_globals_table[] = {
    { MP_ROM_QSTR(MP_QSTR___name__), MP_ROM_QSTR(MP_QSTR_os) },
    { MP_ROM_QSTR(MP_QSTR_name), MP_ROM_QSTR(MP_QSTR_dos) },
    { MP_ROM_QSTR(MP_QSTR_system), MP_ROM_PTR(&py86_os_system_obj) },
};
static MP_DEFINE_CONST_DICT(py86_os_globals, py86_os_globals_table);
const mp_obj_module_t py86_os_module = {
    .base = { &mp_type_module },
    .globals = (mp_obj_dict_t *)&py86_os_globals,
};
MP_REGISTER_MODULE(MP_QSTR_os, py86_os_module);

static mp_obj_t py86_time_sleep(mp_obj_t seconds_in) {
    mp_float_t seconds = mp_obj_get_float(seconds_in);
    unsigned long ticks;
    unsigned long start;
    unsigned long current;
    unsigned long elapsed;
    if (!(seconds >= 0) || seconds > 3600) {
        mp_raise_ValueError(MP_ERROR_TEXT("sleep requires 0..3600 seconds"));
    }
    ticks = (unsigned long)(seconds * 18.20648 + 0.999999);
    if (ticks == 0) {
        return mp_const_none;
    }
    start = py86_bios_ticks();
    do {
        current = py86_bios_ticks();
        elapsed = current >= start ? current - start :
            PY86_TICKS_PER_DAY - start + current;
    } while (elapsed < ticks);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(py86_time_sleep_obj, py86_time_sleep);

static mp_obj_t py86_time_localtime(void) {
    struct dosdate_t date;
    struct dostime_t time;
    const unsigned char month_lengths[12] = {
        31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31
    };
    unsigned short day_of_year;
    unsigned short month;
    int leap;
    mp_obj_t tuple[9];
    _dos_getdate(&date);
    _dos_gettime(&time);
    leap = (date.year % 4 == 0 && (date.year % 100 != 0 || date.year % 400 == 0));
    day_of_year = date.day;
    for (month = 1; month < date.month && month <= 12; ++month) {
        day_of_year += month_lengths[month - 1];
    }
    if (leap && date.month > 2) {
        ++day_of_year;
    }
    tuple[0] = mp_obj_new_int(date.year);
    tuple[1] = mp_obj_new_int(date.month);
    tuple[2] = mp_obj_new_int(date.day);
    tuple[3] = mp_obj_new_int(time.hour);
    tuple[4] = mp_obj_new_int(time.minute);
    tuple[5] = mp_obj_new_int(time.second);
    tuple[6] = mp_obj_new_int((date.dayofweek + 6) % 7); /* Monday=0 */
    tuple[7] = mp_obj_new_int(day_of_year);
    tuple[8] = MP_OBJ_NEW_SMALL_INT(-1); /* DST information unavailable */
    return mp_obj_new_tuple(9, tuple);
}
static MP_DEFINE_CONST_FUN_OBJ_0(py86_time_localtime_obj, py86_time_localtime);

static const mp_rom_map_elem_t py86_time_globals_table[] = {
    { MP_ROM_QSTR(MP_QSTR___name__), MP_ROM_QSTR(MP_QSTR_time) },
    { MP_ROM_QSTR(MP_QSTR_sleep), MP_ROM_PTR(&py86_time_sleep_obj) },
    { MP_ROM_QSTR(MP_QSTR_localtime), MP_ROM_PTR(&py86_time_localtime_obj) },
};
static MP_DEFINE_CONST_DICT(py86_time_globals, py86_time_globals_table);
const mp_obj_module_t py86_time_module = {
    .base = { &mp_type_module },
    .globals = (mp_obj_dict_t *)&py86_time_globals,
};
MP_REGISTER_MODULE(MP_QSTR_time, py86_time_module);
