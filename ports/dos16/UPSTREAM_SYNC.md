# Upstream reconciliation

Upstream master at `b9620707e3697def3d8829a365aa0c863a69974e` is merged into the repository history, including all 58 commits outstanding at the time of reconciliation. Changes to retained upstream paths are incorporated; previously removed non-DOS ports and upstream CI workflows remain removed (including new files in those areas). The DOS release still explicitly checks out MicroPython 1.29.0 at `0fd6c573ea815774668bbb16b8e197c8822368b2` and uses the established DOS patches, not the repository's updated upstream source snapshot.

The production build selectively backports the three correctness fixes plus [JSON string run printing](https://github.com/micropython/micropython/commit/8901bf220e0cebd6cda9494b1dc328e79c5c1cec), explicitly enabled in the DOS port configuration. The geometric vstr growth optimization is not enabled in production. The validation workflow compares original and optimized JSON serialization at a 48,000-byte heap and checks escaping, Unicode, round trips and allocation/GC behavior at 24,000/48,000/60,000-byte heaps. Emulator measurements are not real hardware benchmarks.

Preserved exclusions (upstream paths):

- `.github/actions/setup_esp32/action.yml`
- `.github/workflows/biome.yml`
- `.github/workflows/code_formatting.yml`
- `.github/workflows/code_size_comment.yml`
- `.github/workflows/codespell.yml`
- `.github/workflows/commit_formatting.yml`
- `.github/workflows/docs.yml`
- `.github/workflows/mpremote.yml`
- `.github/workflows/ports_esp32.yml`
- `.github/workflows/ports_stm32.yml`
- `.github/workflows/ports_unix.yml`
- `.github/workflows/ports_windows.yml`
- `.github/workflows/ports_zephyr.yml`
- `.github/workflows/ruff.yml`
- `ports/alif/alif.mk`
- `ports/alif/machine_uart.c`
- `ports/esp32/README.md`
- `ports/esp32/boards/ESP32_GENERIC/mpconfigvariant_D2WD.cmake`
- `ports/esp32/boards/sdkconfig.p4_wifi_common`
- `ports/esp32/lockfiles/dependencies.lock.esp32`
- `ports/esp32/lockfiles/dependencies.lock.esp32c2`
- `ports/esp32/lockfiles/dependencies.lock.esp32c3`
- `ports/esp32/lockfiles/dependencies.lock.esp32c5`
- `ports/esp32/lockfiles/dependencies.lock.esp32c6`
- `ports/esp32/lockfiles/dependencies.lock.esp32h2`
- `ports/esp32/lockfiles/dependencies.lock.esp32p4`
- `ports/esp32/lockfiles/dependencies.lock.esp32s2`
- `ports/esp32/lockfiles/dependencies.lock.esp32s3`
- `ports/esp32/machine_i2c_target.c`
- `ports/esp32/main.c`
- `ports/esp32/main/idf_component.yml`
- `ports/esp32/network_wlan.c`
- `ports/esp8266/Makefile`
- `ports/nrf/Makefile`
- `ports/rp2/CMakeLists.txt`
- `ports/rp2/Makefile`
- `ports/rp2/modules/_boot.py`
- `ports/rp2/modules/_boot_fat.py`
- `ports/samd/Makefile`
- `ports/stm32/Makefile`
- `ports/webassembly/Makefile`
- `ports/webassembly/README.md`
- `.github/workflows/ports_pic16bit.yml`
- `ports/esp32/boards/ESP32_GENERIC/manifest_d2wd.py`
- `ports/webassembly/variants/browser/npm/README.md`
- `ports/webassembly/variants/browser/npm/package.json`
