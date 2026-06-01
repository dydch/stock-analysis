#!/usr/bin/env python3
"""
Phase 3：HTML 可视化报告生成器（完整版）
==============================
读取 Phase 1 采集的 JSON 数据，生成专业的可交互 HTML 可视化报告。

特性：双主题切换 / 结论置顶 / 公司画像 / 产业链SVG / K线含MA /
      情景分析 / 风险信号 / 五维评分雷达 / 导航滚动高亮

用法
  python stock_html_report.py output/data_600519.json
  python stock_html_report.py output/data_688099_ths.json

输出
  output/个股研究-{股票名称}.html（单文件，浏览器直接打开）
"""

from __future__ import annotations

import json
import os
import sys
import argparse
import datetime as dt
from typing import Any

# ──────────────────── HTML 模板 ────────────────────

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>个股研究 - {STOCK_NAME}</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.6.0/dist/echarts.min.js"></script>
<style>
:root {{
  --bg: #0a0e17; --card: #141b2d; --border: #2a3550;
  --text: #e0e4ed; --text2: #8892b0; --text3: #475569;
  --hl: #3b82f6; --hl2: #60a5fa; --up: #ef4444; --down: #22c55e;
  --warn: #f59e0b; --purple: #8b5cf6;
}}
.light {{
  --bg: #f8fafc; --card: #ffffff; --border: #e2e8f0;
  --text: #1e293b; --text2: #64748b; --text3: #94a3b8;
  --hl: #2563eb; --hl2: #3b82f6; --up: #dc2626; --down: #16a34a;
  --warn: #d97706; --purple: #7c3aed;
}}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{
  font-family: -apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif;
  background: var(--bg); color: var(--text); line-height: 1.6;
  transition: background .3s, color .3s;
}}
/* ── Top Bar ── */
.topbar {{
  position: sticky; top: 0; z-index: 100;
  background: var(--card); border-bottom: 1px solid var(--border);
  padding: 0 20px; height: 48px;
  display: flex; align-items: center; gap: 16px;
  backdrop-filter: blur(8px);
}}
.topbar .nav-links {{ display: flex; gap: 4px; overflow-x: auto; flex:1; }}
.topbar .nav-links a {{
  color: var(--text2); text-decoration: none; font-size: 12px;
  padding: 6px 12px; border-radius: 6px; white-space: nowrap;
  transition: all .2s;
}}
.topbar .nav-links a:hover, .topbar .nav-links a.active {{ background: var(--hl); color: #fff; }}
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
.conclusion-sticky .tag.rating-A {{ background: #22c55e; }}
.conclusion-sticky .tag.rating-B {{ background: #60a5fa; }}
.conclusion-sticky .tag.rating-C {{ background: #f59e0b; }}
.conclusion-sticky .tag.rating-D {{ background: #ef4444; }}

/* ── Header ── */
.header {{
  background: var(--card); border-radius: 16px; padding: 24px 32px;
  margin-bottom: 20px; border: 1px solid var(--border);
  display: flex; justify-content: space-between; align-items: center;
  flex-wrap: wrap; gap: 16px;
}}
.header-left h1 {{ font-size: 26px; font-weight: 700; color: var(--text); }}
.header-left h1 span {{ color: var(--hl); }}
.header-left .subtitle {{ color: var(--text2); font-size: 13px; margin-top: 2px; }}
.header-right {{ text-align: right; }}
.header-right .price {{ font-size: 36px; font-weight: 700; color: var(--text); }}
.header-right .change {{ font-size: 15px; }}
.header-right .change.up {{ color: var(--up); }}
.header-right .change.down {{ color: var(--down); }}
.header-right .date {{ color: var(--text2); font-size: 12px; margin-top: 1px; }}

/* ── 指标卡片 ── */
.card-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(220px,1fr)); gap: 12px; margin-bottom: 20px; }}
.card {{
  background: var(--card); border-radius: 12px; padding: 16px 20px;
  border: 1px solid var(--border); transition: border-color .2s;
}}
.card:hover {{ border-color: var(--hl); }}
.card .label {{ color: var(--text2); font-size: 12px; margin-bottom: 2px; }}
.card .value {{ font-size: 20px; font-weight: 600; color: var(--text); }}
.card .sub {{ color: var(--text3); font-size: 11px; margin-top: 1px; }}

/* ── Section ── */
.section {{
  background: var(--card); border-radius: 16px; padding: 24px;
  margin-bottom: 20px; border: 1px solid var(--border);
}}
.section h2 {{
  font-size: 17px; font-weight: 600; color: var(--text);
  margin-bottom: 16px; padding-bottom: 10px;
  border-bottom: 1px solid var(--border);
  display: flex; align-items: center; gap: 6px;
}}
.section h2 .badge {{
  display: inline-block; background: var(--hl); color: #fff;
  font-size: 10px; padding: 2px 7px; border-radius: 4px;
  font-weight: 500; margin-left: 6px;
}}
.section h2 .badge.warn {{ background: var(--warn); }}
.chart-box {{ width: 100%; height: 380px; }}
.chart-box.tall {{ height: 460px; }}

/* ── 表格 ── */
.table-wrap {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
th, td {{ padding: 8px 10px; text-align: right; white-space: nowrap; }}
th {{ background: color-mix(in srgb, var(--card) 95%, var(--text)); color: var(--text2); font-size: 11px; font-weight: 500; }}
td {{ border-bottom: 1px solid var(--border); }}
tr:hover td {{ background: color-mix(in srgb, var(--card) 98%, var(--text)); }}
td:first-child, th:first-child {{ text-align: left; }}

/* ── 评分 ── */
.score-row {{ display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 14px; }}
.score-item {{
  flex:1; min-width:120px; background: color-mix(in srgb, var(--card) 95%, var(--text));
  border-radius: 8px; padding: 14px; text-align: center;
}}
.score-item .score-label {{ color: var(--text2); font-size: 11px; }}
.score-item .score-value {{ font-size: 26px; font-weight:700; margin:3px 0; }}
.score-item .score-desc {{ font-size: 10px; color: var(--text3); }}
.score-A {{ color: var(--down); }} .score-B {{ color: var(--hl2); }}
.score-C {{ color: var(--warn); }} .score-D {{ color: var(--up); }}

/* ── 产业链SVG ── */
.chain-wrap {{ text-align: center; padding: 10px 0; }}
.chain-svg {{ max-width: 100%; }}

/* ── 情景分析 ── */
.scenario-grid {{ display: grid; grid-template-columns: repeat(3,1fr); gap: 12px; }}
.scenario-item {{
  border-radius: 12px; padding: 16px; text-align: center;
  border: 1px solid var(--border);
}}
.s-optimistic {{ border-color: var(--down); background: color-mix(in srgb, var(--down) 8%, var(--card)); }}
.s-base {{ border-color: var(--hl); background: color-mix(in srgb, var(--hl) 8%, var(--card)); }}
.s-pessimistic {{ border-color: var(--up); background: color-mix(in srgb, var(--up) 8%, var(--card)); }}
.scenario-item .s-label {{ font-size: 11px; color: var(--text2); }}
.scenario-item .s-price {{ font-size: 22px; font-weight: 700; margin: 4px 0; }}
.scenario-item .s-return {{ font-size: 14px; font-weight: 600; }}
.scenario-item .s-desc {{ font-size: 11px; color: var(--text3); margin-top: 6px; }}
.positive-ret {{ color: var(--up); }}
.negative-ret {{ color: var(--down); }}

/* ── 风险信号 ── */
.risk-list {{ list-style: none; }}
.risk-list li {{
  display: flex; align-items: center; gap: 10px;
  padding: 10px 14px; border-bottom: 1px solid var(--border);
  font-size: 13px;
}}
.risk-list li:last-child {{ border-bottom: none; }}
.risk-signal {{ width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }}
.risk-high {{ background: var(--up); }}
.risk-mid {{ background: var(--warn); }}
.risk-low {{ background: var(--down); }}

/* ── 研报 ── */
.report-item {{
  padding: 10px 14px; border-bottom: 1px solid var(--border);
  display: flex; justify-content: space-between; align-items: center;
}}
.report-item:last-child {{ border-bottom: none; }}
.report-item .r-title {{ color: var(--text); font-size: 13px; }}
.report-item .r-meta {{ color: var(--text3); font-size: 11px; }}
.report-item .r-rating {{ color: var(--down); font-weight:600; font-size: 11px; }}

/* ── 公司画像标签 ── */
.tag-cloud {{ display: flex; flex-wrap: wrap; gap: 6px; margin: 8px 0; }}
.tag-pill {{
  background: color-mix(in srgb, var(--hl) 15%, var(--card));
  color: var(--hl2); border: 1px solid color-mix(in srgb, var(--hl) 30%, var(--border));
  padding: 3px 12px; border-radius: 20px; font-size: 11px;
}}

/* ── 新闻 ── */
.news-item {{
  padding: 8px 0; border-bottom: 1px solid var(--border);
  font-size: 13px;
}}
.news-item:last-child {{ border-bottom: none; }}
.news-item .n-source {{ color: var(--text3); font-size: 11px; }}

.footer {{
  text-align: center; color: var(--text3); font-size: 12px;
  padding: 24px; border-top: 1px solid var(--border); margin-top: 40px;
}}

@media (max-width:768px) {{
  .header {{ flex-direction: column; text-align: center; }}
  .header-right {{ text-align: center; }}
  .scenario-grid {{ grid-template-columns: 1fr; }}
  .topbar .nav-links a {{ font-size: 11px; padding: 4px 8px; }}
}}
</style>
</head>
<body>
<!-- ==================== 顶栏/导航 ==================== -->
<div class="topbar">
  <div class="nav-links" id="navLinks">
    <a href="#conclusion">📌结论</a>
    <a href="#company">🏢公司</a>
    <a href="#finance">📊财务</a>
    <a href="#kline">📈K线</a>
    <a href="#valuation">🔍估值</a>
    <a href="#chain">🔗产业链</a>
    <a href="#score">⭐评分</a>
    <a href="#scenarios">🎯情景</a>
    <a href="#risk">⚠️风险</a>
  </div>
  <button class="theme-btn" id="themeToggle" title="切换主题">🌙</button>
</div>

<div class="container">

<!-- ==================== 结论置顶 ==================== -->
<div id="conclusion" class="conclusion-sticky">
  <span class="tag rating-{RATING_LETTER}">{RATING_LETTER}级</span>
  <span>{CONCLUSION}</span>
</div>

<!-- ==================== HEADER ==================== -->
<div class="header">
  <div class="header-left">
    <h1>{STOCK_NAME} <span>({STOCK_CODE})</span></h1>
    <div class="subtitle">{STOCK_SECTOR} ｜ {IPO_DATE}上市 ｜ 股本{TOTAL_SHARES}亿 ｜ 市值{MARKET_CAP}</div>
  </div>
  <div class="header-right">
    <div class="price">{PRICE}</div>
    <div class="change {CHANGE_CLS}">{CHANGE_PCT}% ({CHANGE_AMT})</div>
    <div class="date">{REPORT_DATE}</div>
  </div>
</div>

<!-- ==================== 指标卡片 ==================== -->
<div class="card-grid">
  <div class="card"><div class="label">PE-TTM</div><div class="value">{PE_TTM}</div></div>
  <div class="card"><div class="label">PB</div><div class="value">{PB_MRQ}</div></div>
  <div class="card"><div class="label">营收(最近年报)</div><div class="value">{REVENUE}</div><div class="sub">YOY {REVENUE_YOY}</div></div>
  <div class="card"><div class="label">净利润(最近年报)</div><div class="value">{NET_PROFIT}</div><div class="sub">YOY {PROFIT_YOY}</div></div>
  <div class="card"><div class="label">EPS-TTM</div><div class="value">{EPS_TTM}</div></div>
  <div class="card"><div class="label">一致预期2026E</div><div class="value">{EPS_CONSENSUS}</div><div class="sub">对应PE {PE_FWD}x</div></div>
  <div class="card"><div class="label">ROE</div><div class="value">{ROE}</div></div>
  <div class="card"><div class="label">毛利率/净利率</div><div class="value" style="font-size:17px">{GROSS_MARGIN} / {NET_MARGIN}</div></div>
</div>

<!-- ==================== 公司画像 ==================== -->
<div class="section" id="company">
  <h2>🏢 公司画像</h2>
  <div style="font-size:14px;margin-bottom:12px;line-height:1.7;">
    主营业务：{BIZ_DESC}
  </div>
  <div class="tag-cloud">{TAGS_HTML}</div>
  <div style="margin-top:12px;"><strong style="color:var(--text2);font-size:13px;">主营构成</strong></div>
  <div id="chart-revenue-bd" class="chart-box" style="height:260px;"></div>
  {NEWS_HTML}
</div>

<!-- ==================== 财务趋势 ==================== -->
<div class="section" id="finance">
  <h2>📊 财务趋势</h2>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;">
    <div><div style="color:var(--text2);font-size:12px;margin-bottom:6px;">营收 & 净利润</div><div id="chart-revenue" class="chart-box" style="height:280px;"></div></div>
    <div><div style="color:var(--text2);font-size:12px;margin-bottom:6px;">毛利率 & 净利率</div><div id="chart-margin" class="chart-box" style="height:280px;"></div></div>
  </div>
</div>

<!-- ==================== K线图 ==================== -->
<div class="section" id="kline">
  <h2>📈 K线走势 <span class="badge">MA5/20/60</span></h2>
  <div id="chart-kline" class="chart-box tall"></div>
</div>

<!-- ==================== 估值走势 ==================== -->
<div class="section" id="valuation">
  <h2>🔍 估值走势 <span class="badge">PE/PB</span></h2>
  <div id="chart-valuation" class="chart-box tall"></div>
</div>

<!-- ==================== 五维评分 ==================== -->
<div class="section" id="score">
  <h2>⭐ 五维度质量评分</h2>
  <div class="score-row">{SCORE_ITEMS}</div>
  <div id="chart-radar" class="chart-box" style="height:300px;"></div>
</div>

<!-- ==================== 产业链SVG ==================== -->
<div class="section" id="chain">
  <h2>🔗 产业链定位</h2>
  <div class="chain-wrap">
    <svg class="chain-svg" viewBox="0 0 800 120" width="800" height="120">{CHAIN_SVG}</svg>
  </div>
</div>

<!-- ==================== 情景分析 ==================== -->
<div class="section" id="scenarios">
  <h2>🎯 情景分析 <span class="badge warn">目标价预测</span></h2>
  <div class="scenario-grid">
    <div class="scenario-item s-optimistic">
      <div class="s-label">🟢 乐观情景</div>
      <div class="s-price" style="color:var(--up)">{S_OPT_PRICE}</div>
      <div class="s-return positive-ret">{S_OPT_RET}%</div>
      <div class="s-desc">{S_OPT_DESC}</div>
    </div>
    <div class="scenario-item s-base">
      <div class="s-label">🟡 中性情景</div>
      <div class="s-price" style="color:var(--hl)">{S_BASE_PRICE}</div>
      <div class="s-return" style="color:var(--warn)">{S_BASE_RET}%</div>
      <div class="s-desc">{S_BASE_DESC}</div>
    </div>
    <div class="scenario-item s-pessimistic">
      <div class="s-label">🔴 保守情景</div>
      <div class="s-price" style="color:var(--down)">{S_CONS_PRICE}</div>
      <div class="s-return negative-ret">{S_CONS_RET}%</div>
      <div class="s-desc">{S_CONS_DESC}</div>
    </div>
  </div>
</div>

<!-- ==================== 风险信号 ==================== -->
<div class="section" id="risk">
  <h2>⚠️ 风险信号 <span class="badge warn">止损参考</span></h2>
  <ul class="risk-list">{RISK_ITEMS}</ul>
</div>

<!-- ==================== 机构预期 & 股东 ==================== -->
<div class="section">
  <h2>📋 机构一致预期 <span class="badge">{CONSENSUS_COUNT}家</span></h2>
  <div class="table-wrap"><table><thead><tr><th>年度</th><th>营收</th><th>营收增长</th><th>净利润</th><th>净利增长</th><th>EPS</th><th>对应PE</th></tr></thead><tbody>{CONSENSUS_ROWS}</tbody></table></div>
</div>

<div class="section">
  <h2>🏛️ 十大股东</h2>
  <div class="table-wrap"><table><thead><tr><th>#</th><th>股东名称</th><th>持股比例</th><th>变动</th></tr></thead><tbody>{SHAREHOLDER_ROWS}</tbody></table></div>
</div>

<!-- ==================== 资金流向 ==================== -->
<div class="section">
  <h2>💰 资金流向 <span class="badge">近5日</span></h2>
  <div id="chart-moneyflow" class="chart-box" style="height:260px;"></div>
</div>

<!-- ==================== 研报 ==================== -->
<div class="section">
  <h2>📰 近期研报</h2>
  <div>{RESEARCH_ITEMS}</div>
</div>

<div class="footer">
  数据来源：BaoStock / akshare / 同花顺thsdk / 腾讯行情<br>
  {REPORT_DATE} 生成 ｜ 不构成投资建议
</div>
</div><!-- /container -->

<script>
// ============ 主题切换 ============
(function(){{
  var btn = document.getElementById('themeToggle');
  var isLight = localStorage.getItem('theme') === 'light';
  function applyTheme(light) {{
    document.body.classList.toggle('light', light);
    btn.textContent = light ? '☀️' : '🌙';
    localStorage.setItem('theme', light ? 'light' : 'dark');
  }}
  applyTheme(isLight);
  btn.onclick = function() {{ applyTheme(!document.body.classList.contains('light')); reRenderAll(); }};
  window.reRenderAll = function() {{
    setTimeout(function() {{
      document.querySelectorAll('[id^=chart-]').forEach(function(el) {{
        var inst = echarts.getInstanceByDom(el);
        if (inst) inst.resize();
      }});
    }}, 100);
  }};
}})();

// ============ 导航滚动高亮 ============
(function(){{
  var links = document.querySelectorAll('#navLinks a');
  var sections = [];
  links.forEach(function(a) {{
    var id = a.getAttribute('href').slice(1);
    var el = document.getElementById(id);
    if (el) sections.push({{ el: el, a: a }});
  }});
  function onScroll() {{
    var top = window.scrollY + 100;
    var active = null;
    sections.forEach(function(s) {{
      if (s.el.offsetTop <= top) active = s.a;
    }});
    links.forEach(function(a) {{ a.classList.remove('active'); }});
    if (active) active.classList.add('active');
  }}
  window.addEventListener('scroll', onScroll);
  onScroll();
  // 平滑滚动
  links.forEach(function(a) {{
    a.addEventListener('click', function(e) {{
      e.preventDefault();
      var id = a.getAttribute('href').slice(1);
      var el = document.getElementById(id);
      if (el) el.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
    }});
  }});
}})();

// ============ 1. K线图 ============
(function(){{
  var chart = echarts.init(document.getElementById('chart-kline'), 'dark');
  var raw = {KLINE_DATA};
  var dates = raw.map(function(d){{return d[0]}});
  var prices = raw.map(function(d){{return d.slice(1,5)}});
  var volumes = raw.map(function(d){{return d[5]}});
  var ma5 = raw.map(function(d){{return d[6]||'-'}});
  var ma20 = raw.map(function(d){{return d[7]||'-'}});
  var ma60 = raw.map(function(d){{return d[8]||'-'}});
  chart.setOption({{
    tooltip: {{trigger:'axis',axisPointer:{{type:'cross'}},backgroundColor:'#1a2338',borderColor:'#2a3550',textStyle:{{color:'#e0e4ed'}}}},
    legend: {{data:['K线','MA5','MA20','MA60','成交量'],top:0,textStyle:{{color:'#8892b0'}}}},
    grid:[{{left:'8%',right:'8%',top:'40px',height:'58%'}},{{left:'8%',right:'8%',top:'75%',height:'15%'}}],
    xAxis:[
      {{type:'category',data:dates,gridIndex:0,axisLabel:{{color:'#64748b',fontSize:10,rotate:30}},axisLine:{{lineStyle:{{color:'#2a3550'}}}}}},
      {{type:'category',gridIndex:1,axisLabel:{{show:false}},axisLine:{{show:false}}}}
    ],
    yAxis:[
      {{type:'value',gridIndex:0,scale:true,splitLine:{{lineStyle:{{color:'#1e293b'}}}},axisLabel:{{color:'#64748b'}}}},
      {{type:'value',gridIndex:1,splitLine:{{show:false}},axisLabel:{{color:'#64748b'}}}}
    ],
    dataZoom:[{{type:'inside',xAxisIndex:[0,1],start:Math.max(0,{KH_START}),end:100}}],
    series:[
      {{name:'K线',type:'candlestick',xAxisIndex:0,yAxisIndex:0,data:prices,itemStyle:{{color:'#ef4444',color0:'#22c55e',borderColor:'#ef4444',borderColor0:'#22c55e'}}}},
      {{name:'MA5',type:'line',xAxisIndex:0,yAxisIndex:0,data:ma5,smooth:true,symbol:'none',lineStyle:{{width:1,color:'#f59e0b'}}}},
      {{name:'MA20',type:'line',xAxisIndex:0,yAxisIndex:0,data:ma20,smooth:true,symbol:'none',lineStyle:{{width:1,color:'#3b82f6'}}}},
      {{name:'MA60',type:'line',xAxisIndex:0,yAxisIndex:0,data:ma60,smooth:true,symbol:'none',lineStyle:{{width:1,color:'#8b5cf6'}}}},
      {{name:'成交量',type:'bar',xAxisIndex:1,yAxisIndex:1,data:volumes.map(function(v,i){{return [i,v,prices[i][0]>=prices[i][3]?1:-1]}}),encode:{{x:0,y:1}},itemStyle:{{color:function(p){{return p.data[2]>=0?'#ef444480':'#22c55e80'}}}}}}
    ]}});
  window.addEventListener('resize',function(){{chart.resize()}});
  window.__charts = window.__charts || []; window.__charts.push(chart);
}})();

// ============ 2. 营收 & 净利润 ============
(function(){{
  var chart = echarts.init(document.getElementById('chart-revenue'),'dark');
  var data = {REVENUE_DATA};
  chart.setOption({{
    tooltip:{{trigger:'axis',backgroundColor:'#1a2338',borderColor:'#2a3550',textStyle:{{color:'#e0e4ed'}}}},
    legend:{{data:['营收','净利润'],textStyle:{{color:'#8892b0'}}}},
    grid:{{left:'10%',right:'8%',top:'15%',bottom:'12%'}},
    xAxis:{{type:'category',data:data.labels,axisLabel:{{color:'#64748b',rotate:20}},axisLine:{{lineStyle:{{color:'#2a3550'}}}}}},
    yAxis:[{{type:'value',name:'营收(亿)',nameTextStyle:{{color:'#8892b0'}},splitLine:{{lineStyle:{{color:'#1e293b'}}}},axisLabel:{{color:'#64748b'}}}},{{type:'value',name:'净利(亿)',nameTextStyle:{{color:'#8892b0'}},splitLine:{{show:false}},axisLabel:{{color:'#64748b'}}}}],
    series:[
      {{name:'营收',type:'bar',data:data.revenue,itemStyle:{{color:'#3b82f6'}},barWidth:'30%'}},
      {{name:'净利润',type:'line',yAxisIndex:1,data:data.profit,smooth:true,symbol:'circle',lineStyle:{{width:2,color:'#f59e0b'}},itemStyle:{{color:'#f59e0b'}}}}
    ]}});
  window.addEventListener('resize',function(){{chart.resize()}});
  window.__charts.push(chart);
}})();

// ============ 3. 毛利率 & 净利率 ============
(function(){{
  var chart = echarts.init(document.getElementById('chart-margin'),'dark');
  var data = {MARGIN_DATA};
  chart.setOption({{
    tooltip:{{trigger:'axis',backgroundColor:'#1a2338',borderColor:'#2a3550',textStyle:{{color:'#e0e4ed'}},valueFormatter:function(v){{return v.toFixed(1)+'%'}}}},
    legend:{{data:['毛利率','净利率'],textStyle:{{color:'#8892b0'}}}},
    grid:{{left:'10%',right:'8%',top:'15%',bottom:'12%'}},
    xAxis:{{type:'category',data:data.labels,axisLabel:{{color:'#64748b',rotate:20}},axisLine:{{lineStyle:{{color:'#2a3550'}}}}}},
    yAxis:{{type:'value',name:'%',axisLabel:{{formatter:'{{value}}%',color:'#64748b'}},splitLine:{{lineStyle:{{color:'#1e293b'}}}}}},
    series:[
      {{name:'毛利率',type:'line',data:data.gross,smooth:true,symbol:'diamond',lineStyle:{{width:2,color:'#3b82f6'}},itemStyle:{{color:'#3b82f6'}},areaStyle:{{color:'rgba(59,130,246,0.1)'}}}},
      {{name:'净利率',type:'line',data:data.net,smooth:true,symbol:'circle',lineStyle:{{width:2,color:'#22c55e'}},itemStyle:{{color:'#22c55e'}},areaStyle:{{color:'rgba(34,197,94,0.1)'}}}}
    ]}});
  window.addEventListener('resize',function(){{chart.resize()}});
  window.__charts.push(chart);
}})();

// ============ 4. 估值走势 ============
(function(){{
  var chart = echarts.init(document.getElementById('chart-valuation'),'dark');
  var data = {VALUATION_DATA};
  chart.setOption({{
    tooltip:{{trigger:'axis',backgroundColor:'#1a2338',borderColor:'#2a3550',textStyle:{{color:'#e0e4ed'}}}},
    legend:{{data:['PE-TTM','PB'],top:0,textStyle:{{color:'#8892b0'}}}},
    grid:{{left:'10%',right:'8%',top:'15%',bottom:'12%'}},
    xAxis:{{type:'category',data:data.dates,axisLabel:{{color:'#64748b',fontSize:10,rotate:30}},axisLine:{{lineStyle:{{color:'#2a3550'}}}}}},
    yAxis:[{{type:'value',name:'PE',nameTextStyle:{{color:'#8892b0'}},splitLine:{{lineStyle:{{color:'#1e293b'}}}},axisLabel:{{color:'#64748b'}}}},{{type:'value',name:'PB',nameTextStyle:{{color:'#8892b0'}},splitLine:{{show:false}},axisLabel:{{color:'#64748b'}}}}],
    series:[
      {{name:'PE-TTM',type:'line',data:data.pe,smooth:true,symbol:'none',lineStyle:{{width:2,color:'#ef4444'}},areaStyle:{{color:'rgba(239,68,68,0.08)'}}}},
      {{name:'PB',type:'line',yAxisIndex:1,data:data.pb,smooth:true,symbol:'none',lineStyle:{{width:2,color:'#3b82f6'}},areaStyle:{{color:'rgba(59,130,246,0.08)'}}}}
    ]}});
  window.addEventListener('resize',function(){{chart.resize()}});
  window.__charts.push(chart);
}})();

// ============ 5. 评分雷达图 ============
(function(){{
  var chart = echarts.init(document.getElementById('chart-radar'),'dark');
  var data = {RADAR_DATA};
  chart.setOption({{
    tooltip:{{backgroundColor:'#1a2338',borderColor:'#2a3550',textStyle:{{color:'#e0e4ed'}}}},
    radar:{{indicator:data.indicators,radius:'60%',axisName:{{color:'#8892b0'}},splitArea:{{areaStyle:{{color:['rgba(59,130,246,0.02)','rgba(59,130,246,0.04)','rgba(59,130,246,0.06)','rgba(59,130,246,0.08)','rgba(59,130,246,0.1)']}}}},axisLine:{{lineStyle:{{color:'#2a3550'}}}}}},
    series:[{{type:'radar',data:[{{value:data.values,name:'质量评分',areaStyle:{{color:'rgba(59,130,246,0.3)'}},lineStyle:{{color:'#3b82f6',width:2}},itemStyle:{{color:'#60a5fa'}}}}]}}]
  }});
  window.addEventListener('resize',function(){{chart.resize()}});
  window.__charts.push(chart);
}})();

// ============ 6. 主营构成 ============
(function(){{
  var chart = echarts.init(document.getElementById('chart-revenue-bd'),'dark');
  var data = {REVENUE_BREAKDOWN};
  chart.setOption({{
    tooltip:{{trigger:'item',backgroundColor:'#1a2338',borderColor:'#2a3550',textStyle:{{color:'#e0e4ed'}},formatter:'{{b}}: {{c}}%'}},
    series:[{{type:'pie',radius:['35%','60%'],center:['50%','55%'],data:data,label:{{color:'#8892b0',formatter:'{{b}}\n{{d}}%'}},labelLine:{{lineStyle:{{color:'#2a3550'}}}},itemStyle:{{borderRadius:6,color:['#3b82f6','#22c55e','#f59e0b','#ef4444','#8b5cf6','#ec4899']}}}}]
  }});
  window.addEventListener('resize',function(){{chart.resize()}});
  window.__charts.push(chart);
}})();

// ============ 7. 资金流向 ============
(function(){{
  var chart = echarts.init(document.getElementById('chart-moneyflow'),'dark');
  var data = {MONEYFLOW_DATA};
  chart.setOption({{
    tooltip:{{trigger:'axis',backgroundColor:'#1a2338',borderColor:'#2a3550',textStyle:{{color:'#e0e4ed'}}}},
    legend:{{data:['主力净流入','超大单','大单'],textStyle:{{color:'#8892b0'}}}},
    grid:{{left:'10%',right:'8%',top:'12%',bottom:'14%'}},
    xAxis:{{type:'category',data:data.dates,axisLabel:{{color:'#64748b',rotate:20}},axisLine:{{lineStyle:{{color:'#2a3550'}}}}}},
    yAxis:{{type:'value',name:'净额(万)',nameTextStyle:{{color:'#8892b0'}},splitLine:{{lineStyle:{{color:'#1e293b'}}}},axisLabel:{{color:'#64748b'}}}},
    series:[
      {{name:'主力净流入',type:'bar',data:data.mainForce,itemStyle:{{color:function(p){{return p.value>=0?'#ef4444':'#22c55e'}}}}}},
      {{name:'超大单',type:'line',data:data.super,smooth:true,symbol:'none',lineStyle:{{width:1,color:'#f59e0b'}}}},
      {{name:'大单',type:'line',data:data.big,smooth:true,symbol:'none',lineStyle:{{width:1,color:'#8b5cf6'}}}}
    ]}});
  window.addEventListener('resize',function(){{chart.resize()}});
  window.__charts.push(chart);
}})();
</script>
</body>
</html>"""


# ──────────────────── 数据提取 + 渲染 ────────────────────


def load_data(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def fmt_num(v, suffix="") -> str:
    if v is None or v == "" or v == "—":
        return "—"
    v = float(v)
    if abs(v) >= 1e8:
        return f"{v/1e8:.2f}亿{suffix}"
    if abs(v) >= 1e4:
        return f"{v/1e4:.2f}万{suffix}"
    return f"{v:.2f}{suffix}"


def fmt_pct(v, digits=2) -> str:
    if v is None or v == "" or v == "—":
        return "—"
    v = float(v)
    return f"{v:.{digits}f}%"


def fmt_date(ts: str | None) -> str:
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
        return self.b.get(key, default) if default is not None else self.b.get(key)

    def stock_name(self):
        return self.spot.get("名称", self.bs_info.get("code_name", "—"))

    def stock_code(self):
        code = self.bs_info.get("code", self.spot.get("代码", ""))
        return code.replace("sh.", "").replace("sz.", "")

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
            price = float(self.spot.get("最新价", 0))
            shares = float(self.total_shares())
            return fmt_num(price * shares * 1e8)
        except:
            return "—"

    def kline_series(self, max_days=365):
        kline = self._get("kline_daily", [])
        filtered = [k for k in kline if str(k.get("adjustflag", "")) == "2"]
        if not filtered:
            filtered = kline[-max_days:]
        filtered = filtered[-max_days:]
        result = []
        for k in filtered:
            try:
                o, h, l, c = float(k["open"]), float(k["high"]), float(k["low"]), float(k["close"])
                v = float(k.get("volume", 0))
                ma5 = k.get("ma5") or k.get("MA5") or ""
                ma20 = k.get("ma20") or k.get("MA20") or ""
                ma60 = k.get("ma60") or k.get("MA60") or ""
                result.append([k["date"], o, h, l, c, v,
                               float(ma5) if ma5 else "-",
                               float(ma20) if ma20 else "-",
                               float(ma60) if ma60 else "-"])
            except:
                continue
        return result

    def last_pe_pb(self):
        kline = self._get("kline_daily", [])
        for k in reversed(kline):
            pe, pb = k.get("peTTM"), k.get("pbMRQ")
            if pe and pb and pe != "" and pb != "":
                try:
                    return float(pe), float(pb)
                except:
                    pass
        return None, None

    def valuation_series(self, max_days=365):
        kline = self._get("kline_daily", [])
        filtered = [k for k in kline if k.get("peTTM") and k.get("pbMRQ") and
                    str(k.get("peTTM", "")) != "" and str(k.get("pbMRQ", "")) != ""]
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

    def financial_data(self):
        indicator = self._get("fin_bs", {}).get("ak_indicator", []) or self._get("fin_merged", {}).get("ak_indicator", [])
        labels, revs, profits, gross, net_m = [], [], [], [], []
        for row in indicator[-5:]:
            try:
                labels.append(row["报告期"][:7] if row.get("报告期") else "—")
                revs.append(float(str(row.get("营业总收入", "0")).replace("亿", "")))
                profits.append(float(str(row.get("净利润", "0")).replace("亿", "")))
                gross.append(float(str(row.get("销售毛利率", "0%")).replace("%", "")))
                net_m.append(float(str(row.get("销售净利率", "0%")).replace("%", "")))
            except:
                continue
        return {"labels": labels, "revenue": revs, "profit": profits, "gross": gross, "net": net_m}

    def key_metrics(self):
        indicator = self._get("fin_bs", {}).get("ak_indicator", []) or self._get("fin_merged", {}).get("ak_indicator", [])
        if not indicator:
            return {}
        latest = indicator[-1]
        result = {}
        try:
            result["毛利率"] = latest.get("销售毛利率", "—")
            result["净利率"] = latest.get("销售净利率", "—")
            result["ROE"] = latest.get("净资产收益率", "—")
            result["资产负债率"] = latest.get("资产负债率", "—")
        except:
            pass
        return result

    def last_year_growth(self):
        indicator = self._get("fin_bs", {}).get("ak_indicator", []) or self._get("fin_merged", {}).get("ak_indicator", [])
        if indicator:
            try:
                return indicator[-1].get("营业总收入同比增长率", "—"), indicator[-1].get("净利润同比增长率", "—")
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
        eps_summary = forecast.get("eps_summary", [])
        for item in eps_summary:
            if item.get("年度") == 2026:
                avg = item.get("均值", "—")
                if isinstance(avg, (int, float)):
                    # 数据源中均值可能=净利润(亿), 需转为EPS
                    # 尝试从净利润预测推算
                    consensus = forecast.get("consensus", [])
                    for c in consensus:
                        if c.get("预测指标") == "净利润(元)":
                            np = c.get("预测2026（平均）", "—")
                            if isinstance(np, (int, float)):
                                shares = float(self.total_shares())
                                if shares and shares > 0:
                                    return f"{np/1e8/shares:.2f}"
                            break
                    return f"{avg:.2f}"
                return str(avg)
        research = self._get("research", [])
        if research:
            try:
                eps = research[0].get("2026-盈利预测-收益", "—")
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
        count = str(eps_summary[0].get("预测机构数", "0")) if eps_summary else "0"
        rev_map, np_map, rev_g_map, np_g_map = {}, {}, {}, {}
        for item in consensus:
            key = item.get("预测指标", "")
            for yr in [2023, 2024, 2025, 2026, 2027, 2028]:
                yr_key = f"预测{yr}（平均）" if yr > 2025 else f"{yr}（实际值）"
                val = item.get(yr_key, "—")
                if "营业收入" == key and "增长" not in key:
                    rev_map[yr] = val
                elif "净利润" == key and "增长" not in key and "率" not in key:
                    np_map[yr] = val
                elif "营业收入增长率" == key:
                    rev_g_map[yr] = val
                elif "净利润增长率" == key:
                    np_g_map[yr] = val

        # EPS: 从净利润/股本计算
        eps_map = {}
        shares = float(self.total_shares())
        for yr in [2025, 2026, 2027]:
            np_v = np_map.get(yr)
            if isinstance(np_v, (int, float)) and shares > 0:
                eps_map[yr] = np_v / 1e8 / shares
            else:
                eps_map[yr] = None

        cur_price = float(self.spot.get("最新价", 0)) if self.spot.get("最新价") else 0

        rows = ""
        for yr in [2025, 2026, 2027]:
            label = f"{yr}E" if yr > 2025 else f"{yr}A"
            rev = rev_map.get(yr, "—")
            rev_g = rev_g_map.get(yr, "—")
            np_ = np_map.get(yr, "—")
            np_g = np_g_map.get(yr, "—")
            eps = eps_map.get(yr)
            eps_str = f"{eps:.2f}" if eps else "—"
            pe_str = f"{cur_price/eps:.1f}x" if eps and cur_price else "—"
            rev_str = str(rev) if isinstance(rev, str) else f"{float(rev)/1e8:.2f}亿" if isinstance(rev, (int, float)) and abs(rev) > 1e6 else str(rev)
            np_str = str(np_) if isinstance(np_, str) else f"{float(np_)/1e8:.2f}亿" if isinstance(np_, (int, float)) and abs(np_) > 1e6 else str(np_)
            rows += f"<tr><td>{label}</td><td>{rev_str}</td><td>{rev_g}</td><td>{np_str}</td><td>{np_g}</td><td>{eps_str}</td><td>{pe_str}</td></tr>\n"
        return rows, count

    def shareholder_rows(self):
        top10 = self._get("top10", [])
        rows = ""
        for i, sh in enumerate(top10[:10], 1):
            name = str(sh.get("股东名称", "—"))[:24]
            pct = sh.get("占总股本持股比例", "—")
            change = sh.get("增减", "—")
            if change not in ("不变", "新进", "—"):
                try:
                    change = f"{float(change):.1f}%"
                except:
                    pass
            rows += f"<tr><td>{i}</td><td>{name}</td><td>{pct}%</td><td>{change}</td></tr>\n"
        return rows

    def moneyflow_data(self):
        flow = self._get("fund_flow", [])[-5:]
        dates, main_f, super_f, big_f = [], [], [], []
        for f in flow:
            dates.append(fmt_date(f.get("日期", "")))
            try:
                main = float(f.get("主力净流入-净额", 0)) / 1e4
                sup = float(f.get("超大单净流入-净额", 0)) / 1e4
                big = float(f.get("大单净流入-净额", 0)) / 1e4
            except:
                main = sup = big = 0
            main_f.append(main)
            super_f.append(sup)
            big_f.append(big)
        return {"dates": dates, "mainForce": main_f, "super": super_f, "big": big_f}

    def revenue_breakdown(self):
        zygc = self._get("zygc", [])
        if not zygc:
            return []
        dates = set(r["报告日期"] for r in zygc)
        latest_date = max(dates) if dates else ""
        items = [r for r in zygc if r["报告日期"] == latest_date and r["主营构成"] and
                 r["主营构成"] not in ("半导体集成电路芯片的生产和研发",)]
        seen, result = set(), []
        for item in items:
            name = item["主营构成"]
            if name in seen:
                continue
            seen.add(name)
            if any(kw in name for kw in ("境内", "境外", "内部", "全部地区")):
                continue
            try:
                ratio = float(str(item.get("收入比例", "0")).replace("%", ""))
                result.append({"name": name, "value": ratio * 100})
            except:
                result.append({"name": name, "value": 0})
        if not result:
            seen2 = set()
            for item in items:
                name = item["主营构成"]
                if name in seen2:
                    continue
                seen2.add(name)
                if any(kw in name for kw in ("境内", "境外")):
                    try:
                        ratio = float(str(item.get("收入比例", "0")).replace("%", ""))
                        result.append({"name": name, "value": ratio * 100})
                    except:
                        pass
        return result[:6]

    def scores(self):
        metrics = self.key_metrics()
        try:
            gp = float(str(metrics.get("毛利率", "0%")).replace("%", ""))
        except:
            gp = 0
        try:
            np = float(str(metrics.get("净利率", "0%")).replace("%", ""))
        except:
            np = 0
        try:
            roe = float(str(metrics.get("ROE", "0%")).replace("%", ""))
        except:
            roe = 0
        _, rev_yoy = self.last_year_growth()
        try:
            rev_yoy_v = float(str(rev_yoy).replace("%", ""))
        except:
            rev_yoy_v = 0
        try:
            debt = float(str(metrics.get("资产负债率", "100%")).replace("%", ""))
            health = min(100, max(0, 100 - debt))
        except:
            health = 50
        pe, _ = self.last_pe_pb()
        if pe and pe > 0:
            val_score = 80 if pe < 30 else (60 if pe < 50 else (40 if pe < 80 else 25))
        else:
            val_score = 50
        pos_score = 85 if gp >= 40 else (65 if gp >= 30 else (45 if gp >= 20 else 30))
        if np >= 20:
            profit_score = 80
        elif np >= 15:
            profit_score = 65
        elif np >= 10:
            profit_score = 50
        else:
            profit_score = 30

        scores = {
            "盈利能力": {"value": min(100, max(0, int(gp))), "desc": f"毛利率{gp:.1f}%"},
            "成长性": {"value": min(100, max(0, int(abs(rev_yoy_v) * 2))), "desc": f"营收增{rev_yoy}"},
            "财务健康": {"value": min(100, max(0, int(health))), "desc": f"负债率{debt:.1f}%"},
            "估值合理": {"value": val_score, "desc": f"PE {pe if pe else '—'}x"},
            "产业地位": {"value": min(100, pos_score), "desc": f"毛利率{gp:.1f}%"},
        }
        radar = {"indicators": [{"name": k, "max": 100} for k in scores],
                 "values": [v["value"] for v in scores.values()]}
        items_html = ""
        for k, v in scores.items():
            val = v["value"]
            letter = "A" if val >= 80 else ("B" if val >= 60 else ("C" if val >= 40 else ("D" if val >= 20 else "E")))
            items_html += f'<div class="score-item"><div class="score-label">{k}</div><div class="score-value score-{letter}">{letter}</div><div class="score-desc">{v["desc"]}</div></div>\n'
        return items_html, radar

    def chain_svg(self):
        name = self.stock_name()
        sector = self.sector()
        if "半导" in sector:
            return f'''
<rect x="80" y="40" width="140" height="50" rx="10" fill="#1a2338" stroke="#2a3550" stroke-width="1"/>
<text x="150" y="58" text-anchor="middle" fill="#8892b0" font-size="11">上游</text>
<text x="150" y="76" text-anchor="middle" fill="#e0e4ed" font-size="13">晶圆代工</text>
<text x="225" y="68" fill="#475569" font-size="20">→</text>
<rect x="250" y="35" width="180" height="60" rx="10" fill="#1e3a5f" stroke="#3b82f6" stroke-width="2"/>
<text x="340" y="53" text-anchor="middle" fill="#60a5fa" font-size="11">★ 中游</text>
<text x="340" y="73" text-anchor="middle" fill="#e0e4ed" font-size="13" font-weight="600">{name[:12]}</text>
<text x="340" y="88" text-anchor="middle" fill="#8892b0" font-size="10">芯片设计</text>
<text x="435" y="68" fill="#475569" font-size="20">→</text>
<rect x="460" y="40" width="140" height="50" rx="10" fill="#1a2338" stroke="#2a3550" stroke-width="1"/>
<text x="530" y="58" text-anchor="middle" fill="#8892b0" font-size="11">下游</text>
<text x="530" y="76" text-anchor="middle" fill="#e0e4ed" font-size="13">终端品牌/OEM</text>'''
        return f'''
<rect x="250" y="35" width="180" height="60" rx="10" fill="#1e3a5f" stroke="#3b82f6" stroke-width="2"/>
<text x="340" y="58" text-anchor="middle" fill="#60a5fa" font-size="11">★ {name[:16]}</text>
<text x="340" y="78" text-anchor="middle" fill="#e0e4ed" font-size="13">{sector[:20]}</text>'''

    def research_items(self, max_n=5):
        research = self._get("research", [])
        items = ""
        for r in research[:max_n]:
            title = (r.get("报告名称", "") or "")[:50]
            org = r.get("机构", "—")
            rating = r.get("东财评级", "—")
            date = fmt_date(r.get("日期", ""))
            items += f'<div class="report-item"><div><div class="r-title">{title}</div><div class="r-meta">{org} ｜ {date}</div></div><div class="r-rating">★ {rating}</div></div>\n'
        if not items:
            items = '<div style="color:var(--text3);padding:16px;text-align:center;">暂无近期研报</div>'
        return items

    def conclusion(self):
        pe, _ = self.last_pe_pb()
        if pe and pe <= 30:
            return "估值偏低，ROE较高，安全边际充裕，适合中长线布局"
        elif pe and pe <= 50:
            return "估值合理，关注业绩拐点，等待确定性信号"
        else:
            return "估值偏高，已反映乐观预期，需业绩超预期验证才能支撑当前定价"

    def rating_letter(self):
        pe, _ = self.last_pe_pb()
        metrics = self.key_metrics()
        try:
            roe = float(str(metrics.get("ROE", "0%")).replace("%", ""))
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
        if "半导" in sector:
            tags.append("半导体")
        if "电气" in sector:
            tags.append("电力设备")
        if "IOT" in name.upper() or "软件" in sector or "信息" in name:
            tags.append("AIoT")
        if "能源" in sector or "光伏" in sector or "风" in sector:
            tags.append("新能源")
        tags.append("科创板")
        pe, _ = self.last_pe_pb()
        if pe and pe <= 30:
            tags.append("低估值")
        elif pe and pe >= 60:
            tags.append("高估值")
        metrics = self.key_metrics()
        try:
            gp = float(str(metrics.get("毛利率", "0%")).replace("%", ""))
            tags.append("高毛利" if gp >= 40 else ("中毛利" if gp >= 20 else "低毛利"))
        except:
            pass
        return "".join(f'<span class="tag-pill">{t}</span>' for t in tags[:8])

    def news_html(self):
        news = self._get("news", [])
        if not news:
            return ""
        html = '<div style="margin-top:14px;"><strong style="color:var(--text2);font-size:13px;">最新资讯</strong></div>'
        for n in news[:3]:
            title = (n.get("新闻标题", "") or "")[:60]
            source = n.get("文章来源", "网络")
            html += f'<div class="news-item">{title}<div class="n-source">{source}</div></div>\n'
        return html

    def scenarios(self, cur_price=None):
        if cur_price is None:
            try:
                cur_price = float(self.spot.get("最新价", 0))
            except:
                cur_price = 100
        # 从一致预期获取参考
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
                    np_2026e = None
                break
        shares = float(self.total_shares())
        if np_2026e and shares > 0:
            eps_base = np_2026e / shares  # np_2026e is in 亿
        else:
            eps_base = 1.0

        pe, _ = self.last_pe_pb()
        pe = pe or 30

        def scenario(mult, label):
            eps = eps_base * mult
            # reasonable PE varies
            if pe < 30:
                opt_pe, base_pe, cons_pe = 35, 28, 20
            elif pe < 50:
                opt_pe, base_pe, cons_pe = pe * 1.15, pe * 0.85, pe * 0.6
            else:
                opt_pe, base_pe, cons_pe = pe * 0.8, pe * 0.6, pe * 0.4
            return opt_pe, base_pe, cons_pe

        # 乐观: 1.2x consensus EPS, 合理PE
        opt_pe, base_pe, cons_pe = scenario(1.2, "乐观")
        s_opt = {"price": round(eps_base * 1.2 * opt_pe, 1), "ret": round(eps_base * 1.2 * opt_pe / cur_price * 100 - 100, 1),
                 "desc": "业绩超预期+估值合理"}
        s_base = {"price": round(eps_base * 1.0 * base_pe, 1), "ret": round(eps_base * 1.0 * base_pe / cur_price * 100 - 100, 1),
                  "desc": "符合预期+估值中性"}
        s_cons = {"price": round(eps_base * 0.8 * cons_pe, 1), "ret": round(eps_base * 0.8 * cons_pe / cur_price * 100 - 100, 1),
                  "desc": "业绩miss+估值收缩"}
        return s_opt, s_base, s_cons

    def risk_items(self):
        pe, _ = self.last_pe_pb()
        items = []
        if pe and pe >= 60:
            items.append(("high", f"PE高达{pe:.0f}x，远高于行业均值，杀估值风险大"))
        if pe and pe <= 20:
            items.append(("low", f"PE仅{pe:.0f}x，估值已充分反映悲观预期"))
        try:
            debt = float(str(self.key_metrics().get("资产负债率", "0%")).replace("%", ""))
            if debt >= 50:
                items.append(("mid", f"资产负债率{debt:.0f}%，杠杆偏高，利率上行承压"))
        except:
            pass
        items.append(("low", "跌破止损位应严格执行减仓/清仓"))
        if len(items) < 3:
            items.append(("mid", "跟踪中报业绩，验证全年预期"))
        return items

    def biz_desc(self):
        zygc = self._get("zygc", [])
        if zygc:
            dates = set(r["报告日期"] for r in zygc)
            latest = max(dates) if dates else ""
            top = [r for r in zygc if r["报告日期"] == latest and r.get("收入比例")]
            parts = []
            for r in top[:4]:
                name = r["主营构成"]
                if any(kw in name for kw in ("境内", "境外", "内部", "全部地区", "其他")):
                    continue
                try:
                    pct = float(str(r.get("收入比例", "0")).replace("%", "")) * 100
                    parts.append(f"{name}({pct:.0f}%)")
                except:
                    parts.append(name)
            if parts:
                return "、".join(parts[:3]) + "等"
        return "—"


def build_report(data_path: str) -> str:
    data = load_data(data_path)
    rb = ReportBuilder(data)

    stock_name = rb.stock_name()
    stock_code = rb.stock_code()
    ipo_date = rb.ipo_date()
    sector = rb.sector()
    total_shares = rb.total_shares()
    price_str = rb.price()
    change_pct = rb.change_pct()
    change_amt = rb.change_amt()
    change_cls = "up" if float(change_pct) >= 0 else "down"
    mcap = rb.market_cap()

    pe_ttm, pb_mrq = rb.last_pe_pb()
    fin = rb.financial_data()
    rev_yoy, prof_yoy = rb.last_year_growth()
    metrics = rb.key_metrics()

    revenue_str = f"{fin['revenue'][-1]:.2f}亿" if fin.get("revenue") and len(fin["revenue"]) > 0 else "—"
    profit_str = f"{fin['profit'][-1]:.2f}亿" if fin.get("profit") and len(fin["profit"]) > 0 else "—"
    gp_str = metrics.get("毛利率", "—")
    np_str = metrics.get("净利率", "—")
    roe_str = metrics.get("ROE", "—")
    debt_str = metrics.get("资产负债率", "—")
    eps_ttm_str = rb.eps_ttm()
    eps_con_str = rb.eps_consensus()

    cur_price = float(price_str) if price_str != "—" else 0
    pe_fwd = f"{cur_price/float(eps_con_str):.1f}" if eps_con_str != "—" and cur_price else "—"

    # K线
    kline_data = rb.kline_series(365)
    kline_json = json.dumps(kline_data)
    kh_start = max(0, 100 - min(120, len(kline_data)//3)) if kline_data else 0

    val_data = rb.valuation_series(365)
    val_json = json.dumps(val_data)

    rev_json = json.dumps({"labels": fin["labels"], "revenue": fin["revenue"], "profit": fin["profit"]})
    margin_json = json.dumps({"labels": fin["labels"], "gross": fin["gross"], "net": fin["net"]})

    score_items, radar_data = rb.scores()
    radar_json = json.dumps(radar_data)

    chain_svg = rb.chain_svg()

    rev_breakdown = rb.revenue_breakdown()
    rev_bd_json = json.dumps(rev_breakdown)

    consensus_rows, consensus_count = rb.consensus_table()
    sh_rows = rb.shareholder_rows()
    mf_data = rb.moneyflow_data()
    mf_json = json.dumps(mf_data)
    research_items = rb.research_items()
    conclusion = rb.conclusion()
    rating = rb.rating_letter()
    tags_html = rb.tags()
    news_html = rb.news_html()
    biz_desc = rb.biz_desc()

    s_opt, s_base, s_cons = rb.scenarios(cur_price)
    risk_list = rb.risk_items()
    risk_items_html = ""
    for level, text in risk_list:
        risk_items_html += f'<li><span class="risk-signal risk-{level}"></span>{text}</li>\n'

    report_date = dt.datetime.now().strftime("%Y-%m-%d %H:%M")

    html = HTML_TEMPLATE.format(
        STOCK_NAME=stock_name, STOCK_CODE=stock_code,
        STOCK_SECTOR=sector, IPO_DATE=ipo_date,
        TOTAL_SHARES=total_shares, MARKET_CAP=mcap,
        PRICE=price_str, CHANGE_PCT=change_pct,
        CHANGE_AMT=change_amt, CHANGE_CLS=change_cls,
        REPORT_DATE=report_date,
        PE_TTM=f"{pe_ttm:.1f}x" if pe_ttm else "—",
        PE_FWD=pe_fwd,
        PB_MRQ=f"{pb_mrq:.2f}" if pb_mrq else "—",
        REVENUE=revenue_str, REVENUE_YOY=str(rev_yoy),
        NET_PROFIT=profit_str, PROFIT_YOY=str(prof_yoy),
        GROSS_MARGIN=str(gp_str), NET_MARGIN=str(np_str),
        ROE=str(roe_str), DEBT_RATIO=str(debt_str),
        EPS_TTM=eps_ttm_str, EPS_CONSENSUS=eps_con_str,
        KLINE_DATA=kline_json, KH_START=kh_start,
        REVENUE_DATA=rev_json, MARGIN_DATA=margin_json,
        VALUATION_DATA=val_json,
        SCORE_ITEMS=score_items, RADAR_DATA=radar_json,
        CHAIN_SVG=chain_svg,
        REVENUE_BREAKDOWN=rev_bd_json,
        CONSENSUS_ROWS=consensus_rows, CONSENSUS_COUNT=consensus_count,
        SHAREHOLDER_ROWS=sh_rows,
        MONEYFLOW_DATA=mf_json,
        RESEARCH_ITEMS=research_items,
        CONCLUSION=conclusion, RATING_LETTER=rating,
        TAGS_HTML=tags_html, NEWS_HTML=news_html, BIZ_DESC=biz_desc,
        S_OPT_PRICE=s_opt["price"], S_OPT_RET=s_opt["ret"], S_OPT_DESC=s_opt["desc"],
        S_BASE_PRICE=s_base["price"], S_BASE_RET=s_base["ret"], S_BASE_DESC=s_base["desc"],
        S_CONS_PRICE=s_cons["price"], S_CONS_RET=s_cons["ret"], S_CONS_DESC=s_cons["desc"],
        RISK_ITEMS=risk_items_html,
    )
    return html


def main():
    parser = argparse.ArgumentParser(description="Phase 3：HTML 可视化报告生成器（完整版）")
    parser.add_argument("json_path", nargs="?", default="", help="Phase 1 JSON 数据文件路径")
    parser.add_argument("-o", "--output", default="", help="输出 HTML 文件路径")
    args = parser.parse_args()

    json_path = args.json_path
    if not json_path:
        output_dir = os.path.join(os.path.dirname(__file__), "output")
        if os.path.isdir(output_dir):
            jsons = sorted([f for f in os.listdir(output_dir) if f.endswith(".json")])
            if jsons:
                json_path = os.path.join(output_dir, jsons[-1])
                print(f"📂 自动选择最新数据文件: {json_path}")

    if not json_path or not os.path.isfile(json_path):
        print("❌ 请指定 JSON 数据文件路径")
        sys.exit(1)

    print(f"📊 正在生成 HTML 报告...")
    html = build_report(json_path)

    if args.output:
        out_path = args.output
    else:
        base = os.path.basename(json_path)
        code_part = base.split("_")[1] if "_" in base else "unknown"
        code_part = code_part.replace(".json", "").replace("_ths", "")
        try:
            with open(json_path) as f:
                d = json.load(f)
            rb = ReportBuilder(d)
            name = rb.stock_name()
        except:
            name = f"股票_{code_part}"
        out_dir = os.path.join(os.path.dirname(__file__), "output")
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, f"个股研究-{name}.html")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"✅ HTML 报告已生成: {out_path} ({os.path.getsize(out_path)/1024:.1f} KB)")

    qq_dir = "/root/.openclaw/media/qqbot"
    if os.path.isdir(qq_dir):
        qq_path = os.path.join(qq_dir, f"个股研究-{name}.html")
        with open(qq_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"✅ 已同步到 QQ 媒体目录: {qq_path}")


if __name__ == "__main__":
    main()
