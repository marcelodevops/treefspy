"""Unit tests for treefs.py's tree-file parser and build logic.

Run with: python -m unittest discover -s tests
(stdlib unittest is used so no extra test-runner dependency is required.)
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import treefs  # noqa: E402


class TreeToDictTests(unittest.TestCase):
    def _parse(self, text: str) -> dict:
        with tempfile.NamedTemporaryFile("w", suffix=".tree", delete=False) as f:
            f.write(text)
            path = Path(f.name)
        try:
            return treefs.tree_to_dict(path)
        finally:
            path.unlink()

    def test_directories_without_trailing_slash(self):
        # This is what the stock `tree` command actually outputs: no
        # trailing "/" on directory names.
        text = (
            "myproj\n"
            "├── src\n"
            "│   ├── main.py\n"
            "│   └── utils.py\n"
            "└── README.md\n"
        )
        structure = self._parse(text)
        self.assertEqual(
            structure,
            {
                "myproj": {
                    "src": {"main.py": "", "utils.py": ""},
                    "README.md": "",
                }
            },
        )

    def test_directories_with_trailing_slash(self):
        text = (
            "myproj/\n"
            "├── src/\n"
            "│   └── main.py\n"
            "└── README.md\n"
        )
        structure = self._parse(text)
        self.assertEqual(
            structure,
            {"myproj": {"src": {"main.py": ""}, "README.md": ""}},
        )

    def test_deep_nesting_with_spacer_indent(self):
        # Last child of a directory uses plain spaces instead of "│   ".
        text = (
            "myproj\n"
            "├── src\n"
            "│   ├── pkg\n"
            "│   │   └── deep.py\n"
            "│   └── utils.py\n"
            "└── docs\n"
            "    └── guide.md\n"
        )
        structure = self._parse(text)
        self.assertEqual(
            structure,
            {
                "myproj": {
                    "src": {"pkg": {"deep.py": ""}, "utils.py": ""},
                    "docs": {"guide.md": ""},
                }
            },
        )

    def test_empty_directory_needs_trailing_slash(self):
        # An empty directory has no children to infer depth from, so it must
        # be marked explicitly with a trailing "/".
        text = "myproj\n├── empty_dir/\n└── file.txt\n"
        structure = self._parse(text)
        self.assertEqual(
            structure,
            {"myproj": {"empty_dir": {}, "file.txt": ""}},
        )


class BuildFromTreeTests(unittest.TestCase):
    def test_build_creates_expected_files_on_disk(self):
        text = (
            "myproj\n"
            "├── src\n"
            "│   └── main.py\n"
            "└── README.md\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            tree_file = tmp_path / "sample.tree"
            tree_file.write_text(text, encoding="utf-8")

            root = tmp_path / "out"
            root.mkdir()
            treefs.build_from_tree(tree_file, root, force=False, dry_run=False)

            self.assertTrue((root / "src").is_dir())
            self.assertTrue((root / "src" / "main.py").is_file())
            self.assertTrue((root / "README.md").is_file())


if __name__ == "__main__":
    unittest.main()
