"""Manage Remotion compositions in Root.tsx — register, unregister, archive.

Usage:
  python manage_compositions.py register <ComponentName> <duration_frames> <width> <height>
      [--root-tsx <path>] [--component-path <relative-import-path>]

  python manage_compositions.py unregister <ComponentName>
      [--root-tsx <path>]

  python manage_compositions.py archive <ComponentName>
      [--root-tsx <path>] [--source-dir <dir>] [--archive-dir <dir>]

  python manage_compositions.py replace <ComponentName> <duration_frames> <width> <height>
      [--root-tsx <path>] [--component-path <relative-import-path>]
      [--archive-dir <dir>]

Actions:
  register    — Add import + <Composition> to Root.tsx
  unregister  — Remove import + <Composition> from Root.tsx (keeps files)
  archive     — Unregister + move TSX file to _archive/ folder
  replace     — Archive ALL existing highlight compositions, then register new one
"""
import re
import os
import shutil
import argparse
import json


DEFAULT_ROOT = "src/Root.tsx"
DEFAULT_SOURCE_DIR = "src/text-highlights"
DEFAULT_ARCHIVE_DIR = "src/text-highlights/_archive"
DEFAULT_FPS = 30


def read_root(path: str) -> str:
    with open(path) as f:
        return f.read()


def write_root(path: str, content: str):
    with open(path, "w") as f:
        f.write(content)


def find_highlight_components(content: str) -> list[str]:
    """Find all component names imported from text-highlights/."""
    return re.findall(
        r"import\s+\{\s*(\w+)\s*\}\s+from\s+['\"]\.\/text-highlights\/\w+['\"]",
        content
    )


def remove_component(content: str, name: str) -> str:
    """Remove import line and <Composition> block for a component."""
    content = re.sub(
        rf"import\s+\{{\s*{re.escape(name)}\s*\}}\s+from\s+['\"]\.\/text-highlights\/\w+['\"];\n?",
        "", content
    )
    content = re.sub(
        rf"\s*<Composition\s[^>]*component=\{{{re.escape(name)}\}}[^/]*/>\n?",
        "\n", content, flags=re.DOTALL
    )
    content = re.sub(r"\n{3,}", "\n\n", content)
    return content


def add_component(content: str, name: str, duration: int, width: int, height: int,
                  import_path: str | None = None) -> str:
    """Add import line and <Composition> block for a component."""
    if import_path is None:
        import_path = f"./text-highlights/{name}"

    import_line = f"import {{ {name} }} from '{import_path}';\n"

    composition_block = (
        f"      <Composition\n"
        f"        id=\"{name}\"\n"
        f"        component={{{name}}}\n"
        f"        durationInFrames={{{duration}}}\n"
        f"        fps={{{DEFAULT_FPS}}}\n"
        f"        width={{{width}}}\n"
        f"        height={{{height}}}\n"
        f"      />\n"
    )

    if f"import {{ {name} }}" not in content:
        last_import = 0
        for m in re.finditer(r"^import\s.+;\n", content, re.MULTILINE):
            last_import = m.end()
        if last_import > 0:
            content = content[:last_import] + import_line + content[last_import:]
        else:
            content = import_line + content

    close_match = re.search(r"(\s*)</>", content)
    if close_match:
        insert_pos = close_match.start()
        content = content[:insert_pos] + composition_block + content[insert_pos:]

    return content


def archive_component(name: str, source_dir: str, archive_dir: str):
    """Move a component's TSX file to the archive directory."""
    os.makedirs(archive_dir, exist_ok=True)
    source = os.path.join(source_dir, f"{name}.tsx")
    if os.path.exists(source):
        dest = os.path.join(archive_dir, f"{name}.tsx")
        if os.path.exists(dest):
            i = 1
            while os.path.exists(f"{dest}.{i}"):
                i += 1
            dest = f"{dest}.{i}"
        shutil.move(source, dest)
        return dest
    return None


def main():
    parser = argparse.ArgumentParser(description="Manage Remotion highlight compositions")
    parser.add_argument("action", choices=["register", "unregister", "archive", "replace"])
    parser.add_argument("component_name", help="Component name (e.g. BlogImageEvalHighlight)")
    parser.add_argument("duration_frames", nargs="?", type=int, default=None)
    parser.add_argument("width", nargs="?", type=int, default=None)
    parser.add_argument("height", nargs="?", type=int, default=None)
    parser.add_argument("--root-tsx", default=DEFAULT_ROOT)
    parser.add_argument("--component-path", default=None,
                        help="Relative import path (default: ./text-highlights/<Name>)")
    parser.add_argument("--source-dir", default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--archive-dir", default=DEFAULT_ARCHIVE_DIR)
    args = parser.parse_args()

    result = {"action": args.action, "component": args.component_name}

    content = read_root(args.root_tsx)

    if args.action == "register":
        if not all([args.duration_frames, args.width, args.height]):
            parser.error("register requires: duration_frames width height")
        content = add_component(content, args.component_name,
                                args.duration_frames, args.width, args.height,
                                args.component_path)
        write_root(args.root_tsx, content)
        result["status"] = "registered"

    elif args.action == "unregister":
        content = remove_component(content, args.component_name)
        write_root(args.root_tsx, content)
        result["status"] = "unregistered"

    elif args.action == "archive":
        content = remove_component(content, args.component_name)
        write_root(args.root_tsx, content)
        dest = archive_component(args.component_name, args.source_dir, args.archive_dir)
        result["status"] = "archived"
        result["archived_to"] = dest

    elif args.action == "replace":
        if not all([args.duration_frames, args.width, args.height]):
            parser.error("replace requires: duration_frames width height")

        existing = find_highlight_components(content)
        archived = []
        for comp in existing:
            content = remove_component(content, comp)
            dest = archive_component(comp, args.source_dir, args.archive_dir)
            if dest:
                archived.append({"component": comp, "archived_to": dest})

        content = add_component(content, args.component_name,
                                args.duration_frames, args.width, args.height,
                                args.component_path)
        write_root(args.root_tsx, content)
        result["status"] = "replaced"
        result["archived"] = archived

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
