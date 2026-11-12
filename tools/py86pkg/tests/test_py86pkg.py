"""Offline converter tests. Downloaded package code is never executed by py86pkg."""
import ast
import io
import json
import sys
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path, PurePosixPath
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import py86pkg as pkg


class ConverterTests(unittest.TestCase):
    def setUp(self):
        self.profile = json.loads(pkg.DEFAULT_PROFILE.read_text())

    def one(self, code, name="module.py", **kwargs):
        with tempfile.TemporaryDirectory() as temp:
            dst = Path(temp) / "PY86PKG.ZIP"
            report = pkg.convert({PurePosixPath(name): code.encode()},
                                 self.profile, dst, "example", **kwargs)
            with zipfile.ZipFile(dst) as z:
                self.assertIn("REPORT.JSON", z.namelist())
                self.assertIn("README.TXT", z.namelist())
                output = z.read(name).decode()
                self.assertEqual(json.loads(z.read("REPORT.JSON"))["status"], report["status"])
            return report, output

    def test_fstring_and_type_annotations(self):
        code = ("from typing import Optional\n"
                "def greet(name: str, count: int = 2) -> str:\n"
                "    return f'Hello {name!r}: {count}'\n")
        report, output = self.one(code)
        self.assertEqual(report["status"], "candidate_untested_on_dos")
        self.assertNotIn("typing", output)
        namespace = {}
        exec(compile(output, "module.py", "exec"), namespace)
        self.assertEqual(namespace["greet"]("Ada"), "Hello 'Ada': 2")
        self.assertGreater(report["transformations"]["annotations"], 0)

    def test_annotated_field_without_value(self):
        report, output = self.one("x: int = 4\nclass Thing:\n    value: int\n")
        self.assertEqual(report["status"], "candidate_untested_on_dos")
        self.assertIn("x = 4", output)
        ast.parse(output)

    def test_match_is_not_falsely_supported(self):
        report, _ = self.one("def action(x):\n    match x:\n        case 1: return 2\n")
        self.assertEqual(report["status"], "needs_porting")

    def test_format_spec_requires_port(self):
        report, _ = self.one("value = 5\ntext = f'{value:02d}'\n")
        self.assertEqual(report["status"], "needs_porting")

    def test_unsupported_import_and_open(self):
        report, _ = self.one("import requests\nf = open('A.TXT')\n")
        self.assertEqual(report["status"], "needs_porting")
        self.assertTrue({"missing_module", "unsupported_api"}.issubset(
            {x["code"] for x in report["issues"]}))

    def test_dos_83(self):
        report, _ = self.one("x = 1\n", name="longfilename.py")
        self.assertIn("dos_filename", {x["code"] for x in report["issues"]})

    def test_source_limit(self):
        with tempfile.TemporaryDirectory() as temp:
            profile = dict(self.profile, max_source_bytes=3)
            report = pkg.convert({PurePosixPath("ok.py"): b"x = 1\n"},
                                 profile, Path(temp) / "x.zip", "x")
            self.assertIn("source_size", {x["code"] for x in report["issues"]})

    def test_no_execution_of_source(self):
        report, output = self.one("raise RuntimeError('must not execute')\n")
        self.assertEqual(report["status"], "candidate_untested_on_dos")
        self.assertIn("raise RuntimeError", output)

    def test_offline_directory_and_cli(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "src"
            source.mkdir()
            (source / "helper.py").write_text("ANSWER: int = 42\n")
            (source / "setup.py").write_text("raise RuntimeError('not executed')\n")
            sources, _ = pkg.read_local(source)
            self.assertEqual(set(sources), {PurePosixPath("helper.py")})
            out = Path(temp) / "MYLIB.ZIP"
            self.assertEqual(pkg.main(["convert", "--source", str(source),
                                       "--output", str(out)]), 0)
            with zipfile.ZipFile(out) as z:
                self.assertIn("helper.py", z.namelist())
                self.assertNotIn("setup.py", z.namelist())

    def test_zip_slip_is_not_extracted(self):
        src = io.BytesIO()
        with zipfile.ZipFile(src, "w") as z:
            z.writestr("../escape.py", "x = 1")
            z.writestr("safe.py", "y = 2")
            z.writestr("native/fast.so", b"binary")
        sources, native = pkg.read_archive(src.getvalue(), "pkg.whl")
        self.assertEqual(set(sources), {PurePosixPath("safe.py")})
        self.assertEqual(native, ["native/fast.so"])

    def test_tar_links_are_ignored(self):
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tf:
            link = tarfile.TarInfo("bad.py")
            link.type = tarfile.SYMTYPE
            link.linkname = "/etc/passwd"
            tf.addfile(link)
            data = b"x = 1"
            entry = tarfile.TarInfo("pkg-1/good.py")
            entry.size = len(data)
            tf.addfile(entry, io.BytesIO(data))
        source, _ = pkg.read_archive(buf.getvalue(), "pkg.tar")
        self.assertEqual(set(source), {PurePosixPath("good.py")})

    def test_urls_are_pypi_only(self):
        self.assertEqual(pkg.parse_spec("https://pypi.org/project/roman/5.0/"),
                         ("roman", "5.0"))
        for value in ("http://pypi.org/project/roman",
                      "https://evil.example/project/roman",
                      "https://pypi.org/project/../danger"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                pkg.parse_spec(value)

    def test_dependency_is_reported(self):
        report, _ = self.one("x = 1", requirements=["requests>=2"])
        self.assertEqual(report["requires_dist"], ["requests>=2"])
        self.assertIn("dependencies", {x["code"] for x in report["issues"]})


    def test_library_only_roman_shape(self):
        code = (b"import argparse\nimport re\n"
                b"pattern = re.compile(' A{0,4} # comment\\n', re.VERBOSE)\n"
                b"def toRoman(n: int) -> str:\n    return 'A'\n"
                b"def parse_args():\n    return argparse.ArgumentParser()\n"
                b"def main():\n    return parse_args()\n"
                b"if __name__ == '__main__':\n    main()\n")
        with tempfile.TemporaryDirectory() as temp:
            dest = Path(temp) / "roman.zip"
            result = pkg.convert({
                PurePosixPath("roman/__init__.py"): code,
                PurePosixPath("roman/__main__.py"): b"from roman import main\nmain()\n",
            }, self.profile, dest, "roman", "5.2", library_only=True)
            self.assertEqual(result["status"], "candidate_untested_on_dos")
            with zipfile.ZipFile(dest) as archive:
                self.assertEqual(set(archive.namelist()),
                                 {"roman.py", "REPORT.JSON", "README.TXT"})
                source = archive.read("roman.py").decode()
            self.assertNotIn("argparse", source)
            self.assertNotIn("parse_args", source)
            self.assertNotIn("re.VERBOSE", source)
            namespace = {}
            exec(compile(source, "roman.py", "exec"), namespace)
            self.assertTrue(namespace["pattern"].fullmatch("AAA"))
            self.assertFalse(namespace["pattern"].fullmatch("AAAAA"))
            self.assertEqual(result["transformations"]["verbose_regex"], 1)

    def test_no_parseable_file_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "No parseable"):
                pkg.convert({PurePosixPath("bad.py"): b"def wrong(:\n"},
                            self.profile, Path(temp) / "bad.zip", "bad")


if __name__ == "__main__":
    unittest.main()
