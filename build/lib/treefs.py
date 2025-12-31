#!/usr/bin/env python3
"""
TreeFS — deluxe edition
Features:
 - build from tree / yaml / json / toml
 - export tree / config (yaml/json/toml)
 - templates (inline in config or from a templates directory)
 - git init support (with .gitignore and hooks)
 - --force, --dry-run, --bundle (PyInstaller)
"""
from __future__ import annotations
import os
import sys
import argparse
import json
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

# optional deps: pyyaml, toml
try:
    import yaml
except Exception:
    yaml = None

try:
    import toml
except Exception:
    toml = None

TREE_CHARS = ["│", "├", "└", "─"]

# ---------- Utilities ----------
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
    return f"{codes.get(color,'')}{text}{codes['reset']}"

def safe_print(msg: str = "", c: str = "green"):
    print(colorize(msg, c))

def strip_tree_chars(line: str) -> str:
    for ch in TREE_CHARS:
        line = line.replace(ch, "")
    return line.strip()

def ensure_parent(path: Path):
    if not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)

# ---------- Build from tree file ----------
def build_from_tree(tree_file: Path, root: Path, force: bool, dry_run: bool, templates_dir: Optional[Path]=None):
    created = []
    with tree_file.open("r", encoding="utf-8") as f:
        lines = f.readlines()

    for raw in lines:
        line = raw.rstrip()
        if not line or line.lower().startswith("project"):
            continue
        clean = strip_tree_chars(line)
        if clean == "":
            continue

        fs_path = root / clean
        if clean.endswith("/"):
            if dry_run:
                created.append(f"{fs_path}/ (would create)")
            else:
                fs_path.mkdir(parents=True, exist_ok=True)
                created.append(str(fs_path) + "/")
        else:
            ensure_parent(fs_path)
            if fs_path.exists() and not force:
                created.append(f"{fs_path} (exists, kept)")
            else:
                if dry_run:
                    created.append(f"{fs_path} (would create file)")
                else:
                    fs_path.write_text("", encoding="utf-8")
                    created.append(str(fs_path))
    # try applying templates (if provided): copy templates root into root/templates if exists
    if templates_dir and templates_dir.exists():
        for item in templates_dir.rglob("*"):
            rel = item.relative_to(templates_dir)
            dest = root / rel
            if item.is_dir():
                if not dry_run:
                    dest.mkdir(parents=True, exist_ok=True)
                created.append(str(dest)+"/")
            else:
                ensure_parent(dest)
                if dest.exists() and not force:
                    created.append(f"{dest} (template exists, kept)")
                else:
                    if not dry_run:
                        shutil.copy2(item, dest)
                    created.append(str(dest))
    return created

# ---------- Build from mapping (dict) (YAML/JSON/TOML) ----------
def build_from_dict(root: Path, structure: Dict[str, Any], force: bool, dry_run: bool, templates_dir: Optional[Path]=None):
    created = []

    def recurse(base: Path, node: Dict[str, Any]):
        for name, val in node.items():
            # special keys: __template__ indicates copying a template
            if name == "__template__" and isinstance(val, str):
                # copy an entire template folder (relative to templates_dir)
                if templates_dir:
                    src_template = templates_dir / val
                    if src_template.exists():
                        for item in src_template.rglob("*"):
                            rel = item.relative_to(src_template)
                            dest = base / rel
                            if item.is_dir():
                                if not dry_run:
                                    dest.mkdir(parents=True, exist_ok=True)
                                created.append(str(dest)+"/")
                            else:
                                ensure_parent(dest)
                                if dest.exists() and not force:
                                    created.append(f"{dest} (exists, kept)")
                                else:
                                    if not dry_run:
                                        shutil.copy2(item, dest)
                                    created.append(str(dest))
                continue

            path = base / name
            if isinstance(val, dict):
                # directory
                if dry_run:
                    created.append(str(path)+"/ (would create)")
                else:
                    path.mkdir(parents=True, exist_ok=True)
                    created.append(str(path)+"/")
                recurse(path, val)
            else:
                # val can be None or a string content
                ensure_parent(path)
                if path.exists() and not force:
                    created.append(f"{path} (exists, kept)")
                else:
                    if dry_run:
                        created.append(f"{path} (would create file)")
                    else:
                        content = val if isinstance(val, str) else ""
                        path.write_text(content, encoding="utf-8")
                        created.append(str(path))

    # top-level may have single root node; if multiple, we create them directly under root
    recurse(root, structure)
    return created

# ---------- Export helpers ----------
def export_tree(root: Path, output: Path):
    lines = [root.name + "/"]
    def tree(p: Path, prefix: str=""):
        entries = sorted([e.name for e in p.iterdir()])
        last_idx = len(entries)-1
        for i, name in enumerate(entries):
            full = p / name
            connector = "└── " if i==last_idx else "├── "
            lines.append(prefix + connector + name)
            if full.is_dir():
                ext = "    " if i==last_idx else "│   "
                tree(full, prefix + ext)
    tree(root)
    output.write_text("\n".join(lines), encoding="utf-8")
    return str(output)

def export_dict(root: Path) -> Dict[str, Any]:
    def recurse(p: Path):
        data = {}
        for child in sorted(p.iterdir(), key=lambda x: x.name):
            if child.is_dir():
                data[child.name] = recurse(child)
            else:
                try:
                    data[child.name] = child.read_text(encoding="utf-8")
                except Exception:
                    data[child.name] = ""
        return data
    return {root.name: recurse(root)}

# ---------- Git support ----------
def init_git(root: Path, gitignore: Optional[Path]=None, hooks_dir: Optional[Path]=None, dry_run: bool=False):
    created = []
    if dry_run:
        created.append("git init (would run)")
    else:
        try:
            subprocess.run(["git","init"], cwd=str(root), check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            created.append("git init")
        except Exception as e:
            created.append(f"git init (failed: {e})")

    if gitignore:
        dest = root / ".gitignore"
        if gitignore.exists():
            if dry_run:
                created.append(f".gitignore -> {dest} (would copy)")
            else:
                shutil.copy2(gitignore, dest)
                created.append(str(dest))
        else:
            # create empty .gitignore if not provided
            if dry_run:
                created.append(f".gitignore (would create empty)")
            else:
                dest.write_text("", encoding="utf-8")
                created.append(str(dest))

    if hooks_dir and hooks_dir.exists():
        dest_hooks = root / ".git" / "hooks"
        if not dry_run:
            dest_hooks.mkdir(parents=True, exist_ok=True)
        for h in hooks_dir.iterdir():
            target = dest_hooks / h.name
            if dry_run:
                created.append(f"hook {h.name} -> {target} (would copy)")
            else:
                shutil.copy2(h, target)
                os.chmod(target, 0o755)
                created.append(str(target))
    return created

# ---------- Bundling (PyInstaller) ----------
def bundle_binary(entry: Path, name: Optional[str]=None, clean: bool=True):
    """
    Try to call PyInstaller to create a single-file executable.
    Returns tuple(success:bool, message:str)
    """
    if shutil.which("pyinstaller") is None:
        return False, "PyInstaller not found on PATH. Install it: pip install pyinstaller"
    cmd = ["pyinstaller", "--onefile", "--name", name or entry.stem, str(entry)]
    if clean:
        cmd.append("--clean")
    try:
        subprocess.run(cmd, check=True)
        return True, "Bundled with PyInstaller (dist/{}).".format(name or entry.stem)
    except Exception as e:
        return False, f"PyInstaller failed: {e}"

# ---------- File format helpers ----------
def load_config(path: Path) -> Dict[str, Any]:
    ext = path.suffix.lower()
    if ext in (".yaml", ".yml"):
        if yaml is None:
            raise RuntimeError("PyYAML required for YAML support. pip install pyyaml")
        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    elif ext == ".json":
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    elif ext == ".toml":
        if toml is None:
            raise RuntimeError("toml required for TOML support. pip install toml")
        with path.open("r", encoding="utf-8") as f:
            return toml.load(f)
    else:
        raise RuntimeError("Unsupported config format: " + ext)

def dump_config(structure: Dict[str,Any], output: Path, fmt: str):
    if fmt == "yaml":
        if yaml is None:
            raise RuntimeError("PyYAML required for YAML support. pip install pyyaml")
        output.write_text(yaml.safe_dump(structure, sort_keys=False), encoding="utf-8")
    elif fmt == "json":
        output.write_text(json.dumps(structure, indent=2), encoding="utf-8")
    elif fmt == "toml":
        if toml is None:
            raise RuntimeError("toml required for TOML support. pip install toml")
        output.write_text(toml.dumps(structure), encoding="utf-8")
    else:
        raise RuntimeError("Unknown output format: " + fmt)

# ---------- CLI ----------
def main(argv=None):
    parser = argparse.ArgumentParser(prog="treefs", description="TreeFS — build/export directory structures (deluxe)")
    sub = parser.add_subparsers(dest="cmd")

    # build
    b = sub.add_parser("build", help="Build directory tree from tree/config")
    b.add_argument("input", help="Input file (tree, yaml, json, toml)")
    b.add_argument("root", help="Target root directory (created if missing)")
    b.add_argument("--templates", help="Templates folder to copy from (optional)", default=None)
    b.add_argument("--force", action="store_true", help="Overwrite existing files")
    b.add_argument("--dry-run", action="store_true", help="Show what would be created, don't touch FS")
    b.add_argument("--init-git", action="store_true", help="Run git init inside the root after build")
    b.add_argument("--gitignore", help="Path to .gitignore file to copy into root", default=None)
    b.add_argument("--git-hooks", help="Path to hooks directory which will be copied to .git/hooks", default=None)

    # export tree
    t = sub.add_parser("export-tree", help="Export a directory as tree-format text")
    t.add_argument("root", help="Directory to export")
    t.add_argument("output", help="Output tree file path")

    # export config
    c = sub.add_parser("export-config", help="Export a directory to YAML/JSON/TOML config")
    c.add_argument("root", help="Directory to export")
    c.add_argument("output", help="Output file path (ext decides format .yaml/.json/.toml)")

    # bundle
    p = sub.add_parser("bundle", help="Bundle a script into a single binary using PyInstaller (requires PyInstaller)")
    p.add_argument("entry", help="Python entry script to bundle (e.g. treefs.py)")
    p.add_argument("--name", help="Name for the binary", default=None)

    args = parser.parse_args(argv)

    if args.cmd == "build":
        inp = Path(args.input)
        root = Path(args.root)
        root.mkdir(parents=True, exist_ok=True)
        templates_dir = Path(args.templates) if args.templates else None

        ext = inp.suffix.lower()
        created = []
        # tree formats: detect tree-style by no known ext
        if ext in (".yaml", ".yml", ".json", ".toml"):
            safe_print("Loading structured config...", "blue")
            structure = load_config(inp)
            if isinstance(structure, dict) and len(structure)==1 and any(isinstance(v, dict) for v in structure.values()):
                # If top-level is a named root, unwrap to build under root/<name>
                # We will create under root/<topname> by default; to mimic prior behavior, if user
                # expects top-level root to be the name of project, they can set root accordingly.
                # Here we build the structure inside the provided root.
                pass
            created = build_from_dict(root, structure, force=args.force, dry_run=args.dry_run, templates_dir=templates_dir)
        else:
            safe_print("Parsing tree text file...", "blue")
            created = build_from_tree(inp, root, force=args.force, dry_run=args.dry_run, templates_dir=templates_dir)

        safe_print("\nCreated / Verified:", "yellow")
        for cstr in created:
            safe_print(" - " + cstr)

        # git init if requested
        if args.init_git:
            safe_print("\nInitializing git...", "blue")
            gi = init_git(root, gitignore=Path(args.gitignore) if args.gitignore else None, hooks_dir=Path(args.git_hooks) if args.git_hooks else None, dry_run=args.dry_run)
            for g in gi:
                safe_print(" - " + g)

    elif args.cmd == "export-tree":
        root = Path(args.root)
        out = Path(args.output)
        safe_print("Exporting tree...", "blue")
        path = export_tree(root, out)
        safe_print("Saved to " + path, "yellow")

    elif args.cmd == "export-config":
        root = Path(args.root)
        out = Path(args.output)
        fmt = out.suffix.lower().lstrip(".")
        safe_print(f"Exporting to {fmt}...", "blue")
        struct = export_dict(root)
        dump_config(struct, out, fmt)
        safe_print("Saved to " + str(out), "yellow")

    elif args.cmd == "bundle":
        entry = Path(args.entry)
        success, msg = bundle_binary(entry, name=args.name)
        if success:
            safe_print(msg, "green")
        else:
            safe_print(msg, "red")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
