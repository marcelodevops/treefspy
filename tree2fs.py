import os

def create_path(path):
    """Create directories as needed and touch files."""
    if path.endswith("/"):
        os.makedirs(path, exist_ok=True)
    else:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            pass

def parse_tree_file(file_path):
    with open(file_path, "r") as f:
        lines = f.readlines()

    created = []

    for line in lines:
        line = line.rstrip()

        # Ignore empty lines or header line like "Project tree"
        if not line or line.lower().startswith("project") or line.startswith(" "):
            continue

        # Remove tree characters
        cleaned = (
            line.replace("├── ", "")
                .replace("│   ", "")
                .replace("└── ", "")
                .replace("│", "")
                .strip()
        )

        # Skip weird leftovers
        if cleaned == "":
            continue

        # Normalize directory paths
        if cleaned.endswith("/"):
            path = cleaned
        else:
            path = cleaned

        create_path(path)
        created.append(path)

    return created

if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("Usage: python tree_to_fs.py <tree-file>")
        exit(1)

    input_file = sys.argv[1]
    created_paths = parse_tree_file(input_file)

    print("\nCreated:")
    for p in created_paths:
        print(" -", p)
