# 将现有绘图代码转成模板

目标不是复制原图，而是保留可复用的绘图结构，同时清除原论文、数据集和机器环境的
偶然细节。输出始终是 `.ipynb`。

## 1. 确定模板边界

先识别输入代码实际生成的图。如果一个 Notebook 同时生成多张无关图，为每张图分别
创建模板。根据主要视觉语法，从 `line_chart.ipynb`、
`gaussian_smoothed_line_chart.ipynb`、`bar_chart.ipynb`、
`radar_chart.ipynb`、`scatter_chart.ipynb`、`box_chart.ipynb`、
`heatmap_chart.ipynb` 或 `errorbar_chart.ipynb` 中选择骨架；
不要从空白 Notebook 重新搭建公共结构，也不要把不同图形融合为一个 `mode` 模板。

输入 `.py` 时，将导入与路径、数据读取、参数、内存转换、绘图函数和导出分别放入
Notebook 单元。输入 `.ipynb` 时先找出真正影响目标图的单元，忽略实验日志和其他图。

## 2. 区分保留与参数化内容

保留：

- 图表类型和有意义的几何结构；
- 正确的数据变换、误差计算和排序逻辑；
- 能泛化的 legend、坐标轴和注释处理；
- 经过验证的导出逻辑。

参数化或删除：

- 绝对路径、用户名、环境目录和临时文件；
- 论文名、数据集名、固定标题和具体输出文件名；
- 固定列名、系列名称、颜色数量和类别顺序；
- 仅为某次实验存在的筛选条件；
- 已执行输出、execution count、调试打印和无关单元；
- 随机生成或硬编码的示例观测值。

不要把坐标范围、归一化或筛选误当作视觉样式自动继承。这些内容具有科学含义，应由
模板使用者明确确认。

## 3. 使用标准 Notebook 结构

转换后的 Notebook 按以下顺序组织：

1. 图的用途与修改提示；
2. imports 和相对工作区路径；
3. 自包含的 `figure-style` 单元；
4. `FIGURE_METADATA`；
5. 读取 `data/source/`；
6. `PLOT_SPEC`；
7. 四层 `CHART_STYLE`；
8. `in-memory-transform`；
9. `build_figure()`；
10. PDF、SVG、PNG 导出。

从现有模板复制 `figure-style` 单元。`base.mplstyle` 只包含跨图复用的 Matplotlib
rcParams；柱宽、箱体宽度、热图色标、误差帽、雷达填充透明度、坐标范围和
legend 位置仍留在 `CHART_STYLE`。

## 4. 建立清楚的参数入口

`PLOT_SPEC` 负责数据语义，例如列名、轴标签、系列字段以及高斯平滑参数。
`CHART_STYLE` 只负责视觉：

```python
CHART_STYLE = {
    "canvas": {...},
    "marks": {...},
    "legend": {...},
    "axes": {...},
}
```

将绘图函数中的颜色、marker、线型、线宽、字号、背景、grid、spines、legend 和
tick 常量移入对应层。`build_figure()` 只读取这些配置，不保留重复的隐藏默认值。

系列样式必须一一对应。例如 `colors[0]`、`markers[0]` 和 `linestyles[0]` 表示同一
系列；柱图的 `hatches[0]` 也遵循同一顺序。legend 使用真实 artists 的 handles。

## 5. 模板验收

完成前确认：

- 文件是无执行输出、无 execution count 的有效 `.ipynb`；
- 不含 `/Users/...`、`/Volumes/...` 等绝对路径；
- 不含原实验的真实数值或随机生成的替代数据；
- 所有项目专属值都集中在 `FIGURE_METADATA`、`SOURCE_FILE` 或 `PLOT_SPEC`；
- 视觉常量集中在四层 `CHART_STYLE`；
- 派生数据只存在于 Notebook 内存；
- `savefig.dpi` 及任何显式 PNG 保存 `dpi` 均不低于 300，保证 PNG 在最终排版尺寸下
  至少达到 300 PPI；
- 填入一个小型、明确标为测试夹具的数据文件后能够从新 kernel Run All；
- PDF、SVG 和 PNG 的尺寸、内容和 legend 对应关系一致。

先用静态审计检查新模板：

```bash
python3 <skill-root>/scripts/charts/audit_notebook.py /path/to/new-template.ipynb
```

然后把模板复制到一个包含 `data/source/`、`notebooks/` 和 `figures/` 的临时工作区，
填入明确标记为测试夹具的数据，再执行：

```bash
python3 <skill-root>/scripts/charts/execute_notebook.py \
  /path/to/test-workspace/notebooks/new-template.ipynb
```

只有用户明确要求更新全局视觉基线时，才比较多个示例并人工修改
`assets/styles/base.mplstyle`。单个代码文件中的局部风格默认只进入新模板的
`CHART_STYLE`，不提升为所有模板的默认值。
