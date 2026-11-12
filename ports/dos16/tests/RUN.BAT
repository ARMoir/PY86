@echo off
py86 SMOKE.PY > SMOKE.OUT
if errorlevel 1 goto fail
py86 METHOD.PY > METHOD.OUT
if errorlevel 1 goto fail
py86 CORE.PY > CORE.OUT
if errorlevel 1 goto fail
py86 GC.PY > GC.OUT
if errorlevel 1 goto fail
py86 COUNT16.PY > COUNT16.OUT
if errorlevel 1 goto fail
py86 ROBUST.PY > ROBUST.OUT
if errorlevel 1 goto fail
py86 BADSYNT.PY > BADSYNT.OUT
if not errorlevel 1 goto fail
if errorlevel 2 goto fail
py86 -c "print('PASS after_parse_error')" > RECOV.OUT
if errorlevel 1 goto fail
set PY86_HEAP=48000
py86 --heap-info > MEM48.OUT
if errorlevel 1 goto fail
set PY86_HEAP=24000
py86 --heap-info > MEM24.OUT
if errorlevel 1 goto fail
set PY86_HEAP=60000
py86 --heap-info > MEM60.OUT
if errorlevel 1 goto fail
set PY86_HEAP=
set PY86_HEAP_MAX=32000
py86 --heap-info > MEMCAP.OUT
if errorlevel 1 goto fail
set PY86_HEAP_MAX=
py86 --heap-info > MEMAUTO.OUT
if errorlevel 1 goto fail
py86 MEMSIZE.PY > MEMSIZE.OUT
if errorlevel 1 goto fail
set PY86_HEAP=72000
py86 --heap-info > MEMBAD.OUT
if not errorlevel 2 goto fail
if errorlevel 3 goto fail
set PY86_HEAP=

py86 INPUT.PY < INPUT.IN > INPUT.OUT
if errorlevel 1 goto fail
py86 < REPL.IN > REPL.OUT
if errorlevel 1 goto fail
py86 CLOCKAPI.PY > CLOCKAPI.OUT
if errorlevel 1 goto fail
py86 --home-cls CLKTEST.PY > CLOCK.OUT
if errorlevel 1 goto fail
echo scratch> P86TMP.TXT
py86 LIBTEST.PY > LIBTEST.OUT
if errorlevel 1 goto fail
py86 MODTEST.PY > MODTEST.OUT
if errorlevel 1 goto fail
py86 ONECLK.PY > ONECLK.OUT
if errorlevel 1 goto fail
start86 py86 DEMO.PY > DEMO.OUT
if errorlevel 1 goto fail
py86 SHOW.PY > SHOW.OUT
if errorlevel 1 goto fail
py86 LOOKUP.PY > LOOKUP.OUT
if errorlevel 1 goto fail
py86 STRHASH.PY > STRHASH.OUT
if errorlevel 1 goto fail
py86 HELP.PY > HELP.OUT
if errorlevel 1 goto fail
py86 FILEIO.PY > FILEIO.OUT
if errorlevel 1 goto fail
py86 FILEMORE.PY > FILEMORE.OUT
if errorlevel 1 goto fail
py86 ARGS.PY alpha beta > ARGS.OUT
if errorlevel 1 goto fail
py86 -c "import sys;assert sys.argv==['-c','one','two'];print('PASS command_argv')" one two > CARGS.OUT
if errorlevel 1 goto fail
py86 --help > CLIHELP.OUT
if errorlevel 1 goto fail
py86 -h > HELPFLAG.OUT
if errorlevel 1 goto fail
py86 -V > VERSION.OUT
if errorlevel 1 goto fail
py86 --version > VERNAME.OUT
if errorlevel 1 goto fail
py86 -c > CMISS.OUT
if not errorlevel 2 goto fail
if errorlevel 3 goto fail
set PY86_TEST_CTRLC=1
py86 CTRLC.PY > CTRLC.OUT
if errorlevel 1 goto fail
py86 CTRLSLP.PY > CTRLSLP.OUT
if errorlevel 1 goto fail
set PY86_TEST_CTRLC=
py86 ERROR.PY > ERROR.OUT
if not errorlevel 1 goto fail

py86 EXCATCH.PY > EXCATCH.OUT
if errorlevel 1 goto fail
py86 EXIT0.PY > EXIT0.OUT
if errorlevel 1 goto fail
py86 QUIT0.PY > QUIT0.OUT
if errorlevel 1 goto fail
py86 SYSEX0.PY > SYSEX0.OUT
if errorlevel 1 goto fail
py86 SYSEX7.PY > SYSEX7.OUT
if not errorlevel 7 goto fail
if errorlevel 8 goto fail
py86 SYSEX9.PY > SYSEX9.OUT
if not errorlevel 9 goto fail
if errorlevel 10 goto fail
py86 SYSEXTXT.PY > SYSEXTXT.OUT
if not errorlevel 1 goto fail
if errorlevel 2 goto fail
py86 EXNEG.PY > EXNEG.OUT
if not errorlevel 255 goto fail
py86 < REPLEX.IN > REPLEX.OUT
if errorlevel 1 goto fail
py86 < REPLCODE.IN > REPLCODE.OUT
if not errorlevel 6 goto fail
if errorlevel 7 goto fail
echo PASS > RESULT.TXT
goto end
:fail
echo FAIL > RESULT.TXT
:end
