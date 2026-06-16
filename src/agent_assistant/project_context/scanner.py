"""Rule-based project scanner — extracts structural data without LLM."""

from __future__ import annotations

import ast
import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class FileInfo:
    """Information about a single source file."""

    path: str
    language: str  # "python", "javascript", "typescript", "other"
    classes: list[str] = field(default_factory=list)
    functions: list[str] = field(default_factory=list)


@dataclass
class ScanResult:
    """Output of the rule-based project scanner."""

    root_dir: str
    file_tree: list[str]
    dependencies: dict[str, list[str]]  # e.g. {"python": ["flask", "sqlalchemy"]}
    files: list[FileInfo]
    entry_points: list[str]

    def to_dict(self) -> dict:
        return {
            "root_dir": self.root_dir,
            "file_tree": self.file_tree,
            "dependencies": self.dependencies,
            "files": [
                {"path": f.path, "language": f.language, "classes": f.classes, "functions": f.functions}
                for f in self.files
            ],
            "entry_points": self.entry_points,
        }


# Extensions we recognize
LANG_EXTENSIONS = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".jsx": "javascript",
}

# Directories to skip during scanning
SKIP_DIRS = {
    "__pycache__", ".git", ".venv", "venv", "node_modules",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", "dist", "build",
    ".eggs", "*.egg-info",
}

# Files to look for dependency info
DEP_FILES = {
    "pyproject.toml": "python",
    "requirements.txt": "python",
    "package.json": "javascript",
}


class ProjectScanner:
    """Scans a project directory to extract structural information."""

    def __init__(self, root: Path, max_depth: int = 4, max_files: int = 200):
        self._root = root
        self._max_depth = max_depth
        self._max_files = max_files

    def scan(self) -> ScanResult:
        """Perform the full scan and return structured results."""
        file_tree = self._scan_tree()
        dependencies = self._scan_dependencies()
        files = self._scan_source_files()
        entry_points = self._find_entry_points(files)

        return ScanResult(
            root_dir=str(self._root),
            file_tree=file_tree,
            dependencies=dependencies,
            files=files,
            entry_points=entry_points,
        )

    def _scan_tree(self) -> list[str]:
        """Build a simplified file tree (paths only, max depth)."""
        entries = []
        for dirpath, dirnames, filenames in os.walk(self._root):
            # Skip ignored directories
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]

            depth = len(Path(dirpath).relative_to(self._root).parts)
            if depth > self._max_depth:
                dirnames.clear()
                continue

            rel = Path(dirpath).relative_to(self._root)
            if str(rel) != ".":
                entries.append(f"{rel}/")

            for f in sorted(filenames)[:20]:  # limit files per directory
                entries.append(str(rel / f))

            if len(entries) > self._max_files * 2:
                break

        return entries[:self._max_files * 2]

    def _scan_dependencies(self) -> dict[str, list[str]]:
        """Extract dependency lists from known config files."""
        deps: dict[str, list[str]] = {}

        for filename, lang in DEP_FILES.items():
            filepath = self._root / filename
            if not filepath.exists():
                continue

            if filename == "requirements.txt":
                deps.setdefault(lang, []).extend(self._parse_requirements(filepath))
            elif filename == "package.json":
                deps.setdefault(lang, []).extend(self._parse_package_json(filepath))
            elif filename == "pyproject.toml":
                deps.setdefault(lang, []).extend(self._parse_pyproject(filepath))

        return deps

    def _parse_requirements(self, path: Path) -> list[str]:
        """Parse requirements.txt for dependency names."""
        deps = []
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and not line.startswith("-"):
                name = line.split("==")[0].split(">=")[0].split("<=")[0].split("~=")[0].strip()
                if name:
                    deps.append(name)
        return deps

    def _parse_package_json(self, path: Path) -> list[str]:
        """Parse package.json for dependency names."""
        import json

        try:
            data = json.loads(path.read_text())
            return list(data.get("dependencies", {}).keys())
        except (json.JSONDecodeError, KeyError):
            return []

    def _parse_pyproject(self, path: Path) -> list[str]:
        """Parse pyproject.toml for dependency names (simple regex)."""
        import re

        deps = []
        text = path.read_text()
        # Match lines like: "flask>=2.0" or "requests"
        for match in re.finditer(r'"([a-zA-Z0-9_-]+)', text):
            dep = match.group(1)
            if dep not in ("build-system", "project", "tool", "hatchling"):
                deps.append(dep)
        return deps[:30]  # limit to avoid noise

    def _scan_source_files(self) -> list[FileInfo]:
        """Scan source files for classes and functions."""
        files = []
        for dirpath, dirnames, filenames in os.walk(self._root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            depth = len(Path(dirpath).relative_to(self._root).parts)
            if depth > self._max_depth:
                dirnames.clear()
                continue

            for fname in filenames:
                ext = Path(fname).suffix
                if ext not in LANG_EXTENSIONS:
                    continue

                filepath = Path(dirpath) / fname
                rel_path = str(filepath.relative_to(self._root))
                lang = LANG_EXTENSIONS[ext]

                file_info = FileInfo(path=rel_path, language=lang)

                if lang == "python":
                    self._extract_python_symbols(filepath, file_info)

                files.append(file_info)

                if len(files) >= self._max_files:
                    return files

        return files

    def _extract_python_symbols(self, path: Path, info: FileInfo) -> None:
        """Extract class and function names from a Python file using AST."""
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            return

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                info.classes.append(node.name)
            elif isinstance(node, ast.FunctionDef) and node.col_offset == 0:
                info.functions.append(node.name)

    def _find_entry_points(self, files: list[FileInfo]) -> list[str]:
        """Identify likely entry points (main.py, app.py, manage.py, etc.)."""
        entry_names = {"main.py", "app.py", "manage.py", "cli.py", "wsgi.py", "asgi.py"}
        return [f.path for f in files if Path(f.path).name in entry_names]
