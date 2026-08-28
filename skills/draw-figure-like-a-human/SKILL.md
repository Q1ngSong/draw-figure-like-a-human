---
name: draw-figure-like-a-human
description: Create publication-quality Matplotlib figures from reusable Jupyter Notebook templates, or turn an existing plotting notebook or Python script into a reusable notebook template. Use for editable and reproducible line, Gaussian-smoothed line, bar, radar, scatter, box, heatmap, and error-bar charts commonly used in CCF A-class computer science papers. Do not use for method diagrams, architectures, flowcharts, or decorative illustrations.
---

# Draw Figure Like a Human

以 Jupyter Notebook 作为科研绘图的可编辑源码，只处理两种任务：

1. 使用独立模板绘制 CCF A 类计算机科学论文常用的折线图、高斯平滑折线图、柱状图、
   雷达图、散点图、箱线图、热图或误差棒图；
2. 将现有 `.ipynb` 或 Matplotlib `.py` 代码整理成可复用模板。

默认视觉底盘来自 `assets/styles/base.mplstyle`，并已嵌入每个模板，因此复制出去的
Notebook 是自包含的。四个脚本只承担适合自动化的确定性工作：创建目录、填写模板、
静态检查和从新 kernel 执行；数据含义、转换方法和视觉取舍仍由 Agent 与用户判断。
执行脚本时使用安装了 Jupyter、Matplotlib、pandas、NumPy、SciPy、`nbformat` 和
`nbclient` 的同一个 Python 环境；读取 Excel 还需要 `openpyxl` 等引擎。

最终优先交付矢量 PDF 和 SVG。PNG 必须在论文最终排版尺寸下至少达到 300 PPI；
Matplotlib 使用 `dpi` 作为对应的导出参数名，因此 `savefig.dpi` 及任何显式 PNG
保存参数都不得低于 300。`figure.dpi` 只控制 Notebook 交互预览。期刊要求更高时
按更高值导出。

## 选择工作流

### 使用模板

选择最接近目标的模板：

- `assets/templates/line_chart.ipynb`
- `assets/templates/gaussian_smoothed_line_chart.ipynb`
- `assets/templates/bar_chart.ipynb`
- `assets/templates/radar_chart.ipynb`
- `assets/templates/scatter_chart.ipynb`
- `assets/templates/box_chart.ipynb`
- `assets/templates/heatmap_chart.ipynb`
- `assets/templates/errorbar_chart.ipynb`

每种图保持为单独文件。不要为了减少文件数量而在一个 Notebook 中增加图表 `mode`；
只有用户明确要求，并且多个模板的科学语义和验收条件已经稳定时，才讨论共享组件。

开始前阅读 `references/using-templates.md`，然后：

1. 检查真实数据和用户想表达的结论；
2. 用 `scripts/resolve_io.py` 解析并创建工作区，同时复制源数据；
3. 用 `scripts/create_notebook.py` 选择模板并填写基础参数；
4. 修改 Notebook 中的转换逻辑、`FIGURE_METADATA`、`PLOT_SPEC` 和
   `CHART_STYLE`；
5. 用 `scripts/charts/audit_notebook.py` 做静态检查；
6. 用 `scripts/charts/execute_notebook.py` 从新 kernel 执行全部单元，检查
   `figures/` 中的 PDF、SVG 和 PNG。

### 将代码转为模板

输入可以是一个 `.ipynb` 或绘图 `.py` 文件。阅读
`references/building-templates.md`，以最接近的现有模板为骨架，保留有科学含义的
计算和绘图逻辑，移除论文、机器和数据集专属内容。

转换结果必须是一个结构清晰、无执行输出、无绝对路径的 `.ipynb`。完成转换后使用
同一套 `audit_notebook.py` 和 `execute_notebook.py` 验收。不要通过正则批量抽取
样式，也不要自动修改 `base.mplstyle`。只有用户明确要求把多个示例中的共同视觉
特征提升为全局默认时，才人工审阅并更新该文件。

## 默认输入与输出

输入可以是用户提示词，也可以是论文或实验项目文件夹。论文文字可以说明图的目的、
标签和结论，但不能代替缺失的数值数据。

用户指定的输出目录优先；否则使用：

```text
{project_root}/figs/{paper_slug}/
├── data/
│   └── source/          # CSV、Excel、JSON 等不可变输入
├── notebooks/           # 可编辑、可重跑的 .ipynb
└── figures/             # PDF、SVG、PNG
```

不要创建 `data/derived/`。聚合、归一化、排序、平滑和误差计算只存在于 Notebook
内存，并在代码或 `FIGURE_METADATA` 中明确记录。

## Notebook 约定

每个模板保留四个清楚的修改入口：

- `FIGURE_METADATA`：图名、论文名、结论、数据来源和转换说明；
- `SOURCE_FILE`：`../data/source/` 中的相对数据文件；
- `PLOT_SPEC`：列名、轴标签和系列字段；
- `CHART_STYLE`：`canvas`、`marks`、`legend`、`axes` 四层视觉配置。

`build_figure()` 返回完整的 Matplotlib `Figure`。颜色、marker、线型、柱宽、
hatch、legend 和坐标轴文字等视觉常量应从 `CHART_STYLE` 读取，不要散落在绘图
函数中。图例必须使用真实绘图对象的 handles，保持图标与颜色、marker、线型或
hatch 一致。

新增模板继续沿用折线图和柱状图的基础视觉规范：四条坐标轴边框均可见，边框使用
统一灰色与线宽，网格使用浅灰虚线，轴标签和刻度保持相同的粗体层级，分类图例使用
相同的白底细边框。不要默认生成隐藏上边框或右边框的半开放坐标轴。

分类系列图统一使用 `base-style-cycle` 的六色顺序，并让系列标签稳定映射到颜色及冗余
marker、线型或 hatch。热图例外：它使用连续 colormap 编码数值大小，palette
`source_kind` 必须是 `continuous-colormap`，palette `id` 必须与 `marks.cmap`
一致。不要把热图每一行的方法名称误当成分类颜色身份。

## 科研真实性

- 只使用用户提供或真实源文件中的数值，不编造缺失数据或随机补齐图表；
- 不静默删除缺失值，不把单次运行中的重复观测当成独立实验；
- 明确记录筛选、聚合、归一化、平滑、不确定性和坐标范围；
- 柱状图通常从零开始；雷达图必须明确归一化方法和统一径向范围；
- 高斯平滑不是参数拟合。仅对等距横轴数据按系列排序后使用，明确记录以样本间隔为单位
  的 `sigma`、边界模式和截断半径；不得手工覆盖平滑后的端点；
- 箱线图默认保留异常值，不把箱体误当作误差区间；
- 热图不自动聚合重复单元，色标范围和中心点需要明确记录；
- 误差棒必须说明表示 SD、SE、CI 还是其他区间，不能从列名猜测；
- 样式修改不得暗中改变数据、系列顺序、轴语义或统计方法；
- PNG 在最终排版尺寸下至少为 300 PPI，PDF 和 SVG 保持矢量输出；
- 最终在论文实际宽度检查文字碰撞、裁切、灰度可辨性和图例对应关系。
