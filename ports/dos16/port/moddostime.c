/* Py86 DOS-backed os and time modules. MIT license.
 * Do not require a 386, DOS extender, graphics card or Unix runtime.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <errno.h>
#include <time.h>
#include <direct.h>
#include <dos.h>
#include <i86.h>
#include <sys/stat.h>

#include "py/runtime.h"
#include "py/objtuple.h"
#include "py/objlist.h"
#include "py/objstr.h"

#define PY86_TICKS_PER_DAY 1573040UL
#define PY86_MS_PER_DAY 86400000UL
#define PY86_DOS_FIND_ATTR (_A_RDONLY | _A_HIDDEN | _A_SYSTEM | _A_SUBDIR | _A_ARCH)

/* Only the explicit --home-cls option intercepts CLS with a cursor-home. */
static int py86_home_on_cls = 0;
void py86_set_home_cls(int enabled) {
    py86_home_on_cls = enabled;
}

static void py86_cursor_home(void) {
    union REGS in_regs, out_regs;
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

static void py86_clear_screen(void) {
    union REGS in_regs, out_regs;
    unsigned char cols, page;
    fflush(stdout);
    memset(&in_regs, 0, sizeof(in_regs));
    in_regs.h.ah = 0x0f;
    int86(0x10, &in_regs, &out_regs);
    cols = out_regs.h.ah;
    page = out_regs.h.bh;
    if (cols == 0) {
        cols = 80;
    }
    memset(&in_regs, 0, sizeof(in_regs));
    in_regs.h.ah = 0x06;
    in_regs.h.bh = 0x07;
    in_regs.h.dh = 24;
    in_regs.h.dl = cols - 1;
    int86(0x10, &in_regs, &out_regs);
    py86_cursor_home();
}

static unsigned long py86_bios_ticks(void) {
    union REGS in_regs, out_regs;
    memset(&in_regs, 0, sizeof(in_regs));
    in_regs.h.ah = 0;
    int86(0x1a, &in_regs, &out_regs);
    return ((unsigned long)out_regs.x.cx << 16) | out_regs.x.dx;
}

static mp_obj_t py86_os_system(mp_obj_t command_in) {
    const char *cmd = mp_obj_str_get_str(command_in);
    const char *p = cmd;
    const char *end;
    while (*p == ' ' || *p == '\t') ++p;
    end = p + strlen(p);
    while (end > p && (end[-1] == ' ' || end[-1] == '\t')) --end;
    if (end - p == 3 && tolower((unsigned char)p[0]) == 'c'
        && tolower((unsigned char)p[1]) == 'l'
        && tolower((unsigned char)p[2]) == 's') {
        if (py86_home_on_cls) py86_cursor_home();
        else py86_clear_screen();
        return MP_OBJ_NEW_SMALL_INT(0);
    }
    return mp_obj_new_int(system(cmd));
}
static MP_DEFINE_CONST_FUN_OBJ_1(py86_os_system_obj, py86_os_system);

static mp_obj_t py86_os_getcwd(void) {
    char path[128];
    if (getcwd(path, sizeof(path)) == NULL) mp_raise_OSError(errno);
    return mp_obj_new_str_from_cstr(path);
}
static MP_DEFINE_CONST_FUN_OBJ_0(py86_os_getcwd_obj, py86_os_getcwd);

static mp_obj_t py86_os_chdir(mp_obj_t path_obj) {
    if (chdir(mp_obj_str_get_str(path_obj))) mp_raise_OSError(errno);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(py86_os_chdir_obj, py86_os_chdir);

static mp_obj_t py86_os_mkdir(mp_obj_t path_obj) {
    if (mkdir(mp_obj_str_get_str(path_obj))) mp_raise_OSError(errno);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(py86_os_mkdir_obj, py86_os_mkdir);

static mp_obj_t py86_os_rmdir(mp_obj_t path_obj) {
    if (rmdir(mp_obj_str_get_str(path_obj))) mp_raise_OSError(errno);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(py86_os_rmdir_obj, py86_os_rmdir);

static mp_obj_t py86_os_remove(mp_obj_t path_obj) {
    if (remove(mp_obj_str_get_str(path_obj))) mp_raise_OSError(errno);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(py86_os_remove_obj, py86_os_remove);

static mp_obj_t py86_os_rename(mp_obj_t old_obj, mp_obj_t new_obj) {
    if (rename(mp_obj_str_get_str(old_obj), mp_obj_str_get_str(new_obj))) mp_raise_OSError(errno);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_2(py86_os_rename_obj, py86_os_rename);

static mp_obj_t py86_os_getenv(mp_obj_t key_obj) {
    const char *value = getenv(mp_obj_str_get_str(key_obj));
    return value == NULL ? mp_const_none : mp_obj_new_str_from_cstr(value);
}
static MP_DEFINE_CONST_FUN_OBJ_1(py86_os_getenv_obj, py86_os_getenv);

static mp_obj_t py86_os_listdir(size_t argc, const mp_obj_t *argv) {
    const char *dirname = argc ? mp_obj_str_get_str(argv[0]) : ".";
    struct stat st;
    struct find_t found;
    char pattern[128];
    size_t n = strlen(dirname);
    unsigned rc;
    mp_obj_t out;
    if (stat(dirname, &st)) {
        mp_raise_OSError(errno);
    }
    if (!(st.st_mode & S_IFDIR)) {
        mp_raise_OSError(ENOTDIR);
    }
    if (n + 5 >= sizeof(pattern)) {
        mp_raise_ValueError(MP_ERROR_TEXT("DOS path too long"));
    }
    memcpy(pattern, dirname, n);
    if (n && dirname[n - 1] != '\\' && dirname[n - 1] != '/') {
        pattern[n++] = '\\';
    }
    memcpy(pattern + n, "*.*", 4);
    out = mp_obj_new_list(0, NULL);
    rc = _dos_findfirst(pattern, PY86_DOS_FIND_ATTR, &found);
    while (rc == 0) {
        if (strcmp(found.name, ".") && strcmp(found.name, "..")) {
            mp_obj_list_append(out, mp_obj_new_str_from_cstr(found.name));
        }
        rc = _dos_findnext(&found);
    }
    _dos_findclose(&found);
    return out;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(py86_os_listdir_obj, 0, 1, py86_os_listdir);

static mp_obj_t py86_os_stat(mp_obj_t path_obj) {
    struct stat st;
    mp_obj_t parts[10];
    if (stat(mp_obj_str_get_str(path_obj), &st)) mp_raise_OSError(errno);
    parts[0] = mp_obj_new_int(st.st_mode);
    parts[1] = mp_obj_new_int(st.st_ino);
    parts[2] = mp_obj_new_int(st.st_dev);
    parts[3] = mp_obj_new_int(st.st_nlink);
    parts[4] = mp_obj_new_int(st.st_uid);
    parts[5] = mp_obj_new_int(st.st_gid);
    parts[6] = mp_obj_new_int_from_uint((mp_uint_t)st.st_size);
    parts[7] = mp_obj_new_int((mp_int_t)st.st_atime);
    parts[8] = mp_obj_new_int((mp_int_t)st.st_mtime);
    parts[9] = mp_obj_new_int((mp_int_t)st.st_ctime);
    return mp_obj_new_tuple(10, parts);
}
static MP_DEFINE_CONST_FUN_OBJ_1(py86_os_stat_obj, py86_os_stat);

static const MP_DEFINE_STR_OBJ(py86_os_sep_obj, "\\");

static const mp_rom_map_elem_t py86_os_globals_table[] = {
    { MP_ROM_QSTR(MP_QSTR___name__), MP_ROM_QSTR(MP_QSTR_os) },
    { MP_ROM_QSTR(MP_QSTR_name), MP_ROM_QSTR(MP_QSTR_dos) },
    { MP_ROM_QSTR(MP_QSTR_sep), MP_ROM_PTR(&py86_os_sep_obj) },
    { MP_ROM_QSTR(MP_QSTR_system), MP_ROM_PTR(&py86_os_system_obj) },
    { MP_ROM_QSTR(MP_QSTR_getcwd), MP_ROM_PTR(&py86_os_getcwd_obj) },
    { MP_ROM_QSTR(MP_QSTR_chdir), MP_ROM_PTR(&py86_os_chdir_obj) },
    { MP_ROM_QSTR(MP_QSTR_mkdir), MP_ROM_PTR(&py86_os_mkdir_obj) },
    { MP_ROM_QSTR(MP_QSTR_rmdir), MP_ROM_PTR(&py86_os_rmdir_obj) },
    { MP_ROM_QSTR(MP_QSTR_remove), MP_ROM_PTR(&py86_os_remove_obj) },
    { MP_ROM_QSTR(MP_QSTR_unlink), MP_ROM_PTR(&py86_os_remove_obj) },
    { MP_ROM_QSTR(MP_QSTR_rename), MP_ROM_PTR(&py86_os_rename_obj) },
    { MP_ROM_QSTR(MP_QSTR_getenv), MP_ROM_PTR(&py86_os_getenv_obj) },
    { MP_ROM_QSTR(MP_QSTR_listdir), MP_ROM_PTR(&py86_os_listdir_obj) },
    { MP_ROM_QSTR(MP_QSTR_stat), MP_ROM_PTR(&py86_os_stat_obj) },
};
static MP_DEFINE_CONST_DICT(py86_os_globals, py86_os_globals_table);
const mp_obj_module_t py86_os_module = {
    .base = { &mp_type_module },
    .globals = (mp_obj_dict_t *)&py86_os_globals,
};
MP_REGISTER_MODULE(MP_QSTR_os, py86_os_module);

static void py86_wait_ticks(unsigned long ticks) {
    unsigned long start = py86_bios_ticks();
    unsigned long current, elapsed;
    if (ticks == 0) return;
    do {
        current = py86_bios_ticks();
        elapsed = current >= start ? current - start : PY86_TICKS_PER_DAY - start + current;
    } while (elapsed < ticks);
}

static mp_obj_t py86_time_sleep(mp_obj_t seconds_obj) {
    mp_float_t seconds = mp_obj_get_float(seconds_obj);
    unsigned long ticks;
    if (!(seconds >= 0) || seconds > 3600) {
        mp_raise_ValueError(MP_ERROR_TEXT("sleep requires 0..3600 seconds"));
    }
    ticks = (unsigned long)(seconds * 18.20648 + 0.999999);
    py86_wait_ticks(ticks);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(py86_time_sleep_obj, py86_time_sleep);

static mp_obj_t py86_time_sleep_ms(mp_obj_t milliseconds_obj) {
    mp_int_t ms = mp_obj_get_int(milliseconds_obj);
    if (ms < 0 || ms > 3600000L) {
        mp_raise_ValueError(MP_ERROR_TEXT("sleep_ms requires 0..3600000 ms"));
    }
    py86_wait_ticks((unsigned long)((mp_float_t)ms * 18.20648 / 1000.0 + 0.999999));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(py86_time_sleep_ms_obj, py86_time_sleep_ms);

static mp_obj_t py86_time_localtime(size_t argc, const mp_obj_t *argv) {
    struct dosdate_t d;
    struct dostime_t t;
    struct tm *tm_ptr;
    time_t requested;
    unsigned short month, yday;
    int leap;
    const unsigned char month_lengths[12] = {31,28,31,30,31,30,31,31,30,31,30,31};
    mp_obj_t fields[9];
    if (argc) {
        requested = (time_t)mp_obj_get_int(argv[0]);
        tm_ptr = localtime(&requested);
        if (tm_ptr == NULL) mp_raise_ValueError(MP_ERROR_TEXT("invalid timestamp"));
        fields[0] = mp_obj_new_int(tm_ptr->tm_year + 1900);
        fields[1] = mp_obj_new_int(tm_ptr->tm_mon + 1);
        fields[2] = mp_obj_new_int(tm_ptr->tm_mday);
        fields[3] = mp_obj_new_int(tm_ptr->tm_hour);
        fields[4] = mp_obj_new_int(tm_ptr->tm_min);
        fields[5] = mp_obj_new_int(tm_ptr->tm_sec);
        fields[6] = mp_obj_new_int((tm_ptr->tm_wday + 6) % 7);
        fields[7] = mp_obj_new_int(tm_ptr->tm_yday + 1);
        fields[8] = mp_obj_new_int(tm_ptr->tm_isdst);
    } else {
        _dos_getdate(&d);
        _dos_gettime(&t);
        leap = d.year % 4 == 0 && (d.year % 100 != 0 || d.year % 400 == 0);
        yday = d.day;
        for (month = 1; month < d.month && month <= 12; ++month) yday += month_lengths[month - 1];
        if (leap && d.month > 2) ++yday;
        fields[0] = mp_obj_new_int(d.year);
        fields[1] = mp_obj_new_int(d.month);
        fields[2] = mp_obj_new_int(d.day);
        fields[3] = mp_obj_new_int(t.hour);
        fields[4] = mp_obj_new_int(t.minute);
        fields[5] = mp_obj_new_int(t.second);
        fields[6] = mp_obj_new_int((d.dayofweek + 6) % 7);
        fields[7] = mp_obj_new_int(yday);
        fields[8] = MP_OBJ_NEW_SMALL_INT(-1);
    }
    return mp_obj_new_tuple(9, fields);
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(py86_time_localtime_obj, 0, 1, py86_time_localtime);

static mp_obj_t py86_time_time(void) {
    return mp_obj_new_int((mp_int_t)time(NULL));
}
static MP_DEFINE_CONST_FUN_OBJ_0(py86_time_time_obj, py86_time_time);

static mp_obj_t py86_time_ticks_ms(void) {
    unsigned long ticks = py86_bios_ticks();
    /* A BIOS tick is about 54.925 ms; avoid 64-bit arithmetic on the V20. */
    return mp_obj_new_int((mp_int_t)((ticks * 55UL - ticks * 75UL / 1000UL) % PY86_MS_PER_DAY));
}
static MP_DEFINE_CONST_FUN_OBJ_0(py86_time_ticks_ms_obj, py86_time_ticks_ms);

static mp_obj_t py86_time_ticks_diff(mp_obj_t end_obj, mp_obj_t start_obj) {
    mp_int_t diff = mp_obj_get_int(end_obj) - mp_obj_get_int(start_obj);
    if (diff < -(mp_int_t)(PY86_MS_PER_DAY / 2UL)) diff += PY86_MS_PER_DAY;
    else if (diff > (mp_int_t)(PY86_MS_PER_DAY / 2UL)) diff -= PY86_MS_PER_DAY;
    return mp_obj_new_int(diff);
}
static MP_DEFINE_CONST_FUN_OBJ_2(py86_time_ticks_diff_obj, py86_time_ticks_diff);

static const mp_rom_map_elem_t py86_time_globals_table[] = {
    { MP_ROM_QSTR(MP_QSTR___name__), MP_ROM_QSTR(MP_QSTR_time) },
    { MP_ROM_QSTR(MP_QSTR_sleep), MP_ROM_PTR(&py86_time_sleep_obj) },
    { MP_ROM_QSTR(MP_QSTR_sleep_ms), MP_ROM_PTR(&py86_time_sleep_ms_obj) },
    { MP_ROM_QSTR(MP_QSTR_localtime), MP_ROM_PTR(&py86_time_localtime_obj) },
    { MP_ROM_QSTR(MP_QSTR_time), MP_ROM_PTR(&py86_time_time_obj) },
    { MP_ROM_QSTR(MP_QSTR_ticks_ms), MP_ROM_PTR(&py86_time_ticks_ms_obj) },
    { MP_ROM_QSTR(MP_QSTR_ticks_diff), MP_ROM_PTR(&py86_time_ticks_diff_obj) },
};
static MP_DEFINE_CONST_DICT(py86_time_globals, py86_time_globals_table);
const mp_obj_module_t py86_time_module = {
    .base = { &mp_type_module },
    .globals = (mp_obj_dict_t *)&py86_time_globals,
};
MP_REGISTER_MODULE(MP_QSTR_time, py86_time_module);
