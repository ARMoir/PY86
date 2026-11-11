/* Py86 built-in datetime subset for 16-bit DOS.
 * MIT license. No Python source shim required.
 * Supports datetime.datetime.now() and the constructor/fields used by
 * PythonClock, without depending on a host platform's calendar library.
 */
#include <dos.h>
#include "py/runtime.h"

/* Native fixed-size fields avoid a Python class/dict allocation per refresh. */
typedef struct _py86_datetime_t {
    mp_obj_base_t base;
    mp_int_t year, month, day, hour, minute, second, microsecond;
} py86_datetime_t;

static int py86_month_days(int year, int month) {
    static const unsigned char days[] = {31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31};
    int leap;
    if (month < 1 || month > 12) {
        mp_raise_ValueError(MP_ERROR_TEXT("month must be in 1..12"));
    }
    leap = year % 4 == 0 && (year % 100 != 0 || year % 400 == 0);
    return days[month - 1] + (month == 2 && leap);
}

static mp_obj_t py86_datetime_create(const mp_obj_type_t *type, mp_int_t year,
    mp_int_t month, mp_int_t day, mp_int_t hour, mp_int_t minute,
    mp_int_t second, mp_int_t microsecond) {
    py86_datetime_t *obj;
    if (year < 1 || year > 9999) {
        mp_raise_ValueError(MP_ERROR_TEXT("year must be in 1..9999"));
    }
    if (day < 1 || day > py86_month_days((int)year, (int)month)) {
        mp_raise_ValueError(MP_ERROR_TEXT("day is out of range for month"));
    }
    if (hour < 0 || hour > 23 || minute < 0 || minute > 59 ||
        second < 0 || second > 59 || microsecond < 0 || microsecond > 999999) {
        mp_raise_ValueError(MP_ERROR_TEXT("time component out of range"));
    }
    obj = mp_obj_malloc(py86_datetime_t, type);
    obj->year = year;
    obj->month = month;
    obj->day = day;
    obj->hour = hour;
    obj->minute = minute;
    obj->second = second;
    obj->microsecond = microsecond;
    return MP_OBJ_FROM_PTR(obj);
}

static mp_obj_t py86_datetime_make_new(const mp_obj_type_t *type,
    size_t n_args, size_t n_kw, const mp_obj_t *all_args) {
    enum { ARG_year, ARG_month, ARG_day, ARG_hour, ARG_minute, ARG_second, ARG_microsecond };
    static const mp_arg_t allowed[] = {
        { MP_QSTR_year, MP_ARG_REQUIRED | MP_ARG_INT, {.u_int = 0} },
        { MP_QSTR_month, MP_ARG_REQUIRED | MP_ARG_INT, {.u_int = 0} },
        { MP_QSTR_day, MP_ARG_REQUIRED | MP_ARG_INT, {.u_int = 0} },
        { MP_QSTR_hour, MP_ARG_INT, {.u_int = 0} },
        { MP_QSTR_minute, MP_ARG_INT, {.u_int = 0} },
        { MP_QSTR_second, MP_ARG_INT, {.u_int = 0} },
        { MP_QSTR_microsecond, MP_ARG_INT, {.u_int = 0} },
    };
    mp_arg_val_t a[MP_ARRAY_SIZE(allowed)];
    mp_arg_parse_all_kw_array(n_args, n_kw, all_args,
        MP_ARRAY_SIZE(allowed), allowed, a);
    return py86_datetime_create(type, a[ARG_year].u_int, a[ARG_month].u_int,
        a[ARG_day].u_int, a[ARG_hour].u_int, a[ARG_minute].u_int,
        a[ARG_second].u_int, a[ARG_microsecond].u_int);
}

static mp_obj_t py86_datetime_now(mp_obj_t cls) {
    struct dosdate_t date;
    struct dostime_t time;
    _dos_getdate(&date);
    _dos_gettime(&time);
    return py86_datetime_create(MP_OBJ_TO_PTR(cls), date.year, date.month,
        date.day, time.hour, time.minute, time.second,
        (mp_int_t)time.hsecond * 10000);
}
static MP_DEFINE_CONST_FUN_OBJ_1(py86_datetime_now_fun_obj, py86_datetime_now);
static MP_DEFINE_CONST_CLASSMETHOD_OBJ(py86_datetime_now_obj,
    MP_ROM_PTR(&py86_datetime_now_fun_obj));

static void py86_datetime_attr(mp_obj_t self_in, qstr attr, mp_obj_t *dest) {
    py86_datetime_t *self = MP_OBJ_TO_PTR(self_in);
    mp_int_t v;
    if (dest[0] != MP_OBJ_NULL) {
        mp_raise_msg(&mp_type_AttributeError, MP_ERROR_TEXT("readonly datetime"));
    }
    if (attr == MP_QSTR_year) v = self->year;
    else if (attr == MP_QSTR_month) v = self->month;
    else if (attr == MP_QSTR_day) v = self->day;
    else if (attr == MP_QSTR_hour) v = self->hour;
    else if (attr == MP_QSTR_minute) v = self->minute;
    else if (attr == MP_QSTR_second) v = self->second;
    else if (attr == MP_QSTR_microsecond) v = self->microsecond;
    else return;
    dest[0] = mp_obj_new_int(v);
}

static void py86_datetime_print(const mp_print_t *print, mp_obj_t self_in,
    mp_print_kind_t kind) {
    py86_datetime_t *self = MP_OBJ_TO_PTR(self_in);
    (void)kind;
    mp_printf(print, "datetime.datetime(%ld, %ld, %ld, %ld, %ld, %ld, %ld)",
        (long)self->year, (long)self->month, (long)self->day,
        (long)self->hour, (long)self->minute, (long)self->second,
        (long)self->microsecond);
}

static const mp_rom_map_elem_t py86_datetime_locals_table[] = {
    { MP_ROM_QSTR(MP_QSTR_now), MP_ROM_PTR(&py86_datetime_now_obj) },
    { MP_ROM_QSTR(MP_QSTR_today), MP_ROM_PTR(&py86_datetime_now_obj) },
};
static MP_DEFINE_CONST_DICT(py86_datetime_locals, py86_datetime_locals_table);

static MP_DEFINE_CONST_OBJ_TYPE(
    py86_datetime_type,
    MP_QSTR_datetime,
    MP_TYPE_FLAG_NONE,
    make_new, py86_datetime_make_new,
    print, py86_datetime_print,
    attr, py86_datetime_attr,
    locals_dict, &py86_datetime_locals
    );

static const mp_rom_map_elem_t py86_datetime_globals_table[] = {
    { MP_ROM_QSTR(MP_QSTR___name__), MP_ROM_QSTR(MP_QSTR_datetime) },
    { MP_ROM_QSTR(MP_QSTR_datetime), MP_ROM_PTR(&py86_datetime_type) },
};
static MP_DEFINE_CONST_DICT(py86_datetime_globals, py86_datetime_globals_table);

const mp_obj_module_t py86_datetime_module = {
    .base = { &mp_type_module },
    .globals = (mp_obj_dict_t *)&py86_datetime_globals,
};
MP_REGISTER_MODULE(MP_QSTR_datetime, py86_datetime_module);
