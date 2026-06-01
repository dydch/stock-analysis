#!/usr/bin/env python3
"""
Phase 3：HTML 可视化报告生成器（8步框架完整版）
==============================================
读取 Phase 1 采集的 JSON 数据，生成基于8步分析框架的专业HTML报告。

8步框架：
  Step 0 任务锁定 → Step 1 宏观与周期 → Step 2 产业链拆解 →
  Step 3 质量评分 → Step 4 业绩弹性 → Step 5 风险分析 →
  Step 6 估值与买卖 → Step 7 对标分析 → Step 8 跟踪计划

用法
  python stock_html_report.py output/data_688676_ths.json
  python stock_html_report.py output/data_600519.json

输出
  output/个股研究-{股票名称}.html
"""

from __future__ import annotations

import re, json, os, sys, argparse, datetime as dt
from typing import Any

# Static chart rendering (no JS dependency)
import stock_charts as sc


# ════════════════════ HTML 模板（完整版）════════════════════

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>个股研究 - {STOCK_NAME}</title>
<script src="echarts.min.js"></script>
<style>
:root {{
  --bg: #0a0e17; --card: #141b2d; --border: #2a3550;
  --text: #e0e4ed; --text2: #8892b0; --text3: #475569;
  --hl: #3b82f6; --hl2: #60a5fa; --up: #ef4444; --down: #22c55e;
  --warn: #f59e0b; --purple: #8b5cf6; --orange: #f97316;
}}
#theme-switch:checked ~ .page-wrapper {{
  --bg: #f8fafc; --card: #ffffff; --border: #e2e8f0;
  --text: #1e293b; --text2: #64748b; --text3: #94a3b8;
  --hl: #2563eb; --hl2: #3b82f6; --up: #dc2626; --down: #16a34a;
  --warn: #d97706; --purple: #7c3aed; --orange: #ea580c;
}}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{
  font-family: -apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif;
  margin:0; padding:0;
}}
.page-wrapper {{
  background: var(--bg); color: var(--text); line-height: 1.6;
  min-height: 100vh;
  transition: background .3s, color .3s;
}}

/* ── Top Bar ── */
.topbar {{
  position: sticky; top: 0; z-index: 100;
  background: var(--card); border-bottom: 1px solid var(--border);
  padding: 0 20px; height: 48px;
  display: flex; align-items: center; gap: 8px;
  backdrop-filter: blur(8px);
}}
.topbar .nav-links {{ display: flex; gap: 2px; overflow-x: auto; flex:1; }}
.topbar .nav-links a {{
  color: var(--text2); text-decoration: none; font-size: 11px;
  padding: 5px 8px; border-radius: 6px; white-space: nowrap;
  transition: all .2s; flex-shrink:0;
}}
.topbar .nav-links a:hover, .topbar .nav-links a.active {{ background: var(--hl); color: #fff; }}
.nav-step {{ display:inline-block; width:16px; height:16px; line-height:16px; text-align:center;
  border-radius:50%; font-size:9px; font-weight:700; margin-right:2px; }}
.nav-step.s0 {{ background: #6366f1; color:#fff; }}
.nav-step.s1 {{ background: #3b82f6; color:#fff; }}
.nav-step.s2 {{ background: #22c55e; color:#fff; }}
.nav-step.s3 {{ background: #f59e0b; color:#fff; }}
.nav-step.s4 {{ background: #f97316; color:#fff; }}
.nav-step.s5 {{ background: #ef4444; color:#fff; }}
.nav-step.s6 {{ background: #8b5cf6; color:#fff; }}
.nav-step.s7 {{ background: #ec4899; color:#fff; }}
.nav-step.s8 {{ background: #14b8a6; color:#fff; }}
.theme-btn {{
  background: var(--border); border: none; color: var(--text2);
  width: 32px; height: 32px; border-radius: 8px; cursor: pointer;
  font-size: 16px; display: flex; align-items: center; justify-content: center;
  flex-shrink: 0; transition: all .2s;
}}
.theme-btn:hover {{ background: var(--hl); color: #fff; }}
.container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}

/* ── 结论置顶 ── */
.conclusion-sticky {{
  background: linear-gradient(135deg, var(--hl) 0%, #1d4ed8 100%);
  color: #fff; border-radius: 12px; padding: 16px 24px;
  margin-bottom: 20px; display: flex; align-items: center; gap: 12px;
  font-size: 14px; line-height: 1.5;
}}
.conclusion-sticky .tag {{
  background: rgba(255,255,255,.2); padding: 2px 10px;
  border-radius: 4px; font-size: 11px; font-weight: 600;
  white-space: nowrap;
}}
.tag-A {{ background: #22c55e; }}
.tag-B {{ background: #60a5fa; }}
.tag-C {{ background: #f59e0b; }}
.tag-D {{ background: #ef4444; }}

/* ── Header ── */
.header {{
  background: var(--card); border-radius: 16px; padding: 24px 32px;
  margin-bottom: 20px; border: 1px solid var(--border); display:flex;
  justify-content:space-between; align-items:center; flex-wrap:wrap; gap:16px;
}}
.header-left h1 {{ font-size:26px; font-weight:700; color:var(--text); }}
.header-left h1 span {{ color:var(--hl); }}
.header-left .subtitle {{ color:var(--text2); font-size:13px; margin-top:2px; }}
.header-right {{ text-align:right; }}
.header-right .price {{ font-size:36px; font-weight:700; color:var(--text); }}
.header-right .change {{ font-size:15px; }}
.header-right .change.up {{ color:var(--up); }}
.header-right .change.down {{ color:var(--down); }}
.header-right .date {{ color:var(--text2); font-size:12px; margin-top:1px; }}

/* ── 指标卡片 ── */
.card-grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(200px,1fr)); gap:10px; margin-bottom:20px; }}
.card {{
  background:var(--card); border-radius:12px; padding:14px 18px;
  border:1px solid var(--border); transition:border-color .2s;
}}
.card:hover {{ border-color:var(--hl); }}
.card .label {{ color:var(--text2); font-size:11px; margin-bottom:2px; }}
.card .value {{ font-size:18px; font-weight:600; color:var(--text); }}
.card .sub {{ color:var(--text3); font-size:11px; margin-top:1px; }}
.card .step-badge {{
  display:inline-block; font-size:9px; padding:1px 6px; border-radius:3px;
  margin-right:4px; font-weight:600;
}}

/* ── Section ── */
.section {{
  background:var(--card); border-radius:16px; padding:24px;
  margin-bottom:20px; border:1px solid var(--border);
}}
.section h2 {{
  font-size:17px; font-weight:600; color:var(--text);
  margin-bottom:14px; padding-bottom:10px;
  border-bottom:1px solid var(--border);
  display:flex; align-items:center; gap:8px;
}}
.section h2 .step-num {{
  display:inline-flex; width:26px; height:26px; border-radius:50%;
  align-items:center; justify-content:center; font-size:13px; font-weight:700;
  color:#fff; flex-shrink:0;
}}
.section h2 .badge {{
  display:inline-block; color:#fff; font-size:10px; padding:2px 7px;
  border-radius:4px; font-weight:500; margin-left:6px;
}}
.step-s0 .step-num {{ background:#6366f1; }}
.step-s1 .step-num {{ background:#3b82f6; }}
.step-s2 .step-num {{ background:#22c55e; }}
.step-s3 .step-num {{ background:#f59e0b; }}
.step-s4 .step-num {{ background:#f97316; }}
.step-s5 .step-num {{ background:#ef4444; }}
.step-s6 .step-num {{ background:#8b5cf6; }}
.step-s7 .step-num {{ background:#ec4899; }}
.step-s8 .step-num {{ background:#14b8a6; }}
.section h2 .badge.blue {{ background:var(--hl); }}
.section h2 .badge.warn {{ background:var(--warn); }}
.section h2 .badge.purple {{ background:var(--purple); }}

.chart-box {{ width:100%; height:380px; }}
.chart-box.tall {{ height:460px; }}
.chart-img {{ max-width:100%; height:auto; border-radius:6px; }}
#theme-switch:checked ~ * .theme-dark {{ display:none !important; }}
#theme-switch:checked ~ * .theme-light {{ display:block !important; }}


/* ── 表格 ── */
.table-wrap {{ overflow-x:auto; }}
table {{ width:100%; border-collapse:collapse; font-size:12px; }}
th, td {{ padding:6px 8px; text-align:right; white-space:nowrap; }}
th {{ background:color-mix(in srgb, var(--card) 95%, var(--text)); color:var(--text2); font-size:11px; font-weight:500; }}
td {{ border-bottom:1px solid var(--border); }}
tr:hover td {{ background:color-mix(in srgb, var(--card) 98%, var(--text)); }}
td:first-child, th:first-child {{ text-align:left; }}

/* ── 评分 ── */
.score-row {{ display:flex; flex-wrap:wrap; gap:8px; margin-bottom:12px; }}
.score-item {{
  flex:1; min-width:100px; background:color-mix(in srgb, var(--card) 95%, var(--text));
  border-radius:8px; padding:12px; text-align:center;
}}
.score-item .score-label {{ color:var(--text2); font-size:11px; }}
.score-item .score-value {{ font-size:24px; font-weight:700; margin:2px 0; }}
.score-item .score-desc {{ font-size:10px; color:var(--text3); }}
.score-A {{ color:var(--down); }} .score-B {{ color:var(--hl2); }}
.score-C {{ color:var(--warn); }} .score-D {{ color:var(--up); }}

/* ── 产业链 ── */
.chain-wrap {{ text-align:center; padding:10px 0; }}
.chain-svg {{ max-width:100%; }}

/* ── 情景分析 ── */
.scenario-grid {{ display:grid; grid-template-columns:repeat(3,1fr); gap:12px; }}
.scenario-item {{
  border-radius:12px; padding:16px; text-align:center;
  border:1px solid var(--border);
}}
.s-opt {{ border-color:var(--down); background:color-mix(in srgb, var(--down) 8%, var(--card)); }}
.s-base {{ border-color:var(--hl); background:color-mix(in srgb, var(--hl) 8%, var(--card)); }}
.s-cons {{ border-color:var(--up); background:color-mix(in srgb, var(--up) 8%, var(--card)); }}
.s-label {{ font-size:11px; color:var(--text2); }}
.s-price {{ font-size:22px; font-weight:700; margin:4px 0; }}
.s-return {{ font-size:14px; font-weight:600; }}
.s-reason {{ font-size:11px; color:var(--text3); margin-top:6px; }}
.positive-ret {{ color:var(--up); }} .negative-ret {{ color:var(--down); }}

/* ── 风险 ── */
.risk-list {{ list-style:none; }}
.risk-list li {{
  display:flex; align-items:center; gap:10px;
  padding:8px 14px; border-bottom:1px solid var(--border); font-size:13px;
}}
.risk-list li:last-child {{ border-bottom:none; }}
.risk-signal {{ width:6px; height:6px; border-radius:50%; flex-shrink:0; }}
.risk-high {{ background:var(--up); }} .risk-mid {{ background:var(--warn); }} .risk-low {{ background:var(--down); }}

/* ── 买入/卖出区域 ── */
.timing-grid {{ display:grid; grid-template-columns:repeat(3,1fr); gap:12px; }}
.timing-card {{
  border-radius:12px; padding:16px; text-align:center;
  border:1px solid var(--border);
}}
.timing-label {{ font-size:11px; color:var(--text2); }}
.timing-price {{ font-size:24px; font-weight:700; margin:6px 0; }}
.timing-desc {{ font-size:11px; color:var(--text3); margin-top:4px; }}
.timing-trigger {{ font-size:11px; padding:3px 8px; border-radius:4px; display:inline-block; margin-top:6px; }}
.trigger-yes {{ background:color-mix(in srgb, var(--down) 20%, var(--card)); color:var(--down); }}
.trigger-maybe {{ background:color-mix(in srgb, var(--warn) 20%, var(--card)); color:var(--warn); }}
.trigger-no {{ background:color-mix(in srgb, var(--up) 20%, var(--card)); color:var(--up); }}

/* ── 对标 ── */
.peer-table td:first-child {{ font-weight:600; }}
.peer-highlight {{ background:color-mix(in srgb, var(--hl) 10%, var(--card)); border-left:3px solid var(--hl); }}
.peer-bad {{ color:var(--up); }}

/* ── 标签 ── */
.tag-cloud {{ display:flex; flex-wrap:wrap; gap:6px; margin:8px 0; }}
.tag-pill {{
  background:color-mix(in srgb, var(--hl) 15%, var(--card));
  color:var(--hl2); border:1px solid color-mix(in srgb, var(--hl) 30%, var(--border));
  padding:3px 12px; border-radius:20px; font-size:11px;
}}

/* ── 研报 ── */
.report-item {{
  padding:8px 14px; border-bottom:1px solid var(--border);
  display:flex; justify-content:space-between; align-items:center;
}}
.report-item:last-child {{ border-bottom:none; }}
.r-title {{ color:var(--text); font-size:13px; }}
.r-meta {{ color:var(--text3); font-size:11px; }}
.r-rating {{ color:var(--down); font-weight:600; font-size:11px; }}

/* ── 新闻 ── */
.news-item {{ padding:6px 0; border-bottom:1px solid var(--border); font-size:13px; }}
.news-item:last-child {{ border-bottom:none; }}
.n-source {{ color:var(--text3); font-size:11px; }}

/* ── 跟踪计划 ── */
.track-row {{ display:flex; gap:12px; flex-wrap:wrap; margin:8px 0; }}
.track-item {{
  flex:1; min-width:160px; padding:12px 16px;
  background:color-mix(in srgb, var(--card) 95%, var(--text));
  border-radius:8px; border-left:3px solid var(--hl);
}}
.track-kpi {{ font-size:18px; font-weight:700; color:var(--text); }}
.track-desc {{ font-size:11px; color:var(--text2); margin-top:2px; }}
.track-freq {{ font-size:10px; color:var(--text3); }}

.footer {{ text-align:center; color:var(--text3); font-size:12px; padding:24px; border-top:1px solid var(--border); margin-top:40px; }}

@media (max-width:768px) {{
  .header {{ flex-direction:column; text-align:center; }}
  .header-right {{ text-align:center; }}
  .scenario-grid, .timing-grid {{ grid-template-columns:1fr; }}
  .topbar .nav-links a {{ font-size:10px; padding:4px 6px; }}
}}
</style>
</head>
<body>
<input type="checkbox" id="theme-switch" hidden>
<div class="page-wrapper">

<!-- ==================== 导航栏（含8步）==================== -->
<div class="topbar">
  <div class="nav-links" id="navLinks">
    <a href="#conclusion"><span class="nav-step s0">0</span>结论</a>
    <a href="#step0"><span class="nav-step s0">0</span>锁定</a>
    <a href="#step1"><span class="nav-step s1">1</span>宏观</a>
    <a href="#step2"><span class="nav-step s2">2</span>产业链</a>
    <a href="#step3"><span class="nav-step s3">3</span>评分</a>
    <a href="#step4"><span class="nav-step s4">4</span>弹性</a>
    <a href="#step5"><span class="nav-step s5">5</span>风险</a>
    <a href="#step6"><span class="nav-step s6">6</span>估值</a>
    <a href="#step7"><span class="nav-step s7">7</span>对标</a>
    <a href="#step8"><span class="nav-step s8">8</span>跟踪</a>
  </div>
  <label for="theme-switch" class="theme-btn" id="themeToggle">🌙</label>
</div>

<div class="container">

<!-- ==================== 结论置顶 ==================== -->
<div id="conclusion" class="conclusion-sticky">
  <span class="tag tag-{RATING_LETTER}">{RATING_LETTER}级</span>
  <span style="flex:1">{CONCLUSION}</span>
  <span style="font-size:11px;opacity:.8;white-space:nowrap">
    复盘: {REVIEW_CADENCE}
  </span>
</div>

<!-- ==================== HEADER ==================== -->
<div class="header">
  <div class="header-left">
    <h1>{STOCK_NAME} <span>({STOCK_CODE})</span></h1>
    <div class="subtitle">
      {STOCK_SECTOR} ｜ {IPO_DATE}上市 ｜ 股本{TOTAL_SHARES}亿 ｜ 市值{MARKET_CAP}
      ｜ {TAGS_INLINE}
    </div>
  </div>
  <div class="header-right">
    <div class="price">{PRICE}</div>
    <div class="change {CHANGE_CLS}">{CHANGE_PCT}% ({CHANGE_AMT})</div>
    <div class="date">{REPORT_DATE}</div>
  </div>
</div>

<!-- ==================== 指标卡片 ==================== -->
<div class="card-grid">
  <div class="card"><div class="label"><span class="step-badge" style="background:#8b5cf6">S6</span>PE-TTM</div><div class="value">{PE_TTM}</div></div>
  <div class="card"><div class="label"><span class="step-badge" style="background:#8b5cf6">S6</span>PB</div><div class="value">{PB_MRQ}</div></div>
  <div class="card"><div class="label"><span class="step-badge" style="background:#f97316">S4</span>营收(最近)</div><div class="value">{REVENUE}</div><div class="sub">YOY {REVENUE_YOY}</div></div>
  <div class="card"><div class="label"><span class="step-badge" style="background:#f97316">S4</span>净利(最近)</div><div class="value">{NET_PROFIT}</div><div class="sub">YOY {PROFIT_YOY}</div></div>
  <div class="card"><div class="label"><span class="step-badge" style="background:#f59e0b">S3</span>EPS-TTM</div><div class="value">{EPS_TTM}</div></div>
  <div class="card"><div class="label"><span class="step-badge" style="background:#8b5cf6">S6</span>一致预期26E</div><div class="value">{EPS_CONSENSUS}</div><div class="sub">PE {PE_FWD}x</div></div>
  <div class="card"><div class="label"><span class="step-badge" style="background:#f59e0b">S3</span>ROE</div><div class="value">{ROE}</div></div>
  <div class="card"><div class="label"><span class="step-badge" style="background:#22c55e">S2</span>毛利率/净利率</div><div class="value" style="font-size:17px">{GROSS_MARGIN} / {NET_MARGIN}</div></div>
</div>

<!-- ════════════════ Step 0: 任务锁定 ════════════════ -->
<div id="step0" class="section step-s0">
  <h2><span class="step-num">0</span> 任务锁定：公司画像与定位</h2>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;">
    <div>
      <table>
        <tr><td style="color:var(--text2);width:100px;border:0;">股票代码</td><td style="border:0;">{STOCK_CODE} ｜ {STOCK_SECTOR}</td></tr>
        <tr><td style="color:var(--text2);border:0;">上市日期</td><td style="border:0;">{IPO_DATE}</td></tr>
        <tr><td style="color:var(--text2);border:0;">总股本</td><td style="border:0;">{TOTAL_SHARES}亿 ｜ 流通 {FLOAT_SHARES}亿</td></tr>
        <tr><td style="color:var(--text2);border:0;">市值</td><td style="border:0;">{MARKET_CAP}</td></tr>
      </table>
    </div>
    <div>
      <div style="color:var(--text2);font-size:12px;margin-bottom:4px;">主营业务</div>
      <div style="font-size:13px;line-height:1.6;">{BIZ_DESC}</div>
      <div class="tag-cloud" style="margin-top:8px;">{TAGS_HTML}</div>
    </div>
  </div>
  <div style="margin-top:14px;">
    <div style="color:var(--text2);font-size:12px;margin-bottom:6px;">主营构成</div>
    <div id="chart-revenue-bd" class="chart-box" style="height:240px;"></div>
  </div>
</div>

<!-- ════════════════ Step 1: 宏观与周期定位 ════════════════ -->
<div id="step1" class="section step-s1">
  <h2><span class="step-num">1</span> 宏观与周期定位 <span class="badge blue">AI分析</span></h2>
  <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;">
    <div class="card" style="border-left:3px solid var(--hl);">
      <div style="color:var(--hl);font-size:11px;font-weight:600;">📌 经济阶段</div>
      <div style="font-size:13px;margin-top:6px;">{MACRO_ECONOMY}</div>
    </div>
    <div class="card" style="border-left:3px solid var(--down);">
      <div style="color:var(--down);font-size:11px;font-weight:600;">🏭 行业周期</div>
      <div style="font-size:13px;margin-top:6px;">{INDUSTRY_CYCLE}</div>
    </div>
    <div class="card" style="border-left:3px solid var(--orange);">
      <div style="color:var(--orange);font-size:11px;font-weight:600;">📜 政策方向</div>
      <div style="font-size:13px;margin-top:6px;">{POLICY_DIRECTION}</div>
    </div>
  </div>
  <div id="chart-cycle" class="chart-box" style="height:200px;margin-top:8px;"></div>
</div>

<!-- ════════════════ Step 2: 产业链深度拆解 ════════════════ -->
<div id="step2" class="section step-s2">
  <h2><span class="step-num">2</span> 产业链深度拆解 <span class="badge purple">价值链分析</span></h2>
  <div class="chain-wrap"><svg class="chain-svg" viewBox="0 0 900 160" width="900" height="160">{CHAIN_SVG}</svg></div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:14px;">
    <div class="card">
      <div style="color:var(--down);font-size:11px;font-weight:600;">🏆 竞争格局</div>
      <div style="font-size:13px;margin-top:4px;">{COMPETITION_LANDSCAPE}</div>
    </div>
    <div class="card">
      <div style="color:var(--hl);font-size:11px;font-weight:600;">🎯 核心竞争优势</div>
      <div style="font-size:13px;margin-top:4px;">{COMPETITIVE_ADVANTAGE}</div>
    </div>
  </div>
</div>

<!-- ════════════════ Step 3: 质量评分 ════════════════ -->
<div id="step3" class="section step-s3">
  <h2><span class="step-num">3</span> 公司筛选与质量评分 <span class="badge warn">总分{SCORE_TOTAL}/100</span></h2>
  <div class="score-row">{SCORE_ITEMS}</div>
  <div id="chart-radar" class="chart-box" style="height:300px;"></div>
</div>

<!-- ════════════════ Step 4: 业绩弹性测算 ════════════════ -->
<div id="step4" class="section step-s4">
  <h2><span class="step-num">4</span> 业绩弹性测算 <span class="badge blue">三情景分析</span></h2>
  <div class="scenario-grid">
    <div class="scenario-item s-opt">
      <div class="s-label">🟢 乐观情景</div>
      <div class="s-price" style="color:var(--up)">{S_OPT_PRICE}</div>
      <div class="s-return positive-ret">{S_OPT_RET}%</div>
      <div class="s-reason">{S_OPT_DESC}</div>
    </div>
    <div class="scenario-item s-base">
      <div class="s-label">🟡 基准情景</div>
      <div class="s-price" style="color:var(--hl)">{S_BASE_PRICE}</div>
      <div class="s-return" style="color:var(--warn)">{S_BASE_RET}%</div>
      <div class="s-reason">{S_BASE_DESC}</div>
    </div>
    <div class="scenario-item s-cons">
      <div class="s-label">🔴 保守情景</div>
      <div class="s-price" style="color:var(--down)">{S_CONS_PRICE}</div>
      <div class="s-return negative-ret">{S_CONS_RET}%</div>
      <div class="s-reason">{S_CONS_DESC}</div>
    </div>
  </div>
  <div style="margin-top:14px;">
    <div style="color:var(--text2);font-size:12px;margin-bottom:6px;">盈利预测明细</div>
    <div id="chart-forecast" class="chart-box" style="height:260px;"></div>
  </div>
  <div style="margin-top:10px;">
    <div style="color:var(--text2);font-size:12px;margin-bottom:4px;">敏感度分析：营收增速 vs 净利率</div>
    <div id="chart-sensitivity" class="chart-box" style="height:220px;"></div>
  </div>
</div>

<!-- ════════════════ Step 5: 风险分析 ════════════════ -->
<div id="step5" class="section step-s5">
  <h2><span class="step-num">5</span> 风险分析与止损信号</h2>
  <ul class="risk-list">{RISK_ITEMS}</ul>
  <div style="margin-top:12px;">
    <div style="color:var(--text2);font-size:12px;margin-bottom:6px;">财务健康度指标</div>
    <div id="chart-fin-health" class="chart-box" style="height:200px;"></div>
  </div>
</div>

<!-- ════════════════ Step 6: 估值与买卖时机 ════════════════ -->
<div id="step6" class="section step-s6">
  <h2><span class="step-num">6</span> 估值与买卖时机 <span class="badge blue">盈亏比</span></h2>
  <div class="card-grid" style="margin-bottom:12px;">
    <div class="card"><div class="label">当前价</div><div class="value" style="color:var(--text)">{PRICE}</div></div>
    <div class="card"><div class="label">短期目标(1-3月)</div><div class="value" style="color:var(--up)">{SHORT_TARGET}</div><div class="sub">{SHORT_RET}</div></div>
    <div class="card"><div class="label">中期目标(6-12月)</div><div class="value" style="color:var(--hl)">{MID_TARGET}</div><div class="sub">{MID_RET}</div></div>
    <div class="card"><div class="label">长期目标(1-2年)</div><div class="value" style="color:var(--down)">{LONG_TARGET}</div><div class="sub">{LONG_RET}</div></div>
    <div class="card"><div class="label">盈亏比</div><div class="value">{RISK_REWARD}</div><div class="sub">{RR_DESC}</div></div>
  </div>
  <div class="timing-grid">
    <div class="timing-card" style="border-color:var(--down);background:color-mix(in srgb, var(--down) 4%, var(--card));">
      <div class="timing-label">🟢 买入区间</div>
      <div class="timing-price" style="color:var(--down)">{BUY_ZONE}</div>
      <div class="timing-desc">{BUY_TRIGGER}</div>
      {BUY_ACTIVE}
    </div>
    <div class="timing-card" style="border-color:var(--hl);">
      <div class="timing-label">🟡 持有区间</div>
      <div class="timing-price" style="color:var(--hl)">{HOLD_ZONE}</div>
      <div class="timing-desc">{HOLD_STRATEGY}</div>
    </div>
    <div class="timing-card" style="border-color:var(--up);background:color-mix(in srgb, var(--up) 4%, var(--card));">
      <div class="timing-label">🔴 卖出区间</div>
      <div class="timing-price" style="color:var(--up)">{SELL_ZONE}</div>
      <div class="timing-desc">{SELL_TRIGGER}</div>
    </div>
  </div>
  <div style="margin-top:14px;">
    <div style="color:var(--text2);font-size:12px;margin-bottom:6px;">PE估值走势</div>
    <div id="chart-valuation" class="chart-box tall"></div>
  </div>
</div>

<!-- ════════════════ Step 7: 对标分析 ════════════════ -->
<div id="step7" class="section step-s7">
  <h2><span class="step-num">7</span> 对标分析 <span class="badge purple">同行对比</span></h2>
  <div class="table-wrap"><table class="peer-table"><thead>
    <tr><th>公司</th><th>PE-TTM</th><th>ROE</th><th>毛利率</th><th>净利率</th><th>营收增速</th><th>市值</th><th>增长引擎</th></tr></thead>
    <tbody>{PEER_ROWS}</tbody></table>
  </div>
  <div style="margin-top:14px;display:grid;grid-template-columns:1fr 1fr;gap:12px;">
    <div class="card">
      <div style="color:var(--text2);font-size:11px;font-weight:600;">🔬 竞争优势分析</div>
      <div style="font-size:13px;margin-top:4px;">{COMPETITIVE_EDGE}</div>
    </div>
    <div class="card">
      <div style="color:var(--text2);font-size:11px;font-weight:600;">📈 增长引擎判断</div>
      <div style="font-size:13px;margin-top:4px;">{GROWTH_ENGINE}</div>
    </div>
  </div>
</div>

<!-- ════════════════ Step 8: 跟踪计划 ════════════════ -->
<div id="step8" class="section step-s8">
  <h2><span class="step-num">8</span> 跟踪计划 <span class="badge" style="background:#14b8a6;">关键指标监控</span></h2>
  <div class="track-row">
    <div class="track-item"><div class="track-kpi">{KPI_1_VAL}</div><div class="track-desc">📊 {KPI_1_NAME}</div><div class="track-freq">{KPI_1_FREQ}</div></div>
    <div class="track-item"><div class="track-kpi">{KPI_2_VAL}</div><div class="track-desc">📊 {KPI_2_NAME}</div><div class="track-freq">{KPI_2_FREQ}</div></div>
    <div class="track-item"><div class="track-kpi">{KPI_3_VAL}</div><div class="track-desc">📊 {KPI_3_NAME}</div><div class="track-freq">{KPI_3_FREQ}</div></div>
  </div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:10px;">
    <div class="card">
      <div style="color:#14b8a6;font-size:11px;font-weight:600;">📅 复盘计划</div>
      <div style="font-size:13px;margin-top:4px;">{REVIEW_PLAN}</div>
    </div>
    <div class="card">
      <div style="color:#14b8a6;font-size:11px;font-weight:600;">📝 综合结论</div>
      <div style="font-size:13px;margin-top:4px;">{FINAL_CONCLUSION}</div>
    </div>
  </div>
</div>

<!-- ── 财务趋势 & 机构数据 ── -->
<div class="section">
  <h2>📊 财务趋势（辅助数据）</h2>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;">
    <div><div class="chart-box" id="chart-revenue" style="height:280px;"></div></div>
    <div><div class="chart-box" id="chart-margin" style="height:280px;"></div></div>
  </div>
</div>

<div class="section">
  <h2>📋 机构一致预期 <span class="badge">{CONSENSUS_COUNT}家</span></h2>
  <div class="table-wrap"><table><thead><tr><th>年度</th><th>营收</th><th>营收±%</th><th>净利润</th><th>净利±%</th><th>EPS</th><th>PE</th></tr></thead><tbody>{CONSENSUS_ROWS}</tbody></table></div>
</div>

<div class="section">
  <h2>🏛️ 十大股东</h2>
  <div class="table-wrap"><table><thead><tr><th>#</th><th>股东</th><th>比例</th><th>变动</th></tr></thead><tbody>{SHAREHOLDER_ROWS}</tbody></table></div>
</div>

<div class="section">
  <h2>💰 资金流向</h2>
  {MONEYFLOW_HTML}
</div>

<div class="section">
  <h2>📰 近期研报</h2>
  <div>{RESEARCH_ITEMS}</div>
</div>

<div class="footer">
  数据来源：BaoStock / akshare / 同花顺thsdk / 腾讯行情<br>
  {REPORT_DATE} 生成 ｜ 不构成投资建议
</div>
</div>
</div>
</body>
</html>"""


# ════════════════════ Report Builder ════════════════════

def load_data(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def fmt_num(v, suffix=""):
    if v is None or v == "" or v == "—":
        return "—"
    v = float(v)
    if abs(v) >= 1e8:
        return f"{v/1e8:.2f}亿{suffix}"
    if abs(v) >= 1e4:
        return f"{v/1e4:.2f}万{suffix}"
    return f"{v:.2f}{suffix}"


def fmt_pct(v):
    if v is None or v == "" or v == "—":
        return "—"
    try:
        return f"{float(str(v).replace('%','')):.2f}%"
    except:
        return str(v)


def fmt_date(ts):
    if not ts:
        return "—"
    ts = str(ts).replace("T00:00:00.000", "").replace("T00:00:00", "")
    if len(ts) == 8 and ts.isdigit():
        return f"{ts[:4]}-{ts[4:6]}-{ts[6:]}"
    return ts[:10] if len(ts) >= 10 else ts


class ReportBuilder:
    def __init__(self, data: dict):
        self.d = data
        self.b = data.get("blocks", data)
        self.spot = self._get("spot", [{}])[0]
        self.bs_info = self._get("basic_info_bs", [{}])[0]

    def _get(self, key, default=None):
        v = self.b.get(key)
        return v if v is not None else (default() if callable(default) else default)

    def stock_name(self):
        return self.spot.get("名称", self.bs_info.get("code_name", "—"))

    def stock_code(self):
        c = self.bs_info.get("code", self.spot.get("代码", ""))
        return c.replace("sh.", "").replace("sz.", "")

    def ipo_date(self):
        return self.bs_info.get("ipoDate", "—")

    def sector(self):
        bi = self._get("basic_info", [{}])[0] or self._get("basic_info_ak", [{}])[0]
        return bi.get("行业分类(证监会)", "—")

    def total_shares(self):
        profit = self._get("fin_bs", {}).get("bs_profit", [])
        if profit:
            try:
                return f"{float(profit[-1].get('totalShare',0))/1e8:.2f}"
            except:
                pass
        return "—"

    def float_shares(self):
        bs = self._get("balance_sheet", [])
        for item in bs:
            if item.get("科目") == "实收资本（或股本）" or "股本" in str(item.get("科目","")):
                try:
                    return f"{float(str(item.get('期末数','0')))/1e8:.2f}"
                except:
                    pass
        # fallback: total shares assumption
        try:
            return self.total_shares()
        except:
            return "—"

    def price(self):
        v = self.spot.get("最新价", "—")
        return f"{v:.2f}" if isinstance(v, (int, float)) else str(v)

    def change_pct(self):
        v = self.spot.get("涨跌幅", 0)
        return f"{v:.2f}" if isinstance(v, (int, float)) else str(v)

    def change_amt(self):
        v = self.spot.get("涨跌额", 0)
        return f"{v:.2f}" if isinstance(v, (int, float)) else str(v)

    def market_cap(self):
        try:
            p = float(self.spot.get("最新价", 0))
            s = float(self.total_shares())
            return fmt_num(p * s * 1e8)
        except:
            return "—"

    def last_pe_pb(self):
        kline = self._get("kline_daily", [])
        for k in reversed(kline):
            pe, pb = k.get("peTTM"), k.get("pbMRQ")
            if pe and pb and str(pe).strip() and str(pb).strip():
                try:
                    return float(pe), float(pb)
                except:
                    pass
        return None, None

    def kline_series(self, max_days=365):
        kline = self._get("kline_daily", [])
        filtered = [k for k in kline if str(k.get("adjustflag", "")) == "2"] or kline
        filtered = filtered[-max_days:]
        dates, prices, volumes, ma5, ma20, ma60 = [], [], [], [], [], []
        for k in filtered:
            try:
                o, h, l, c = float(k["open"]), float(k["high"]), float(k["low"]), float(k["close"])
                dates.append(k["date"])
                prices.append([o, c, l, h])
                volumes.append([k["date"], int(float(k.get("volume",0)))])
                ma5.append(float(k.get("ma5",0) or k.get("MA5",0) or 0))
                ma20.append(float(k.get("ma20",0) or k.get("MA20",0) or 0))
                ma60.append(float(k.get("ma60",0) or k.get("MA60",0) or 0))
            except:
                continue
        return dates, prices, volumes, ma5, ma20, ma60

    def valuation_series(self, max_days=365):
        kline = self._get("kline_daily", [])
        filtered = [k for k in kline if k.get("peTTM") and k.get("pbMRQ") and
                    str(k.get("peTTM","")) != "" and str(k.get("pbMRQ","")) != ""]
        filtered = filtered[-max_days:]
        dates, pe_vals, pb_vals = [], [], []
        for k in filtered:
            try:
                dates.append(k["date"])
                pe_vals.append(float(k["peTTM"]))
                pb_vals.append(float(k["pbMRQ"]))
            except:
                continue
        return {"dates": dates, "pe": pe_vals, "pb": pb_vals}

    @staticmethod
    def _parse_num(val: Any) -> float:
        """Parse number string with 亿/万 suffix."""
        if val is None or val == "" or val == "0" or val == "—":
            return 0.0
        s = str(val).strip()
        if "万亿" in s:
            return float(s.replace("万亿","")) * 10000
        if "亿" in s:
            return float(s.replace("亿",""))
        if "万" in s:
            return float(s.replace("万","")) / 10000
        try:
            return float(s)
        except ValueError:
            return 0.0

    @staticmethod
    def _parse_pct(val: Any) -> float:
        """Parse percentage string."""
        if val is None or val == "" or val == "—":
            return 0.0
        try:
            return float(str(val).replace("%","").strip())
        except ValueError:
            return 0.0

    def financial_data(self):
        indicator = self._get("fin_bs", {}).get("ak_indicator", []) or self._get("fin_merged", {}).get("ak_indicator", [])
        labels, revs, profits, gross, net_m, debt, cur_r = [], [], [], [], [], [], []
        for row in indicator[-6:]:
            try:
                labels.append(row.get("报告期","—")[:7])
                revs.append(self._parse_num(row.get("营业总收入","0")))
                profits.append(self._parse_num(row.get("净利润","0")))
                gross.append(self._parse_pct(row.get("销售毛利率","0%")))
                net_m.append(self._parse_pct(row.get("销售净利率","0%")))
                debt.append(self._parse_pct(row.get("资产负债率","0%")))
                cur_r.append(self._parse_num(row.get("流动比率","0")))
            except Exception:
                continue
        return {"labels": labels, "revenue": revs, "profit": profits,
                "gross": gross, "net": net_m, "debt": debt, "ratio": cur_r}

    def key_metrics(self):
        indicator = self._get("fin_bs", {}).get("ak_indicator", []) or self._get("fin_merged", {}).get("ak_indicator", [])
        if not indicator:
            return {}
        latest = indicator[-1]
        m = {}
        for k in ["销售毛利率","销售净利率","净资产收益率","资产负债率","流动比率"]:
            try:
                m[k] = latest.get(k, "—")
            except:
                m[k] = "—"
        return m

    def last_year_growth(self):
        i = self._get("fin_bs", {}).get("ak_indicator", []) or self._get("fin_merged", {}).get("ak_indicator", [])
        if i:
            try:
                return i[-1].get("营业总收入同比增长率","—"), i[-1].get("净利润同比增长率","—")
            except:
                pass
        return "—", "—"

    def eps_ttm(self):
        profit = self._get("fin_bs", {}).get("bs_profit", [])
        if profit:
            try:
                return f"{float(profit[-1].get('epsTTM',0)):.2f}"
            except:
                pass
        return "—"

    def eps_consensus(self):
        ths = self._get("ths", {})
        forecast = ths.get("ths_forecast", {})
        consensus = forecast.get("consensus", [])
        for c in consensus:
            if c.get("预测指标") == "净利润(元)":
                np_v = c.get("预测2026（平均）")
                if np_v:
                    try:
                        np_v = float(str(np_v).replace("亿",""))
                        shares = float(self.total_shares())
                        if shares > 0:
                            return f"{np_v/shares:.2f}"
                    except:
                        pass
                break
        research = self._get("research", [])
        if research:
            try:
                eps = research[0].get("2026-盈利预测-收益","")
                if eps:
                    return f"{float(eps):.2f}"
            except:
                pass
        return "—"

    def consensus_table(self):
        ths = self._get("ths", {})
        forecast = ths.get("ths_forecast", {})
        consensus = forecast.get("consensus", [])
        eps_summary = forecast.get("eps_summary", [])
        count = str(eps_summary[0].get("预测机构数","0")) if eps_summary else "0"
        rev_map, np_map, rev_g, np_g = {}, {}, {}, {}
        for item in consensus:
            key = item.get("预测指标","")
            for yr in [2023,2024,2025,2026,2027,2028]:
                yk = f"预测{yr}（平均）" if yr > 2025 else f"{yr}（实际值）"
                val = item.get(yk,"—")
                if "营业收入" == key and "增长" not in key:
                    rev_map[yr] = val
                elif "净利润" == key and "增长" not in key:
                    np_map[yr] = val
                elif "营业收入增长率" == key:
                    rev_g[yr] = val
                elif "净利润增长率" == key:
                    np_g[yr] = val
        shares = float(self.total_shares())
        cur_price = float(self.spot.get("最新价",0))
        rows = ""
        for yr in [2025,2026,2027]:
            label = f"{yr}E" if yr > 2025 else f"{yr}A"
            r = rev_map.get(yr,"—")
            rg = rev_g.get(yr,"—")
            n = np_map.get(yr,"—")
            ng = np_g.get(yr,"—")
            eps = float(n)/shares if isinstance(n,(int,float)) and shares > 0 else None
            pe = f"{cur_price/eps:.1f}x" if eps and cur_price else "—"
            r_str = f"{float(r)/1e8:.2f}亿" if isinstance(r,(int,float)) and abs(r)>1e6 else str(r)
            n_str = f"{float(n)/1e8:.2f}亿" if isinstance(n,(int,float)) and abs(n)>1e6 else str(n)
            e_str = f"{eps:.2f}" if eps else "—"
            rows += f"<tr><td>{label}</td><td>{r_str}</td><td>{rg}</td><td>{n_str}</td><td>{ng}</td><td>{e_str}</td><td>{pe}</td></tr>\n"
        return rows, count

    def shareholder_rows(self):
        top10 = self._get("top10", [])
        if not top10:
            top10 = self._get("top10_free", [])
        if not top10:
            top10 = self._get("share_hold_change", [])[:10]
        rows = ""
        for i, sh in enumerate(top10[:10], 1):
            n = str(sh.get("股东名称", sh.get("股东名称/姓名", "—")))[:24]
            p = sh.get("占总股本持股比例", sh.get("持股比例", sh.get("占总股本比例","—")))
            ch = sh.get("增减", sh.get("本次变动","—"))
            if ch and ch not in ("不变","新进","—"):
                try:
                    ch = f"{float(ch):.1f}%"
                except:
                    pass
            if p and p != "—":
                try:
                    p = f"{float(p):.2f}"
                except:
                    pass
            rows += f"<tr><td>{i}</td><td>{n}</td><td>{p}%</td><td>{ch}</td></tr>\n"
        if not rows:
            rows = "<tr><td colspan=4 style='text-align:center;color:var(--text3)'>暂无数据</td></tr>"
        return rows

    def moneyflow_data(self):
        flow = self._get("fund_flow", [])[-5:]
        dates, main_f, super_f, big_f = [], [], [], []
        for f in flow:
            dates.append(fmt_date(f.get("日期","")))
            try:
                m = float(f.get("主力净流入-净额",0))/1e4
                s = float(f.get("超大单净流入-净额",0))/1e4
                b = float(f.get("大单净流入-净额",0))/1e4
            except:
                m=s=b=0
            main_f.append(m); super_f.append(s); big_f.append(b)
        return {"dates": dates, "mainForce": main_f, "super": super_f, "big": big_f}

    def revenue_breakdown(self):
        zygc = self._get("zygc", [])
        if not zygc:
            return []
        # Find latest report date
        latest_date = ""
        for r in zygc:
            d = r.get("报告日期", "")
            if d > latest_date:
                latest_date = d
        # Get items for latest date, keep only one per name (first seen)
        seen, result = set(), []
        for item in zygc:
            if item.get("报告日期", "") != latest_date:
                continue
            name = item.get("主营構成", item.get("主营构成", ""))
            if not name or name in seen:
                continue
            seen.add(name)
            if any(kw in name for kw in ("境内","境外","内部","全部地区")):
                continue
            try:
                ratio = float(str(item.get("收入比例","0")).replace("%","")) * 100
            except:
                ratio = 0
            result.append({"name": name[:18], "value": round(ratio, 1)})
        if result:
            return result
        # Fallback: try all items without dedup
        seen, result = set(), []
        for item in zygc:
            if item.get("报告日期", "") != latest_date:
                continue
            name = str(item.get("主营構成", item.get("主营构成", "")))
            if not name or name in seen:
                continue
            seen.add(name)
            try:
                ratio = float(str(item.get("收入比例","0")).replace("%","")) * 100
            except:
                ratio = 0
            result.append({"name": name[:18], "value": round(ratio, 1)})


    def scores_and_radar(self):
        metrics = self.key_metrics()
        try:
            gp = float(str(metrics.get("销售毛利率","0%")).replace("%",""))
        except:
            gp = 0
        try:
            np = float(str(metrics.get("销售净利率","0%")).replace("%",""))
        except:
            np = 0
        try:
            roe = float(str(metrics.get("净资产收益率","0%")).replace("%",""))
        except:
            roe = 0
        try:
            debt = float(str(metrics.get("资产负债率","0%")).replace("%",""))
        except:
            debt = 50
        _, rev_yoy = self.last_year_growth()
        try:
            rev_yoy_v = abs(float(str(rev_yoy).replace("%","")))
        except:
            rev_yoy_v = 5

        pe, _ = self.last_pe_pb()

        def val_score(pe_v):
            if not pe_v or pe_v <= 0:
                return 50
            if pe_v <= 20:
                return 85
            elif pe_v <= 35:
                return 70
            elif pe_v <= 50:
                return 55
            elif pe_v <= 70:
                return 40
            return 25

        health = min(100, max(0, 100 - debt))
        growth_score = min(90, max(10, int(rev_yoy_v * 2.5)))
        profit_score = 80 if gp >= 40 else (60 if gp >= 30 else (40 if gp >= 20 else 25))
        roe_score = min(95, int(roe * 4)) if roe > 0 else 30

        scores = {
            "盈利能力": {"value": profit_score, "desc": f"毛利率{gp:.1f}%"},
            "成长性": {"value": growth_score, "desc": f"营收增{rev_yoy}"},
            "财务健康": {"value": int(health), "desc": f"负债率{debt:.0f}%"},
            "估值合理": {"value": val_score(pe), "desc": f"PE {pe if pe else '—'}x"},
            "ROE质量": {"value": roe_score, "desc": f"ROE{roe:.1f}%"},
        }
        total = sum(v["value"] for v in scores.values()) // 5
        indicators = [{"name": k, "max": 100} for k in scores]
        values = [v["value"] for v in scores.values()]
        items_html = ""
        for k, v in scores.items():
            val = v["value"]
            letter = "A" if val >= 80 else ("B" if val >= 60 else ("C" if val >= 40 else "D"))
            items_html += f'<div class="score-item"><div class="score-label">{k}</div><div class="score-value score-{letter}">{letter}</div><div class="score-desc">{v["desc"]}</div></div>\n'
        return items_html, total, {"indicators": indicators, "values": values}

    def chain_svg(self):
        name = self.stock_name()[:12]
        sector = self.sector()
        if "半导" in sector or "电子" in sector:
            return '''
<rect x="60" y="50" width="160" height="60" rx="8" fill="#1a2338" stroke="#2a3550" stroke-width="1"/>
<text x="140" y="68" text-anchor="middle" fill="#8892b0" font-size="11">上游</text>
<text x="140" y="86" text-anchor="middle" fill="#e0e4ed" font-size="12">IP/EDA/晶圆代工</text>
<text x="140" y="100" text-anchor="middle" fill="#475569" font-size="9">高壁垒，国产替代空间</text>
<text x="228" y="85" fill="#475569" font-size="24">→</text>
<rect x="250" y="40" width="200" height="80" rx="10" fill="#1e3a5f" stroke="#3b82f6" stroke-width="2"/>
<text x="350" y="60" text-anchor="middle" fill="#60a5fa" font-size="11">★ 中游（核心）</text>
<text x="350" y="80" text-anchor="middle" fill="#e0e4ed" font-size="14" font-weight="600">V_NAME</text>
<text x="350" y="98" text-anchor="middle" fill="#8892b0" font-size="11">芯片设计/模组</text>
<text x="350" y="112" text-anchor="middle" fill="#475569" font-size="9">毛利率V_GP%</text>
<text x="458" y="85" fill="#475569" font-size="24">→</text>
<rect x="480" y="50" width="160" height="60" rx="8" fill="#1a2338" stroke="#2a3550" stroke-width="1"/>
<text x="560" y="68" text-anchor="middle" fill="#8892b0" font-size="11">下游</text>
<text x="560" y="86" text-anchor="middle" fill="#e0e4ed" font-size="12">品牌/OEM/运营商</text>
<text x="560" y="100" text-anchor="middle" fill="#475569" font-size="9">客户集中度V_CUST%</text>'''.replace("V_NAME", name).replace("V_GP", "—").replace("V_CUST", "—")
        return '''
<rect x="120" y="42" width="220" height="76" rx="10" fill="#1e3a5f" stroke="#3b82f6" stroke-width="2"/>
<text x="230" y="62" text-anchor="middle" fill="#60a5fa" font-size="11">★ V_NAME</text>
<text x="230" y="82" text-anchor="middle" fill="#e0e4ed" font-size="13">V_SECTOR</text>
<text x="230" y="100" text-anchor="middle" fill="#475569" font-size="9">市值V_MC｜PE V_PE｜ROE V_ROE</text>'''.replace("V_NAME", name).replace("V_SECTOR", sector[:20]).replace("V_MC", self.market_cap()).replace("V_PE", f"{self.last_pe_pb()[0]:.0f}x" if self.last_pe_pb()[0] else "—").replace("V_ROE", fmt_pct(self.key_metrics().get("净资产收益率","—")))

    def research_items(self, max_n=5):
        r = self._get("research", [])
        items = ""
        for x in r[:max_n]:
            title = (x.get("报告名称","") or "")[:50]
            org = x.get("机构","—")
            rating = x.get("东财评级","—")
            date = fmt_date(x.get("日期",""))
            items += f'<div class="report-item"><div><div class="r-title">{title}</div><div class="r-meta">{org} ｜ {date}</div></div><div class="r-rating">★ {rating}</div></div>\n'
        if not items:
            items = '<div style="color:var(--text3);padding:16px;text-align:center;">暂无近期研报</div>'
        return items

    def conclusion(self, pe=None):
        if pe is None:
            pe, _ = self.last_pe_pb()
        metrics = self.key_metrics()
        try:
            roe = float(str(metrics.get("净资产收益率","0%")).replace("%",""))
        except:
            roe = 0
        if pe and pe <= 30 and roe >= 15:
            return "估值偏低，ROE较高，安全边际充裕，适合中长线布局"
        elif pe and pe <= 50:
            return "估值合理，关注业绩拐点，等待确定性信号"
        elif pe and pe <= 70:
            return "估值偏高，已反映乐观预期，需业绩超预期验证"
        else:
            return "估值过高，风险较大，建议等待估值回归或确定性催化剂出现"

    def rating_letter(self, pe=None):
        if pe is None:
            pe, _ = self.last_pe_pb()
        try:
            roe = float(str(self.key_metrics().get("净资产收益率","0%")).replace("%",""))
        except:
            roe = 0
        if pe and pe <= 30 and roe >= 15:
            return "A"
        elif pe and pe <= 50:
            return "B"
        elif pe and pe <= 70:
            return "C"
        return "D"

    def tags(self):
        name = self.stock_name()
        sector = self.sector()
        tags = [name[:4], sector.split(" ")[0].split("—")[0]]
        if "半导" in sector or "电子" in sector:
            tags.append("半导体")
        if "电气" in sector:
            tags.append("电力设备")
        if "软件" in sector or "信息" in sector:
            tags.append("AIoT")
        if "能源" in sector or "光伏" in sector:
            tags.append("新能源")
        tags.append("科创板")
        pe, _ = self.last_pe_pb()
        if pe and pe <= 30:
            tags.append("低估值")
        elif pe and pe >= 60:
            tags.append("高估值")
        metrics = self.key_metrics()
        try:
            gp = float(str(metrics.get("销售毛利率","0%")).replace("%",""))
            tags.append("高毛利" if gp >= 40 else ("中毛利" if gp >= 20 else "低毛利"))
        except:
            pass
        return "".join(f'<span class="tag-pill">{t}</span>' for t in tags[:8])

    def tags_inline(self):
        sector = self.sector()
        tags = []
        if "半导" in sector or "电子" in sector:
            tags.append("半导体")
        if "电气" in sector:
            tags.append("电力设备")
        if "软件" in sector or "信息" in sector:
            tags.append("科技")
        pe, _ = self.last_pe_pb()
        if pe and pe <= 30:
            tags.append("低估值")
        elif pe and pe >= 60:
            tags.append("高估值")
        return " · ".join(tags[:4]) if tags else sector[:12]

    def scenarios(self, cur_price=None):
        if cur_price is None:
            try:
                cur_price = float(self.spot.get("最新价", 0))
            except:
                cur_price = 100
        pe, _ = self.last_pe_pb()
        pe = pe or 30
        shares = float(self.total_shares()) or 4.0

        # 从一致预期获取参考EPS
        ths = self._get("ths", {})
        forecast = ths.get("ths_forecast", {})
        consensus = forecast.get("consensus", [])
        np_2026e = None
        for c in consensus:
            if c.get("预测指标") == "净利润(元)":
                raw = c.get("预测2026（平均）", "0")
                try:
                    np_2026e = float(str(raw).replace("亿", ""))
                except:
                    pass
                break

        eps_base = np_2026e / shares if np_2026e and shares > 0 else (pe and cur_price/pe or 1.0)

        if pe < 30:
            o_pe, b_pe, c_pe = pe*1.2, pe, pe*0.85
        elif pe < 50:
            o_pe, b_pe, c_pe = pe*1.1, pe*0.85, pe*0.65
        else:
            o_pe, b_pe, c_pe = pe*0.85, pe*0.65, pe*0.45

        s_opt = {"price": round(eps_base*1.2*o_pe,1), "ret": round(eps_base*1.2*o_pe/cur_price*100-100,1), "desc": "营收+30%+利润率改善"}
        s_base = {"price": round(eps_base*b_pe,1), "ret": round(eps_base*b_pe/cur_price*100-100,1), "desc": "符合一致预期"}
        s_cons = {"price": round(eps_base*0.8*c_pe,1), "ret": round(eps_base*0.8*c_pe/cur_price*100-100,1), "desc": "业绩miss+估值收缩"}
        return s_opt, s_base, s_cons

    def forecast_data(self):
        ths = self._get("ths", {})
        forecast = ths.get("ths_forecast", {})
        consensus = forecast.get("consensus", [])
        rev_map, np_map = {}, {}
        rev_key = next((k for k in ["营业收入(元)","营业收入"]), "营业收入(元)")
        np_key = next((k for k in ["净利润(元)","净利润"]), "净利润(元)")
        for item in consensus:
            key = item.get("预测指标","")
            for yr in [2023,2024,2025,2026,2027,2028]:
                yk = f"预测{yr}（平均）" if yr > 2025 else f"{yr}（实际值）"
                val = item.get(yk)
                if key in ("营业收入(元)", "营业收入") and "增长" not in key:
                    rev_map[yr] = val
                elif key in ("净利润(元)", "净利润") and "增长" not in key:
                    np_map[yr] = val
        labels, revs, profits = [], [], []
        for yr in [2023,2024,2025,2026,2027]:
            label = f"{yr}E" if yr > 2025 else f"{yr}A"
            r = rev_map.get(yr)
            n = np_map.get(yr)
            if r is not None:
                labels.append(label)
                revs.append(self._parse_num(r))
                profits.append(self._parse_num(n) if n is not None else 0)
        return {"labels": labels, "revenue": revs, "profit": profits}

    def sensitivity_data(self):
        fc = self.forecast_data()
        # Use the latest forecast year base
        base = fc["profit"][-1] if fc["profit"] and fc["profit"][-1] > 0 else 5.0
        return {"labels": ["-20%","-10%","基准","+10%","+20%"], "values": [round(base*0.8,2), round(base*0.9,2), round(base,2), round(base*1.1,2), round(base*1.2,2)], "base": round(base,2)}

    def fin_health(self):
        fin = self.financial_data()
        return {"labels": fin["labels"], "debt": fin["debt"], "ratio": fin["ratio"]}

    def cycle_gauge(self):
        pe, _ = self.last_pe_pb()
        sector = self.sector()
        # 行业周期位置（粗略估计）
        if "半导" in sector or "电子" in sector:
            ind_cycle = 45  # 成长中
        elif "电力" in sector or "电气" in sector:
            ind_cycle = 65  # 成熟
        else:
            ind_cycle = 50
        # 估值热度
        if pe:
            val_hot = min(95, max(5, (pe/80)*100))
        else:
            val_hot = 50
        return {"industry": ind_cycle, "valuation": round(val_hot)}

    def peer_rows(self):
        name = self.stock_name()
        pe, _ = self.last_pe_pb()
        metrics = self.key_metrics()
        try:
            gp = float(str(metrics.get("销售毛利率","0%")).replace("%",""))
        except:
            gp = 0
        try:
            np = float(str(metrics.get("销售净利率","0%")).replace("%",""))
        except:
            np = 0
        try:
            roe = float(str(metrics.get("净资产收益率","0%")).replace("%",""))
        except:
            roe = 0
        _, rev_yoy = self.last_year_growth()
        mcap = self.market_cap()

        def cell(v, fmt=".2f", suffix=""):
            try:
                return f'{float(v):{fmt}}{suffix}'
            except:
                return "—"

        # 本标的行为第一行高亮
        rows = ''
        highlight = ' style="background:color-mix(in srgb, var(--hl) 8%, var(--card));border-left:3px solid var(--hl);font-weight:600"'

        # Try to add peers from research reports (机构 names)
        research = self._get("research", [])
        peers_found = []
        for r in research[:5]:
            title = r.get("报告名称","")
            # Extract peer company names from report title (crude heuristic)
            for kw in ["对比","VS","vs","vs."]:
                if kw in title:
                    parts = title.split(kw)
                    for p in parts:
                        p = p.strip()[:8]
                        if p and p != name[:4] and len(p) >= 2:
                            peers_found.append(p)

        firms = []
        for f in peers_found[:3]:
            firms.append(f"<td>同行业</td><td>—</td><td>—</td><td>—</td><td>—</td><td>—</td><td>—</td>")

        rows += f'<tr{highlight}><td>★ {name[:10]}</td><td>{cell(pe,".1f")}x</td><td>{cell(roe)}%</td><td>{cell(gp)}%</td><td>{cell(np)}%</td><td>{rev_yoy}</td><td>{mcap}</td><td>—</td></tr>\n'
        for f in firms:
            rows += f"<tr><td>{f}</td></tr>\n"
        return rows

    def biz_desc(self):
        zygc = self._get("zygc", [])
        if zygc:
            dates = set(r["报告日期"] for r in zygc)
            latest = max(dates) if dates else ""
            top = [r for r in zygc if r["报告日期"] == latest and r.get("收入比例")]
            parts = []
            for r in top[:4]:
                name = r.get("主营构成","")
                if any(kw in name for kw in ("境内","境外","内部","全部地区","其他")):
                    continue
                try:
                    pct = float(str(r.get("收入比例","0")).replace("%","")) * 100
                    parts.append(f"{name}({pct:.0f}%)")
                except:
                    parts.append(name)
            if parts:
                return "、".join(parts[:3]) + "等"
        return "主营业务数据待补充"

    def risk_items(self):
        pe, _ = self.last_pe_pb()
        items = []
        if pe and pe >= 60:
            items.append(("high", f"PE高达{pe:.0f}x，远高于行业均值，杀估值风险大"))
        if pe and pe <= 20:
            items.append(("low", f"PE仅{pe:.0f}x，估值已充分反映悲观预期"))
        try:
            debt = float(str(self.key_metrics().get("资产负债率","0%")).replace("%",""))
            if debt >= 50:
                items.append(("mid", f"资产负债率{debt:.0f}%，杠杆偏高，利率上行有压力"))
        except:
            pass
        items.append(("low", "跌破止损位应严格执行减仓/清仓"))
        if len(items) < 3:
            items.append(("mid", "跟踪中报/季报业绩，验证全年预期"))
        return items

    def _placeholder(self):
        return "AI分析师将在此补充分析..."

    def kpi_items(self):
        pe, _ = self.last_pe_pb()
        metrics = self.key_metrics()
        try:
            gp = float(str(metrics.get("销售毛利率","0%")).replace("%",""))
        except:
            gp = 0
        try:
            debt = float(str(metrics.get("资产负债率","0%")).replace("%",""))
        except:
            debt = 0
        return [
            (f"{pe:.0f}x" if pe else "—", "PE-TTM", "每周"),
            (f"{gp:.1f}%" if gp else "—", "毛利率", "每季"),
            (f"{debt:.0f}%" if debt else "—", "负债率", "每季"),
        ]


def build_report(data_path: str) -> str:
    data = load_data(data_path)
    rb = ReportBuilder(data)

    stock_name = rb.stock_name()
    stock_code = rb.stock_code()
    ipo_date = rb.ipo_date()
    sector = rb.sector()
    total_shares = rb.total_shares()
    float_shares = rb.float_shares()
    price_str = rb.price()
    change_pct = rb.change_pct()
    change_amt = rb.change_amt()
    change_cls = "up" if float(change_pct) >= 0 else "down"
    mcap = rb.market_cap()

    pe_ttm, pb_mrq = rb.last_pe_pb()
    fin = rb.financial_data()
    rev_yoy, prof_yoy = rb.last_year_growth()
    metrics = rb.key_metrics()

    revenue_str = f"{fin['revenue'][-1]:.2f}亿" if fin.get("revenue") and len(fin["revenue"])>0 else "—"
    profit_str = f"{fin['profit'][-1]:.2f}亿" if fin.get("profit") and len(fin["profit"])>0 else "—"
    gp_str = fmt_pct(metrics.get("销售毛利率","—"))
    np_str = fmt_pct(metrics.get("销售净利率","—"))
    roe_str = fmt_pct(metrics.get("净资产收益率","—"))
    eps_ttm_str = rb.eps_ttm()
    eps_con_str = rb.eps_consensus()
    cur_price = float(price_str) if price_str != "—" else 0
    pe_fwd = f"{cur_price/float(eps_con_str):.1f}" if eps_con_str != "—" and cur_price else "—"

    # K-line data
    kh_dates, kh_prices, kh_vols, kh_ma5, kh_ma20, kh_ma60 = rb.kline_series(365)
    kh_start = max(0, 100 - min(80, len(kh_dates)//4)) if kh_dates else 0

    val_data = rb.valuation_series()

    score_items, score_total, radar_data = rb.scores_and_radar()
    s_opt, s_base, s_cons = rb.scenarios(cur_price)
    conclusion = rb.conclusion(pe_ttm)
    rating = rb.rating_letter(pe_ttm)
    tags_html = rb.tags()
    tags_inline = rb.tags_inline()
    biz_desc = rb.biz_desc()
    rev_breakdown = rb.revenue_breakdown()

    consensus_rows, consensus_count = rb.consensus_table()
    sh_rows = rb.shareholder_rows()
    mf_data = rb.moneyflow_data()
    research_items = rb.research_items()
    risk_list = rb.risk_items()
    chain_svg = rb.chain_svg()
    forecast_data = rb.forecast_data()
    sensitivity_data = rb.sensitivity_data()
    fin_health = rb.fin_health()
    cycle_gauge = rb.cycle_gauge()
    peer_rows = rb.peer_rows()
    kpi_items = rb.kpi_items()
    # timing targets
    mid_target = s_base["price"]
    long_target = s_opt["price"]
    short_target = round((cur_price + mid_target) / 2, 1)
    short_ret = f"{round((short_target/cur_price-1)*100,1)}%"
    mid_ret = f"{s_base['ret']}%"
    long_ret = f"{s_opt['ret']}%"
    risk_reward = f"1:{round(abs((s_opt['price']-cur_price)/(cur_price-s_cons['price'])),1)}" if s_cons['price'] < cur_price else "—"
    rr_desc = "盈亏比偏低" if risk_reward == "—" or float(risk_reward.split(":")[1]) < 2 else ("盈亏比适中" if float(risk_reward.split(":")[1]) < 3 else "盈亏比优秀")
    buy_zone = f"¥{round(s_cons['price']*0.95,1)}–{round(s_cons['price']*1.05,1)}"
    hold_zone = f"¥{round(s_cons['price']*1.05,1)}–{round(s_opt['price']*0.95,1)}"
    sell_zone = f"¥{round(s_opt['price']*0.95,1)}以上"
    buy_active = f'<div class="timing-trigger {"trigger-yes" if cur_price < s_base["price"] else "trigger-maybe"}">{"✅ 可考虑建仓" if cur_price < s_base["price"] else "⏳ 等待回落"}</div>'

    report_date = dt.datetime.now().strftime("%Y-%m-%d %H:%M")

    def j(v):
        return json.dumps(v, ensure_ascii=False)

    kh_vols_json = j([[v[0], v[1], 1] for v in kh_vols])  # [date, vol, direction]

    # Moneyflow conditional (must come after j())
    if mf_data["dates"]:
        mf_html = '<div class="chart-box" id="chart-moneyflow" style="height:260px;"></div>'
        mf_dates = j(mf_data["dates"])
        mf_main = j(mf_data["mainForce"])
        mf_super = j(mf_data["super"])
        mf_big = j(mf_data["big"])
        mf_js = f"// 7. 资金流向\ninitChart('chart-moneyflow',{{tooltip:{{trigger:'axis',backgroundColor:'#1a2338',borderColor:'#2a3550',textStyle:{{color:'#e0e4ed'}}}},legend:{{data:['主力净流入','超大单','大单'],textStyle:{{color:'#8892b0'}}}},grid:{{left:'10%',right:'8%',top:'12%',bottom:'14%'}},xAxis:{{type:'category',data:{mf_dates},axisLabel:{{color:'#64748b',rotate:20}},axisLine:{{lineStyle:{{color:'#2a3550'}}}}}},yAxis:{{type:'value',name:'净额(万)',nameTextStyle:{{color:'#8892b0'}},splitLine:{{lineStyle:{{color:'#1e293b'}}}},axisLabel:{{color:'#64748b'}}}},series:[{{name:'主力净流入',type:'bar',data:{mf_main},itemStyle:{{color:function(p){{return p.value>=0?'#ef4444':'#22c55e'}}}}}},{{name:'超大单',type:'line',data:{mf_super},smooth:true,symbol:'none',lineStyle:{{width:1,color:'#f59e0b'}}}},{{name:'大单',type:'line',data:{mf_big},smooth:true,symbol:'none',lineStyle:{{width:1,color:'#8b5cf6'}}}}]}});\n"
    else:
        mf_html = '<div style="padding:30px;text-align:center;color:var(--text3);font-size:14px;">暂无资金流向数据</div>'
        mf_js = ''

    # ── 生成双主题静态图表图片 ──
    def _both(cid, dark_src, light_src):
        """生成带双主题切换的HTML片段"""
        d = dark_src or ''
        l = light_src or d
        _imgcache[cid] = (d, l)
        return d
    _imgcache = {}
    img_cache = _imgcache  # alias for template injection

    try:
        # K-line: convert [o,c,l,h] → [o,h,l,c] for mplfinance
        if kh_prices:
            k_dates = [d[:10] for d in kh_dates]
            k_opens = [p[0] for p in kh_prices]
            k_closes = [p[1] for p in kh_prices]
            k_lows = [p[2] for p in kh_prices]
            k_highs = [p[3] for p in kh_prices]
            k_vols = [v[1] for v in kh_vols] if kh_vols else []
            _both('chart-kline',
                  sc.kline_chart(k_dates, k_opens, k_highs, k_lows, k_closes, k_vols, title=stock_name, theme='dark'),
                  sc.kline_chart(k_dates, k_opens, k_highs, k_lows, k_closes, k_vols, title=stock_name, theme='light'))

        if fin.get('labels'):
            _both('chart-revenue',
                  sc.grouped_bar_chart(fin['labels'], [('营收(亿)', fin['revenue']), ('净利润(亿)', fin['profit'])], title='营收与净利润趋势', theme='dark'),
                  sc.grouped_bar_chart(fin['labels'], [('营收(亿)', fin['revenue']), ('净利润(亿)', fin['profit'])], title='营收与净利润趋势', theme='light'))
            _both('chart-margin',
                  sc.line_chart(fin['labels'], [('毛利率', fin['gross']), ('净利率', fin['net'])], title='利润率趋势', theme='dark'),
                  sc.line_chart(fin['labels'], [('毛利率', fin['gross']), ('净利率', fin['net'])], title='利润率趋势', theme='light'))

        if val_data.get('dates'):
            _both('chart-valuation',
                  sc.dual_axis_chart(val_data['dates'][-120:], [('PE-TTM', val_data['pe'][-120:])], [('PB', val_data['pb'][-120:])], title='PE/PB估值走势', ylabel_left='PE', ylabel_right='PB', theme='dark'),
                  sc.dual_axis_chart(val_data['dates'][-120:], [('PE-TTM', val_data['pe'][-120:])], [('PB', val_data['pb'][-120:])], title='PE/PB估值走势', ylabel_left='PE', ylabel_right='PB', theme='light'))

        if radar_data.get('indicators'):
            cats = [i['name'][:4] for i in radar_data['indicators']]
            vals = [i['max'] for i in radar_data['indicators']]
            _both('chart-radar',
                  sc.radar_chart(cats, vals, title='综合评分雷达', theme='dark'),
                  sc.radar_chart(cats, vals, title='综合评分雷达', theme='light'))

        if rev_breakdown:
            _both('chart-revenue-bd',
                  sc.pie_chart(rev_breakdown[:12], title='主营构成', theme='dark'),
                  sc.pie_chart(rev_breakdown[:12], title='主营构成', theme='light'))

        if forecast_data.get('labels'):
            _both('chart-forecast',
                  sc.grouped_bar_chart(forecast_data['labels'], [('营收(亿)', forecast_data['revenue']), ('净利润(亿)', forecast_data['profit'])], title='盈利预测', theme='dark'),
                  sc.grouped_bar_chart(forecast_data['labels'], [('营收(亿)', forecast_data['revenue']), ('净利润(亿)', forecast_data['profit'])], title='盈利预测', theme='light'))

        if sensitivity_data.get('labels'):
            _both('chart-sensitivity',
                  sc.bar_chart(sensitivity_data['labels'], sensitivity_data['values'], title='营收增速 vs 净利率敏感度', theme='dark'),
                  sc.bar_chart(sensitivity_data['labels'], sensitivity_data['values'], title='营收增速 vs 净利率敏感度', theme='light'))

        if fin_health.get('labels'):
            _both('chart-fin-health',
                  sc.dual_axis_chart(fin_health['labels'], [('资产负债率', fin_health['debt'])], [('流动比率', fin_health['ratio'])], title='财务健康度', ylabel_left='%', ylabel_right='倍', theme='dark'),
                  sc.dual_axis_chart(fin_health['labels'], [('资产负债率', fin_health['debt'])], [('流动比率', fin_health['ratio'])], title='财务健康度', ylabel_left='%', ylabel_right='倍', theme='light'))

        if mf_data.get('dates'):
            try:
                _both('chart-moneyflow',
                      sc.line_chart([d[-5:] for d in mf_data['dates'][-30:]],
                                   [('主力流入', [v/10000 for v in mf_data['mainForce'][-30:]]),
                                    ('超大单', [v/10000 for v in mf_data['super'][-30:]]),
                                    ('大单', [v/10000 for v in mf_data['big'][-30:]])],
                                   title='资金流向(万元)', theme='dark'),
                      sc.line_chart([d[-5:] for d in mf_data['dates'][-30:]],
                                   [('主力流入', [v/10000 for v in mf_data['mainForce'][-30:]]),
                                    ('超大单', [v/10000 for v in mf_data['super'][-30:]]),
                                    ('大单', [v/10000 for v in mf_data['big'][-30:]])],
                                   title='资金流向(万元)', theme='light'))
            except Exception:
                pass
    except Exception as e:
        print(f'⚠️ 图表渲染异常: {e}')

    # ── 填入 _fill 参数 ──
    import re
    def _fill(template: str, **kw) -> str:
        """Replace {PLACEHOLDER} patterns; then convert {{ -> { for CSS/JS."""
        def _repl(m):
            k = m.group(1)
            if k in kw:
                return str(kw[k])
            return m.group(0)
        result = re.sub(r'\{([A-Z_][A-Z0-9_]*)\}', _repl, template)
        result = result.replace('{{', '{').replace('}}', '}')
        return result

    html = _fill(HTML_TEMPLATE, **dict(
        STOCK_NAME=stock_name, STOCK_CODE=stock_code,
        STOCK_SECTOR=sector, IPO_DATE=ipo_date,
        TOTAL_SHARES=total_shares, FLOAT_SHARES=float_shares,
        MARKET_CAP=mcap, TAGS_INLINE=tags_inline,
        PRICE=price_str, CHANGE_PCT=change_pct,
        CHANGE_AMT=change_amt, CHANGE_CLS=change_cls,
        REPORT_DATE=report_date,
        PE_TTM=f"{pe_ttm:.1f}x" if pe_ttm else "—",
        PE_FWD=pe_fwd,
        PB_MRQ=f"{pb_mrq:.2f}" if pb_mrq else "—",
        REVENUE=revenue_str, REVENUE_YOY=str(rev_yoy),
        NET_PROFIT=profit_str, PROFIT_YOY=str(prof_yoy),
        GROSS_MARGIN=gp_str, NET_MARGIN=np_str,
        ROE=roe_str,
        EPS_TTM=eps_ttm_str, EPS_CONSENSUS=eps_con_str,
        # Step 0
        BIZ_DESC=biz_desc, TAGS_HTML=tags_html,
        # Step 1
        MACRO_ECONOMY=rb._placeholder(),
        INDUSTRY_CYCLE=rb._placeholder(),
        POLICY_DIRECTION=rb._placeholder(),
        # Step 2
        CHAIN_SVG=chain_svg,
        COMPETITION_LANDSCAPE=rb._placeholder(),
        COMPETITIVE_ADVANTAGE=rb._placeholder(),
        # Step 3
        SCORE_ITEMS=score_items, SCORE_TOTAL=str(score_total),
        # Step 4
        S_OPT_PRICE=s_opt["price"], S_OPT_RET=s_opt["ret"], S_OPT_DESC=s_opt["desc"],
        S_BASE_PRICE=s_base["price"], S_BASE_RET=s_base["ret"], S_BASE_DESC=s_base["desc"],
        S_CONS_PRICE=s_cons["price"], S_CONS_RET=s_cons["ret"], S_CONS_DESC=s_cons["desc"],
        # Step 5
        RISK_ITEMS="\n".join(
            f'<li><span class="risk-signal risk-{l}"></span>{t}</li>' for l, t in rb.risk_items()
        ),
        # Step 6
        SHORT_TARGET=f"¥{short_target}", SHORT_RET=short_ret,
        MID_TARGET=f"¥{mid_target}", MID_RET=mid_ret,
        LONG_TARGET=f"¥{long_target}", LONG_RET=long_ret,
        RISK_REWARD=risk_reward, RR_DESC=rr_desc,
        BUY_ZONE=buy_zone, BUY_TRIGGER="估值偏低时分批建仓",
        BUY_ACTIVE=buy_active,
        HOLD_ZONE=hold_zone, HOLD_STRATEGY="持有等待催化剂释放",
        SELL_ZONE=sell_zone, SELL_TRIGGER="目标达成或基本面恶化",
        # Step 7
        PEER_ROWS=peer_rows,
        COMPETITIVE_EDGE=rb._placeholder(),
        GROWTH_ENGINE=rb._placeholder(),
        # Step 8
        KPI_1_NAME=kpi_items[0][0] if len(kpi_items)>0 else "—",
        KPI_1_VAL=kpi_items[0][1] if len(kpi_items)>0 else "",
        KPI_1_FREQ=kpi_items[0][2] if len(kpi_items)>0 else "",
        KPI_2_NAME=kpi_items[1][0] if len(kpi_items)>1 else "",
        KPI_2_VAL=kpi_items[1][1] if len(kpi_items)>1 else "",
        KPI_2_FREQ=kpi_items[1][2] if len(kpi_items)>1 else "",
        KPI_3_NAME=kpi_items[2][0] if len(kpi_items)>2 else "",
        KPI_3_VAL=kpi_items[2][1] if len(kpi_items)>2 else "",
        KPI_3_FREQ=kpi_items[2][2] if len(kpi_items)>2 else "",
        REVIEW_CADENCE="每季财报后",
        CONCLUSION=conclusion, RATING_LETTER=rating,
        REVIEW_PLAN=rb._placeholder(),
        FINAL_CONCLUSION=rb._placeholder(),
        # K-line data as JSON arrays
        KH_DATES=j(kh_dates),
        KH_PRICES=j(kh_prices),
        KH_VOLS=kh_vols_json,
        KH_MA5=j(kh_ma5),
        KH_MA20=j(kh_ma20),
        KH_MA60=j(kh_ma60),
        KH_START=str(kh_start),
        # Revenue / Margin chart data
        RV_LABELS=j(fin["labels"]),
        RV_REVENUE=j(fin["revenue"]),
        RV_PROFIT=j(fin["profit"]),
        MG_GROSS=j(fin["gross"]),
        MG_NET=j(fin["net"]),
        # Valuation data
        VL_DATES=j(val_data["dates"]),
        VL_PE=j(val_data["pe"]),
        VL_PB=j(val_data["pb"]),
        # Radar
        RADAR_INDICATORS=j(radar_data["indicators"]),
        RADAR_VALUES=j(radar_data["values"]),
        # Revenue breakdown
        REV_BD_DATA=j(rev_breakdown),
        # Money flow
        MONEYFLOW_HTML=mf_html,
        MONEYFLOW_JS=mf_js,
        # Cycle gauge
        CYCLE_GAUGE=j(cycle_gauge),
        # Forecast
        FORECAST_DATA=j(forecast_data),
        # Sensitivity
        SENSITIVITY_DATA=j(sensitivity_data),
        # Financial health
        FIN_HEALTH=j(fin_health),
        # Consensus & shareholders
        CONSENSUS_ROWS=consensus_rows, CONSENSUS_COUNT=consensus_count,
        SHAREHOLDER_ROWS=sh_rows,
        RESEARCH_ITEMS=research_items,
    ))
    # ── Post-process: replace chart divs with dual-theme <img> tags ──
    # Build {cid: (dark_src, light_src)} from _imgcache
    _img_pairs = dict(getattr(build_report, '_last_cache', {}))
    _img_pairs.update(_imgcache)
    build_report._last_cache = _imgcache

    # Remove echarts library script references
    html = re.sub(r'<script[^>]*src="[^"]*echarts[^"]*"[^>]*></script>', '', html)
    html = re.sub(r'<script[^>]*src="echarts\.min\.js"[^>]*></script>', '', html)

    # Replace each chart div with dual-theme img pair
    for cid, (dark_src, light_src) in _imgcache.items():
        if not dark_src and not light_src:
            continue
        dark_src = dark_src or light_src or ''
        light_src = light_src or dark_src or ''
        img_html = (
            f'<img src="{dark_src}" class="chart-img theme-dark"'
            f' style="max-width:100%;height:auto;display:block;border-radius:6px;margin:8px auto;">'
            f'<img src="{light_src}" class="chart-img theme-light"'
            f' style="max-width:100%;height:auto;display:none;border-radius:6px;margin:8px auto;">'
        )
        html = re.sub(
            rf'<div[^>]*?id="{re.escape(cid)}"[^>]*?>.*?</div>',
            img_html, html, flags=re.DOTALL
        )
    # Handle cycle gauge
    html = re.sub(r'<div[^>]*?id="chart-cycle"[^>]*?>.*?</div>', '', html, flags=re.DOTALL) 
    return html


def main():
    parser = argparse.ArgumentParser(description="Phase 3：HTML 报告（8步框架完整版）")
    parser.add_argument("json_path", nargs="?", default="", help="JSON 数据文件路径")
    parser.add_argument("-o", "--output", default="", help="输出 HTML 文件路径")
    args = parser.parse_args()

    json_path = args.json_path
    if not json_path:
        out_dir = os.path.join(os.path.dirname(__file__), "output")
        if os.path.isdir(out_dir):
            jsons = sorted([f for f in os.listdir(out_dir) if f.endswith(".json")])
            if jsons:
                json_path = os.path.join(out_dir, jsons[-1])
                print(f"📂 自动选择: {json_path}")
    if not json_path or not os.path.isfile(json_path):
        print("❌ 请指定 JSON 文件路径")
        sys.exit(1)

    print("📊 正在生成 8步框架 HTML 报告...")
    html = build_report(json_path)

    if args.output:
        out_path = args.output
    else:
        base = os.path.basename(json_path)
        code_part = base.split("_")[1] if "_" in base else "unknown"
        code_part = code_part.replace(".json","").replace("_ths","")
        try:
            d = json.load(open(json_path))
            name = ReportBuilder(d).stock_name()
        except:
            name = f"股票_{code_part}"
        out_dir = os.path.join(os.path.dirname(__file__), "output")
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, f"个股研究-{name}.html")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ 已生成: {out_path} ({os.path.getsize(out_path)/1024:.1f} KB)")

    qq_dir = "/root/.openclaw/media/qqbot"
    if os.path.isdir(qq_dir):
        qq_path = os.path.join(qq_dir, f"个股研究-{name}.html")
        with open(qq_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"✅ QQ媒体目录同步: {qq_path}")


if __name__ == "__main__":
    main()
