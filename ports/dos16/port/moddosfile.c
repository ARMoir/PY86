/* Py86 DOS real-mode file support, adapted for the 16-bit Open Watcom ABI.
 * Built-in open(), basic text and bytes streams, context manager and seek.
 * MIT license.  Does not require a DOS extender or separate Python modules.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <limits.h>

#include "py/runtime.h"
#include "py/objstr.h"
#include "py/builtin.h"
#include "py/stream.h"

typedef struct _py86_file_t {
    mp_obj_base_t base;
    FILE *fp;
} py86_file_t;

static const mp_obj_type_t py86_type_textfile;
static const mp_obj_type_t py86_type_binaryfile;

static mp_uint_t py86_file_read(mp_obj_t self_in, void *buf, mp_uint_t size, int *errcode) {
    py86_file_t *self = MP_OBJ_TO_PTR(self_in);
    size_t n;
    if (self->fp == NULL) { *errcode = MP_EBADF; return MP_STREAM_ERROR; }
    /* Watcom 16-bit size_t and single-segment buffers must not overflow. */
    if (size > 16384U) size = 16384U;
    n = fread(buf, 1, (size_t)size, self->fp);
    if (n < (size_t)size && ferror(self->fp)) {
        *errcode = errno ? errno : MP_EIO;
        clearerr(self->fp);
        return MP_STREAM_ERROR;
    }
    return n;
}

static mp_uint_t py86_file_write(mp_obj_t self_in, const void *buf, mp_uint_t size, int *errcode) {
    py86_file_t *self = MP_OBJ_TO_PTR(self_in);
    size_t n;
    if (self->fp == NULL) { *errcode = MP_EBADF; return MP_STREAM_ERROR; }
    if (size > 16384U) size = 16384U;
    n = fwrite(buf, 1, (size_t)size, self->fp);
    if (n < (size_t)size) {
        *errcode = errno ? errno : MP_EIO;
        return MP_STREAM_ERROR;
    }
    return n;
}

static mp_uint_t py86_file_ioctl(mp_obj_t self_in, mp_uint_t request, uintptr_t arg, int *errcode) {
    py86_file_t *self = MP_OBJ_TO_PTR(self_in);
    if (request == MP_STREAM_CLOSE) {
        int err;
        if (self->fp == NULL) return 0;
        err = fclose(self->fp);
        self->fp = NULL;
        if (err != 0) { *errcode = errno ? errno : MP_EIO; return MP_STREAM_ERROR; }
        return 0;
    }
    if (self->fp == NULL) { *errcode = MP_EBADF; return MP_STREAM_ERROR; }
    if (request == MP_STREAM_FLUSH) {
        if (fflush(self->fp) != 0) { *errcode = errno ? errno : MP_EIO; return MP_STREAM_ERROR; }
        return 0;
    }
    if (request == MP_STREAM_SEEK) {
        struct mp_stream_seek_t *seek = (struct mp_stream_seek_t *)arg;
        long pos;
        if (fseek(self->fp, (long)seek->offset, seek->whence) != 0) {
            *errcode = errno ? errno : MP_EINVAL;
            return MP_STREAM_ERROR;
        }
        pos = ftell(self->fp);
        if (pos < 0) { *errcode = errno ? errno : MP_EIO; return MP_STREAM_ERROR; }
        seek->offset = pos;
        return 0;
    }
    *errcode = MP_EINVAL;
    return MP_STREAM_ERROR;
}

static const mp_stream_p_t py86_file_text_stream = {
    .read = py86_file_read,
    .write = py86_file_write,
    .ioctl = py86_file_ioctl,
    .is_text = 1,
};
static const mp_stream_p_t py86_file_binary_stream = {
    .read = py86_file_read,
    .write = py86_file_write,
    .ioctl = py86_file_ioctl,
};

static mp_obj_t py86_file_enter(mp_obj_t self_in) {
    py86_file_t *self = MP_OBJ_TO_PTR(self_in);
    if (self->fp == NULL) mp_raise_OSError(MP_EBADF);
    return self_in;
}
static MP_DEFINE_CONST_FUN_OBJ_1(py86_file_enter_obj, py86_file_enter);

static void py86_file_attr(mp_obj_t self_in, qstr attr, mp_obj_t *dest) {
    if (dest[0] == MP_OBJ_NULL && attr == MP_QSTR_closed) {
        py86_file_t *self = MP_OBJ_TO_PTR(self_in);
        dest[0] = mp_obj_new_bool(self->fp == NULL);
    }
}

static const mp_rom_map_elem_t py86_file_locals_table[] = {
    { MP_ROM_QSTR(MP_QSTR_read), MP_ROM_PTR(&mp_stream_read_obj) },
    { MP_ROM_QSTR(MP_QSTR_readline), MP_ROM_PTR(&mp_stream_unbuffered_readline_obj) },
    { MP_ROM_QSTR(MP_QSTR_readlines), MP_ROM_PTR(&mp_stream_unbuffered_readlines_obj) },
    { MP_ROM_QSTR(MP_QSTR_write), MP_ROM_PTR(&mp_stream_write_obj) },
    { MP_ROM_QSTR(MP_QSTR_seek), MP_ROM_PTR(&mp_stream_seek_obj) },
    { MP_ROM_QSTR(MP_QSTR_tell), MP_ROM_PTR(&mp_stream_tell_obj) },
    { MP_ROM_QSTR(MP_QSTR_flush), MP_ROM_PTR(&mp_stream_flush_obj) },
    { MP_ROM_QSTR(MP_QSTR_close), MP_ROM_PTR(&mp_stream_close_obj) },
    { MP_ROM_QSTR(MP_QSTR___enter__), MP_ROM_PTR(&py86_file_enter_obj) },
    { MP_ROM_QSTR(MP_QSTR___exit__), MP_ROM_PTR(&mp_stream___exit___obj) },
};
static MP_DEFINE_CONST_DICT(py86_file_locals, py86_file_locals_table);

static MP_DEFINE_CONST_OBJ_TYPE(
    py86_type_textfile,
    MP_QSTR_TextFile,
    MP_TYPE_FLAG_ITER_IS_STREAM,
    protocol, &py86_file_text_stream,
    locals_dict, &py86_file_locals,
    attr, py86_file_attr
    );

static MP_DEFINE_CONST_OBJ_TYPE(
    py86_type_binaryfile,
    MP_QSTR_BinaryFile,
    MP_TYPE_FLAG_ITER_IS_STREAM,
    protocol, &py86_file_binary_stream,
    locals_dict, &py86_file_locals,
    attr, py86_file_attr
    );

mp_obj_t mp_builtin_open(size_t n_args, const mp_obj_t *args, mp_map_t *kwargs) {
    enum { ARG_file, ARG_mode };
    static const mp_arg_t allowed_args[] = {
        { MP_QSTR_file, MP_ARG_REQUIRED | MP_ARG_OBJ, { .u_obj = MP_OBJ_NULL } },
        { MP_QSTR_mode, MP_ARG_OBJ, { .u_obj = MP_OBJ_NULL } },
    };
    mp_arg_val_t values[2];
    const char *name, *mode;
    char fm[5];
    size_t i, len;
    int binary = 0, text = 0, plus = 0;
    py86_file_t *self;

    mp_arg_parse_all(n_args, args, kwargs, 2, allowed_args, values);
    name = mp_obj_str_get_str(values[ARG_file].u_obj);
    mode = values[ARG_mode].u_obj == MP_OBJ_NULL ? "r"
         : mp_obj_str_get_str(values[ARG_mode].u_obj);
    if (strlen(name) >= 128 || name[0] == '\0') {
        mp_raise_ValueError(MP_ERROR_TEXT("invalid DOS filename"));
    }
    len = strlen(mode);
    if (len < 1 || len > 3 || (mode[0] != 'r' && mode[0] != 'w' && mode[0] != 'a')) {
        mp_raise_ValueError(MP_ERROR_TEXT("unsupported file mode"));
    }
    for (i = 1; i < len; ++i) {
        if (mode[i] == 'b') {
            if (binary || text) mp_raise_ValueError(MP_ERROR_TEXT("invalid file mode"));
            binary = 1;
        } else if (mode[i] == 't') {
            if (binary || text) mp_raise_ValueError(MP_ERROR_TEXT("invalid file mode"));
            text = 1;
        } else if (mode[i] == '+') {
            if (plus) mp_raise_ValueError(MP_ERROR_TEXT("invalid file mode"));
            plus = 1;
        } else {
            mp_raise_ValueError(MP_ERROR_TEXT("unsupported file mode"));
        }
    }
    fm[0] = mode[0];
    i = 1;
    if (binary) fm[i++] = 'b';
    if (plus) fm[i++] = '+';
    fm[i] = '\0';

    /* Allocate the GC wrapper before opening the DOS file descriptor, so
     * a MicroPython allocation failure cannot leak the DOS file handle. */
    self = mp_obj_malloc(py86_file_t, binary ? &py86_type_binaryfile : &py86_type_textfile);
    self->fp = fopen(name, fm);
    if (self->fp == NULL) mp_raise_OSError(errno ? errno : MP_EIO);
    return MP_OBJ_FROM_PTR(self);
}
MP_DEFINE_CONST_FUN_OBJ_KW(py86_builtin_open_obj, 1, mp_builtin_open);
