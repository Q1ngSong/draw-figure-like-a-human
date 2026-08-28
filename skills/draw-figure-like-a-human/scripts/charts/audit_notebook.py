#!/usr/bin/env python3
"""静态审计 draw-figure-like-a-human Jupyter Notebook。

Statically audit a draw-figure-like-a-human Jupyter notebook.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

CHART_TYPES = {
    "line",
    "gaussian-line",
    "bar",
    "radar",
    "scatter",
    "box",
    "heatmap",
    "errorbar",
}
MIN_RASTER_PPI = 300
REQUIRED_METADATA = {
    "schema_version",
    "paper_name",
    "figure_slug",
    "chart_type",
    "claim",
    "data_sources",
    "transformations",
    "missing_values",
    "uncertainty",
    "axis_policy",
    "dimensions_inches",
    "palette",
    "outputs",
}
ABSOLUTE_PATH = re.compile(
    r"(?:/Users/|/home/|/Volumes/|(?<![A-Za-z0-9])[A-Za-z]:[\\/])"
)
SAVEFIG_DPI = re.compile(
    r"(?m)^[ \t]*savefig\.dpi[ \t]*:[ \t]*([0-9]+(?:\.[0-9]+)?)[ \t]*(?:#.*)?$"
)


def code_from_notebook(payload: dict) -> str:
    cells = payload.get("cells")
    if not isinstance(cells, list):
        raise ValueError("notebook cells must be a list")
    chunks = []
    for cell in cells:
        if cell.get("cell_type") != "code":
            continue
        source = cell.get("source", "")
        if isinstance(source, list):
            source = "".join(source)
        chunks.append(source)
    return "\n\n".join(chunks)


def parse_python(source: str) -> ast.AST:
    cleaned = "\n".join(
        line for line in source.splitlines() if not line.lstrip().startswith(("%", "!"))
    )
    return ast.parse(cleaned)


def literal_assignment(tree: ast.AST, name: str) -> dict | None:
    for node in getattr(tree, "body", []):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if any(isinstance(target, ast.Name) and target.id == name for target in targets):
            try:
                value = ast.literal_eval(node.value)
            except (ValueError, TypeError, SyntaxError):
                return None
            return value if isinstance(value, dict) else None
    return None


def validate_metadata(metadata: dict | None) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if metadata is None:
        return ["FIGURE_METADATA must be a literal dictionary"], warnings
    for key in sorted(REQUIRED_METADATA - metadata.keys()):
        errors.append(f"FIGURE_METADATA missing {key!r}")
    if metadata.get("chart_type") not in CHART_TYPES:
        errors.append(f"chart_type must be one of {sorted(CHART_TYPES)}")
    dimensions = metadata.get("dimensions_inches")
    if not (
        isinstance(dimensions, (list, tuple))
        and len(dimensions) == 2
        and all(isinstance(value, (int, float)) and value > 0 for value in dimensions)
    ):
        errors.append("dimensions_inches must be two positive numbers")
    if not isinstance(metadata.get("data_sources"), list) or not metadata.get("data_sources"):
        errors.append("data_sources must list at least one immutable source file")
    if not isinstance(metadata.get("transformations"), list):
        errors.append("transformations must be a list, even when empty")
    outputs = metadata.get("outputs")
    if not isinstance(outputs, list):
        errors.append("outputs must be a list")
    else:
        suffixes = {Path(item).suffix.lower() for item in outputs if isinstance(item, str)}
        if not {".pdf", ".svg", ".png"}.issubset(suffixes):
            errors.append("outputs must include PDF, SVG, and PNG")
        for item in outputs:
            if isinstance(item, str) and (Path(item).is_absolute() or ".." in Path(item).parts):
                errors.append(f"output must stay inside figures/: {item!r}")
    return errors, warnings


def validate_chart_style(style: dict | None, chart_type: str | None) -> list[str]:
    if style is None:
        return ["CHART_STYLE must be a literal dictionary"]
    errors = []
    required_layers = {"canvas", "marks", "legend", "axes"}
    for layer in sorted(required_layers - style.keys()):
        errors.append(f"CHART_STYLE missing {layer!r}")
    for layer in required_layers & style.keys():
        if not isinstance(style[layer], dict):
            errors.append(f"CHART_STYLE[{layer!r}] must be a dictionary")
    canvas = style.get("canvas", {})
    size = canvas.get("figure_size") if isinstance(canvas, dict) else None
    if not (
        isinstance(size, (list, tuple))
        and len(size) == 2
        and all(isinstance(value, (int, float)) and value > 0 for value in size)
    ):
        errors.append("CHART_STYLE canvas.figure_size must be two positive numbers")
    marks = style.get("marks", {})
    colors = marks.get("colors") if isinstance(marks, dict) else None
    if not isinstance(colors, list) or not colors:
        errors.append("CHART_STYLE marks.colors must be a non-empty list")
    if chart_type in {"line", "gaussian-line", "radar", "errorbar"} and isinstance(colors, list):
        for key in ("markers", "linestyles"):
            values = marks.get(key)
            if not isinstance(values, list) or len(values) != len(colors):
                errors.append(f"CHART_STYLE marks.{key} must align one-to-one with colors")
    if chart_type == "bar" and isinstance(colors, list):
        hatches = marks.get("hatches")
        if not isinstance(hatches, list) or len(hatches) < len(colors):
            errors.append("CHART_STYLE marks.hatches must cover every color")
    if chart_type == "scatter" and isinstance(colors, list):
        markers = marks.get("markers")
        if not isinstance(markers, list) or len(markers) != len(colors):
            errors.append("CHART_STYLE marks.markers must align one-to-one with colors")
    if chart_type == "heatmap" and not isinstance(marks.get("cmap"), str):
        errors.append("CHART_STYLE marks.cmap must name a Matplotlib colormap")
    return errors


def validate_gaussian_smoothing(
    metadata: dict | None, plot_spec: dict | None, source: str
) -> list[str]:
    """把高斯平滑作为可审计的数据变换，而不是纯视觉效果。"""
    if metadata is None or metadata.get("chart_type") != "gaussian-line":
        return []
    errors: list[str] = []
    if plot_spec is None:
        return ["gaussian-line PLOT_SPEC must be a literal dictionary"]
    smoothing = plot_spec.get("smoothing")
    declared = metadata.get("smoothing")
    if not isinstance(smoothing, dict):
        return ["gaussian-line PLOT_SPEC.smoothing must be a dictionary"]
    if not isinstance(declared, dict):
        errors.append("gaussian-line FIGURE_METADATA.smoothing must be a dictionary")
        declared = {}
    if smoothing.get("method") != "scipy.ndimage.gaussian_filter1d":
        errors.append("gaussian-line smoothing.method must be scipy.ndimage.gaussian_filter1d")
    sigma = smoothing.get("sigma_samples")
    if not isinstance(sigma, (int, float)) or isinstance(sigma, bool) or sigma <= 0:
        errors.append("gaussian-line smoothing.sigma_samples must be positive")
    if smoothing.get("boundary_mode") not in {"reflect", "nearest", "mirror", "wrap"}:
        errors.append("gaussian-line smoothing.boundary_mode is not supported")
    truncate = smoothing.get("truncate")
    if not isinstance(truncate, (int, float)) or isinstance(truncate, bool) or truncate <= 0:
        errors.append("gaussian-line smoothing.truncate must be positive")
    if not isinstance(smoothing.get("require_shared_x_grid"), bool):
        errors.append("gaussian-line smoothing.require_shared_x_grid must be boolean")
    for key in ("spacing_rtol", "spacing_atol"):
        value = smoothing.get(key)
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
            errors.append(f"gaussian-line smoothing.{key} must be non-negative")
    for key in ("method", "sigma_samples", "boundary_mode", "truncate"):
        if declared.get(key) != smoothing.get(key):
            errors.append(f"FIGURE_METADATA smoothing.{key} must match PLOT_SPEC")
    if declared.get("endpoint_override") != "none":
        errors.append("gaussian-line endpoints must not be manually overwritten")
    if "gaussian_filter1d" not in source:
        errors.append("gaussian-line notebook must call gaussian_filter1d")
    if "np.allclose" not in source:
        errors.append("gaussian-line notebook must validate equal x spacing")
    if re.search(r"\b\w*smooth\w*\s*\[\s*0\s*\]\s*=", source):
        errors.append("gaussian-line notebook must not overwrite a smoothed endpoint")
    return errors


def validate_palette_consistency(metadata: dict | None, style: dict | None) -> list[str]:
    """区分分类系列色板与连续热图色标，并检查声明和实际绘图一致。"""
    if metadata is None or style is None:
        return []
    errors: list[str] = []
    palette = metadata.get("palette")
    marks = style.get("marks")
    if not isinstance(palette, dict) or not isinstance(marks, dict):
        return errors
    colors = marks.get("colors")
    if palette.get("colors") != colors:
        errors.append("FIGURE_METADATA palette.colors must match CHART_STYLE marks.colors")
    if metadata.get("chart_type") == "heatmap":
        if palette.get("source_kind") != "continuous-colormap":
            errors.append("heatmap palette.source_kind must be 'continuous-colormap'")
        if palette.get("id") != marks.get("cmap"):
            errors.append("heatmap palette.id must match CHART_STYLE marks.cmap")
    elif palette.get("source_kind") == "continuous-colormap":
        errors.append("categorical chart must not declare a continuous colormap palette")
    return errors


def audit_source(source: str, tree: ast.AST) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    functions = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
    if "build_figure" not in functions:
        errors.append("notebook must define build_figure()")
    if "data/source" not in source and '"data" / "source"' not in source:
        errors.append("notebook must read immutable inputs from data/source")
    if '"figures"' not in source and "'figures'" not in source:
        errors.append("notebook must export into figures/")
    if re.search(r"__[A-Z][A-Z_]+__", source):
        errors.append("notebook contains unresolved template tokens")
    if "NotImplementedError" in source:
        errors.append("notebook still contains a NotImplementedError scaffold")
    if "BASE_MPLSTYLE" not in source or "figure-style" not in source:
        errors.append("notebook must contain a self-contained figure-style cell")
    if "CHART_STYLE" not in source or "chart-style" not in source:
        errors.append("notebook must contain an editable four-layer CHART_STYLE cell")
    if "PLOT_SPEC" not in source:
        errors.append("notebook must contain an explicit PLOT_SPEC mapping")
    if ABSOLUTE_PATH.search(source):
        errors.append("notebook contains a machine-specific absolute path")
    if re.search(r"bbox_inches\s*=\s*[\"']tight[\"']", source):
        errors.append("bbox_inches='tight' changes physical page geometry")
    if re.search(r"(?:DATA_DIR|SOURCE_DIR).*(?:to_csv|to_excel|write_text|write_bytes)", source):
        errors.append("notebook must not write derived data into data/source")
    if ".dropna(" in source:
        warnings.append("dropna() requires an explicit missing-data justification")
    if "tight_layout(" in source:
        warnings.append("tight_layout() conflicts with the constrained-layout workflow")
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        owner = node.func.value.id if isinstance(node.func.value, ast.Name) else None
        if owner in {"np", "numpy", "random"} and node.func.attr in {
            "random",
            "rand",
            "randn",
            "default_rng",
        }:
            errors.append(f"line {node.lineno}: random data generation is not allowed")
    return errors, warnings


def validate_raster_resolution(source: str, tree: ast.AST) -> list[str]:
    """要求最终 PNG 在物理排版尺寸下至少使用 300 PPI。

    Matplotlib 将位图导出参数称为 dpi；在此工作流中它与目标 PPI 使用相同数值。
    """
    errors: list[str] = []
    matches = SAVEFIG_DPI.findall(source)
    if not matches:
        errors.append(
            f"embedded style must set numeric savefig.dpi >= {MIN_RASTER_PPI}"
        )
    elif float(matches[-1]) < MIN_RASTER_PPI:
        errors.append(
            f"savefig.dpi must be >= {MIN_RASTER_PPI}, found {matches[-1]}"
        )

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for keyword in node.keywords:
                if keyword.arg != "dpi" or not isinstance(keyword.value, ast.Constant):
                    continue
                value = keyword.value.value
                if isinstance(value, (int, float)) and value < MIN_RASTER_PPI:
                    errors.append(
                        f"line {node.lineno}: explicit dpi={value} is below "
                        f"{MIN_RASTER_PPI}"
                    )
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            positional = [*node.args.posonlyargs, *node.args.args]
            defaults = [None] * (len(positional) - len(node.args.defaults)) + list(
                node.args.defaults
            )
            for argument, default in zip(positional, defaults):
                if argument.arg != "dpi" or not isinstance(default, ast.Constant):
                    continue
                value = default.value
                if isinstance(value, (int, float)) and value < MIN_RASTER_PPI:
                    errors.append(
                        f"line {node.lineno}: default dpi={value} is below "
                        f"{MIN_RASTER_PPI}"
                    )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("notebook", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.notebook.read_text(encoding="utf-8"))
    try:
        source = code_from_notebook(payload)
        tree = parse_python(source)
    except (ValueError, SyntaxError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    metadata = literal_assignment(tree, "FIGURE_METADATA")
    plot_spec = literal_assignment(tree, "PLOT_SPEC")
    errors, warnings = validate_metadata(metadata)
    chart_style = literal_assignment(tree, "CHART_STYLE")
    errors.extend(validate_chart_style(chart_style, metadata.get("chart_type") if metadata else None))
    errors.extend(validate_palette_consistency(metadata, chart_style))
    errors.extend(validate_gaussian_smoothing(metadata, plot_spec, source))
    source_errors, source_warnings = audit_source(source, tree)
    errors.extend(source_errors)
    warnings.extend(source_warnings)
    errors.extend(validate_raster_resolution(source, tree))
    for message in errors:
        print(f"ERROR: {message}")
    for message in warnings:
        print(f"WARNING: {message}")
    if errors:
        print(f"FAIL: {len(errors)} error(s), {len(warnings)} warning(s)", file=sys.stderr)
        return 1
    print(f"PASS: {args.notebook} ({len(warnings)} warning(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
