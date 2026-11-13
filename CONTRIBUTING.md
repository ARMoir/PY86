# Contributing to Py86

This repository is maintained as an independent **Py86** project targeting 16-bit MS-DOS and 8086/8088/NEC V20 systems. We are not preparing an upstream MicroPython port submission.

For bug reports, include the Py86 version (`PY86 -V`), DOS version, CPU/memory configuration, steps to reproduce, expected and actual behavior, and whether the issue reproduces under DOSBox. For performance regressions, provide repeatable A/B timings on the same hardware when possible.

Please scope pull requests to `ports/dos16/`, its tests and tooling, or changes that are demonstrably required for the DOS port. Keep the core MicroPython source compatible with the pinned upstream version and preserve existing license and contributor notices. Changes to the production interpreter need to pass the DOSBox integration suite and relevant GC/VM safety tests.

See [README.md](README.md), [ports/dos16/README.md](ports/dos16/README.md) and [CODECONVENTIONS.md](CODECONVENTIONS.md) for project documentation and the inherited MicroPython core conventions.
