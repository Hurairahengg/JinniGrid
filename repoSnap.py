from pathlib import Path
from datetime import datetime, timezone
import mimetypes
import os

ROOT = Path.cwd().resolve()

CHUNK_COUNT = 5
OUTPUT_PREFIX = "repo_snapshot_part_"
OUTPUT_SUFFIX = ".md"
MAX_CHARS_PER_CHUNK = 12000
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024

EXCLUDED_DIRS = {
    ".git", ".hg", ".svn", "__pycache__", ".pytest_cache", ".mypy_cache",
    ".ruff_cache", ".tox", ".idea", ".vscode", "node_modules", ".venv",
    "venv", "env", "dist", "build", "coverage", ".next", ".nuxt", ".turbo",
    ".cache", "target", "bin", "obj",
}

EXCLUDED_FILES = {".DS_Store", "Thumbs.db"}

EXCLUDED_EXTENSIONS = {".pyc", ".md"}

TEXT_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".json", ".md",
    ".mdx", ".txt", ".yml", ".yaml", ".toml", ".ini", ".cfg", ".conf",
    ".css", ".scss", ".sass", ".less", ".html", ".htm", ".xml", ".svg",
    ".sql", ".sh", ".bash", ".zsh", ".ps1", ".bat", ".cmd", ".java",
    ".kt", ".kts", ".cs", ".cpp", ".c", ".h", ".hpp", ".go", ".rs",
    ".php", ".rb", ".swift", ".dart", ".vue", ".svelte",
}

TEXT_FILENAMES = {
    ".env", ".env.local", ".env.development", ".env.production", ".env.test",
    ".gitignore", ".gitattributes", ".editorconfig", ".prettierrc",
    ".eslintrc", ".babelrc", "Dockerfile", "dockerfile", "Makefile",
    "makefile", "README", "LICENSE", "CHANGELOG", "requirements.txt",
    "Pipfile", "pyproject.toml", "package.json", "package-lock.json",
    "pnpm-lock.yaml", "yarn.lock", "tsconfig.json", "vite.config.ts",
    "vite.config.js", "next.config.js", "next.config.ts",
}

LANG_MAP = {
    ".py": "python", ".js": "javascript", ".jsx": "jsx", ".ts": "typescript",
    ".tsx": "tsx", ".mjs": "javascript", ".cjs": "javascript", ".json": "json",
    ".md": "markdown", ".mdx": "mdx", ".yml": "yaml", ".yaml": "yaml",
    ".toml": "toml", ".ini": "ini", ".cfg": "ini", ".conf": "text",
    ".css": "css", ".scss": "scss", ".sass": "sass", ".less": "less",
    ".html": "html", ".htm": "html", ".xml": "xml", ".svg": "xml",
    ".sql": "sql", ".sh": "bash", ".bash": "bash", ".zsh": "bash",
    ".ps1": "powershell", ".bat": "batch", ".cmd": "batch", ".java": "java",
    ".kt": "kotlin", ".kts": "kotlin", ".cs": "csharp", ".cpp": "cpp",
    ".c": "c", ".h": "c", ".hpp": "cpp", ".go": "go", ".rs": "rust",
    ".php": "php", ".rb": "ruby", ".swift": "swift", ".dart": "dart",
    ".vue": "vue", ".svelte": "svelte",
}


def output_file_names() -> set[str]:
    return {f"{OUTPUT_PREFIX}{i}{OUTPUT_SUFFIX}" for i in range(1, CHUNK_COUNT + 1)}


def should_skip_path(path: Path) -> bool:
    if path.name in EXCLUDED_FILES or path.name in output_file_names():
        return True
    if path.name == Path(__file__).name:
        return True
    if path.suffix.lower() in EXCLUDED_EXTENSIONS:
        return True
    try:
        parts = path.relative_to(ROOT).parts
    except ValueError:
        parts = path.parts
    return any(p in EXCLUDED_DIRS for p in parts)


def is_probably_text(path: Path) -> bool:
    if path.name in TEXT_FILENAMES or path.suffix.lower() in TEXT_EXTENSIONS:
        return True
    guessed, _ = mimetypes.guess_type(str(path))
    if guessed and guessed.startswith("text/"):
        return True
    try:
        chunk = path.open("rb").read(4096)
        if b"\x00" in chunk:
            return False
        chunk.decode("utf-8")
        return True
    except Exception:
        return False


def md_lang(path: Path) -> str:
    name = path.name
    if name in {"Dockerfile", "dockerfile"}:
        return "dockerfile"
    if name in {"Makefile", "makefile"}:
        return "makefile"
    if name.startswith(".env"):
        return "bash"
    return LANG_MAP.get(path.suffix.lower(), "text")


def safe_fence(content: str) -> str:
    longest = current = 0
    for ch in content:
        if ch == "`":
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return "`" * max(3, longest + 1)


def collect_files() -> list[Path]:
    files = []
    for cur_root, dirs, fnames in os.walk(ROOT):
        cur = Path(cur_root)
        dirs[:] = [d for d in dirs if not should_skip_path(cur / d)]
        for f in fnames:
            fp = cur / f
            if not should_skip_path(fp) and fp.is_file():
                files.append(fp)
    files.sort(key=lambda p: p.relative_to(ROOT).as_posix().lower())
    return files


def file_block(fp: Path) -> str:
    rel = fp.relative_to(ROOT).as_posix()
    size = fp.stat().st_size
    parts = [f"\n---\n\n## `{rel}`\n\n"]

    if size > MAX_FILE_SIZE_BYTES:
        parts.append(f"> Skipped: too large ({size} bytes)\n")
        return "".join(parts)

    if not is_probably_text(fp):
        parts.append("> Binary file, content skipped.\n")
        return "".join(parts)

    try:
        content = fp.read_text(encoding="utf-8", errors="replace")
        lang = md_lang(fp)
        fence = safe_fence(content)
        parts.append(f"{fence}{lang}\n")
        parts.append(content)
        if not content.endswith("\n"):
            parts.append("\n")
        parts.append(f"{fence}\n")
    except Exception as e:
        parts.append(f"> Error reading: `{e}`\n")

    return "".join(parts)


def build_blocks(files: list[Path]) -> list[tuple[Path, str]]:
    """Pre-render every file block and return (path, block_text) pairs."""
    return [(fp, file_block(fp)) for fp in files]


def distribute_chunks(blocks: list[tuple[Path, str]], chunk_count: int) -> list[list[tuple[Path, str]]]:
    """Greedy distribution by character length into chunk_count buckets."""
    chunks: list[list[tuple[Path, str]]] = [[] for _ in range(chunk_count)]
    sizes = [0] * chunk_count

    # Sort blocks largest-first for better bin-packing
    for item in sorted(blocks, key=lambda x: len(x[1]), reverse=True):
        idx = sizes.index(min(sizes))
        chunks[idx].append(item)
        sizes[idx] += len(item[1])

    return chunks


def project_tree(files: list[Path]) -> str:
    return "\n".join(fp.relative_to(ROOT).as_posix() for fp in files)


def write_chunk(
    chunk_idx: int,
    total: int,
    chunk_blocks: list[tuple[Path, str]],
    all_files: list[Path],
) -> Path:
    out = ROOT / f"{OUTPUT_PREFIX}{chunk_idx}{OUTPUT_SUFFIX}"
    with out.open("w", encoding="utf-8", newline="\n") as f:
        f.write(f"# Repo Snapshot — Part {chunk_idx}/{total}\n\n")
        f.write(f"- Root: `{ROOT}`\n")
        f.write(f"- Total files: `{len(all_files)}` | This chunk: `{len(chunk_blocks)}`\n")
        f.write(f"- you knwo my whole jinni grid systeM/ basically it is thereliek a kubernetes server setup what it does is basically a mother server with ui and bunch of lank state VMs. the vms run a speacial typa of renko style bars not normal timeframe u will get more context in the codes but yeha and we can uipload strategy codes though mother ui and it wiill run strategy mt5 report and ecetra ecetra.theres the whole ui with a professional protfolio and contorls such as settings and fleet management and so on yeah. currently im mostly dont and need bug fixes for many thigns so yeah. understand each code its role and keep in ur context i will give u big promtps to update code later duinerstood\n\n")

        if chunk_idx == 1:
            f.write("## Project Tree\n\n```text\n")
            f.write(project_tree(all_files))
            f.write("\n```\n\n")

        f.write(f"## Files in Part {chunk_idx}\n\n```text\n")
        for fp, _ in chunk_blocks:
            f.write(fp.relative_to(ROOT).as_posix() + "\n")
        f.write("```\n\n## Contents\n")

        for _, block in chunk_blocks:
            f.write(block)

    return out

def delete_old_outputs():
    for i in range(1, CHUNK_COUNT + 1):
        p = ROOT / f"{OUTPUT_PREFIX}{i}{OUTPUT_SUFFIX}"
        if p.exists():
            p.unlink()


def main():
    delete_old_outputs()
    files = collect_files()
    blocks = build_blocks(files)
    chunks = distribute_chunks(blocks, CHUNK_COUNT)

    outputs = []
    for i, chunk in enumerate(chunks, 1):
        outputs.append(write_chunk(i, CHUNK_COUNT, chunk, files))

    print("\n✅ Snapshot created.")
    print(f"Root: {ROOT}")
    print(f"Total files: {len(files)}\n")

    over_limit = False
    for out in outputs:
        size = out.stat().st_size
        chars = out.read_text(encoding="utf-8").__len__()
        flag = " ⚠️ OVER 12K" if chars > MAX_CHARS_PER_CHUNK else ""
        print(f"  {out.name}  ({chars} chars / {size} bytes){flag}")
        if chars > MAX_CHARS_PER_CHUNK:
            over_limit = True

    if over_limit:
        print("\n⚠️  Some chunks exceed 12k chars. Consider increasing CHUNK_COUNT.")
    print()


if __name__ == "__main__":
    main()