#!/usr/bin/env python3
"""解析并按需创建最小科研绘图工作区。

Resolve and optionally create the minimal figure workspace.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import tempfile
from pathlib import Path


def slugify(value: str) -> str:
    value = value.strip().lower().replace("_", "-")
    value = re.sub(r"\s+", "-", value)
    value = re.sub(r"[^\w\-]+", "-", value, flags=re.UNICODE)
    return re.sub(r"-+", "-", value).strip("-.")[:80] or "untitled-paper"


def clean_title(value: str) -> str:
    value = re.sub(r"\\[A-Za-z]+\*?(?:\[[^]]*\])?", "", value)
    value = value.replace("{", "").replace("}", "")
    return re.sub(r"\s+", " ", value).strip()


def detect_paper_name(project_root: Path) -> str:
    preferred = [project_root / "main.tex", project_root / "paper.tex"]
    tex_files = [path for path in preferred if path.is_file()]
    tex_files.extend(path for path in sorted(project_root.glob("*.tex")) if path not in tex_files)
    for path in tex_files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        match = re.search(r"\\title\s*\{(.{1,500}?)\}", text, flags=re.DOTALL)
        if match and (title := clean_title(match.group(1))):
            return title

    markdown_files = [*project_root.glob("*.md"), *project_root.glob("*.markdown")]
    for path in sorted(markdown_files):
        head = "\n".join(path.read_text(encoding="utf-8", errors="ignore").splitlines()[:40])
        match = re.search(r"^title:\s*[\"']?(.+?)[\"']?\s*$", head, flags=re.MULTILINE)
        if match:
            return match.group(1).strip()
    return project_root.name or "untitled-paper"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_source(raw: str, project_root: Path) -> Path:
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        candidate = project_root / candidate
    candidate = candidate.resolve()
    if not candidate.is_file():
        raise FileNotFoundError(f"source file not found: {candidate}")
    return candidate


def copy_source(source: Path, source_dir: Path) -> dict[str, object]:
    checksum = sha256(source)
    destination = source_dir / source.name
    if destination.exists():
        if sha256(destination) != checksum:
            raise FileExistsError(
                f"refusing to overwrite a different source snapshot: {destination}"
            )
        status = "reused"
    else:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{destination.name}.", dir=source_dir
        )
        os.close(descriptor)
        try:
            shutil.copy2(source, temporary_name)
            os.replace(temporary_name, destination)
        except Exception:
            Path(temporary_name).unlink(missing_ok=True)
            raise
        status = "copied"
    return {
        "original_path": str(source),
        "workspace_path": f"data/source/{destination.name}",
        "filename": destination.name,
        "sha256": checksum,
        "bytes": destination.stat().st_size,
        "status": status,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "input_dir",
        nargs="?",
        type=Path,
        help="paper/project directory; defaults to the current directory",
    )
    parser.add_argument("--paper-name", help="explicit paper or project name")
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="explicit workspace; relative paths resolve from the project root",
    )
    parser.add_argument(
        "--source",
        action="append",
        default=[],
        help="source data file to snapshot; repeat for multiple files",
    )
    parser.add_argument(
        "--create",
        action="store_true",
        help="create the directories and copy source files after resolving paths",
    )
    args = parser.parse_args()

    project_root = (args.input_dir or Path.cwd()).expanduser().resolve()
    if not project_root.is_dir():
        parser.error(f"project directory does not exist: {project_root}")

    paper_name = args.paper_name or detect_paper_name(project_root)
    paper_slug = slugify(paper_name)
    if args.output_dir:
        workspace_root = args.output_dir.expanduser()
        if not workspace_root.is_absolute():
            workspace_root = project_root / workspace_root
        workspace_root = workspace_root.resolve()
    else:
        workspace_root = (project_root / "figs" / paper_slug).resolve()

    skill_root = Path(__file__).resolve().parent.parent
    try:
        workspace_root.relative_to(skill_root)
    except ValueError:
        pass
    else:
        parser.error("figure output must not be written inside the installed Skill")

    source_dir = workspace_root / "data" / "source"
    notebook_dir = workspace_root / "notebooks"
    figure_dir = workspace_root / "figures"
    sources = [resolve_source(raw, project_root) for raw in args.source]

    payload: dict[str, object] = {
        "project_root": str(project_root),
        "paper_name": paper_name,
        "paper_slug": paper_slug,
        "workspace_root": str(workspace_root),
        "paths": {
            "source_data": str(source_dir),
            "notebooks": str(notebook_dir),
            "figures": str(figure_dir),
        },
        "sources": [str(path) for path in sources],
        "created": False,
    }

    if args.create:
        source_dir.mkdir(parents=True, exist_ok=True)
        notebook_dir.mkdir(parents=True, exist_ok=True)
        figure_dir.mkdir(parents=True, exist_ok=True)
        payload["materialized_sources"] = [copy_source(path, source_dir) for path in sources]
        payload["created"] = True

    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileExistsError, FileNotFoundError, OSError) as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(1)
