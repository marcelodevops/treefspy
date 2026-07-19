#!/usr/bin/env python3
"""
TreeFS — deluxe edition (fixed parser version)

Changes:
- Replaced fragile ASCII-tree stack parser
- Introduced AST-based tree parser (tree → dict)
- build_from_tree now reuses build_from_dict safely
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# optional deps: pyyaml, toml
try:
    import yaml
except Exception:
    yaml = None

try:
    import toml
except Exception:
    toml = None


# ---------- Utilities ----------

# 4-character indentation units a tree line's prefix is built from (one per
# ancestor depth level that is *not* the immediate parent connector).
_INDENT_UNITS = ("│   ", "    ", "|   ")

# 4-character connectors that introduce an entry's own name.
_CONNECTORS = ("├── ", "└── ", "|-- ", "`-- ")


def _parse_tree_line(line: str) -> tuple[int, str]:
    """Split a single tree line into (depth, name).

    This walks the line manually instead of relying on trailing slashes or
    fragile character-replacement math, so it works whether or not the tree
    file marks directories with a trailing "/" (the stock `tree` command does
    not do so unless run with `-F`).

    A bare root line (no leading indent units and no connector, e.g. the
    "myproj" line at the very top of `tree` output) is one level *above* its
    connector-prefixed children, even though they share the same count of
    indent units, so it gets depth -1 relative to them.
    """
    i = 0
    depth = 0
    while line[i:i + 4] in _INDENT_UNITS:
        depth += 1
        i += 4

    has_connector = line[i:i + 4] in _CONNECTORS
    if has_connector:
        i += 4
    else:
        depth -= 1

    name = line[i:].strip()
    return depth, name


def is_tty() -> bool:
    return sys.stdout.isatty()


def colorize(text: str, color: str) -> str:
    if not is_tty():
        return text
    codes = {
        "green": "\033[92m",
        "yellow": "\033[93m",
        "blue": "\033[94m",
        "red": "\033[91m",
        "reset": "\033[0m",
    }
    return f"{codes.get(color, '')}{text}{codes['reset']}"


def safe_print(msg: str = "", c: str = "green"):
    print(colorize(msg, c))


def ensure_parent(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)


# ---------- FIXED: TREE PARSER (AST BUILDER) ----------


def tree_to_dict(tree_file: Path) -> dict:
    """
    Converts ASCII tree file into nested dictionary (AST).

    Directories are detected either by an explicit trailing "/" on the name,
    or (since the stock `tree` command doesn't add one) by the presence of a
    following line indented one level deeper.
    """

    entries = []  # (depth, name, has_trailing_slash)

    with tree_file.open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip()

            if not line or line.strip() == "│":
                continue

            if line.lower().startswith("project"):
                continue

            depth, name = _parse_tree_line(line)
            if not name:
                continue

            has_slash = name.endswith("/")
            entries.append((depth, name.rstrip("/"), has_slash))

    root: dict = {}
    stack = [(-2, root)]  # (depth, node); -2 is below any real/root depth

    for idx, (depth, name, has_slash) in enumerate(entries):
        is_dir = has_slash
        if not is_dir and idx + 1 < len(entries):
            is_dir = entries[idx + 1][0] > depth

        # move to correct parent
        while stack and stack[-1][0] >= depth:
            stack.pop()

        parent = stack[-1][1]

        if is_dir:
            node: dict = {}
            parent[name] = node
            stack.append((depth, node))
        else:
            parent[name] = ""

    return root


# ---------- FIXED: BUILD FROM TREE ----------


def build_from_tree(
    tree_file: Path,
    root: Path,
    force: bool,
    dry_run: bool,
    templates_dir: Optional[Path] = None,
):
    structure = tree_to_dict(tree_file)

    # unwrap single-root tree (platform/ etc.)
    if len(structure) == 1:
        structure = list(structure.values())[0]

    return build_from_dict(
        root=root,
        structure=structure,
        force=force,
        dry_run=dry_run,
        templates_dir=templates_dir,
    )


# ---------- BUILD FROM DICT (UNCHANGED CORE) ----------


def build_from_dict(
    root: Path,
    structure: Dict[str, Any],
    force: bool,
    dry_run: bool,
    templates_dir: Optional[Path] = None,
):
    created = []

    def recurse(base: Path, node: Dict[str, Any]):
        for name, val in node.items():
            path = base / name

            if isinstance(val, dict):
                if dry_run:
                    created.append(str(path) + "/ (would create)")
                else:
                    path.mkdir(parents=True, exist_ok=True)
                    created.append(str(path) + "/")

                recurse(path, val)

            else:
                ensure_parent(path)

                if path.exists() and not force:
                    created.append(f"{path} (exists, kept)")
                else:
                    if dry_run:
                        created.append(f"{path} (would create file)")
                    else:
                        path.write_text(val or "", encoding="utf-8")
                        created.append(str(path))

    recurse(root, structure)
    return created


# ---------- EXPORT TREE ----------


def export_tree(root: Path, output: Path):
    lines = [root.name + "/"]

    def walk(p: Path, prefix: str = ""):
        entries = sorted(p.iterdir(), key=lambda x: x.name)
        for i, entry in enumerate(entries):
            connector = "└── " if i == len(entries) - 1 else "├── "
            lines.append(prefix + connector + entry.name)

            if entry.is_dir():
                ext = "    " if i == len(entries) - 1 else "│   "
                walk(entry, prefix + ext)

    walk(root)
    output.write_text("\n".join(lines), encoding="utf-8")
    return str(output)


# ---------- EXPORT CONFIG ----------


def export_dict(root: Path) -> Dict[str, Any]:
    def recurse(p: Path):
        data = {}
        for child in sorted(p.iterdir(), key=lambda x: x.name):
            if child.is_dir():
                data[child.name] = recurse(child)
            else:
                data[child.name] = child.read_text(encoding="utf-8")
        return data

    return {root.name: recurse(root)}


# ---------- CLI ----------


def main(argv=None):
    parser = argparse.ArgumentParser("treefs")
    sub = parser.add_subparsers(dest="cmd")

    b = sub.add_parser("build")
    b.add_argument("input")
    b.add_argument("root")
    b.add_argument("--force", action="store_true")
    b.add_argument("--dry-run", action="store_true")

    t = sub.add_parser("export-tree")
    t.add_argument("root")
    t.add_argument("output")

    c = sub.add_parser("export-config")
    c.add_argument("root")
    c.add_argument("output")

    args = parser.parse_args(argv)

    if args.cmd == "build":
        inp = Path(args.input)
        root = Path(args.root)
        root.mkdir(parents=True, exist_ok=True)

        created = build_from_tree(
            inp,
            root,
            force=args.force,
            dry_run=args.dry_run,
        )

        safe_print("\nCreated / Verified:", "yellow")
        for cstr in created:
            safe_print(" - " + cstr)

    elif args.cmd == "export-tree":
        out = Path(args.output)
        safe_print("Exporting tree...", "blue")
        export_tree(Path(args.root), out)
        safe_print("Saved", "yellow")

    elif args.cmd == "export-config":
        root = Path(args.root)
        out = Path(args.output)
        struct = export_dict(root)

        fmt = out.suffix.lower().lstrip(".")
        if fmt == "json":
            out.write_text(json.dumps(struct, indent=2))
        elif fmt == "yaml" and yaml:
            out.write_text(yaml.safe_dump(struct))
        elif fmt == "toml" and toml:
            out.write_text(toml.dumps(struct))
        else:
            raise RuntimeError("Unsupported format")

        safe_print("Saved", "yellow")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
