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


/* A single C loop replaces MicroPython's generic readline() path which
 * dispatches through the stream protocol and grows the vstr per character.
 * Watcom's getc() benefits from the DOS CRT FILE* buffer.  Use the same
 * translation rules as the generic path (text mode maps CRLF, binary doesn't).
 * The old path is retained for reproducible A/B measurements.
 */
#if PY86_FAST_READLINE
static mp_obj_t py86_file_readline_core(mp_obj_t self_in, mp_int_t limit) {
    py86_file_t *self = MP_OBJ_TO_PTR(self_in);
    vstr_t buf;
    if (self->fp == NULL) {
        mp_raise_OSError(MP_EBADF);
    }
    vstr_init(&buf, 64);
    while (limit == -1 || limit-- > 0) {
        int ch = fgetc(self->fp);
        if (ch == EOF) {
            if (ferror(self->fp)) {
                mp_raise_OSError(errno ? errno : MP_EIO);
            }
            break;
        }
        vstr_add_byte(&buf, (byte)ch);
        if (ch == '\n') {
            break;
        }
    }
    if (self->base.type == &py86_type_textfile) {
        return mp_obj_new_str_from_vstr(&buf);
    }
    return mp_obj_new_bytes_from_vstr(&buf);
}

static mp_obj_t py86_file_readline(size_t n_args, const mp_obj_t *args) {
    mp_int_t max_len = -1;
    if (n_args == 2) {
        max_len = mp_obj_get_int(args[1]);
        if (max_len < 0) max_len = -1;
    }
    return py86_file_readline_core(args[0], max_len);
}
MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(py86_file_readline_obj, 1, 2, py86_file_readline);

static mp_obj_t py86_file_readlines(mp_obj_t self_in) {
    mp_obj_t lines = mp_obj_new_list(0, NULL);
    for (;;) {
        mp_obj_t line = py86_file_readline_core(self_in, -1);
        if (!mp_obj_is_true(line)) break;
        mp_obj_list_append(lines, line);
    }
    return lines;
}
static MP_DEFINE_CONST_FUN_OBJ_1(py86_file_readlines_obj, py86_file_readlines);

static mp_obj_t py86_file_iternext(mp_obj_t self_in) {
    mp_obj_t line = py86_file_readline_core(self_in, -1);
    return mp_obj_is_true(line) ? line : MP_OBJ_STOP_ITERATION;
}
#endif

/* Reuse the existing stream writer and buffer protocol, avoiding a new
 * intermediate Python string for each line.  writelines does not add '\n'. */
static mp_obj_t py86_file_writelines(mp_obj_t self_in, mp_obj_t iterable) {
    mp_obj_t it;
    mp_obj_t item;
    py86_file_t *self = MP_OBJ_TO_PTR(self_in);
    if (self->fp == NULL) mp_raise_OSError(MP_EBADF);
    it = mp_getiter(iterable, NULL);
    while ((item = mp_iternext(it)) != MP_OBJ_STOP_ITERATION) {
        mp_buffer_info_t b;
        int error = 0;
        mp_uint_t written;
        mp_get_buffer_raise(item, &b, MP_BUFFER_READ);
        written = mp_stream_rw(self_in, b.buf, b.len, &error, MP_STREAM_RW_WRITE);
        if (error != 0) mp_raise_OSError(error);
        if (written != b.len) mp_raise_OSError(MP_EIO);
    }
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_2(py86_file_writelines_obj, py86_file_writelines);

static mp_obj_t py86_file_enter(mp_obj_t self_in) {
    py86_file_t *self = MP_OBJ_TO_PTR(self_in);
    if (self->fp == NULL) mp_raise_OSError(MP_EBADF);
    return self_in;
}
static MP_DEFINE_CONST_FUN_OBJ_1(py86_file_enter_obj, py86_file_enter);

static void py86_file_attr(mp_obj_t self_in, qstr attr, mp_obj_t *dest) {
    if (dest[0] != MP_OBJ_NULL) return;
    if (attr == MP_QSTR_closed) {
        py86_file_t *self = MP_OBJ_TO_PTR(self_in);
        dest[0] = mp_obj_new_bool(self->fp == NULL);
    } else {
        /* Let MicroPython continue searching the type's locals_dict for
         * normal methods such as __exit__, read, write, and close. */
        dest[1] = MP_OBJ_SENTINEL;
    }
}

static const mp_rom_map_elem_t py86_file_locals_table[] = {
    { MP_ROM_QSTR(MP_QSTR_read), MP_ROM_PTR(&mp_stream_read_obj) },
    #if PY86_FAST_READLINE
    { MP_ROM_QSTR(MP_QSTR_readline), MP_ROM_PTR(&py86_file_readline_obj) },
    { MP_ROM_QSTR(MP_QSTR_readlines), MP_ROM_PTR(&py86_file_readlines_obj) },
    #else
    { MP_ROM_QSTR(MP_QSTR_readline), MP_ROM_PTR(&mp_stream_unbuffered_readline_obj) },
    { MP_ROM_QSTR(MP_QSTR_readlines), MP_ROM_PTR(&mp_stream_unbuffered_readlines_obj) },
    #endif
    { MP_ROM_QSTR(MP_QSTR_readinto), MP_ROM_PTR(&mp_stream_readinto_obj) },
    { MP_ROM_QSTR(MP_QSTR_write), MP_ROM_PTR(&mp_stream_write_obj) },
    { MP_ROM_QSTR(MP_QSTR_writelines), MP_ROM_PTR(&py86_file_writelines_obj) },
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
    #if PY86_FAST_READLINE
    MP_TYPE_FLAG_ITER_IS_ITERNEXT,
    iter, py86_file_iternext,
    #else
    MP_TYPE_FLAG_ITER_IS_STREAM,
    #endif
    protocol, &py86_file_text_stream,
    locals_dict, &py86_file_locals,
    attr, py86_file_attr
    );

static MP_DEFINE_CONST_OBJ_TYPE(
    py86_type_binaryfile,
    MP_QSTR_BinaryFile,
    #if PY86_FAST_READLINE
    MP_TYPE_FLAG_ITER_IS_ITERNEXT,
    iter, py86_file_iternext,
    #else
    MP_TYPE_FLAG_ITER_IS_STREAM,
    #endif
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
