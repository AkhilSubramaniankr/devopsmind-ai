import os
import zipfile
import pathspec
from pathlib import Path
from typing import List, Dict, Any

DEFAULT_EXCLUSIONS = [
    ".git/", ".venv/", "venv/", "node_modules/", "__pycache__/",
    "*.pyc", "*.pyo", ".pytest_cache/", ".mypy_cache/", "dist/", "build/"
]

def load_gitignore_patterns(repo_path: Path) -> pathspec.PathSpec:
    """Loads .gitignore patterns along with default exclusions."""
    patterns = list(DEFAULT_EXCLUSIONS)
    gitignore_file = repo_path / ".gitignore"
    if gitignore_file.exists():
        with open(gitignore_file, "r", encoding="utf-8", errors="ignore") as f:
            patterns.extend(f.readlines())
    return pathspec.PathSpec.from_lines("gitwildmatch", patterns)

def extract_zip(zip_path: str, extract_to: str) -> Path:
    """Safely extracts a ZIP archive into a target directory."""
    target_dir = Path(extract_to)
    target_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(target_dir)
    return target_dir

def scan_repository(repo_path: str) -> List[Dict[str, Any]]:
    """Scans the repository directory and returns a list of valid source files."""
    base_path = Path(repo_path).resolve()
    spec = load_gitignore_patterns(base_path)
    
    file_inventory = []
    
    for root, dirs, files in os.walk(base_path):
        rel_root = Path(root).relative_to(base_path)
        
        # Prune ignored directories in-place
        dirs[:] = [d for d in dirs if not spec.match_file(str(rel_root / d) + "/")]
        
        for file in files:
            rel_file_path = str(rel_root / file) if str(rel_root) != "." else file
            if not spec.match_file(rel_file_path):
                full_path = base_path / rel_file_path
                file_inventory.append({
                    "relative_path": rel_file_path,
                    "full_path": str(full_path),
                    "extension": full_path.suffix.lower(),
                    "size_bytes": full_path.stat().st_size
                })
                
    return file_inventory