# 使用 Notebook 模板

## 1. 选择模板

- 随横轴连续变化的数据、学习曲线和带误差区间的趋势使用 `line_chart.ipynb`；
- 需要明确展示高斯平滑趋势、同时保留原始淡线时使用
  `gaussian_smoothed_line_chart.ipynb`。高斯平滑是描述性变换，不是参数拟合；
- 离散类别比较、消融实验、分组或堆叠结果使用 `bar_chart.ipynb`；
- 只有多个同向指标确实需要展示整体轮廓时才使用 `radar_chart.ipynb`。如果精确
  比较更重要，优先考虑表格、散点图或柱状图；
- 两个连续变量的关系或分组观测使用 `scatter_chart.ipynb`；
- 比较中位数、四分位距和异常值使用 `box_chart.ipynb`；
- 方法 × 数据集矩阵、相关矩阵或参数网格使用 `heatmap_chart.ipynb`；
- 展示估计量及 SD、SE、CI 等已知不确定性使用 `errorbar_chart.ipynb`。

每种图保持为一个单独 Notebook。不要把不同图形压缩为一个带 `mode` 开关的模板。

不要直接修改 Skill 中的模板。优先使用 `create_notebook.py` 将它复制到项目的
`notebooks/` 并填入基础参数，然后再编辑生成的文件。

## 2. 准备项目目录

以下命令中的 `python3` 表示安装了本项目 Jupyter 依赖的 Python 解释器。如果系统
Python 和 Jupyter 来自不同环境，应使用 Jupyter 所在环境的 Python。

```text
figs/{paper_slug}/
├── data/
│   └── source/
├── notebooks/
└── figures/
```

用户指定目录时使用用户目录。否则在论文或实验项目根目录下创建上述结构。只把本图
实际使用的 CSV、Excel 或 JSON 文件复制到 `data/source/`。如果用户在提示词中提供
了完整数值表，可以先原样保存为 CSV；不要根据论文描述推测数值。

Notebook 应从 `notebooks/` 目录运行，并通过 `../data/source/` 和
`../figures/` 访问数据与输出。不要写入机器专属绝对路径。

先解析路径，确认输出正确后再增加 `--create`：

```bash
python3 <skill-root>/scripts/resolve_io.py /path/to/paper \
  --paper-name "Paper Name" \
  --source results.csv

python3 <skill-root>/scripts/resolve_io.py /path/to/paper \
  --paper-name "Paper Name" \
  --source results.csv \
  --create
```

用户指定输出目录时增加 `--output-dir /path/to/output`。脚本不会创建
`figure-project.json`，也不会处理配色 catalog；它只建立三层目录、复制源数据并
报告 checksum。

## 3. 修改四个入口

使用模板生成 Notebook：

```bash
python3 <skill-root>/scripts/create_notebook.py /path/to/figs/paper-slug \
  --paper-name "Paper Name" \
  --figure-name "fig-01-results" \
  --chart-type line \
  --source-file results.csv \
  --x-column epoch \
  --y-column accuracy \
  --series-column method \
  --x-label "Epoch" \
  --y-label "Accuracy (%)" \
  --claim "The proposed method converges faster."
```

脚本拒绝覆盖已有 Notebook。它不会修改或重新注入 style，只填写已有自包含模板中的
metadata、源文件路径和 `PLOT_SPEC`。

### `FIGURE_METADATA`

更新 `paper_name`、`figure_slug`、`claim`、`data_sources`、`transformations`、
`uncertainty`、`axis_policy` 和输出文件名。它用于记录科学决策，不是装饰信息。

### `SOURCE_FILE`

把默认的 `results.csv` 改成 `data/source/` 中的真实文件名。模板支持 CSV、TSV、
Excel 和 JSON。一个图需要多个源文件时，显式定义多个路径和读取步骤。

### `PLOT_SPEC`

不同模板拥有独立的数据语义字段：折线图、高斯平滑折线图、柱状图、雷达图和散点图使用
`x_column`、`y_column` 与可选 `series_column`；箱线图使用 `category_column` 和
`value_column`；热图使用 `x_column`、`y_column`、
`value_column` 与 `colorbar_label`；误差棒图另外使用 `error_column`，或成对使用
`lower_column` 与 `upper_column`。没有系列列时使用 `None`。轴标签应带单位；不要
让代码依赖 DataFrame 当前排序来决定稳定的系列身份。

高斯平滑折线图还使用 `PLOT_SPEC.smoothing` 记录
`sigma_samples`、`boundary_mode`、`truncate` 和横轴间距容差。`sigma_samples` 的单位
是样本间隔，因此模板要求每个系列的横轴严格递增且等距，默认还要求所有系列共享同一
横轴网格。横轴不等距时，应先明确重采样方法，不能直接把数组下标当作真实距离。

### `CHART_STYLE`

- `canvas`：画布尺寸、背景、grid 和 spines；
- `marks`：颜色、marker、线型、线宽、柱宽、hatch 或雷达填充；
- `legend`：位置、列数、字体、背景和边框；
- `axes`：轴标签、刻度、粗体、旋转、格式、scale 和 limits。

默认外观以 `line_chart.ipynb` 和 `bar_chart.ipynb` 为基准：保留完整四边框、浅灰
虚线网格、粗体轴标签与刻度，并为分类图例保留白底细边框。除非目标期刊或用户明确
要求，不要隐藏上边框和右边框形成半开放坐标轴。

常用 marker：`o` 圆、`s` 方块、`^` 上三角、`v` 下三角、`D` 菱形、`X`
实心叉。常用线型：`-` 实线、`--` 虚线、`-.` 点划线、`:` 点线。除颜色外，至少
使用 marker、线型、位置或 hatch 中的一种冗余编码。

图例直接读取绘制出的 artists 或由实际箱体样式生成的 handles，不要再手工维护第二份
颜色与标记映射。

分类系列图沿用 `base-style-cycle` 的颜色顺序；跨图比较同一批系列时，以稳定系列标签
解析颜色，不要根据 DataFrame 出现顺序临时换色。热图颜色表示单元格数值而不是行或列
的系列身份，因此使用连续 colormap，并让 `FIGURE_METADATA.palette.id` 与
`CHART_STYLE.marks.cmap` 保持一致。

## 4. 数据转换

聚合、归一化、排序、平滑和不确定性计算写在 `in-memory-transform` 单元中。不要把
派生表写回 `data/source/`，也不要新建 `data/derived/`。每项转换都应有可读的变量
和简短说明。

对 `dropna()`、截断坐标轴、平滑、归一化和误差带尤其谨慎：它们会影响读者对结果
的判断，不能作为纯粹的排版操作。

高斯平滑使用 SciPy `gaussian_filter1d`，默认 `boundary_mode="reflect"`。原始观测以
同色淡线保留，粗线和 marker 表示平滑后的值。不要像旧实验脚本那样把第一个平滑点
手工改回 `0`、`100` 或原始值；如端点具有硬约束，应把该约束作为单独模型说明，而不是
在平滑后悄悄覆盖。

## 5. 执行和检查

先静态检查，再从新 kernel 执行：

```bash
python3 <skill-root>/scripts/charts/audit_notebook.py \
  /path/to/figs/paper-slug/notebooks/fig-01-results.ipynb

python3 <skill-root>/scripts/charts/execute_notebook.py \
  /path/to/figs/paper-slug/notebooks/fig-01-results.ipynb
```

执行脚本只有在所有单元成功后才原子更新 Notebook。之后确认 PDF、SVG、PNG 均已
刷新，并在论文最终宽度检查轴标题、刻度、legend、裁切、元素重叠以及颜色与 marker、
线型或 hatch 的对应关系。

PNG 必须在最终排版尺寸下至少达到 300 PPI。Matplotlib 将该导出参数称为 `dpi`，
模板的 `savefig.dpi` 和 PNG 保存函数默认均为 300。`figure.dpi: 100` 只影响
Notebook 内的交互预览，不表示最终图片分辨率。PDF 和 SVG 是矢量输出，不使用 PPI
判断清晰度；期刊要求 600 PPI 等更高值时，应同步提高 PNG 导出 `dpi`。

不要使用 `bbox_inches="tight"` 暗中改变最终画布尺寸。需要更多空间时，明确调整
`canvas.figure_size`、legend 位置或标签长度。
