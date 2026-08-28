#!/usr/bin/env python3
"""从自包含模板创建可编辑的科研绘图 Notebook。

Create an editable figure notebook from a self-contained bundled template.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import pprint
import re
import tempfile
from pathlib import Path


CHART_TYPES = (
    "line",
    "gaussian-line",
    "bar",
    "radar",
    "scatter",
    "box",
    "heatmap",
    "errorbar",
)

TEMPLATE_FILES = {
    "gaussian-line": "gaussian_smoothed_line_chart.ipynb",
}


def slugify(value: str) -> str:
    value = re.sub(r"\s+", "-", value.strip().lower().replace("_", "-"))
    value = re.sub(r"[^\w\-]+", "-", value, flags=re.UNICODE)
    return re.sub(r"-+", "-", value).strip("-.") or "figure"


def cell_by_id(payload: dict, cell_id: str) -> dict:
    matches = [cell for cell in payload.get("cells", []) if cell.get("id") == cell_id]
    if len(matches) != 1:
        raise ValueError(f"template must contain exactly one {cell_id!r} cell")
    return matches[0]


def source_text(cell: dict) -> str:
    source = cell.get("source", "")
    return "".join(source) if isinstance(source, list) else source


def set_source(cell: dict, source: str) -> None:
    cell["source"] = source.splitlines(keepends=True)
    if cell.get("cell_type") == "code":
        cell["execution_count"] = None
        cell["outputs"] = []


def literal_dictionary(cell: dict, name: str) -> dict:
    tree = ast.parse(source_text(cell))
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if any(isinstance(target, ast.Name) and target.id == name for target in targets):
            value = ast.literal_eval(node.value)
            if isinstance(value, dict):
                return value
    raise ValueError(f"template cell must define literal {name}")


def atomic_json(path: Path, payload: dict) -> None:
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        os.replace(temporary_name, path)
    except Exception:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def update_source_file(cell: dict, source_file: str) -> None:
    lines = source_text(cell).splitlines(keepends=True)
    replacement = f"SOURCE_FILE = SOURCE_DIR / {json.dumps(source_file, ensure_ascii=False)}\n"
    indexes = [index for index, line in enumerate(lines) if line.startswith("SOURCE_FILE = SOURCE_DIR / ")]
    if len(indexes) != 1:
        raise ValueError("template load-source-data cell must define SOURCE_FILE once")
    lines[indexes[0]] = replacement
    set_source(cell, "".join(lines))


def require_arguments(parser: argparse.ArgumentParser, args: argparse.Namespace, *names: str) -> None:
    missing = [f"--{name.replace('_', '-')}" for name in names if not getattr(args, name)]
    if missing:
        parser.error(f"--chart-type {args.chart_type} requires {', '.join(missing)}")


def build_plot_spec(parser: argparse.ArgumentParser, args: argparse.Namespace) -> dict:
    """按图表类型建立数据语义映射，不把不同统计图融合为同一模式。"""
    if args.chart_type == "gaussian-line":
        require_arguments(parser, args, "x_column", "y_column")
        if args.smoothing_sigma <= 0:
            parser.error("--smoothing-sigma must be positive")
        return {
            "x_column": args.x_column,
            "y_column": args.y_column,
            "series_column": args.series_column,
            "x_label": args.x_label or args.x_column,
            "y_label": args.y_label or args.y_column,
            "smoothing": {
                "method": "scipy.ndimage.gaussian_filter1d",
                "sigma_samples": args.smoothing_sigma,
                "boundary_mode": "reflect",
                "truncate": 4.0,
                "require_shared_x_grid": True,
                "spacing_rtol": 1e-6,
                "spacing_atol": 1e-12,
            },
        }
    if args.chart_type in {"line", "bar", "radar", "scatter"}:
        require_arguments(parser, args, "x_column", "y_column")
        return {
            "x_column": args.x_column,
            "y_column": args.y_column,
            "series_column": args.series_column,
            "x_label": args.x_label or args.x_column,
            "y_label": args.y_label or args.y_column,
        }
    if args.chart_type == "box":
        require_arguments(parser, args, "x_column", "y_column")
        return {
            "category_column": args.x_column,
            "value_column": args.y_column,
            "series_column": args.series_column,
            "x_label": args.x_label or args.x_column,
            "y_label": args.y_label or args.y_column,
        }
    if args.chart_type == "heatmap":
        require_arguments(parser, args, "x_column", "y_column", "value_column")
        return {
            "x_column": args.x_column,
            "y_column": args.y_column,
            "value_column": args.value_column,
            "x_label": args.x_label or args.x_column,
            "y_label": args.y_label or args.y_column,
            "colorbar_label": args.colorbar_label or args.value_column,
        }
    if args.chart_type == "errorbar":
        require_arguments(parser, args, "x_column", "y_column")
        symmetric = bool(args.error_column)
        bounded = bool(args.lower_column and args.upper_column)
        partial_bounds = bool(args.lower_column) != bool(args.upper_column)
        if partial_bounds or symmetric == bounded:
            parser.error(
                "--chart-type errorbar requires either --error-column or both "
                "--lower-column and --upper-column"
            )
        return {
            "x_column": args.x_column,
            "y_column": args.y_column,
            "series_column": args.series_column,
            "error_column": args.error_column,
            "lower_column": args.lower_column,
            "upper_column": args.upper_column,
            "x_label": args.x_label or args.x_column,
            "y_label": args.y_label or args.y_column,
        }
    raise ValueError(f"unsupported chart type: {args.chart_type}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--paper-name", required=True)
    parser.add_argument("--figure-name", required=True)
    parser.add_argument("--chart-type", required=True, choices=CHART_TYPES)
    parser.add_argument("--source-file", required=True, help="path relative to data/source/")
    parser.add_argument("--x-column")
    parser.add_argument("--y-column")
    parser.add_argument("--value-column")
    parser.add_argument("--series-column")
    parser.add_argument("--error-column")
    parser.add_argument("--lower-column")
    parser.add_argument("--upper-column")
    parser.add_argument("--x-label")
    parser.add_argument("--y-label")
    parser.add_argument("--colorbar-label")
    parser.add_argument(
        "--smoothing-sigma",
        type=float,
        default=1.0,
        help="Gaussian sigma measured in sample intervals for --chart-type gaussian-line",
    )
    parser.add_argument(
        "--claim",
        default="请填写该图支持的准确结论。 / Replace with the precise claim this figure supports.",
    )
    args = parser.parse_args()

    workspace = args.workspace.expanduser().resolve()
    source_root = (workspace / "data" / "source").resolve()
    relative_source = Path(args.source_file)
    if relative_source.is_absolute() or ".." in relative_source.parts:
        parser.error("--source-file must be a relative path inside data/source/")
    source = (source_root / relative_source).resolve()
    try:
        source.relative_to(source_root)
    except ValueError:
        parser.error("--source-file must stay inside data/source/")
    if not source.is_file():
        parser.error(f"source file is not present in data/source/: {source}")

    notebook_dir = workspace / "notebooks"
    figure_dir = workspace / "figures"
    if not notebook_dir.is_dir() or not figure_dir.is_dir():
        parser.error("workspace must contain notebooks/ and figures/")

    figure_slug = slugify(args.figure_name)
    destination = notebook_dir / f"{figure_slug}.ipynb"
    if destination.exists():
        parser.error(f"refusing to overwrite notebook: {destination}")

    skill_root = Path(__file__).resolve().parent.parent
    template_name = TEMPLATE_FILES.get(args.chart_type, f"{args.chart_type}_chart.ipynb")
    template = skill_root / "assets" / "templates" / template_name
    payload = json.loads(template.read_text(encoding="utf-8"))

    metadata_cell = cell_by_id(payload, "figure-metadata")
    metadata = literal_dictionary(metadata_cell, "FIGURE_METADATA")
    metadata.update(
        {
            "paper_name": args.paper_name,
            "figure_slug": figure_slug,
            "chart_type": args.chart_type,
            "claim": args.claim,
            "data_sources": [
                {
                    "workspace_path": f"data/source/{relative_source.as_posix()}",
                    "sha256": "computed-at-runtime",
                }
            ],
            "outputs": [
                f"{figure_slug}.pdf",
                f"{figure_slug}.svg",
                f"{figure_slug}.png",
            ],
        }
    )
    if args.chart_type == "bar":
        metadata["axis_policy"] = {
            "x_scale": "categorical",
            "y_scale": "linear",
            "bar_baseline": "zero",
        }
    elif args.chart_type == "radar":
        metadata["axis_policy"] = {
            "radial_limits": [0, 1],
            "normalization": "values must already share the displayed scale",
        }
    elif args.chart_type in {"line", "gaussian-line", "scatter", "errorbar"}:
        metadata["axis_policy"] = {"x_scale": "linear", "y_scale": "linear"}
        if args.chart_type == "gaussian-line":
            metadata["smoothing"] = {
                "method": "scipy.ndimage.gaussian_filter1d",
                "sigma_samples": args.smoothing_sigma,
                "boundary_mode": "reflect",
                "truncate": 4.0,
                "x_spacing": "equal spacing required within each series",
                "endpoint_override": "none",
            }
    elif args.chart_type == "box":
        metadata["axis_policy"] = {"x_scale": "categorical", "y_scale": "linear"}
    elif args.chart_type == "heatmap":
        metadata["axis_policy"] = {
            "x_scale": "categorical",
            "y_scale": "categorical",
            "color_scale": "configured colormap and bounds",
        }
    set_source(
        metadata_cell,
        "FIGURE_METADATA = " + pprint.pformat(metadata, sort_dicts=False, width=100) + "\n",
    )

    plot_spec = build_plot_spec(parser, args)
    set_source(
        cell_by_id(payload, "plot-specification"),
        "# 修改这个映射后，请重新运行全部单元。\n"
        "# Edit this mapping, then rerun all cells.\n"
        + "PLOT_SPEC = "
        + pprint.pformat(plot_spec, sort_dicts=False, width=100)
        + "\n",
    )
    update_source_file(cell_by_id(payload, "load-source-data"), relative_source.as_posix())

    brief = (
        f"# {figure_slug}\n\n"
        f"论文 / Paper: **{args.paper_name}**  \n"
        f"模板 / Template: `{args.chart_type}`  \n\n"
        "修改 `PLOT_SPEC` 以调整内容，修改 `CHART_STYLE` 以调整外观。每次改变科学含义后，"
        "都要从新 kernel 运行全部单元。  \n"
        "Modify `PLOT_SPEC` for content and `CHART_STYLE` for appearance. "
        "Run all cells from a fresh kernel after each scientific change.\n"
    )
    set_source(cell_by_id(payload, "figure-brief"), brief)

    for cell in payload.get("cells", []):
        if cell.get("cell_type") == "code":
            cell["execution_count"] = None
            cell["outputs"] = []
    atomic_json(destination, payload)
    print(destination)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(1)
