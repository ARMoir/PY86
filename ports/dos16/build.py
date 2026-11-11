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
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parent
p = argparse.ArgumentParser()
p.add_argument('--source', type=Path, required=True)
p.add_argument('--watcom', type=Path, required=True)
p.add_argument('--only', default='')
p.add_argument('--string-mode', choices=('original', 'char-cache', 'lazy-hash', 'both'),
               default='both', help='String optimization (production default: both)')
p.add_argument('--resume', action='store_true')
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
flags = ['-q', '-bt=dos', '-0', '-ml', '-za99', '-ot', '-s', '-fpc', '-zp2',
         '-zt=' + str(threshold), *vm_optimizations,
         '-dPY86_VM_FAST_UINT=' + str(fast_uint),
         '-dPY86_FAST_READLINE=' + ('1' if args.file_readline_mode == 'fast' else '0'),
         *lookup_flags[args.lookup_mode],
         '-dPY86_CHAR_QSTR_CACHE=' + ('1' if args.string_mode in ('char-cache', 'both') else '0'),
         '-dPY86_LAZY_STR_HASH=' + ('1' if args.string_mode in ('lazy-hash', 'both') else '0'),
         '-i=' + str(ROOT / 'port'), '-i=' + str(src), '-i=' + str(build)]

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
        pp_parts = list(pool.map(lambda c: run(['wcc', *flags, '-dNO_QSTR', '-p', c]), sources))
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
        run(['wcc', *flags, '-fo=' + str(obj), c], build / (c.stem + '.log'))
    except SystemExit:
        failures.append(c.stem)

if failures:
    raise SystemExit('Failed: ' + ','.join(failures))

link = ['system dos', 'option quiet', 'option stack=16384', 'option map=py86.map',
        'name py86.exe', *['file ' + x.name for x in objects]]
(build / 'link.lnk').write_text('\n'.join(link) + '\n')
print(run(['wlink', '@link.lnk'], build / 'link.log'))
print('Built', build / 'py86.exe')




# Datetime is now a registered C module. Remove any leftover old shim after a rebuild.
(build / 'datetime.py').unlink(missing_ok=True)
