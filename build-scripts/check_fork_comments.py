#!/usr/bin/env python3
"""List comments in fork-owned code.

Fork-owned code is every file the fork added over ``--base`` plus every line the fork added to a
file that already exists in ``--base``. Every comment line is printed as ``path:line: text``; the
count goes to stderr and the exit status is 1 when at least one comment is found.

``--list`` prints the files that would be scanned, ``--self-check`` runs the per-language scanners
against generated fixtures and needs no git checkout.
"""

import argparse
import ast
import bisect
import io
import re
import subprocess
import sys
import tempfile
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_PREFIXES = ("docs/", "lang/", "data/json/")
EXTENSIONS = {
    ".cpp": "cpp",
    ".h": "cpp",
    ".hpp": "cpp",
    ".py": "python",
    ".sh": "shell",
    ".ts": "ts",
    ".js": "ts",
    ".lua": "lua",
}
SHEBANG = re.compile(r"^#!\s*(?:/usr/bin/env\s+)?(?:\S*/)?(?:ba|da|k|z)?sh\b")
HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")
LUA_LONG_OPEN = re.compile(r"\[(=*)\[")
C_DIRECTIVE = re.compile(
    r"^//(?:~|\s*(?:\*NOPAD\*|NOLINT\b|clang-format\b|IWYU pragma\b|deno-lint-ignore\b|@ts-))"
)
HASH_DIRECTIVE = re.compile(
    r"^#\s*(?:noqa\b|type:|pragma\b|pylint:|fmt:|shellcheck\b)"
)
C_PARAMETER_NAME = re.compile(r"^/\*\s*[A-Za-z_][A-Za-z0-9_]*\s*=?\s*\*/$")
LUA_ANNOTATION = re.compile(r"^---@(?:param|class|field|return|type|alias|meta)\b")
LICENSE_WORDS = ("license", "spdx", "copyright")
HEADER_MAX_LINE = 5
MAX_TEXT = 120


class Comment:
    __slots__ = ("first", "last", "text", "kind", "whole_line", "module")

    def __init__(self, first, last, text, kind, whole_line=True, module=False):
        self.first = first
        self.last = last
        self.text = text
        self.kind = kind
        self.whole_line = whole_line
        self.module = module


def _line_index(src):
    starts = [0]
    for index, char in enumerate(src):
        if char == "\n":
            starts.append(index + 1)
    return starts


def _line_no(starts, offset):
    return bisect.bisect_right(starts, offset)


def _ident_char(char):
    return char.isalnum() or char == "_"


def _skip_quoted(src, offset, quote):
    index = offset + 1
    length = len(src)
    while index < length:
        char = src[index]
        if char == "\\":
            index += 2
            continue
        if char == quote:
            return index + 1
        if quote != "`" and char == "\n":
            return index
        index += 1
    return length


def _skip_raw(src, offset):
    open_paren = src.find("(", offset + 2)
    if open_paren < 0 or open_paren - (offset + 2) > 16:
        return offset + 2
    delimiter = src[offset + 2 : open_paren]
    if any(char.isspace() or char in ')\\("' for char in delimiter):
        return offset + 2
    marker = ")" + delimiter + '"'
    end = src.find(marker, open_paren + 1)
    if end < 0:
        return _skip_quoted(src, offset + 1, '"')
    return end + len(marker)


def scan_c_like(src, lang):
    starts = _line_index(src)
    lines = src.splitlines()
    raw_strings = lang == "cpp"
    templates = lang == "ts"
    comments = []
    index = 0
    length = len(src)
    while index < length:
        char = src[index]
        if char == "/" and src.startswith("//", index):
            end = src.find("\n", index)
            if end < 0:
                end = length
            row = _line_no(starts, index)
            prefix = lines[row - 1][: index - starts[row - 1]]
            comments.append(Comment(row, row, src[index:end], "line", not prefix.strip()))
            index = end
        elif char == "/" and src.startswith("/*", index):
            end_marker = src.find("*/", index + 2)
            end = length if end_marker < 0 else end_marker + 2
            comments.append(
                Comment(
                    _line_no(starts, index),
                    _line_no(starts, max(index, end - 1)),
                    src[index:end],
                    "block",
                )
            )
            index = end
        elif (
            raw_strings
            and char == "R"
            and src.startswith('R"', index)
            and (index == 0 or not _ident_char(src[index - 1]))
        ):
            index = _skip_raw(src, index)
        elif char in "\"'":
            if char == "'" and index > 0 and _ident_char(src[index - 1]):
                index += 1
            else:
                index = _skip_quoted(src, index, char)
        elif templates and char == "`":
            index = _skip_quoted(src, index, "`")
        else:
            index += 1
    return comments


def scan_lua(src):
    starts = _line_index(src)
    lines = src.splitlines()
    comments = []
    index = 0
    length = len(src)
    while index < length:
        char = src[index]
        if char == "-" and src.startswith("--", index):
            long_open = LUA_LONG_OPEN.match(src, index + 2)
            if long_open:
                close = "]" + long_open.group(1) + "]"
                end_marker = src.find(close, long_open.end())
                end = length if end_marker < 0 else end_marker + len(close)
                comments.append(
                    Comment(
                        _line_no(starts, index),
                        _line_no(starts, max(index, end - 1)),
                        src[index:end],
                        "block",
                    )
                )
                index = end
            else:
                end = src.find("\n", index)
                if end < 0:
                    end = length
                row = _line_no(starts, index)
                prefix = lines[row - 1][: index - starts[row - 1]]
                comments.append(
                    Comment(row, row, src[index:end], "line", not prefix.strip())
                )
                index = end
        elif char in "\"'":
            index = _skip_quoted(src, index, char)
        elif char == "[":
            long_open = LUA_LONG_OPEN.match(src, index)
            if long_open:
                close = "]" + long_open.group(1) + "]"
                end_marker = src.find(close, long_open.end())
                index = length if end_marker < 0 else end_marker + len(close)
            else:
                index += 1
        else:
            index += 1
    return comments


def _parse_heredoc(line, offset):
    index = offset + 2
    strip_tabs = False
    if index < len(line) and line[index] == "-":
        strip_tabs = True
        index += 1
    while index < len(line) and line[index] in " \t":
        index += 1
    if index >= len(line):
        return None, index
    quote = line[index]
    if quote in "'\"":
        end = line.find(quote, index + 1)
        if end < 0:
            return None, index
        return (line[index + 1 : end], strip_tabs), end + 1
    if quote == "\\":
        index += 1
    match = re.match(r"[\w.-]+", line[index:])
    if not match:
        return None, index
    return (match.group(0), strip_tabs), index + match.end()


def _heredoc_terminated(lines, row, heredoc):
    delimiter, strip_tabs = heredoc
    for line in lines[row:]:
        candidate = line.lstrip("\t") if strip_tabs else line
        if candidate.rstrip() == delimiter:
            return True
    return False


def scan_shell(src):
    lines = src.splitlines()
    comments = []
    in_single = False
    in_double = False
    pending = []
    for row, line in enumerate(lines, 1):
        if pending:
            delimiter, strip_tabs = pending[0]
            candidate = line.lstrip("\t") if strip_tabs else line
            if candidate.rstrip() == delimiter:
                pending.pop(0)
            continue
        index = 0
        length = len(line)
        while index < length:
            char = line[index]
            if in_single:
                if char == "'":
                    in_single = False
                index += 1
            elif in_double:
                if char == "\\":
                    index += 2
                elif char == '"':
                    in_double = False
                    index += 1
                else:
                    index += 1
            elif char == "\\":
                index += 2
            elif char == "'":
                in_single = True
                index += 1
            elif char == '"':
                in_double = True
                index += 1
            elif char == "#" and (index == 0 or line[index - 1] in " \t;&|()<>"):
                comments.append(
                    Comment(row, row, line[index:], "line", not line[:index].strip())
                )
                index = length
            elif line.startswith("<<", index) and not line.startswith("<<<", index):
                heredoc, after = _parse_heredoc(line, index)
                if heredoc is None or not _heredoc_terminated(lines, row, heredoc):
                    index += 2
                else:
                    pending.append(heredoc)
                    index = after
            else:
                index += 1
    return comments


def _module_doc_allowed(src):
    if "argparse" in src and re.search(r"description\s*=\s*__doc__", src):
        return True
    return re.search(r"\bprint\s*\([^)\n]*__doc__", src) is not None


def scan_python(src):
    lines = src.splitlines(True)
    plain = src.splitlines()
    module_ok = _module_doc_allowed(src)
    comments = []
    try:
        tree = ast.parse(src)
    except SyntaxError:
        tree = None
    if tree is not None:
        for node in ast.walk(tree):
            if not isinstance(
                node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
            ):
                continue
            body = node.body
            if not body or not isinstance(body[0], ast.Expr):
                continue
            value = body[0].value
            if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
                continue
            first = body[0].lineno
            last = body[0].end_lineno or first
            text = "".join(lines[first - 1 : last]).strip()
            module = isinstance(node, ast.Module) and module_ok
            comments.append(Comment(first, last, text, "docstring", True, module))
    try:
        for token in tokenize.generate_tokens(io.StringIO(src).readline):
            if token.type == tokenize.COMMENT:
                row, column = token.start
                prefix = plain[row - 1][:column]
                comments.append(
                    Comment(row, token.end[0], token.string, "line", not prefix.strip())
                )
    except (tokenize.TokenError, IndentationError, SyntaxError):
        pass
    return comments


def _is_license(text):
    lowered = text.lower()
    return any(word in lowered for word in LICENSE_WORDS)


def _directive_allowed(lang, comment):
    if comment.kind == "docstring":
        return comment.module
    if comment.kind == "block":
        return lang == "cpp" and C_PARAMETER_NAME.match(comment.text.strip()) is not None
    if comment.kind != "line":
        return False
    text = comment.text
    if lang == "lua":
        return LUA_ANNOTATION.match(text) is not None
    if lang in ("cpp", "ts"):
        return C_DIRECTIVE.match(text) is not None
    if text.startswith("#!"):
        return comment.first == 1
    return HASH_DIRECTIVE.match(text) is not None


def violation_rows(lang, comments):
    allowed = [False] * len(comments)
    for index, comment in enumerate(comments):
        if _directive_allowed(lang, comment):
            allowed[index] = True
        elif (
            comment.kind in ("block", "docstring")
            and comment.first <= HEADER_MAX_LINE
            and _is_license(comment.text)
        ):
            allowed[index] = True

    def close(run):
        if run and comments[run[0]].first <= HEADER_MAX_LINE:
            if any(_is_license(comments[item].text) for item in run):
                for item in run:
                    allowed[item] = True

    run = []
    for index, comment in enumerate(comments):
        eligible = comment.kind == "line" and comment.whole_line
        if eligible and run and comment.first == comments[run[-1]].last + 1:
            run.append(index)
            continue
        close(run)
        run = [index] if eligible else []
    close(run)

    rows = set()
    for index, comment in enumerate(comments):
        if not allowed[index]:
            rows.update(range(comment.first, comment.last + 1))
    return rows


def scan_source(lang, src, only=None):
    if lang == "python":
        comments = scan_python(src)
    elif lang == "lua":
        comments = scan_lua(src)
    elif lang == "shell":
        comments = scan_shell(src)
    else:
        comments = scan_c_like(src, lang)
    src_lines = src.splitlines()
    rows = sorted(violation_rows(lang, comments))
    if only is not None:
        rows = [row for row in rows if row in only]
    found = []
    for row in rows:
        text = src_lines[row - 1].strip()[:MAX_TEXT] if row <= len(src_lines) else ""
        found.append((row, text))
    return found


def _git(*args):
    result = subprocess.run(
        ["git", "-C", str(ROOT), *args], capture_output=True, text=True, check=True
    )
    return result.stdout


def _added_line_numbers(diff_text):
    added = {}
    current = None
    header = False
    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            current = None
            header = True
        elif header and line.startswith("+++ "):
            path = line[4:].strip()
            if path == "/dev/null":
                current = None
            else:
                current = path[2:] if path.startswith("b/") else path
                added.setdefault(current, set())
            header = False
        elif header and line.startswith("--- "):
            continue
        elif current is not None and line.startswith("@@"):
            match = HUNK.match(line)
            if match:
                start = int(match.group(1))
                count = 1 if match.group(2) is None else int(match.group(2))
                added[current].update(range(start, start + count))
            header = False
    return added


def _skipped(rel):
    return rel.startswith(SKIP_PREFIXES)


def owned_targets(base):
    fork_point = _git("merge-base", base, "HEAD").strip()
    added = [
        rel
        for rel in _git(
            "diff", "--diff-filter=A", "-z", "--name-only", fork_point
        ).split("\0")
        if rel
    ]
    added_set = set(added)
    diff_text = _git(
        "-c",
        "core.quotePath=false",
        "diff",
        "-U0",
        "--no-color",
        "--diff-algorithm=histogram",
        "--src-prefix=a/",
        "--dst-prefix=b/",
        fork_point,
    )
    hunks = _added_line_numbers(diff_text)
    targets = []
    for rel in added:
        if not _skipped(rel):
            targets.append((rel, None))
    for rel in sorted(hunks):
        if rel in added_set or _skipped(rel) or not hunks[rel]:
            continue
        targets.append((rel, hunks[rel]))
    return targets


def _read(rel):
    path = ROOT / rel
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8", errors="replace")
    return text.lstrip("\ufeff")


def _language(rel, src):
    suffix = Path(rel).suffix.lower()
    if suffix:
        return EXTENSIONS.get(suffix)
    first = src.split("\n", 1)[0]
    if SHEBANG.match(first):
        return "shell"
    return None


CPP_FIXTURE = "\n".join(
    [
        "#include <string> // IWYU pragma: keep",
        "int main() { // real comment",
        '    const char *u = "http://example.com // not a comment";',
        '    const char *r = R"tag(a /* b */ c)tag";',
        '    const char *q = R"q(a "b" // c)q";',
        "    /* first",
        "       second */",
        "    int x = 1'000; // *NOPAD*",
        "    return 0;",
        "}",
        "void unused( int /*count*/ ) {}",
        "//~ %s: a translator note",
    ]
)
CPP_EXPECTED = {2, 6, 7}

PYTHON_FIXTURE = "\n".join(
    [
        "#!/usr/bin/env python3",
        '"""Sample module docstring."""',
        "import argparse",
        "",
        "def main():",
        '    """Function docstring."""',
        '    text = "# not a comment"',
        "    # real comment",
        "    print(text)  # noqa: T201",
        "    return 0",
        "",
        'if __name__ == "__main__":',
        "    argparse.ArgumentParser(description=__doc__)",
        "    raise SystemExit(main())",
    ]
)
PYTHON_EXPECTED = {6, 8}

SHELL_FIXTURE = "\n".join(
    [
        "#!/bin/sh",
        "# shellcheck disable=SC2086",
        'echo "# not a comment"  # real comment',
        "x=1 # trailing",
        "cat <<'EOF'",
        "# heredoc body hash",
        "EOF",
        'y=2; echo "$y" # another',
        "n=$((1 << 2))",
        "# after shift",
    ]
)
SHELL_EXPECTED = {3, 4, 8, 10}

TS_FIXTURE = "\n".join(
    [
        "// @ts-expect-error",
        'const url = "http://x"; // real comment',
        "const t = `a // b`;",
        "/* block",
        "   end */",
        "const f = 1; // deno-lint-ignore no-explicit-any",
    ]
)
TS_EXPECTED = {2, 4, 5}

LUA_FIXTURE = "\n".join(
    [
        "local M = {}",
        "---@param x number",
        "local function f(x) -- real comment",
        '  local s = "--- not a comment"',
        "  --[[ first",
        "  second ]]",
        '  return s, "--[["',
        "end",
        "return M",
    ]
)
LUA_EXPECTED = {3, 5, 6}

LICENSE_FIXTURE = "\n".join(
    [
        "/*",
        " * Copyright 2026 Kenja",
        " * SPDX-License-Identifier: GPL-3.0",
        " */",
        "// real comment",
    ]
)
LICENSE_EXPECTED = {5}

FIXTURES = [
    ("header.hpp", LICENSE_FIXTURE, LICENSE_EXPECTED),
    ("sample.cpp", CPP_FIXTURE, CPP_EXPECTED),
    ("sample.py", PYTHON_FIXTURE, PYTHON_EXPECTED),
    ("sample.sh", SHELL_FIXTURE, SHELL_EXPECTED),
    ("sample.ts", TS_FIXTURE, TS_EXPECTED),
    ("sample.lua", LUA_FIXTURE, LUA_EXPECTED),
]


def self_check():
    ok = True
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        for name, src, expected in FIXTURES:
            path = root / name
            path.write_text(src, encoding="utf-8")
            lang = _language(name, src)
            found = scan_source(lang, src)
            got = {row for row, _ in found}
            if got != expected:
                print(
                    f"{name}: expected {sorted(expected)} got {sorted(got)}",
                    file=sys.stderr,
                )
                ok = False
            bodies = {row: text for row, text in found}
            for row, text in bodies.items():
                if not text:
                    print(f"{name}:{row}: empty text", file=sys.stderr)
                    ok = False
    if ok:
        print("self-check ok")
        return 0
    print("self-check failed", file=sys.stderr)
    return 1


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--base", default="upstream/main")
    parser.add_argument(
        "--list",
        action="store_true",
        help="print the files that would be scanned instead of the comments",
    )
    parser.add_argument(
        "--self-check",
        action="store_true",
        help="run the scanners against generated fixtures",
    )
    args = parser.parse_args(argv)
    if args.self_check:
        return self_check()
    try:
        targets = owned_targets(args.base)
    except subprocess.CalledProcessError as err:
        print(
            (err.stderr or "").strip() or f"git failed for base {args.base}",
            file=sys.stderr,
        )
        return 2

    total = 0
    for rel, only in sorted(targets, key=lambda item: item[0]):
        src = _read(rel)
        if src is None:
            print(f"warning: {rel} missing from the working tree", file=sys.stderr)
            continue
        lang = _language(rel, src)
        if lang is None:
            continue
        if args.list:
            print(f"{rel}\t{'all' if only is None else 'partial'}")
            continue
        for row, text in scan_source(lang, src, only):
            print(f"{rel}:{row}: {text}")
            total += 1
    if args.list:
        return 0
    print(f"{total} comment lines in fork-owned code", file=sys.stderr)
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
