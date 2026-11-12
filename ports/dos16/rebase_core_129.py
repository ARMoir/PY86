"""Adapt v1.24.1 DOS core rejected hunks for the pinned v1.29.0 source.
Only run after prepare_source_129.py on an isolated checkout.
"""
from pathlib import Path
import re

EXPECTED = {
    "py/binary.c", "py/formatfloat.c", "py/gc.c", "py/misc.h",
    "py/objint.c", "py/objint_longlong.c", "py/objlist.c",
    "py/parsenum.c", "py/runtime.h", "py/stream.c",
}

def one(s, old, new):
    if old not in s:
        if new in s:
            return s
        raise ValueError("Unexpected upstream source, expected: "+old[:95])
    return s.replace(old, new)

def binary(s):
    s=one(s, "fpu.i = ((hf & 0x8000u) << 16) | (e << 23) | (m << 13);",
        "fpu.i = (((uint32_t)hf & 0x8000UL) << 16) | ((uint32_t)e << 23) | ((uint32_t)m << 13);")
    s=one(s, "} fpu = { .i = hf };", "} fpu; fpu.i = hf;")
    s=one(s, "} fpu = { .f = x };", "} fpu; fpu.f = x;")
    return one(s, "} fpu = {val};", "} fpu; fpu.i = val;")

def formatfloat(s):
    regex=re.compile(r"mp_float_union_t\s+([A-Za-z_]\w*)\s*=\s*\{\s*([A-Za-z_]\w*)\s*\};")
    if len(regex.findall(s))<2:
        raise ValueError("Unexpected float union initializers")
    return regex.sub(lambda m:"mp_float_union_t "+m[1]+"; "+m[1]+".f = "+m[2]+";",s)

def gc(s):
    return one(s,"(~(BYTES_PER_BLOCK - 1))","(~((uintptr_t)BYTES_PER_BLOCK - 1))")

def misc(s):
    return one(s,"#if defined(_MSC_VER) || defined(__cplusplus)\n#define MP_STATIC_ASSERT_NONCONSTEXPR",
        "#if defined(_MSC_VER) || defined(__cplusplus) || defined(__WATCOMC__)\n#define MP_STATIC_ASSERT_NONCONSTEXPR")

def objint(s):
    before=s
    for name in ("MP_FLOAT_SIGN_SHIFT_I32","MP_FLOAT_EXP_BITS","MP_FLOAT_EXP_SHIFT_I32"):
        s=s.replace("1U << "+name,"1UL << "+name)
    s=s.replace("8 * sizeof(uintptr_t) + MP_FLOAT_EXP_BIAS","8UL * sizeof(uintptr_t) + MP_FLOAT_EXP_BIAS")
    if before==s:
        raise ValueError("No unsafe small-int shifts discovered")
    return s

def labels(s, names):
    for label in names:
        regex=r"(?m)^("+re.escape(label)+r":)\s*$"
        s,n=re.subn(regex,r";\n\1",s,count=1)
        if n!=1:
            raise ValueError("Expected numerical parser label "+label)
    return s

def objint_ll(s):
    return labels(s,("zero_division",))

def objlist(s):
    return one(s,"mp_obj_t args[2] = {self_in, index};",
               "mp_obj_t args[2]; args[0] = self_in; args[1] = index;")

def parsenum(s):
    return labels(s,("have_ret_val","overflow","value_error"))

def runtime(s):
    if "nlr_jump_callback_node_call_function_1_t ctx; \\" not in s:
        raise ValueError("Expected upstream callback declaration")
    return s

def stream(s):
    return one(s,"const mp_obj_t args[3] = {self, offset, whence};",
               "mp_obj_t args[3]; args[0] = self; args[1] = offset; args[2] = whence;")

TRANSFORMS = {
    "py/binary.c":binary,"py/formatfloat.c":formatfloat,
    "py/gc.c":gc,"py/misc.h":misc,"py/objint.c":objint,
    "py/objint_longlong.c":objint_ll,"py/objlist.c":objlist,
    "py/parsenum.c":parsenum,"py/runtime.h":runtime,"py/stream.c":stream,
}

def adapt_new_core(root:Path):
    # 1.29 moved labels after local declarations; Watcom's mixed C99
    # syntax rejects labels unless a statement precedes them.
    src=root/"py/lexer.c"
    data=src.read_text()
    data=one(data,"\nfetch_next_byte:\n","\n;\n;\n;\n;\n;\n;\nfetch_next_byte:\n")
    src.write_text(data)

    src=root/"py/formatfloat.c"
    data=src.read_text()
    data=one(data,"\ntry_again:\n    ;\n","\n;\n;\n;\n;\n;\n;\ntry_again:\n    ;\n")
    src.write_text(data)

    src=root/"py/parsenum.c"
    data=src.read_text()
    data=one(data,"mp_float_union_t res = {num};",
             "mp_float_union_t res; res.f = num;")
    src.write_text(data)

    src=root/"py/vm.c"
    data=src.read_text()
    old="mp_obj_slice_t slice = { .base = { .type = &mp_type_slice }, .start = start, .stop = stop, .step = step };"
    new=("mp_obj_slice_t slice; slice.base.type = &mp_type_slice; "
         "slice.start = start; slice.stop = stop; slice.step = step;")
    data=one(data,old,new)
    src.write_text(data)
    for item in ("py/lexer.c","py/formatfloat.c","py/parsenum.c","py/vm.c"):
        print("REBASED 1.29 new core",item,flush=True)


def rebase(root:Path, report:Path):
    root=root.resolve()
    report.mkdir(parents=True,exist_ok=True)
    rejected={str(p.relative_to(root))[:-4] for p in root.rglob("*.rej")}
    if rejected != EXPECTED:
        raise ValueError("Unexpected 1.29 rejected hunks: missing="+str(EXPECTED-rejected)+
                         " unknown="+str(rejected-EXPECTED))
    results=[]
    for name in sorted(rejected):
        p=root/name
        old=p.read_text()
        new=TRANSFORMS[name](old)
        if old==new and name!="py/runtime.h":
            raise ValueError("Did not rebase "+name)
        p.write_text(new)
        (root/(name+".rej")).unlink()
        results.append(name)
        print("REBASED",name,flush=True)
    adapt_new_core(root)
    (report/"rebased-files.txt").write_text("\n".join(results)+"\n")
    return results
