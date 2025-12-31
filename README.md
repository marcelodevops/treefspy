# 🧰 TreeFS

A powerful CLI toolkit to build and export directory structures from **tree text**, **YAML**, **JSON**, or **TOML** configs — with support for templates, Git initialization, and cross-platform release binaries.

Originally inspired by a tiny Bash script, TreeFS has grown into a full-featured Python project that helps automate project scaffolding and structure generation.

---

##  Features

-  **Build directory trees** from:
  - Tree-formatted text files
  - YAML / JSON / TOML config files
-  Support for **file templates** and content templates
-  **Export** file systems into tree text or structured configs
-  **Git integration**
  - `git init` with optional `.gitignore` and hooks
-  **Cross-platform binaries**
  - Build single-file executables via PyInstaller
-  GitHub Actions workflow included to auto-build release binaries

---

## 🧾 Installation

Install locally using `pip`:

```bash
pip install .
```

## Usage
- Build from a tree file
```bash
treefs build tree.txt myproject/

```
- Add optional templates and git setup
```bash
treefs build project.yaml myproj/ \
  --templates ./templates \
  --init-git \
  --gitignore ./common_gitignore \
  --git-hooks ./my-hooks
```
- Preview what would be created without writing to disk:
```bash
treefs build project.yaml myproj/ --dry-run
```
### Export project structure
- Export a folder to a tree layout text:
```bash
treefs export-tree myproj/ tree.txt
```
- Or export to structured configs:
```bash
treefs export-config myproj/ project.yaml
treefs export-config myproj/ project.json
treefs export-config myproj/ project.toml
```
### Bundling a binary
- If PyInstaller is installed, you can auto-bundle TreeFS:
```bash
treefs bundle treefs.py --name treefs
```
