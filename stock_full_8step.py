#!/usr/bin/env python3
"""
8步分析框架 — 完整整合脚本
===========================
输入 Phase 1 JSON 数据 → 输出 8步框架的 MD 报告草稿 + HTML 可视化报告

用法:
  python stock_full_8step.py output/data_688676_ths.json

输出:
  output/个股研究8步-{名称}.md    (8步框架MD草稿)
  output/个股研究-{名称}.html     (完整HTML报告)

说明:
  - 所有自动化可填充的数据来自Pipeline(财务/行情/一致预期/股东…)
  - 定性的AI分析部分(S1宏观/S2竞争/S7对标/S8跟踪)以 [AI] 标记
  - 分析师(我) 在发送前填充标记部分即可
"""

from __future__ import annotations

import argparse
import json, os, sys, datetime as dt
from typing import Any

# ──────────── 引入 HTML 生成器 ────────────
sys.path.insert(0, os.path.dirname(__file__))
import stock_html_report as html_mod


class StepBuilder:
    """从Pipeline JSON构建8步框架的MD草稿"""

    def __init__(self, data: dict):
        self.d = data
        self.b = data.get("blocks", data)
        self.spot = self._get("spot", [{}])[0]
        self.bs_info = self._get("basic_info_bs", [{}])[0]
        self.rb = html_mod.ReportBuilder(data)  # 复用HTML的builder

    def _get(self, key, default=None):
        v = self.b.get(key)
        return v if v is not None else (default() if callable(default) else default)

    # ─── S0: 任务锁定 ───
    def step0(self) -> str:
        name = self.rb.stock_name()
        code = self.rb.stock_code()
        sector = self.rb.sector()
        ipo = self.rb.ipo_date()
        shares = self.rb.total_shares()
        mcap = self.rb.market_cap()
        biz = self.rb.biz_desc()
        zygc = self.zygc_top3()

        pe, pb = self.rb.last_pe_pb()
        pe_s = f"{pe:.1f}x" if pe else "—"
        pb_s = f"{pb:.2f}" if pb else "—"

        return f"""## S0: 任务锁定 — {name}({code})

| 项目 | 数据 |
|------|------|
| 代码 | {code} | {sector} |
| 上市 | {ipo} | 股本 {shares}亿 | 市值 {mcap} |
| PE-TTM | {pe_s} | PB | {pb_s} |

**主营业务**: {biz}

**主营构成**: {zygc}
"""

    def zygc_top3(self) -> str:
        bd = self.rb.revenue_breakdown()
        if bd:
            return "、".join(f"{x['name']}({x['value']:.0f}%)" for x in bd[:3])
        return "—"

    # ─── S1: 宏观与周期定位 ───
    def step1(self) -> str:
        sector = self.rb.sector()
        pe, _ = self.rb.last_pe_pb()
        pe_s = f"{pe:.0f}x" if pe else "—"
        return f"""## S1: 宏观与周期定位 — 需AI补充

**经济阶段**: [AI] 当前宏观经济所处阶段分析

**行业周期**: [AI] {sector}行业当前处于(导入/成长/成熟/衰退)期
  - 参考: PE {pe_s} | 行业景气判断

**政策方向**: [AI] 相关政策分析
"""

    # ─── S2: 产业链拆解 ───
    def step2(self) -> str:
        sector = self.rb.sector()
        metrics = self.rb.key_metrics()
        gp = metrics.get("销售毛利率", "—")
        return f"""## S2: 产业链深度拆解

**价值链定位**: 毛利率 {gp}

| 环节 | 内容 | 利润率参考 |
|------|------|-----------|
| 上游 | [AI] | — |
| ★中游 | {self.rb.stock_name()} | 毛利率 {gp} |
| 下游 | [AI] | — |

**竞争格局**: [AI] 主要竞争对手、市场集中度

**核心竞争优势**: [AI] 技术/品牌/渠道/成本壁垒
"""

    # ─── S3: 公司筛选与质量评分 ───
    def step3(self) -> str:
        score_items, total, _ = self.rb.scores_and_radar()
        metrics = self.rb.key_metrics()
        gp = metrics.get("销售毛利率", "—")
        np = metrics.get("销售净利率", "—")
        roe = metrics.get("净资产收益率", "—")
        debt = metrics.get("资产负债率", "—")
        mcap = self.rb.market_cap()
        shares_f = float(self.rb.total_shares()) or 0
        cap_str = f"{float(mcap.replace('亿','')):.0f}亿" if mcap != "—" else "—"
        size = "大盘(>500亿)" if cap_str and float(cap_str.replace('亿','')) > 500 else ("中盘(100-500亿)" if cap_str and float(cap_str.replace('亿','')) > 100 else "小盘(<100亿)")

        grades = {}
        for line in score_items.split("\n"):
            for k in ["盈利能力","成长性","财务健康","估值合理","ROE质量"]:
                if k in line:
                    for g in ["A","B","C","D"]:
                        if f"score-{g}" in line and "score-value" in line:
                            grades[k] = g
                            break

        return f"""## S3: 公司筛选与质量评分

**市值门槛**: {size} ({mcap})

**行业地位**: [AI] 龙头/领先/跟随

**业务聚焦度**: [AI] 专注度评估

| 维度 | 评分 | 说明 |
|------|------|------|
| 盈利能力 | {grades.get("盈利能力","—")} | 毛利率 {gp} |
| 成长性 | {grades.get("成长性","—")} | [AI] 营收增速分析 |
| 财务健康 | {grades.get("财务健康","—")} | 负债率 {debt} |
| 估值合理 | {grades.get("估值合理","—")} | PE {f"{self.rb.last_pe_pb()[0]:.1f}x" if self.rb.last_pe_pb()[0] else "—"} |
| ROE质量 | {grades.get("ROE质量","—")} | ROE {roe} |

**总分**: {total}/100
"""

    # ─── S4: 弹性测算 ───
    def step4(self) -> str:
        cur_price = float(self.spot.get("最新价", 0)) or 100
        opt, base, cons = self.rb.scenarios(cur_price)
        sens = self.rb.sensitivity_data()

        sens_rows = ""
        for i, label in enumerate(sens["labels"]):
            v = sens["values"][i]
            base_v = sens["base"] if isinstance(sens["base"], (int,float)) else 0
            pct = f"{(v/base_v-1)*100:+.1f}%" if base_v else "—"
            sens_rows += f"| {label} | {v:.2f}亿 | {pct} |\n"

        return f"""## S4: 业绩弹性测算

### 三情景分析

| 情景 | 条件假设 | 净利润预测 | EPS | 目标价 | 涨跌幅 |
|------|---------|-----------|-----|--------|--------|
| 🟢 乐观 {opt["desc"]} | [AI] | — | — | ¥{opt["price"]} | **{opt["ret"]}%** |
| 🟡 基准 {base["desc"]} | [AI] | — | — | ¥{base["price"]} | **{base["ret"]}%** |
| 🔴 保守 {cons["desc"]} | [AI] | — | — | ¥{cons["price"]} | **{cons["ret"]}%** |

### 敏感度分析（营收增速变化 → 净利润）

| 营收变动 | 净利润预估 | 较基准变动 |
|---------|-----------|-----------|
{sens_rows}

[AI] 补充核心假设条件
"""

    # ─── S5: 风险分析 ───
    def step5(self) -> str:
        items = self.rb.risk_items()
        rows = ""
        for level, text in items:
            lvl_str = "🔴 高" if level == "high" else ("🟡 中" if level == "mid" else "🟢 低")
            rows += f"| {lvl_str} | {text} |\n"
        return f"""## S5: 风险分析

### 风险类型识别

| 风险类型 | 具体描述 | 影响程度 | 发生概率 |
|---------|---------|---------|---------|
| 估值风险 | {items[0][1] if items else '[AI]'} | 高/中/低 | [AI] |
| 业绩风险 | [AI] | 高/中/低 | [AI] |
| 行业风险 | [AI] | 高/中/低 | [AI] |

### 止损信号设定
- **第一止损位**: [AI]（跌破则减半）
- **第二止损位**: [AI]（跌破则清仓）
- **清仓条件**: [AI]（基本面恶化/逻辑破坏）
"""

    # ─── S6: 买卖时机 ───
    def step6(self) -> str:
        cur_price = float(self.spot.get("最新价", 0)) or 100
        opt, base, cons = self.rb.scenarios(cur_price)
        short = round((cur_price + base["price"]) / 2, 1)
        risk_reward = f"1:{abs(round((opt['price']-cur_price)/(cur_price-cons['price']),1))}" if cons["price"] < cur_price else "—"

        return f"""## S6: 估值与买卖时机

### 目标价

| 周期 | 目标价 | 涨幅 | 逻辑 |
|------|--------|------|------|
| 短期(1-3月) | ¥{short} | {f"{(short/cur_price-1)*100:+.1f}%" if cur_price else "—"} | 技术面+催化剂 |
| 中期(6-12月) | ¥{base["price"]} | {base["ret"]}% | 基准情景兑现 |
| 长期(1-2年) | ¥{opt["price"]} | {opt["ret"]}% | 乐观情景兑现 |

**当前价**: ¥{cur_price}
**盈亏比**: {risk_reward}

### 买卖时机

| 区间 | 价位 | 策略 |
|------|------|------|
| 🟢 买入 | [AI] | 估值低时分批建仓 |
| 🟡 持有 | [AI] | 持有等待催化剂 |
| 🔴 卖出 | [AI] | 目标达成/逻辑破坏 |
"""

    # ─── S7: 对标分析 ───
    def step7(self) -> str:
        pe_s = f"{self.rb.last_pe_pb()[0]:.1f}x" if self.rb.last_pe_pb()[0] else "—"
        metrics = self.rb.key_metrics()
        gp = html_mod.fmt_pct(metrics.get("销售毛利率","—"))
        np = html_mod.fmt_pct(metrics.get("销售净利率","—"))
        roe = html_mod.fmt_pct(metrics.get("净资产收益率","—"))
        mcap = self.rb.market_cap()

        return f"""## S7: 对标分析

### 同行业公司对比

| 公司 | PE | ROE | 毛利率 | 净利率 | 营收增速 | 市值 |
|------|----|-----|--------|--------|---------|------|
| ★ {self.rb.stock_name()} | {pe_s} | {roe} | {gp} | {np} | [AI] | {mcap} |
| [AI补充] | — | — | — | — | — | — |

### 增长引擎判断
[AI] 主要增长驱动力分析

### 竞争优势分析
[AI] 核心壁垒与持续能力
"""

    # ─── S8: 跟踪计划 ───
    def step8(self) -> str:
        kpis = self.rb.kpi_items()
        kpi_lines = ""
        for i, (val, name, freq) in enumerate(kpis, 1):
            kpi_lines += f"- **{name}**: 当前 {val} | 频次: {freq}\n"
        return f"""## S8: 跟踪计划

### 关键指标监控
{kpi_lines}
### 定期复盘计划
- **频率**: 每季财报后系统复盘
- **关键节点**: 中报/年报发布日

### 综合结论
- **评级**: {self.rb.rating_letter()}
- **核心逻辑**: [AI] 一句话总结当前投资逻辑
- **操作建议**: [AI] 建仓/持有/卖出

---

*MD由8步框架(Step0-8)整合生成，[AI]标记部分由分析师填充。
数据截止: {dt.datetime.now().strftime("%Y-%m-%d %H:%M")}
"""


def build_8step_report(json_path: str) -> str:
    """从Pipeline JSON生成完整的8步框架MD报告"""
    with open(json_path) as f:
        data = json.load(f)
    sb = StepBuilder(data)
    name = sb.rb.stock_name()
    code = sb.rb.stock_code()
    today = dt.datetime.now().strftime("%Y-%m-%d")

    report = f"""# {name}({code}) — 8步框架深度分析
**生成**: {today} | **当前价**: ¥{sb.spot.get("最新价","—")}
**数据源**: [BaoStock][akshare][同花顺][腾讯行情]
**状态**: AI草稿 — [AI]标记需分析师填充

---

"""
    report += sb.step0() + "\n---\n"
    report += sb.step1() + "\n---\n"
    report += sb.step2() + "\n---\n"
    report += sb.step3() + "\n---\n"
    report += sb.step4() + "\n---\n"
    report += sb.step5() + "\n---\n"
    report += sb.step6() + "\n---\n"
    report += sb.step7() + "\n---\n"
    report += sb.step8()

    report += f"""
---
*本报告由 {name} 8步框架整合脚本自动生成骨架，定性分析需AI补充。*
"""

    return report, name


def main():
    parser = argparse.ArgumentParser(description="8步框架完整整合：MD草稿 + HTML报告")
    parser.add_argument("json_path", nargs="?", default="", help="Phase 1 JSON数据文件路径")
    parser.add_argument("-o", "--output", default="", help="输出目录（默认output/）")
    args = parser.parse_args()

    json_path = args.json_path
    if not json_path:
        out_dir = os.path.join(os.path.dirname(__file__), "output")
        if os.path.isdir(out_dir):
            jsons = sorted([f for f in os.listdir(out_dir) if f.endswith(".json")])
            if jsons:
                json_path = os.path.join(out_dir, jsons[-1])
                print(f"📂 自动选择最新: {json_path}")
    if not json_path or not os.path.isfile(json_path):
        print("❌ 请指定 JSON 数据文件路径")
        sys.exit(1)

    out_dir = args.output or os.path.join(os.path.dirname(__file__), "output")
    os.makedirs(out_dir, exist_ok=True)

    print("=" * 60)
    print("📊 8步框架完整整合 — 开始")
    print("=" * 60)

    # 1. Generate MD report
    print("\n📝 Step 1: 生成8步框架MD草稿...")
    md_content, name = build_8step_report(json_path)
    md_path = os.path.join(out_dir, f"个股研究8步-{name}.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"   ✅ MD草稿: {md_path} ({os.path.getsize(md_path)/1024:.1f} KB)")

    # 2. Sync to QQ media
    qq_dir = "/root/.openclaw/media/qqbot"
    if os.path.isdir(qq_dir):
        qq_md = os.path.join(qq_dir, f"个股研究8步-{name}.md")
        with open(qq_md, "w", encoding="utf-8") as f:
            f.write(md_content)
        print(f"   ✅ QQ同步: {qq_md}")

    # 3. Generate HTML report
    print("\n📊 Step 2: 生成HTML可视化报告...")
    html_content = html_mod.build_report(json_path)
    html_path = os.path.join(out_dir, f"个股研究-{name}.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"   ✅ HTML: {html_path} ({os.path.getsize(html_path)/1024:.1f} KB)")

    if os.path.isdir(qq_dir):
        qq_html = os.path.join(qq_dir, f"个股研究-{name}.html")
        with open(qq_html, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"   ✅ QQ同步: {qq_html}")

    # Count AI placeholders
    ai_count = md_content.count("[AI]")
    print(f"\n{'='*60}")
    print(f"✅ 完成！8步框架MD + HTML 已生成")
    print(f"   MD草稿含 {ai_count} 个 [AI] 标记等待填充")
    print(f"   填充后即可发送到QQ")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
