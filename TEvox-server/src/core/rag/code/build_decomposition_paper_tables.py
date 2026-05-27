# evox-server/src/core/rag/code/build_decomposition_paper_tables.py
"""
从 static_decomposition_metrics.json 与 function_vs_flows_metrics.json 生成论文用表格数据。

表格设计（精简指标，仅保留足以说明「拆解后更内聚、可复用性更高」）：

Table 1 — File → Submodules（静态：内聚/耦合/可复用）
  列：Metric | Before (File) | After (Submodule) | Note
  行：
  1. Declaration count per module — Before: 整文件声明数均值；After: 各 submodule 均值的再平均 → 拆解后单模块更聚焦
  2. Naming consistency        — Before/After 均值 → 拆解后命名更一致（内聚）
  3. Module granularity         — Before: 1；After: 平均 submodule 数 → 粒度更细、可复用单元更多
  4. Coupling (Ce)              — Before: N/A；After: 平均 Ce → 低耦合

Table 2 — Function → Flows（Halstead/复杂度）
  列：Metric | Before (Function) | After (Flow) | Note
  行：
  1. Cyclomatic complexity — 拆解后单 flow 更简单
  2. Lines of code         — 拆解后单 flow 更短
  3. Halstead volume       — 拆解后信息量更小
  4. Halstead difficulty   — 拆解后理解难度更低
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List

# 默认路径（相对项目根 evox-server）
DEFAULT_STATIC_PATH = ".rag/xiaozhi/grapher/static_decomposition_metrics.json"
DEFAULT_FUNCTION_FLOWS_PATH = ".rag/xiaozhi/grapher/function_vs_flows_metrics.json"
DEFAULT_OUTPUT_DIR = ".rag/xiaozhi/grapher"


def _round4(x: float) -> float:
    return round(x, 4)


def _round2(x: float) -> float:
    return round(x, 2)


def load_json(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_table1_static(static_path: str) -> Dict[str, Any]:
    """
    处理 static_decomposition_metrics.json：
    仅保留有 after_aggregate 的 file，汇总 Before/After 均值，得到 Table 1 行数据。
    """
    data = load_json(static_path)
    # 只保留有拆解结果的 file
    decomposed = [r for r in data if r.get("after_aggregate") is not None]
    if not decomposed:
        return {"rows": [], "n_files": 0, "n_decomposed": 0}

    before_dec = [r["before"]["declaration_count"] for r in decomposed]
    before_naming = [r["before"]["naming_consistency"] for r in decomposed]
    after_dec = [r["after_aggregate"]["mean_declaration_count"] for r in decomposed]
    after_naming = [r["after_aggregate"]["mean_naming_consistency"] for r in decomposed]
    after_count = [r["after_aggregate"]["submodule_count"] for r in decomposed]
    after_ce = [r["after_aggregate"]["mean_Ce"] for r in decomposed]

    n = len(decomposed)
    rows = [
        {
            "metric": "Declaration count per module",
            "before": _round2(sum(before_dec) / n),
            "after": _round2(sum(after_dec) / n),
            "note": "Smaller per module → more focused (cohesion)",
        },
        {
            "metric": "Naming consistency",
            "before": _round4(sum(before_naming) / n),
            "after": _round4(sum(after_naming) / n),
            "note": "Higher → more cohesive naming within module",
        },
        {
            "metric": "Module granularity",
            "before": 1,
            "after": _round2(sum(after_count) / n),
            "note": "Finer units → higher reusability",
        },
        {
            "metric": "Coupling (Ce, mean)",
            "before": "—",
            "after": _round4(sum(after_ce) / n),
            "note": "Lower → lower coupling",
        },
    ]
    return {
        "title": "File → Submodules (static: cohesion / coupling / reusability)",
        "n_files_total": len(data),
        "n_files_decomposed": n,
        "columns": ["Metric", "Before (File)", "After (Submodule)", "Note"],
        "rows": rows,
    }


def build_table2_function_flows(flows_path: str) -> Dict[str, Any]:
    """
    处理 function_vs_flows_metrics.json：
    仅保留有非空 aggregate 的 function，汇总 Before/After 均值，得到 Table 2 行数据。
    """
    data = load_json(flows_path)
    # 只保留有拆解出 flow 的 function（aggregate 非空）
    with_flows = [
        r
        for r in data
        if r.get("result")
        and r["result"].get("aggregate")
        and isinstance(r["result"]["aggregate"], dict)
        and len(r["result"]["aggregate"]) > 0
    ]
    if not with_flows:
        return {"rows": [], "n_functions": 0, "n_with_flows": 0}

    before_cc = []
    before_loc = []
    before_vol = []
    before_diff = []
    after_cc = []
    after_loc = []
    after_vol = []
    after_diff = []
    for r in with_flows:
        res = r["result"]
        fm = res["function_metrics"]
        ag = res["aggregate"]
        before_cc.append(fm["avg_cyclomatic_complexity"])
        before_loc.append(fm["lines_of_code"])
        before_vol.append(fm["halstead_volume"])
        before_diff.append(fm["halstead_difficulty"])
        after_cc.append(ag["mean_avg_cyclomatic_complexity"])
        after_loc.append(ag["mean_lines_of_code"])
        after_vol.append(ag["mean_halstead_volume"])
        after_diff.append(ag["mean_halstead_difficulty"])

    n = len(with_flows)
    rows = [
        {
            "metric": "Cyclomatic complexity",
            "before": _round4(sum(before_cc) / n),
            "after": _round4(sum(after_cc) / n),
            "note": "Lower per flow → simpler control flow",
        },
        {
            "metric": "Lines of code",
            "before": _round2(sum(before_loc) / n),
            "after": _round2(sum(after_loc) / n),
            "note": "Smaller per flow → more focused",
        },
        {
            "metric": "Halstead volume",
            "before": _round2(sum(before_vol) / n),
            "after": _round2(sum(after_vol) / n),
            "note": "Lower per flow → less information to maintain",
        },
        {
            "metric": "Halstead difficulty",
            "before": _round4(sum(before_diff) / n),
            "after": _round4(sum(after_diff) / n),
            "note": "Lower per flow → easier to understand",
        },
    ]
    return {
        "title": "Function → Flows (Halstead / complexity)",
        "n_functions_total": len(data),
        "n_functions_with_flows": n,
        "columns": ["Metric", "Before (Function)", "After (Flow)", "Note"],
        "rows": rows,
    }


def to_markdown(table: Dict[str, Any]) -> str:
    cols = table["columns"]
    rows = table["rows"]
    lines = [f"## {table.get('title', '')}", ""]
    header = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join(["---"] * len(cols)) + " |"
    lines.append(header)
    lines.append(sep)
    for r in rows:
        line = "| " + " | ".join(str(r.get(c.lower().split()[0].replace("(", ""), "")) for c in cols) + " |"
        # map column to key
        line = (
            "| "
            + str(r.get("metric", ""))
            + " | "
            + str(r.get("before", ""))
            + " | "
            + str(r.get("after", ""))
            + " | "
            + str(r.get("note", ""))
            + " |"
        )
        lines.append(line)
    lines.append("")
    return "\n".join(lines)


def to_latex(table: Dict[str, Any]) -> str:
    cols = table["columns"]
    rows = table["rows"]
    ncol = len(cols)
    # 最后一列 Note 用 p{5.5cm} 以便换行；需 \usepackage{booktabs}
    col_spec = "lrrp{5.5cm}" if ncol == 4 else "l" + "r" * (ncol - 1)
    lines = [
        "% " + table.get("title", ""),
        "% Requires: \\usepackage{booktabs}",
        "\\begin{table}[htbp]",
        "\\centering",
        "\\caption{" + (table.get("title", "").replace("→", "$\\rightarrow$")) + "}",
        "\\begin{tabular}{" + col_spec + "}",
        "\\toprule",
        " & ".join(cols) + " \\\\",
        "\\midrule",
    ]
    for r in rows:
        cells = [str(r.get("metric", "")), str(r.get("before", "")), str(r.get("after", "")), str(r.get("note", ""))]
        lines.append(" & ".join(cells[:ncol]) + " \\\\")
    lines.append("\\bottomrule")
    lines.append("\\end{tabular}")
    lines.append("\\end{table}")
    return "\n".join(lines)


def main(
    static_path: str = DEFAULT_STATIC_PATH,
    function_flows_path: str = DEFAULT_FUNCTION_FLOWS_PATH,
    output_dir: str = DEFAULT_OUTPUT_DIR,
) -> Dict[str, Any]:
    # 项目根 = evox-server（脚本在 src/core/rag/code/ 下，向上 5 级）
    base = Path(__file__).resolve().parent.parent.parent.parent.parent
    static_full = base / static_path
    flows_full = base / function_flows_path
    out_dir = base / output_dir

    if not static_full.is_file():
        raise FileNotFoundError(f"Static metrics not found: {static_full}")
    if not flows_full.is_file():
        raise FileNotFoundError(f"Function-vs-flows metrics not found: {flows_full}")

    table1 = build_table1_static(str(static_full))
    table2 = build_table2_function_flows(str(flows_full))

    out_dir.mkdir(parents=True, exist_ok=True)

    # 1) JSON：程序可读，便于后续画图或再生成表格
    out_json = out_dir / "table_paper.json"
    payload = {"table1_file_submodules": table1, "table2_function_flows": table2}
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print("Wrote %s" % out_json)

    # 2) Markdown：可直接贴入论文或转 PDF
    out_md = out_dir / "table_paper.md"
    md_lines = [
        "# Paper tables (decomposition metrics)",
        "",
        "Generated from static_decomposition_metrics.json and function_vs_flows_metrics.json.",
        "",
    ]
    md_lines.append(to_markdown(table1))
    md_lines.append("")
    md_lines.append(to_markdown(table2))
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))
    print("Wrote %s" % out_md)

    # 3) LaTeX：可插入论文
    out_tex = out_dir / "table_paper.tex"
    tex_lines = [
        "% Paper tables: decomposition metrics",
        "% Table 1: File -> Submodules",
        to_latex(table1),
        "",
        "% Table 2: Function -> Flows",
        to_latex(table2),
    ]
    with open(out_tex, "w", encoding="utf-8") as f:
        f.write("\n".join(tex_lines))
    print("Wrote %s" % out_tex)

    return payload


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build paper tables from decomposition metrics JSON")
    parser.add_argument("--static", default=DEFAULT_STATIC_PATH, help="Path to static_decomposition_metrics.json")
    parser.add_argument("--flows", default=DEFAULT_FUNCTION_FLOWS_PATH, help="Path to function_vs_flows_metrics.json")
    parser.add_argument("--out-dir", default=DEFAULT_OUTPUT_DIR, help="Output directory for table_paper.*")
    args = parser.parse_args()
    main(static_path=args.static, function_flows_path=args.flows, output_dir=args.out_dir)
