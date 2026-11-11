"""Standalone PyPI -> experimental Py86 source converter (host Python 3.10+).

This tool never imports, builds, installs or executes code from downloaded archives.
The generated ZIP is a *candidate*, not a claim of successful DOS execution.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
import re
import sys
import tarfile
import tokenize
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

HERE = Path(__file__).resolve().parent
DEFAULT_PROFILE = HERE / "profiles" / "v20.json"
MAX_DOWNLOAD = 24 * 1024 * 1024
MAX_SOURCE = 2 * 1024 * 1024
MAX_FILES = 4000
KNOWN_NATIVE = {
    "sys", "gc", "math", "random", "os", "time", "datetime",
    "json", "errno", "re", "hashlib", "builtins",
}
DOS_RESERVED = {"CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3",
                "COM4", "LPT1", "LPT2", "LPT3"}


def issue(path, severity, code, detail):
    return {"path": str(path), "severity": severity, "code": code, "detail": detail}


def parse_spec(value, version=None):
    """Accept PyPI project URLs or project names, without arbitrary URL fetches."""
    if value.startswith(("https://", "http://")):
        parts = urllib.parse.urlsplit(value)
        if parts.scheme != "https" or parts.netloc.lower() != "pypi.org":
            raise ValueError("Only https://pypi.org/project/... URLs are accepted")
        sections = [p for p in parts.path.strip("/").split("/") if p]
        if len(sections) not in (2, 3) or sections[0] != "project":
            raise ValueError("Expected https://pypi.org/project/NAME[/VERSION]/")
        name = urllib.parse.unquote(sections[1])
        url_version = urllib.parse.unquote(sections[2]) if len(sections) == 3 else None
        if version and url_version and version != url_version:
            raise ValueError("Conflicting versions in URL and --version")
        version = version or url_version
    else:
        name = value
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name):
        raise ValueError("Invalid PyPI package name")
    if version and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+!-]*", version):
        raise ValueError("Invalid PyPI release version")
    return name, version


def read_url(url, maximum):
    with urllib.request.urlopen(url, timeout=25) as response:
        size = response.headers.get("Content-Length")
        if size and int(size) > maximum:
            raise ValueError("Remote file exceeds size limit")
        data = response.read(maximum + 1)
    if len(data) > maximum:
        raise ValueError("Remote file exceeds size limit")
    return data


def download_release(name, version):
    name_q = urllib.parse.quote(name)
    version_q = "/" + urllib.parse.quote(version) if version else ""
    metadata = json.loads(read_url(
        "https://pypi.org/pypi/" + name_q + version_q + "/json", 4 * 1024 * 1024
    ))
    info = metadata["info"]
    files = metadata.get("urls", [])
    if not files:
        raise ValueError("Release has no downloadable distributions")
    pure_wheels = [x for x in files if x.get("packagetype") == "bdist_wheel"
                   and x.get("filename", "").endswith("-none-any.whl")
                   and ("-py3-" in x["filename"] or "-py2.py3-" in x["filename"])]
    sdists = [x for x in files if x.get("packagetype") == "sdist"]
    choices = pure_wheels or sdists
    if not choices:
        raise ValueError("No pure-Python wheel or source distribution available")
    dist = choices[0]
    url = urllib.parse.urlsplit(dist["url"])
    if url.scheme != "https" or url.hostname != "files.pythonhosted.org":
        raise ValueError("Unexpected distribution download host")
    if dist.get("size", 0) > MAX_DOWNLOAD:
        raise ValueError("Distribution is too large")
    data = read_url(dist["url"], MAX_DOWNLOAD)
    digest = dist.get("digests", {}).get("sha256")
    if not digest or hashlib.sha256(data).hexdigest() != digest:
        raise ValueError("Distribution SHA-256 verification failed")
    return data, dist["filename"], info.get("version", version), info.get("requires_dist") or []


def safe_path(name):
    if "\\" in name or "\x00" in name or ":" in name or name.startswith("/"):
        return None
    p = PurePosixPath(name)
    if ".." in p.parts or "." in p.parts or not p.parts:
        return None
    return p


def read_archive(data, filename):
    """Read only regular Python source files in memory; never extract archive paths."""
    result = {}
    non_python = []
    seen = 0
    if filename.endswith((".zip", ".whl")):
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            members = [(x.filename, x.file_size, x.is_dir(), x)
                       for x in zf.infolist()]
            if len(members) > MAX_FILES:
                raise ValueError("Archive contains too many entries")
            for name, size, is_dir, member in members:
                p = safe_path(name)
                if not p or is_dir:
                    continue
                if size > MAX_SOURCE:
                    if p.suffix.lower() == ".py":
                        raise ValueError("Source member exceeds safety size limit: " + name)
                    continue
                if p.suffix.lower() == ".py":
                    with zf.open(member) as f:
                        body = f.read(MAX_SOURCE + 1)
                    if len(body) > MAX_SOURCE:
                        raise ValueError("Decompressed source exceeds size limit")
                    result[p] = body
                elif p.suffix.lower() in (".so", ".pyd", ".dll", ".c", ".h"):
                    non_python.append(name)
    elif filename.endswith((".tar.gz", ".tgz", ".tar", ".tar.xz", ".tar.bz2")):
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as tf:
            for member in tf:
                seen += 1
                if seen > MAX_FILES:
                    raise ValueError("Archive contains too many entries")
                p = safe_path(member.name)
                if not p or not member.isfile():
                    continue  # Ignore links, devices, directories, and unsafe paths.
                if member.size > MAX_SOURCE:
                    if p.suffix.lower() == ".py":
                        raise ValueError("Source member exceeds safety size limit: " + member.name)
                    continue
                if p.suffix.lower() == ".py":
                    f = tf.extractfile(member)
                    if f is not None:
                        body = f.read(MAX_SOURCE + 1)
                        if len(body) > MAX_SOURCE:
                            raise ValueError("Decompressed source exceeds size limit")
                        result[p] = body
                elif p.suffix.lower() in (".so", ".pyd", ".dll", ".c", ".h"):
                    non_python.append(member.name)
    else:
        raise ValueError("Only ZIP/wheel/tar source archives are supported")
    return normalize_sources(result), non_python


def normalize_sources(entries):
    if not entries:
        return {}
    parts = [p.parts for p in entries]
    # Strip the usual sdist release directory only when it wraps every file.
    strip_root = all(len(x) > 1 and x[0] == parts[0][0] for x in parts)
    normalized = {}
    for p, data in entries.items():
        path = PurePosixPath(*p.parts[1:]) if strip_root else p
        if path.parts and path.parts[0] == "src":
            path = PurePosixPath(*path.parts[1:])
        if not path.parts or any(s in ("test", "tests", "testing", "examples", "docs",
                                       ".dist-info", ".data", "__pycache__") or
                                s.endswith((".dist-info", ".data"))
                                for s in path.parts[:-1]):
            continue
        if path.name in ("setup.py", "conftest.py"):
            continue
        if path in normalized and normalized[path] != data:
            raise ValueError("Source paths collide after normalization: " + str(path))
        normalized[path] = data
    return normalized


def read_local(source):
    if source.is_file():
        return read_archive(source.read_bytes(), source.name)
    if not source.is_dir():
        raise ValueError("--source must be a directory or supported archive")
    root = source.resolve()
    entries = {}
    non_python = []
    for i, p in enumerate(source.rglob("*")):
        if i > MAX_FILES:
            raise ValueError("Local source directory has too many files")
        if not p.is_file() or p.is_symlink() or not p.resolve().is_relative_to(root):
            continue
        rel = PurePosixPath(p.relative_to(source).as_posix())
        if p.suffix.lower() == ".py":
            if p.stat().st_size > MAX_SOURCE:
                raise ValueError("Source exceeds safety size limit: " + str(rel))
            entries[rel] = p.read_bytes()
        elif p.suffix.lower() in (".so", ".pyd", ".dll", ".c", ".h"):
            non_python.append(str(rel))
    return normalize_sources(entries), non_python


class Downgrade(ast.NodeTransformer):
    """Safe-by-default subset of syntax lowering; do not invent package semantics."""

    def __init__(self, strip_docstrings=False):
        self.strip_docstrings = strip_docstrings
        self.counts = {"annotations": 0, "simple_fstrings": 0,
                       "typing_imports": 0, "docstrings": 0}
        self.errors = []

    def clean_body(self, node):
        if (self.strip_docstrings and node.body and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)):
            node.body.pop(0)
            self.counts["docstrings"] += 1
            if not node.body:
                node.body.append(ast.Pass())
        return node

    def visit_Module(self, node):
        self.generic_visit(node)
        return self.clean_body(node)

    def visit_ClassDef(self, node):
        self.generic_visit(node)
        return self.clean_body(node)

    def visit_FunctionDef(self, node):
        self.generic_visit(node)
        node.returns = None
        for arg in (*node.args.posonlyargs, *node.args.args,
                    *node.args.kwonlyargs, *([node.args.vararg] if node.args.vararg else []),
                    *([node.args.kwarg] if node.args.kwarg else [])):
            if arg.annotation is not None:
                self.counts["annotations"] += 1
                arg.annotation = None
        node.type_comment = None
        return self.clean_body(node)

    def visit_AsyncFunctionDef(self, node):
        self.errors.append("async function cannot be lowered automatically")
        return node

    def visit_AnnAssign(self, node):
        self.generic_visit(node)
        self.counts["annotations"] += 1
        if node.value is None:
            return ast.copy_location(ast.Pass(), node)
        return ast.copy_location(ast.Assign(targets=[node.target], value=node.value), node)

    def visit_JoinedStr(self, node):
        values = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                values.append(value)
            elif isinstance(value, ast.FormattedValue):
                if value.format_spec is not None or value.conversion == 97:
                    self.errors.append("f-string format spec / !a requires manual porting")
                    return node
                conv = "repr" if value.conversion == 114 else "str"
                values.append(ast.Call(func=ast.Name(id=conv, ctx=ast.Load()),
                                       args=[self.visit(value.value)], keywords=[]))
            else:
                self.errors.append("unrecognized f-string element")
                return node
        self.counts["simple_fstrings"] += 1
        if not values:
            return ast.copy_location(ast.Constant(value=""), node)
        result = values[0]
        for value in values[1:]:
            result = ast.BinOp(left=result, op=ast.Add(), right=value)
        return ast.copy_location(result, node)


def remove_unused_typing(tree, counts):
    """Remove typing-only imports only when no runtime use of the name remains."""
    loaded = {n.id for n in ast.walk(tree)
              if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
    new_body = []
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "typing":
            kept = [a for a in node.names if (a.asname or a.name) in loaded]
            counts["typing_imports"] += len(node.names) - len(kept)
            if kept:
                node.names = kept
                new_body.append(node)
        elif isinstance(node, ast.Import) and any(a.name == "typing" for a in node.names):
            kept = [a for a in node.names if
                    a.name != "typing" or (a.asname or "typing") in loaded]
            counts["typing_imports"] += len(node.names) - len(kept)
            if kept:
                node.names = kept
                new_body.append(node)
        elif (isinstance(node, ast.ImportFrom) and node.module == "__future__"
              and all(a.name == "annotations" for a in node.names)):
            counts["typing_imports"] += 1
        else:
            new_body.append(node)
    tree.body = new_body


def unpack_source(data):
    encoding, _ = tokenize.detect_encoding(io.BytesIO(data).readline)
    return data.decode(encoding)


def transform(data, path, strip_docstrings):
    changes = Downgrade(strip_docstrings=strip_docstrings)
    problems = []
    try:
        text = unpack_source(data)
        tree = ast.parse(text, filename=str(path))
        tree = changes.visit(tree)
        remove_unused_typing(tree, changes.counts)
        ast.fix_missing_locations(tree)
        output = ast.unparse(tree) + "\n"
        compile(output, str(path), "exec")  # Compile only, never execute package code.
    except (SyntaxError, UnicodeError, ValueError, RecursionError, TypeError) as exc:
        return None, changes.counts, [issue(path, "error", "parse",
                                               str(exc))]
    for error in changes.errors:
        problems.append(issue(path, "error", "unsupported_syntax", error))
    for node in ast.walk(tree):
        if isinstance(node, (ast.Match, ast.TryStar, ast.NamedExpr)):
            problems.append(issue(path, "error", "unsupported_syntax",
                                  type(node).__name__ + " requires verification/porting"))
        if hasattr(ast, "TypeAlias") and isinstance(node, ast.TypeAlias):
            problems.append(issue(path, "error", "unsupported_syntax",
                                  "Python 3.12 type alias requires porting"))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "open":
            problems.append(issue(path, "error", "unsupported_api",
                                  "CPython open() is unavailable in current PY86"))
    return output.encode("utf-8"), changes.counts, problems


def check_imports(source_bytes, path, local_modules):
    problems = []
    try:
        tree = ast.parse(source_bytes.decode("utf-8"))
    except (SyntaxError, UnicodeError):
        return problems
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module] if not node.level and node.module else []
        else:
            continue
        for name in names:
            root = name.split(".")[0]
            if root not in local_modules and root not in KNOWN_NATIVE:
                problems.append(issue(path, "error", "missing_module",
                                      "Import needs a PY86 port or dependency: " + name))
    return problems


def check_dos_paths(paths):
    errors = []
    seen = set()
    for path in paths:
        p = PurePosixPath(path)
        folded = str(path).upper()
        if folded in seen:
            errors.append(issue(path, "error", "dos_collision", "Case-insensitive path collision"))
        seen.add(folded)
        for part in p.parts:
            if part.count(".") > 1 and part != "__init__.py":
                errors.append(issue(path, "error", "dos_filename", "Not DOS 8.3: " + part))
                break
            stem, dot, ext = part.rpartition(".")
            if not dot:
                stem, ext = part, ""
            if (len(stem) > 8 or len(ext) > 3 or not stem or
                    not re.fullmatch(r"[A-Za-z0-9_$~!#%&'()@^{}-]+", stem) or
                    (ext and not re.fullmatch(r"[A-Za-z0-9_]+", ext)) or
                    stem.upper() in DOS_RESERVED):
                errors.append(issue(path, "error", "dos_filename", "Not DOS 8.3: " + part))
                break
    return errors


def convert(source_files, profile, output, package, version=None,
            requirements=(), native_files=(), strip_docstrings=False):
    if not source_files:
        raise ValueError("No Python source files found")
    issues = []
    result = {}
    stats = {"annotations": 0, "simple_fstrings": 0, "typing_imports": 0,
             "docstrings": 0}
    local_modules = {p.parts[0].split(".")[0] for p in source_files}
    for path, data in sorted(source_files.items(), key=lambda x: str(x[0])):
        converted, changes, failures = transform(data, path, strip_docstrings)
        for key, count in changes.items():
            stats[key] += count
        issues.extend(failures)
        if converted is None:
            continue
        if len(converted) > profile["max_source_bytes"]:
            issues.append(issue(path, "error", "source_size",
                                "Converted file exceeds %d-byte source limit" %
                                profile["max_source_bytes"]))
        issues.extend(check_imports(converted, path, local_modules))
        result[str(path)] = converted
    issues.extend(check_dos_paths(result))
    if requirements:
        issues.append(issue("*", "warning", "dependencies",
                            "PyPI declares dependencies; they are not installed recursively"))
    if native_files:
        issues.append(issue("*", "warning", "native_source",
                            "C/native files were not converted: " +
                            ", ".join(native_files[:5])))
    if strip_docstrings:
        issues.append(issue("*", "warning", "changed_semantics",
                            "Removed docstrings can change __doc__ behavior"))
    if not result:
        raise ValueError("No parseable Python files to package")
    status = "candidate_untested_on_dos" if not any(
        i["severity"] == "error" for i in issues) else "needs_porting"
    report = {
        "package": package, "version": version, "status": status,
        "source_files": len(source_files), "output_files": len(result),
        "total_source_bytes": sum(map(len, result.values())),
        "transformations": stats, "issues": issues,
        "requires_dist": list(requirements),
        "profile": profile, "verified_on_dos": False,
        "notes": [
            "Host CPython parsing/compilation is not PY86 execution.",
            "No downloaded package code was executed during conversion.",
            "Heap limits and actual library API compatibility require runtime testing.",
            "Packages with blocked files may still be included for manual inspection.",
        ],
    }
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, data in sorted(result.items()):
            zf.writestr(name, data)
        zf.writestr("REPORT.JSON", json.dumps(report, indent=2, sort_keys=True))
        zf.writestr("README.TXT",
                    ("PY86 PACKAGE CANDIDATE\r\n"
                     "Package: %s %s\r\nStatus: %s\r\n"
                     "Read REPORT.JSON on a modern PC before copying to DOS.\r\n"
                     "DOS execution has NOT been verified.\r\n") %
                    (package, version or "local", status))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="py86pkg", description="Convert a PyPI pure-Python package for experimental PY86")
    sub = parser.add_subparsers(dest="command", required=True)
    conv = sub.add_parser("convert", help="Download, statically convert and package source")
    conv.add_argument("package", nargs="?", help="PyPI name or https://pypi.org/project/... URL")
    conv.add_argument("--version", help="Pinned PyPI release")
    conv.add_argument("--source", type=Path, help="Offline local directory or sdist/wheel archive")
    conv.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    conv.add_argument("--output", type=Path, default=Path("PY86PKG.ZIP"))
    conv.add_argument("--strip-docstrings", action="store_true",
                      help="Trade docstring behavior for smaller source")
    args = parser.parse_args(argv)
    if args.command != "convert":
        parser.error("Unknown subcommand")
    if bool(args.package) == bool(args.source):
        parser.error("Provide exactly one of a PyPI package/URL or --source")
    try:
        profile = json.loads(args.profile.read_text(encoding="utf-8"))
        if not isinstance(profile.get("max_source_bytes"), int) or profile["max_source_bytes"] <= 0:
            raise ValueError("Profile must contain positive max_source_bytes")
        if args.source:
            files, native_files = read_local(args.source)
            name, version, requirements = args.source.stem, None, []
        else:
            name, requested_version = parse_spec(args.package, args.version)
            raw, filename, version, requirements = download_release(name, requested_version)
            files, native_files = read_archive(raw, filename)
        report = convert(files, profile, args.output, name, version,
                         requirements, native_files, args.strip_docstrings)
    except (ValueError, OSError, KeyError, urllib.error.URLError,
            zipfile.BadZipFile, tarfile.TarError) as exc:
        print("py86pkg: " + str(exc), file=sys.stderr)
        return 1
    print("Created:", args.output)
    print("Status:", report["status"], "| files:", report["output_files"],
          "| issues:", len(report["issues"]))
    for entry in report["issues"]:
        print("  [%s] %s: %s" % (entry["severity"], entry["path"], entry["detail"]))
    return 2 if report["status"] == "needs_porting" else 0


if __name__ == "__main__":
    raise SystemExit(main())
