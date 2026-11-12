"""Build the pinned MicroPython core with Open Watcom C16 on Windows.
Usage: python build.py --source PATH --watcom PATH
"""
import argparse
import os
from pathlib import Path
import re
import subprocess
import sys
import shutil
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parent
p = argparse.ArgumentParser()
p.add_argument('--source', type=Path, required=True)
p.add_argument('--watcom', type=Path, required=True)
p.add_argument('--core-version', choices=('1.24.1','1.29.0'), default='1.24.1',
               help='Pinned upstream MicroPython core; sets accurate DOS version text')
p.add_argument('--only', default='')
p.add_argument('--string-mode', choices=('original', 'char-cache', 'lazy-hash', 'both'),
               default='both', help='String optimization (production default: both)')
p.add_argument('--resume', action='store_true')
p.add_argument('--parser-alloc-mode',
               choices=('original', 'block512', 'block1024', 'block2048', 'geometric'),
               default='original',
               help='Opt-in parser syntax-tree arena strategy; requires parser_allocator_lab.py')
p.add_argument('--parse-chunk', type=int, choices=(16, 32, 64, 128),
               default=16, help='Initial parse allocation chunk; opt-in benchmark')
p.add_argument('--compile-opt', choices=('baseline', 'loop', 'intrinsic', 'all'),
               default='baseline', help='Optimize lexer/parser/compiler C files only')
p.add_argument('--source-loader', choices=('original', 'direct'), default='original',
               help='DOS source file loader; direct is experimental')
p.add_argument('--profile-compile', action='store_true',
               help='Include opt-in BIOS-tick compile timing, enabled by PY86_PROFILE=1')
p.add_argument('--runtime-profile', action='store_true',
               help='Log GC collections and memory around Python execution; includes compile profile')
p.add_argument('--vm-fault-probe', action='store_true',
               help='Also build test-only PY86F.EXE with bytecode fault injection (never release)')
p.add_argument('--data-layout',
               choices=('production', 'far128', 'hotstate', 'medium'),
               default='production',
               help='Experimental DOS memory placement; production remains -ml/-zt=256')
p.add_argument('--file-readline-mode', choices=('generic', 'fast'), default='generic',
               help='DOS file.readline implementation (default: generic; fast is experimental)')
p.add_argument('--vm-mode', choices=('baseline', 'fast-decode', 'compiler', 'far128', 'near384', 'combined',
                                     'inline', 'intrinsic', 'loop', 'reopt'),
               default='baseline', help='8086 VM dispatch, compiler and near/far data experiment')
p.add_argument('--lookup-mode', choices=('off', 'map', 'attr', 'both'),
               default='map', help='Lookup optimizations (production default: map)')
args = p.parse_args()
src = args.source.resolve()
wat = args.watcom.resolve()
build = ROOT / 'build'
gen = build / 'genhdr'
gen.mkdir(parents=True, exist_ok=True)
# Each release build stamps the exact version into the native 16-bit program.
# Local builds default to an explicitly unreleased .0 development number.
version = os.environ.get('PY86_VERSION') or datetime.now(timezone.utc).strftime('0.%y.%m.0')
if not re.fullmatch(r'0\.\d{2}\.(?:0[1-9]|1[0-2])\.\d+', version):
    raise SystemExit('PY86_VERSION must be 0.YY.MM.increment (e.g. 0.26.11.42)')
(build / 'py86-version.h').write_text(
    '#ifndef PY86_VERSION\n#define PY86_VERSION "' + version + '"\n#endif\n',
    encoding='ascii')
(build / 'py86-version.txt').write_text(version + '\n', encoding='ascii')
print('Py86 version:', version, 'data layout:', args.data_layout, flush=True)
env = dict(os.environ, WATCOM=str(wat), INCLUDE=str(wat / 'h'))
toolbin = wat / ('binnt64' if os.name == 'nt' else 'binl64')
exesuffix = '.exe' if os.name == 'nt' else ''
env['PATH'] = str(toolbin) + os.pathsep + env['PATH']
# Explicitly set both flags per mode so 'off' remains a true baseline
# even though the port config now enables the map lookup cache by default.
lookup_flags = {
    'off': ['-dMICROPY_OPT_MAP_LOOKUP_CACHE=0',
            '-dMICROPY_OPT_LOAD_ATTR_FAST_PATH=0'],
    'map': ['-dMICROPY_OPT_MAP_LOOKUP_CACHE=1',
            '-dMICROPY_OPT_LOAD_ATTR_FAST_PATH=0'],
    'attr': ['-dMICROPY_OPT_MAP_LOOKUP_CACHE=0',
             '-dMICROPY_OPT_LOAD_ATTR_FAST_PATH=1'],
    'both': ['-dMICROPY_OPT_MAP_LOOKUP_CACHE=1',
             '-dMICROPY_OPT_LOAD_ATTR_FAST_PATH=1'],
}
# All variants remain 8086/V20 compatible. -zt chooses near-DGROUP data threshold.
vm_configs = {
    'baseline': (256, [], 0),
    'fast-decode': (256, [], 1),
    'compiler': (256, ['-oi', '-ol', '-oe', '-oh'], 0),
    'far128': (128, [], 0),
    'near384': (384, [], 0),
    'combined': (256, ['-oi', '-ol', '-oe', '-oh'], 1),
    'inline': (256, ['-oe'], 0),
    'intrinsic': (256, ['-oi'], 0),
    'loop': (256, ['-ol'], 0),
    'reopt': (256, ['-oh'], 0),
}
threshold, vm_optimizations, fast_uint = vm_configs[args.vm_mode]
# Experimental 8086 memory layouts are fully opt-in.  The default leaves
# precisely the existing production -ml/-zt=256 compiler behavior in place.
if args.data_layout != 'production' and args.vm_mode != 'baseline':
    raise SystemExit('--data-layout experiments require --vm-mode baseline')
if args.data_layout in ('far128', 'hotstate'):
    threshold = 128
if args.data_layout == 'hotstate':
    header = (src / 'py' / 'mpstate.h').read_text()
    if 'PY86_HOT_STATE_NEAR' not in header:
        raise SystemExit('Run memory_model_lab.py patch-source on isolated MicroPython source')
flags = ['-q', '-bt=dos', '-0',
         '-mm' if args.data_layout == 'medium' else '-ml',
         '-za99', '-ot', '-s', '-fpc', '-zp2',
         '-zt=' + str(threshold),
         '-dMICROPY_ALLOC_PARSE_CHUNK_INIT=' + str(args.parse_chunk),
         *(['-dPY86_HOT_STATE_NEAR=1'] if args.data_layout == 'hotstate' else []),
         *vm_optimizations,
         '-dPY86_VM_FAST_UINT=' + str(fast_uint),
         '-dPY86_FAST_READLINE=' + ('1' if args.file_readline_mode == 'fast' else '0'),
         *lookup_flags[args.lookup_mode],
         '-dPY86_CHAR_QSTR_CACHE=' + ('1' if args.string_mode in ('char-cache', 'both') else '0'),
         '-dPY86_LAZY_STR_HASH=' + ('1' if args.string_mode in ('lazy-hash', 'both') else '0'),
         '-i=' + str(ROOT / 'port'), '-i=' + str(src), '-i=' + str(build)]

# A/B compiler options apply solely to source-to-bytecode C compilation.
# All runtime/VM .c files remain production-optimized and untouched.
COMPILER_FILES = frozenset(('lexer.c', 'parse.c', 'compile.c', 'emitbc.c', 'qstr.c'))
COMPILE_OPTS = {
    'baseline': [],
    'loop': ['-ol'],
    'intrinsic': ['-oi'],
    'all': ['-oi', '-ol', '-oe', '-oh'],
}

def per_file_flags(c):
    selected = list(flags)
    if c.name in COMPILER_FILES:
        selected.extend(COMPILE_OPTS[args.compile_opt])
    if c.name == 'parse.c' and args.parser_alloc_mode != 'original':
        if 'PY86_PARSER_ALLOC_MODE' not in (src / 'py' / 'parse.c').read_text():
            raise SystemExit('Apply parser_allocator_lab.py to the isolated pinned checkout first')
        selected.append('-dPY86_PARSER_ALLOC_MODE=' + str({
            'block512': 1, 'block1024': 2, 'block2048': 3, 'geometric': 4,
        }[args.parser_alloc_mode]))
    if c.name == 'main.c':
        if args.core_version == '1.29.0':
            selected.append('-dPY86_UPSTREAM_129=1')
        if args.source_loader == 'direct':
            selected.append('-dPY86_SOURCE_DIRECT=1')
        if args.profile_compile or args.runtime_profile:
            selected.append('-dPY86_COMPILE_PROFILE=1')
        if args.runtime_profile:
            selected.append('-dPY86_RUNTIME_PROFILE=1')
    return selected

def run(cmd, output=None):
    cmd[0] = str(toolbin / (cmd[0] + exesuffix)) if cmd[0] in ('wcc', 'wlink') else cmd[0]
    r = subprocess.run([str(x) for x in cmd], cwd=build, env=env, stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT)
    text = r.stdout.decode('utf-8', 'replace').replace('\r\n', '\n')
    if output:
        Path(output).write_text(text, encoding='utf-8')
    if r.returncode:
        print(text[-12000:])
        raise SystemExit(r.returncode)
    return text

def pytool(name, inputs, output):
    return run([sys.executable, src / 'py' / name, *inputs], output)

mk = (src / 'py/py.mk').read_text()
core = mk.split('PY_CORE_O_BASENAME = $(addprefix py/,', 1)[1].split(')', 1)[0]
sources = [src / 'py' / (x + '.c') for x in re.findall(r'(\w+)\.o', core)]
sources += [ROOT / 'port/main.c', ROOT / 'port/moddostime.c', ROOT / 'port/moddatetime.c',
            ROOT / 'port/moddosfile.c',
            src / 'extmod/modrandom.c', src / 'extmod/modjson.c',
            src / 'extmod/modre.c', src / 'extmod/modhashlib.c',
            src / 'shared/readline/readline.c']

if not args.only and not args.resume:
    # Dependency bootstrap: preprocessing does not require C declarations to resolve.
    for name in ['qstrdefs.generated.h', 'moduledefs.h', 'root_pointers.h']:
        (gen / name).write_text('')
    pytool('makeversionhdr.py', [gen / 'mpversion.h'], build / 'version.log')
    pp_parts = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        pp_parts = list(pool.map(lambda c: run(['wcc', *per_file_flags(c), '-dNO_QSTR', '-p', c]), sources))
    pp = '\n'.join(pp_parts)
    (build / 'all.i').write_text(pp)
    qnames = sorted(set(re.findall(r'MP_QSTR_(\w+)', pp)))
    # makeqstrdata knows the inverse escaping map; ordinary identifiers need no decoding.
    sys.path.insert(0, str(src / 'py'))
    import makeqstrdata as qdata
    reverse = {v: chr(k) for k, v in qdata.codepoint2name.items()}
    def unescape(s):
        for k, v in reverse.items():
            s = s.replace('_' + k + '_', v)
        return s
    qbase = run(['wcc', *flags, '-p', src / 'py/qstrdefs.h'])
    qbase += '\n' + '\n'.join('Q(' + x + ')' for x in qnames)
    (build / 'qstr.in').write_text(qbase, encoding='utf-8')
    pytool('makeqstrdata.py', [build / 'qstr.in'], gen / 'qstrdefs.generated.h')
    pytool('makemoduledefs.py', [build / 'all.i'], gen / 'moduledefs.h')
    pytool('make_root_pointers.py', [build / 'all.i'], gen / 'root_pointers.h')

objects = []
failures = []
for c in sources:
    obj = build / (c.stem + '.obj')
    objects.append(obj)
    if args.only and c.stem not in args.only.split(','):
        continue
    if args.resume and obj.exists():
        continue
    print('CC', c.name, flush=True)
    try:
        run(['wcc', *per_file_flags(c), '-fo=' + str(obj), c], build / (c.stem + '.log'))
    except SystemExit:
        failures.append(c.stem)

if failures:
    raise SystemExit('Failed: ' + ','.join(failures))

link = ['system dos', 'option quiet', 'option stack=16384', 'option map=py86.map',
        'name py86.exe', *['file ' + x.name for x in objects]]
(build / 'link.lnk').write_text('\n'.join(link) + '\n')
print(run(['wlink', '@link.lnk'], build / 'link.log'))
print('Built', build / 'py86.exe')

if args.vm_fault_probe:
    # Relink the EXACT production VM/GC objects with only a test-enabled main.
    # This is not included in the DOS user package. It must stay in DOSBox.
    fault_obj = build / 'mainfault.obj'
    run(['wcc', *flags, '-dPY86_TEST_VMFAULT=1',
         '-fo=' + str(fault_obj), ROOT / 'port/main.c'], build / 'mainfault.log')
    fault_objects = [fault_obj.name if obj.name == 'main.obj' else obj.name
                     for obj in objects]
    fault_link = ['system dos', 'option quiet', 'option stack=16384',
                  'option map=py86f.map', 'name py86f.exe',
                  *['file ' + name for name in fault_objects]]
    (build / 'fault-link.lnk').write_text('\n'.join(fault_link) + '\n')
    run(['wlink', '@fault-link.lnk'], build / 'fault-link.log')
    print('Built test-only, unsafe-on-real-hardware', build / 'py86f.exe')

# Optional launcher for timing the DOS child MZ executable load itself.
# It is a small 8086 executable, independent of MicroPython and its heap.
timer_obj = build / 'start86.obj'
run(['wcc', '-q', '-bt=dos', '-0', '-ml', '-ot', '-s',
     '-fo=' + str(timer_obj), ROOT / 'port/start86.c'], build / 'start86.log')
(build / 'start86.lnk').write_text(
    'system dos\noption quiet\noption stack=2048\n'
    'name start86.exe\nfile start86.obj\n', encoding='ascii')
run(['wlink', '@start86.lnk'], build / 'start86-link.log')
print('Built', build / 'start86.exe')




# Datetime is now a registered C module. Remove any leftover old shim after a rebuild.
(build / 'datetime.py').unlink(missing_ok=True)
