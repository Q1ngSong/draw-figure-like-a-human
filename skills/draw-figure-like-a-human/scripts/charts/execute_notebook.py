#!/usr/bin/env python3
"""从 notebooks/ 目录原子执行科研绘图 Notebook。

Execute a figure notebook atomically from its notebooks/ directory.
"""

from __future__ import annotations

import argparse
import os
import tempfile
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("notebook", type=Path)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--kernel", default="python3")
    parser.add_argument(
        "--executed-output",
        type=Path,
        help="write an executed copy instead of atomically updating the source notebook",
    )
    args = parser.parse_args()

    try:
        import nbformat
        from nbclient import NotebookClient
    except ImportError as exc:
        parser.error(f"nbformat and nbclient are required: {exc}")

    notebook = args.notebook.expanduser().resolve()
    if not notebook.is_file() or notebook.suffix.lower() != ".ipynb":
        parser.error(f"notebook not found: {notebook}")
    if notebook.parent.name != "notebooks":
        parser.error("figure notebook must live directly in a notebooks/ directory")
    workspace_root = notebook.parent.parent
    if not (workspace_root / "data" / "source").is_dir():
        parser.error("workspace is missing data/source/")
    if not (workspace_root / "figures").is_dir():
        parser.error("workspace is missing figures/")

    payload = nbformat.read(notebook, as_version=4)
    client = NotebookClient(
        payload,
        timeout=args.timeout,
        kernel_name=args.kernel,
        allow_errors=False,
    )
    client.execute(cwd=str(notebook.parent))

    destination = (args.executed_output or notebook).expanduser().resolve()
    if args.executed_output and destination.exists():
        parser.error(f"refusing to overwrite executed copy: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".ipynb", dir=destination.parent
    )
    os.close(descriptor)
    try:
        nbformat.write(payload, temporary_name)
        os.replace(temporary_name, destination)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
