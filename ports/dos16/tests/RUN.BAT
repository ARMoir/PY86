@echo off
py86 SMOKE.PY > SMOKE.OUT
if errorlevel 1 goto fail
py86 METHOD.PY > METHOD.OUT
if errorlevel 1 goto fail
py86 CORE.PY > CORE.OUT
if errorlevel 1 goto fail
py86 GC.PY > GC.OUT
if errorlevel 1 goto fail
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
py86 LOOKUP.PY > LOOKUP.OUT
if errorlevel 1 goto fail
py86 STRHASH.PY > STRHASH.OUT
if errorlevel 1 goto fail
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
