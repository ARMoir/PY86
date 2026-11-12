"""Isolated P29OPT/1KA GC experiment. No production sources are committed."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
from zipfile import ZipFile

REPO = Path(__file__).resolve().parents[2]
PORT = REPO / 'ports/dos16'
OUT = PORT / 'build/gc129'
SHA = '0fd6c573ea815774668bbb16b8e197c8822368b2'


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Source drift: ' + old[:100])
    return text.replace(old, new, 1)


def patch_gc(text):
    start = text.index('void gc_collect_root(void **ptrs, size_t len) {')
    end = text.index('\n}\n', start) + 3
    original = text[start:end]
    helper = replace_once(original,
        'void gc_collect_root(void **ptrs, size_t len)',
        'void py86_gc_collect_root_words(void *start, size_t bytes)')
    helper = replace_once(helper,
        '    for (size_t i = 0; i < len; i++) {\n'
        '        MICROPY_GC_HOOK_LOOP(i);\n'
        '        void *ptr = gc_get_ptr(ptrs, i);',
        '    // Same overlapping four-byte windows as the DOS single-root loop.\n'
        '    // Never read a partial far pointer at the end of the range.\n'
        '    byte *cursor = (byte *)start;\n'
        '    for (; bytes >= sizeof(void *); bytes -= 2, cursor += 2) {\n'
        '        MICROPY_GC_HOOK_LOOP(0);\n'
        '        void *ptr = gc_get_ptr((void **)cursor, 0);')
    declaration = 'void py86_gc_collect_root_words(void *start, size_t bytes);\n\n'
    text = replace_once(text, 'void gc_collect_start(void) {',
                        declaration + 'void gc_collect_start(void) {')
    text = replace_once(text, original, original + '\n' + helper)
    return replace_once(text,
        '    for (size_t off = root_start; off + sizeof(void *) <= root_end; off += 2) { gc_collect_root((void **)((char *)ptrs + off), 1); }',
        '    py86_gc_collect_root_words((byte *)ptrs + root_start, root_end - root_start);')


def patch_main(text):
    text = replace_once(text, 'void gc_collect(void) {',
        'extern void py86_gc_collect_root_words(void *start, size_t bytes);\n\nvoid gc_collect(void) {')
    return replace_once(text,
        '    for (p = (char *)&regs; p + sizeof(void *) <= stack_top; p += 2) {\n'
        '        void *root;\n'
        '        memcpy(&root, p, sizeof(root));\n'
        '        gc_collect_root(&root, 1);\n'
        '    }',
        '    p = (char *)&regs;\n'
        '    if (p < stack_top) {\n'
        '        py86_gc_collect_root_words(p, (size_t)(stack_top - p));\n'
        '    }')


def run(*args, log=None):
    command = [str(x) for x in args]
    if log:
        with (OUT / log).open('w') as stream:
            result = subprocess.run(command, cwd=REPO, stdout=stream, stderr=subprocess.STDOUT)
        if result.returncode:
            print((OUT / log).read_text(errors='replace')[-16000:])
            raise RuntimeError('Failed: ' + ' '.join(command))
    else:
        subprocess.run(command, cwd=REPO, check=True)


def selftest():
    # Exhaust every possible DOS size, including empty/partial/trailing windows.
    for size in range(65536):
        old_count = len(range(0, max(0, size - 3), 2))
        new_count = 0 if size < 4 else (size - 4) // 2 + 1
        assert old_count == new_count
        if new_count:
            assert 2 * (new_count - 1) + 4 <= size
    print('PASS all 65536 root-window lengths; four-byte roots, two-byte stride')


PROBE = r'''
// Test-only executable: called after gc_init and BEFORE mp_init.
// No stack/context roots participate: the only root is the supplied byte range.
int py86_gc_root_probe(void) {
    unsigned short storage[12];
    byte *range = (byte *)storage;
    size_t offset, length;
    mp_state_mem_area_t *area = &MP_STATE_MEM(area);
    if (sizeof(void *) != 4) return 10;
    for (offset = 0; offset <= 16; offset += 2) {
        for (length = 0; length <= 20; length++) {
            void *parent = gc_alloc(16, 0);
            void *child = gc_alloc(16, 0);
            size_t parent_block, child_block;
            int expected = length >= offset + sizeof(void *);
            if (!parent || !child) return 11;
            memset(parent, 0, 16);
            memset(child, 0, 16);
            memset(range, 0, sizeof(storage));
            // The only child pointer is at +2, not a four-byte boundary.
            memcpy((byte *)parent + 2, &child, sizeof(child));
            memcpy(range + offset, &parent, sizeof(parent));
            parent_block = BLOCK_FROM_PTR(area, parent);
            child_block = BLOCK_FROM_PTR(area, child);
            gc_collect_start_common();
            py86_gc_collect_root_words(range, length);
            if ((ATB_GET_KIND(area, parent_block) == AT_MARK) != expected) return 12;
            if ((ATB_GET_KIND(area, child_block) == AT_MARK) != expected) return 13;
            gc_collect_end();
            // Free retained objects without any conservative roots.
            gc_sweep_all();
        }
    }
    return 0;
}
'''


def native_probe(source, a, mode):
    gc_file, main_file = source / 'py/gc.c', PORT / 'port/main.c'
    saved_gc, saved_main = gc_file.read_bytes(), main_file.read_bytes()
    gc_text = gc_file.read_text()
    if mode == 'base':
        gc_text += '''
void py86_gc_collect_root_words(void *start, size_t bytes) {
    byte *p = (byte *)start;
    for (; bytes >= sizeof(void *); bytes -= 2, p += 2) {
        void *root;
        memcpy(&root, p, sizeof(root));
        gc_collect_root(&root, 1);
    }
}
'''
    try:
        gc_file.write_text(gc_text + PROBE)
        main_text = replace_once(main_file.read_text(), 'int main(int argc, char **argv) {',
            'extern int py86_gc_root_probe(void);\nint main(int argc, char **argv) {')
        main_file.write_text(replace_once(main_text, '    mp_init();', '    return py86_gc_root_probe();\n    mp_init();'))
        run(sys.executable, PORT / 'build.py', '--source', source,
            '--watcom', a.watcom, '--core-version', '1.29.0', '--data-layout', 'far128',
            '--runtime-profile', '--parser-alloc-mode', 'block1024', '--compile-opt', 'all',
            '--only', 'gc,main', log=mode + '-probe-build.log')
        stage = OUT / (mode + '-probe')
        stage.mkdir(exist_ok=True)
        shutil.copy2(PORT / 'build/py86.exe', stage / 'PROBE.EXE')
        (stage / 'PROBE.BAT').write_bytes(b'@echo off\r\nset PY86_HEAP=48000\r\nPROBE\r\nif errorlevel 1 goto fail\r\necho PASS > RESULT.TXT\r\ngoto end\r\n:fail\r\necho FAIL > RESULT.TXT\r\n:end\r\n')
        conf = stage / 'probe.conf'
        conf.write_text('[sdl]\nfullscreen=false\n[dosbox]\nmemsize=1\n[cpu]\ncore=normal\ncpu_cycles=20000\n[autoexec]\nmount c "' + str(stage) + '"\nc:\ncall PROBE.BAT\nexit\n')
        run(a.dosbox, '--conf', conf, '--noprimaryconf', '--nolocalconf', log=mode + '-probe.log')
        assert (stage / 'RESULT.TXT').read_text().strip() == 'PASS', 'Native root alignment/partial-range probe failed'
        print('PASS ' + mode + ': 189 native root/child alignment and boundary cases')
    finally:
        gc_file.write_bytes(saved_gc)
        main_file.write_bytes(saved_main)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--watcom', type=Path, required=True)
    p.add_argument('--dosbox', required=True)
    a = p.parse_args()
    source = a.source.resolve()
    assert subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip() == SHA
    OUT.mkdir(parents=True, exist_ok=True)
    selftest()
    gc_file, main_file = source / 'py/gc.c', PORT / 'port/main.c'
    gc_original, main_original = gc_file.read_bytes(), main_file.read_bytes()
    patched_gc = patch_gc(gc_original.decode().replace('\r\n', '\n'))
    patched_main = patch_main(main_original.decode().replace('\r\n', '\n'))
    profile_script = PORT / 'run_gc129_profile.py'
    if profile_script.exists():
        raise RuntimeError('Refusing to overwrite an existing temporary profile runner')
    # Use the existing verifier unchanged, at 1/10 speed to reduce BIOS-tick
    # quantisation. The generated runner is never a production source change.
    profile_script.write_text((PORT / 'run_compile_lab.py').read_text().replace('20000', '2000'))
    (OUT / 'candidate-gc.c').write_text(patched_gc)
    (OUT / 'candidate-main.c').write_text(patched_main)
    try:
        for mode, exe in [('base', 'P29OPT.EXE'), ('batch', 'P29GC.EXE')]:
            if mode == 'batch':
                gc_file.write_text(patched_gc)
                main_file.write_text(patched_main)
            run(sys.executable, PORT / 'build.py', '--source', source,
                '--watcom', a.watcom, '--core-version', '1.29.0',
                '--data-layout', 'far128', '--runtime-profile',
                '--parser-alloc-mode', 'block1024', '--compile-opt', 'all',
                log=mode + '-build.log')
            shutil.copy2(PORT / 'build/py86.exe', OUT / exe)
            shutil.copy2(PORT / 'build/py86.map', OUT / (mode + '.map'))
            run(sys.executable, PORT / 'run_dos.py', '--dosbox', a.dosbox,
                '--emulator', 'staging', '--core-version', '1.29.0', '--timeout', '360',
                log=mode + '-regression.log')
            shutil.copy2(PORT / 'build/test-results.json', OUT / (mode + '-regression.json'))
            shutil.copytree(PORT / 'dos-test', OUT / (mode + '-regression'),
                            ignore=shutil.ignore_patterns('*.EXE'), dirs_exist_ok=True)
            native_probe(source, a, mode)
        # Alternate order to expose run-order effects. Six independent DOS sessions.
        for trial in range(3):
            for mode in (('base', 'batch') if trial % 2 == 0 else ('batch', 'base')):
                exe = 'P29OPT.EXE' if mode == 'base' else 'P29GC.EXE'
                for dest in (PORT / 'build/py86.exe', PORT / 'dos-test/PY86.EXE'):
                    shutil.copy2(OUT / exe, dest)
                name = 'gc129-' + mode + '-' + str(trial)
                run(sys.executable, profile_script, '--dosbox', a.dosbox,
                    '--emulator', 'staging', '--timeout', '360', '--parser-stress',
                    '--runtime-stress', '--mode', name, log=name + '.log')
                shutil.copy2(PORT / ('build/compile-profile-' + name + '.json'), OUT / (name + '.json'))
                for item in ('PDEM1.OUT', 'PDEM2.OUT', 'RUNTST.OUT', 'PSTRES.OUT'):
                    shutil.copy2(PORT / 'dos-test' / item, OUT / (name + '-' + item))
        summarize()
    finally:
        gc_file.write_bytes(gc_original)
        main_file.write_bytes(main_original)
        profile_script.unlink()


def summarize():
    data = {mode: [json.loads((OUT / ('gc129-' + mode + '-' + str(i) + '.json')).read_text())
                   for i in range(3)] for mode in ('base', 'batch')}
    report = {'baseline': 'P29OPT: 1.29.0 / 1KA / far128 / runtime-profile',
              'core_sha': SHA, 'environment': 'DOSBox Staging 0.83 normal core, fixed 2000 cycles; NOT V20 hardware timing',
              'native_root_probe_cases_per_build': 189,
              'samples': {}, 'hardware_test_qualified': False}
    gates = []
    expected_samples = {'PDEM1.OUT', 'PDEM2.OUT', 'PCLK.OUT', 'PSHOW.OUT', 'PSTRES.OUT', 'RUNTST.OUT'}
    for profiles in data.values():
        for profile in profiles:
            assert set(profile['samples']) == expected_samples
    for sample in data['base'][0]['samples']:
        rows = {m: [d['samples'][sample] for d in data[m]] for m in data}
        metrics = {}
        for name in ('gc_ms', 'gc_calls', 'free_pre', 'free_post'):
            metrics[name] = {m: [r['runtime'][name] for r in rows[m]] for m in rows}
        for name in ('exec_ms', 'startup_total_ms'):
            metrics[name] = {m: [r[name] for r in rows[m]] for m in rows}
        base_gc, new_gc = (statistics.median(metrics['gc_ms'][m]) for m in ('base', 'batch'))
        metrics['gc_gain_percent'] = 100 * (base_gc - new_gc) / base_gc if base_gc else 0
        # Small conservative-root layout changes may affect retention. Report them;
        # do not qualify a speedup obtained by doing fewer collections.
        same_calls = metrics['gc_calls']['base'] == metrics['gc_calls']['batch']
        same_heap = all(metrics[n]['base'] == metrics[n]['batch'] for n in ('free_pre', 'free_post'))
        no_slowdown = statistics.median(metrics['exec_ms']['batch']) <= statistics.median(metrics['exec_ms']['base']) + 55
        combined = {m: statistics.median(r['exec_ms'] + r['startup_total_ms'] for r in rows[m]) for m in rows}
        gates.append(same_calls and same_heap and no_slowdown and combined['batch'] <= combined['base'] + 55)
        # RUNTST deliberately performs no GC: require no regression there,
        # not an impossible GC speedup from a zero-duration measurement.
        if sample in ('PDEM1.OUT', 'PDEM2.OUT'):
            gates.append(base_gc - new_gc >= 110
                         and metrics['gc_gain_percent'] >= 5
                         and max(metrics['gc_ms']['batch']) < min(metrics['gc_ms']['base'])
                         and min(metrics['exec_ms']['base']) - max(metrics['exec_ms']['batch']) >= 110)
        report['samples'][sample] = metrics
    report['hardware_test_qualified'] = all(gates)
    report['executables'] = {n: {'bytes': (OUT / n).stat().st_size,
        'sha256': hashlib.sha256((OUT / n).read_bytes()).hexdigest()} for n in ('P29OPT.EXE', 'P29GC.EXE')}
    (OUT / 'results.json').write_text(json.dumps(report, indent=2))
    lines = ['P29OPT/1KA only: batched two-byte root scanning', '', report['environment'], '']
    for n, row in report['samples'].items():
        lines.append(n + ': GC ms base=' + str(row['gc_ms']['base']) + ' candidate=' + str(row['gc_ms']['batch']) +
                     '; median gain %.2f%%' % row['gc_gain_percent'])
    lines.append('\nHardware test qualified: ' + str(report['hardware_test_qualified']))
    (OUT / 'RESULTS.txt').write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines))
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as f:
            f.write('\n'.join(lines) + '\n')
    # Only offer a hardware package after all regression and performance gates pass.
    if report['hardware_test_qualified']:
        batch = '@echo off\r\nset PY86_PROFILE=1\r\nset PY86_HEAP=48000\r\nset PY86_PREEXEC_GC=\r\nP29OPT DEMO.PY > BASE.LOG\r\nif errorlevel 1 goto fail\r\nP29GC DEMO.PY > GC.LOG\r\nif errorlevel 1 goto fail\r\necho Done. Return BASE.LOG and GC.LOG.\r\ngoto end\r\n:fail\r\necho FAILED - retain both logs.\r\n:end\r\n'
        with ZipFile(OUT / 'P29GC-AB.zip', 'w') as z:
            for n in ('P29OPT.EXE', 'P29GC.EXE', 'RESULTS.txt', 'results.json'):
                z.write(OUT / n, n)
            z.write(PORT / 'examples/DEMO.PY', 'DEMO.PY')
            z.writestr('RUNGC.BAT', batch)
            z.writestr('README.TXT', 'Experimental 1.29.0 / 1KA GC A-B only.\r\nExtract to a separate directory on your existing DOS drive.\r\nRun RUNGC once and return BASE.LOG and GC.LOG.\r\nDo not replace stable PY86.EXE. DOSBox gain is not a V20 measurement.\r\n')


if __name__ == '__main__':
    main()
