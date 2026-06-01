#!/usr/bin/env python3
"""
Phase 3：HTML 可视化报告生成器
==============================
读取 Phase 1 采集的 JSON 数据，生成可交互的 HTML 可视化报告。

用法
  python stock_html_report.py output/data_600519.json    # 指定数据文件
  python stock_html_report.py output/data_688099_ths.json # 支持三源版 _ths 后缀

输出
  output/个股研究-{股票名称}.html — 可视化报告（单文件，可直接浏览器打开）
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
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  background: #0a0e17; color: #e0e4ed; line-height: 1.6;
}}
.container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}

/* ── Header ── */
.header {{
  background: linear-gradient(135deg, #141b2d 0%, #1a2338 100%);
  border-radius: 16px; padding: 32px 40px; margin-bottom: 24px;
  border: 1px solid #2a3550;
  display: flex; justify-content: space-between; align-items: center;
  flex-wrap: wrap; gap: 16px;
}}
.header-left h1 {{ font-size: 28px; font-weight: 700; color: #fff; }}
.header-left h1 span {{ color: #60a5fa; }}
.header-left .subtitle {{ color: #8892b0; font-size: 14px; margin-top: 4px; }}
.header-right {{ text-align: right; }}
.header-right .price {{ font-size: 36px; font-weight: 700; color: #fff; }}
.header-right .change {{ font-size: 16px; }}
.header-right .change.up {{ color: #ef4444; }}
.header-right .change.down {{ color: #22c55e; }}
.header-right .date {{ color: #8892b0; font-size: 13px; margin-top: 2px; }}

/* ── 指标卡片 ── */
.card-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 16px; margin-bottom: 24px; }}
.card {{
  background: #141b2d; border-radius: 12px; padding: 20px;
  border: 1px solid #2a3550; transition: border-color 0.2s;
}}
.card:hover {{ border-color: #3b82f6; }}
.card .label {{ color: #8892b0; font-size: 13px; margin-bottom: 4px; }}
.card .value {{ font-size: 22px; font-weight: 600; color: #fff; }}
.card .sub {{ color: #64748b; font-size: 12px; margin-top: 2px; }}
.card .highlight {{ color: #f59e0b; }}

/* ── Section ── */
.section {{
  background: #141b2d; border-radius: 16px; padding: 24px;
  margin-bottom: 24px; border: 1px solid #2a3550;
}}
.section h2 {{
  font-size: 18px; font-weight: 600; color: #fff;
  margin-bottom: 20px; padding-bottom: 12px;
  border-bottom: 1px solid #2a3550;
  display: flex; align-items: center; gap: 8px;
}}
.section h2 .badge {{
  display: inline-block; background: #3b82f6; color: #fff;
  font-size: 11px; padding: 2px 8px; border-radius: 4px;
  font-weight: 500; margin-left: 8px;
}}
.chart-box {{ width: 100%; height: 420px; margin-bottom: 8px; }}
.chart-box.tall {{ height: 500px; }}

/* ── 财务表格 ── */
.table-wrap {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
th, td {{ padding: 10px 12px; text-align: right; white-space: nowrap; }}
th {{ background: #1a2338; color: #8892b0; font-weight: 500; font-size: 12px; }}
td {{ border-bottom: 1px solid #1e293b; }}
tr:hover td {{ background: #1a2338; }}
td:first-child, th:first-child {{ text-align: left; }}
.positive {{ color: #ef4444; }}
.negative {{ color: #22c55e; }}
.neutral {{ color: #f59e0b; }}

/* ── 评分系统 ── */
.score-row {{ display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 16px; }}
.score-item {{
  flex: 1; min-width: 140px; background: #1a2338;
  border-radius: 8px; padding: 16px; text-align: center;
}}
.score-item .score-label {{ color: #8892b0; font-size: 12px; }}
.score-item .score-value {{ font-size: 28px; font-weight: 700; margin: 4px 0; }}
.score-item .score-desc {{ font-size: 11px; color: #64748b; }}
.score-A {{ color: #22c55e; }} .score-B {{ color: #60a5fa; }}
.score-C {{ color: #f59e0b; }} .score-D {{ color: #ef4444; }}
.score-E {{ color: #ef4444; }}

/* ── 产业链 ── */
.industry-chain {{
  display: flex; align-items: center; justify-content: center;
  gap: 8px; flex-wrap: wrap; padding: 20px 0;
}}
.chain-node {{
  background: #1a2338; border: 1px solid #2a3550;
  border-radius: 10px; padding: 12px 20px; text-align: center;
  min-width: 100px;
}}
.chain-node .node-label {{ color: #8892b0; font-size: 11px; }}
.chain-node .node-value {{ color: #e0e4ed; font-size: 13px; font-weight: 500; margin-top: 2px; }}
.chain-node.active {{ border-color: #3b82f6; background: #1e3a5f; }}
.chain-node.active .node-label {{ color: #60a5fa; }}
.chain-arrow {{ color: #475569; font-size: 20px; }}

/* ── 研报 ── */
.report-item {{
  padding: 12px 16px; border-bottom: 1px solid #1e293b;
  display: flex; justify-content: space-between; align-items: center;
}}
.report-item:last-child {{ border-bottom: none; }}
.report-item .report-title {{ color: #e0e4ed; font-size: 14px; }}
.report-item .report-org {{ color: #60a5fa; font-size: 12px; }}
.report-item .report-rating {{ color: #22c55e; font-weight: 600; font-size: 12px; }}
.report-item .report-date {{ color: #64748b; font-size: 11px; }}

/* ── 底部 ── */
.footer {{
  text-align: center; color: #475569; font-size: 12px;
  padding: 24px; border-top: 1px solid #1e293b; margin-top: 40px;
}}

@media (max-width: 768px) {{
  .header {{ flex-direction: column; text-align: center; }}
  .header-right {{ text-align: center; }}
  .card-grid {{ grid-template-columns: 1fr 1fr; }}
  .score-row {{ flex-direction: column; }}
}}
</style>
</head>
<body>
<div class="container">

<!-- ==================== HEADER ==================== -->
<div class="header">
  <div class="header-left">
    <h1>{STOCK_NAME} <span>({STOCK_CODE})</span></h1>
    <div class="subtitle">
      {STOCK_SECTOR} ｜ 上市日期: {IPO_DATE} ｜ 总股本: {TOTAL_SHARES} 亿
    </div>
  </div>
  <div class="header-right">
    <div class="price">{PRICE}</div>
    <div class="change {CHANGE_CLS}">{CHANGE_PCT}%  ({CHANGE_AMT})</div>
    <div class="date">{REPORT_DATE}</div>
  </div>
</div>

<!-- ==================== 指标卡片 ==================== -->
<div class="card-grid">
  <div class="card">
    <div class="label">市值</div>
    <div class="value">{MARKET_CAP}</div>
  </div>
  <div class="card">
    <div class="label">PE-TTM</div>
    <div class="value">{PE_TTM}</div>
    <div class="sub">{PE_YQ}</div>
  </div>
  <div class="card">
    <div class="label">PB</div>
    <div class="value">{PB_MRQ}</div>
  </div>
  <div class="card">
    <div class="label">营收(最近年度)</div>
    <div class="value">{REVENUE}</div>
    <div class="sub">同比 {REVENUE_YOY}</div>
  </div>
  <div class="card">
    <div class="label">净利润(最近年度)</div>
    <div class="value">{NET_PROFIT}</div>
    <div class="sub">同比 {PROFIT_YOY}</div>
  </div>
  <div class="card">
    <div class="label">毛利率 / 净利率</div>
    <div class="value" style="font-size:18px">{GROSS_MARGIN} / {NET_MARGIN}</div>
    <div class="sub">ROE: {ROE}</div>
  </div>
  <div class="card">
    <div class="label">资产负债率</div>
    <div class="value">{DEBT_RATIO}</div>
  </div>
  <div class="card">
    <div class="label">EPS-TTM / 一致预期2026E</div>
    <div class="value" style="font-size:18px">{EPS_TTM} / {EPS_CONSENSUS}</div>
  </div>
</div>

<!-- ==================== 1. K线图 ==================== -->
<div class="section">
  <h2>📈 K线走势 <span class="badge">含MA5/20/60均线</span></h2>
  <div id="chart-kline" class="chart-box tall"></div>
</div>

<!-- ==================== 2. 财务趋势 ==================== -->
<div class="section">
  <h2>📊 财务趋势</h2>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;">
    <div>
      <div style="color:#8892b0;font-size:13px;margin-bottom:8px;">营收 & 净利润</div>
      <div id="chart-revenue" class="chart-box" style="height:300px;"></div>
    </div>
    <div>
      <div style="color:#8892b0;font-size:13px;margin-bottom:8px;">毛利率 & 净利率</div>
      <div id="chart-margin" class="chart-box" style="height:300px;"></div>
    </div>
  </div>
</div>

<!-- ==================== 3. 估值走势 ==================== -->
<div class="section">
  <h2>🔍 估值走势</h2>
  <div id="chart-valuation" class="chart-box tall"></div>
</div>

<!-- ==================== 4. 评分系统 ==================== -->
<div class="section">
  <h2>⭐ 五维度质量评分</h2>
  <div class="score-row">{SCORE_ITEMS}</div>
  <div id="chart-radar" class="chart-box" style="height:340px;"></div>
</div>

<!-- ==================== 5. 产业链定位 ==================== -->
<div class="section">
  <h2>🔗 产业链定位</h2>
  <div class="industry-chain">{CHAIN_HTML}</div>
</div>

<!-- ==================== 6. 主营构成 ==================== -->
<div class="section">
  <h2>📦 主营构成</h2>
  <div id="chart-revenue-breakdown" class="chart-box" style="height:300px;"></div>
</div>

<!-- ==================== 7. 机构一致预期 ==================== -->
<div class="section">
  <h2>📋 机构一致预期 (共{CONSENSUS_COUNT}家)</h2>
  <div class="table-wrap">
    <table>
      <thead><tr><th>年度</th><th>营收预测</th><th>营收增长率</th><th>净利润预测</th><th>净利润增长率</th><th>EPS</th><th>对应PE</th><th>PE估值区间</th></tr></thead>
      <tbody>{CONSENSUS_ROWS}</tbody>
    </table>
  </div>
</div>

<!-- ==================== 8. 十大股东 ==================== -->
<div class="section">
  <h2>🏛️ 十大股东</h2>
  <div class="table-wrap">
    <table>
      <thead><tr><th>名次</th><th>股东名称</th><th>持股比例</th><th>变动</th></tr></thead>
      <tbody>{SHAREHOLDER_ROWS}</tbody>
    </table>
  </div>
</div>

<!-- ==================== 9. 资金流向(近5日) ==================== -->
<div class="section">
  <h2>💰 资金流向 <span class="badge">近5日</span></h2>
  <div id="chart-moneyflow" class="chart-box" style="height:300px;"></div>
</div>

<!-- ==================== 10. 近期研报 ==================== -->
<div class="section">
  <h2>📰 近期研报</h2>
  <div>{RESEARCH_ITEMS}</div>
</div>

<!-- ==================== Footer ==================== -->
<div class="footer">
  数据来源：BaoStock / akshare / 同花顺(thsdk) / 腾讯行情<br>
  生成时间：{REPORT_DATE}<br>
  ⚠️ 本报告基于公开数据生成，不构成投资建议
</div>

</div><!-- /container -->

<script>
// ============ 1. K线图 ============
(function() {{
  var chart = echarts.init(document.getElementById('chart-kline'), 'dark');
  var klineData = {KLINE_DATA};
  var dates = klineData.map(function(d) {{ return d[0]; }});
  var prices = klineData.map(function(d) {{ return d.slice(1,5); }});
  var volumes = klineData.map(function(d) {{ return d[5]; }});
  var ma5 = klineData.map(function(d) {{ return d[6] || '-'; }});
  var ma20 = klineData.map(function(d) {{ return d[7] || '-'; }});
  var ma60 = klineData.map(function(d) {{ return d[8] || '-'; }});

  var option = {{
    tooltip: {{ trigger: 'axis', axisPointer: {{ type: 'cross' }}, backgroundColor: '#1a2338', borderColor: '#2a3550', textStyle: {{ color: '#e0e4ed' }} }},
    legend: {{ data: ['K线', 'MA5', 'MA20', 'MA60', '成交量'], top: 0, textStyle: {{ color: '#8892b0' }} }},
    grid: [{{ left: '8%', right: '8%', top: '40px', height: '58%' }}, {{ left: '8%', right: '8%', top: '75%', height: '15%' }}],
    xAxis: [
      {{ type: 'category', data: dates, gridIndex: 0, axisLabel: {{ color: '#64748b', fontSize: 10, rotate: 30 }}, axisLine: {{ lineStyle: {{ color: '#2a3550' }} }} }},
      {{ type: 'category', gridIndex: 1, axisLabel: {{ show: false }}, axisLine: {{ show: false }} }}
    ],
    yAxis: [
      {{ type: 'value', gridIndex: 0, scale: true, splitLine: {{ lineStyle: {{ color: '#1e293b' }} }}, axisLabel: {{ color: '#64748b' }} }},
      {{ type: 'value', gridIndex: 1, splitLine: {{ show: false }}, axisLabel: {{ color: '#64748b' }} }}
    ],
    dataZoom: [{{ type: 'inside', xAxisIndex: [0,1], start: Math.max(0, {KH_START}), end: 100 }}],
    series: [
      {{
        name: 'K线', type: 'candlestick', xAxisIndex: 0, yAxisIndex: 0,
        data: prices,
        itemStyle: {{ color: '#ef4444', color0: '#22c55e', borderColor: '#ef4444', borderColor0: '#22c55e' }}
      }},
      {{ name: 'MA5', type: 'line', xAxisIndex: 0, yAxisIndex: 0, data: ma5, smooth: true, symbol: 'none', lineStyle: {{ width: 1, color: '#f59e0b' }} }},
      {{ name: 'MA20', type: 'line', xAxisIndex: 0, yAxisIndex: 0, data: ma20, smooth: true, symbol: 'none', lineStyle: {{ width: 1, color: '#3b82f6' }} }},
      {{ name: 'MA60', type: 'line', xAxisIndex: 0, yAxisIndex: 0, data: ma60, smooth: true, symbol: 'none', lineStyle: {{ width: 1, color: '#8b5cf6' }} }},
      {{
        name: '成交量', type: 'bar', xAxisIndex: 1, yAxisIndex: 1,
        data: volumes.map(function(v,i) {{ return [i, v, prices[i][0] >= prices[i][3] ? 1 : -1]; }}),
        encode: {{ x: 0, y: 1 }},
        itemStyle: {{ color: function(p) {{ return p.data[2] >= 0 ? '#ef444480' : '#22c55e80'; }} }}
      }}
    ]
  }};
  chart.setOption(option);
  window.addEventListener('resize', function() {{ chart.resize(); }});
}})();

// ============ 2. 营收 & 净利润 ============
(function() {{
  var chart = echarts.init(document.getElementById('chart-revenue'), 'dark');
  var data = {REVENUE_DATA};
  chart.setOption({{
    tooltip: {{ trigger: 'axis', backgroundColor: '#1a2338', borderColor: '#2a3550', textStyle: {{ color: '#e0e4ed' }} }},
    legend: {{ data: ['营收', '净利润'], textStyle: {{ color: '#8892b0' }} }},
    grid: {{ left: '10%', right: '8%', top: '15%', bottom: '12%' }},
    xAxis: {{ type: 'category', data: data.labels, axisLabel: {{ color: '#64748b', rotate: 20 }}, axisLine: {{ lineStyle: {{ color: '#2a3550' }} }} }},
    yAxis: [
      {{ type: 'value', name: '营收(亿)', nameTextStyle: {{ color: '#8892b0' }}, splitLine: {{ lineStyle: {{ color: '#1e293b' }} }}, axisLabel: {{ color: '#64748b' }} }},
      {{ type: 'value', name: '净利润(亿)', nameTextStyle: {{ color: '#8892b0' }}, splitLine: {{ show: false }}, axisLabel: {{ color: '#64748b' }} }}
    ],
    series: [
      {{ name: '营收', type: 'bar', data: data.revenue, itemStyle: {{ color: '#3b82f6' }}, barWidth: '30%' }},
      {{ name: '净利润', type: 'line', yAxisIndex: 1, data: data.profit, smooth: true, symbol: 'circle', lineStyle: {{ width: 2, color: '#f59e0b' }}, itemStyle: {{ color: '#f59e0b' }} }}
    ]
  }});
  window.addEventListener('resize', function() {{ chart.resize(); }});
}})();

// ============ 3. 毛利率 & 净利率 ============
(function() {{
  var chart = echarts.init(document.getElementById('chart-margin'), 'dark');
  var data = {MARGIN_DATA};
  chart.setOption({{
    tooltip: {{ trigger: 'axis', backgroundColor: '#1a2338', borderColor: '#2a3550', textStyle: {{ color: '#e0e4ed' }}, valueFormatter: function(v) {{ return v.toFixed(1) + '%'; }} }},
    legend: {{ data: ['毛利率', '净利率'], textStyle: {{ color: '#8892b0' }} }},
    grid: {{ left: '10%', right: '8%', top: '15%', bottom: '12%' }},
    xAxis: {{ type: 'category', data: data.labels, axisLabel: {{ color: '#64748b', rotate: 20 }}, axisLine: {{ lineStyle: {{ color: '#2a3550' }} }} }},
    yAxis: {{ type: 'value', name: '%', axisLabel: {{ formatter: '{{value}}%', color: '#64748b' }}, splitLine: {{ lineStyle: {{ color: '#1e293b' }} }} }},
    series: [
      {{ name: '毛利率', type: 'line', data: data.gross, smooth: true, symbol: 'diamond', lineStyle: {{ width: 2, color: '#3b82f6' }}, itemStyle: {{ color: '#3b82f6' }}, areaStyle: {{ color: 'rgba(59,130,246,0.1)' }} }},
      {{ name: '净利率', type: 'line', data: data.net, smooth: true, symbol: 'circle', lineStyle: {{ width: 2, color: '#22c55e' }}, itemStyle: {{ color: '#22c55e' }}, areaStyle: {{ color: 'rgba(34,197,94,0.1)' }} }}
    ]
  }});
  window.addEventListener('resize', function() {{ chart.resize(); }});
}})();

// ============ 4. 估值走势 ============
(function() {{
  var chart = echarts.init(document.getElementById('chart-valuation'), 'dark');
  var data = {VALUATION_DATA};
  chart.setOption({{
    tooltip: {{ trigger: 'axis', backgroundColor: '#1a2338', borderColor: '#2a3550', textStyle: {{ color: '#e0e4ed' }} }},
    legend: {{ data: ['PE-TTM', 'PB'], top: 0, textStyle: {{ color: '#8892b0' }} }},
    grid: {{ left: '10%', right: '8%', top: '15%', bottom: '12%' }},
    xAxis: {{ type: 'category', data: data.dates, axisLabel: {{ color: '#64748b', fontSize: 10, rotate: 30 }}, axisLine: {{ lineStyle: {{ color: '#2a3550' }} }} }},
    yAxis: [
      {{ type: 'value', name: 'PE', nameTextStyle: {{ color: '#8892b0' }}, splitLine: {{ lineStyle: {{ color: '#1e293b' }} }}, axisLabel: {{ color: '#64748b' }} }},
      {{ type: 'value', name: 'PB', nameTextStyle: {{ color: '#8892b0' }}, splitLine: {{ show: false }}, axisLabel: {{ color: '#64748b' }} }}
    ],
    series: [
      {{ name: 'PE-TTM', type: 'line', data: data.pe, smooth: true, symbol: 'none', lineStyle: {{ width: 2, color: '#ef4444' }}, areaStyle: {{ color: 'rgba(239,68,68,0.08)' }} }},
      {{ name: 'PB', type: 'line', yAxisIndex: 1, data: data.pb, smooth: true, symbol: 'none', lineStyle: {{ width: 2, color: '#3b82f6' }}, areaStyle: {{ color: 'rgba(59,130,246,0.08)' }} }}
    ]
  }});
  window.addEventListener('resize', function() {{ chart.resize(); }});
}})();

// ============ 5. 评分雷达图 ============
(function() {{
  var chart = echarts.init(document.getElementById('chart-radar'), 'dark');
  var data = {RADAR_DATA};
  chart.setOption({{
    tooltip: {{ backgroundColor: '#1a2338', borderColor: '#2a3550', textStyle: {{ color: '#e0e4ed' }} }},
    radar: {{
      indicator: data.indicators,
      radius: '65%',
      axisName: {{ color: '#8892b0' }},
      splitArea: {{ areaStyle: {{ color: ['rgba(59,130,246,0.02)', 'rgba(59,130,246,0.04)', 'rgba(59,130,246,0.06)', 'rgba(59,130,246,0.08)', 'rgba(59,130,246,0.1)'] }} }},
      axisLine: {{ lineStyle: {{ color: '#2a3550' }} }}
    }},
    series: [{{
      type: 'radar',
      data: [{{
        value: data.values,
        name: '质量评分',
        areaStyle: {{ color: 'rgba(59,130,246,0.3)' }},
        lineStyle: {{ color: '#3b82f6', width: 2 }},
        itemStyle: {{ color: '#60a5fa' }}
      }}]
    }}]
  }});
  window.addEventListener('resize', function() {{ chart.resize(); }});
}})();

// ============ 6. 主营构成 ============
(function() {{
  var chart = echarts.init(document.getElementById('chart-revenue-breakdown'), 'dark');
  var data = {REVENUE_BREAKDOWN};
  chart.setOption({{
    tooltip: {{ trigger: 'item', backgroundColor: '#1a2338', borderColor: '#2a3550', textStyle: {{ color: '#e0e4ed' }}, formatter: '{{b}}: {{c}} ({{d}}%)' }},
    series: [{{
      type: 'pie', radius: ['30%', '60%'],
      center: ['50%', '55%'],
      data: data,
      label: {{ color: '#8892b0', formatter: '{{b}}\n{{d}}%' }},
      labelLine: {{ lineStyle: {{ color: '#2a3550' }} }},
      itemStyle: {{
        borderRadius: 6,
        color: ['#3b82f6', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899']
      }}
    }}]
  }});
  window.addEventListener('resize', function() {{ chart.resize(); }});
}})();

// ============ 7. 资金流向 ============
(function() {{
  var chart = echarts.init(document.getElementById('chart-moneyflow'), 'dark');
  var data = {MONEYFLOW_DATA};
  chart.setOption({{
    tooltip: {{ trigger: 'axis', backgroundColor: '#1a2338', borderColor: '#2a3550', textStyle: {{ color: '#e0e4ed' }} }},
    legend: {{ data: ['主力净流入', '超大单', '大单'], textStyle: {{ color: '#8892b0' }} }},
    grid: {{ left: '10%', right: '8%', top: '12%', bottom: '12%' }},
    xAxis: {{ type: 'category', data: data.dates, axisLabel: {{ color: '#64748b', rotate: 20 }}, axisLine: {{ lineStyle: {{ color: '#2a3550' }} }} }},
    yAxis: {{ type: 'value', name: '净额(万)', nameTextStyle: {{ color: '#8892b0' }}, splitLine: {{ lineStyle: {{ color: '#1e293b' }} }}, axisLabel: {{ color: '#64748b' }} }},
    series: [
      {{ name: '主力净流入', type: 'bar', data: data.mainForce, itemStyle: {{ color: function(p) {{ return p.value >= 0 ? '#ef4444' : '#22c55e'; }} }} }},
      {{ name: '超大单', type: 'line', data: data.super, smooth: true, symbol: 'none', lineStyle: {{ width: 1, color: '#f59e0b' }} }},
      {{ name: '大单', type: 'line', data: data.big, smooth: true, symbol: 'none', lineStyle: {{ width: 1, color: '#8b5cf6' }} }}
    ]
  }});
  window.addEventListener('resize', function() {{ chart.resize(); }});
}})();
</script>
</body>
</html>"""


# ──────────────────── 数据提取 + 渲染 ────────────────────


def load_data(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def safe(v: Any, fmt: str = None) -> str:
    if v is None:
        return "—"
    if fmt and isinstance(v, (int, float)):
        return fmt.format(v)
    return str(v)


def fmt_num(v, suffix="") -> str:
    if v is None or v == "" or v == "—":
        return "—"
    v = float(v)
    if abs(v) >= 1e8:
        return f"{v/1e8:.2f}亿{suffix}"
    if abs(v) >= 1e4:
        return f"{v/1e4:.2f}万{suffix}"
    return f"{v:.2f}{suffix}"


def fmt_pct(v: float | str | None, digits: int = 2) -> str:
    if v is None or v == "" or v == "—":
        return "—"
    v = float(v)
    return f"{v:.{digits}f}%"


def fmt_date(ts: str | None) -> str:
    """'2026-06-01' or '20260601' → '2026-06-01'"""
    if not ts:
        return "—"
    ts = str(ts).replace("T00:00:00.000", "").replace("T00:00:00", "")
    if len(ts) == 8 and ts.isdigit():
        return f"{ts[:4]}-{ts[4:6]}-{ts[6:]}"
    return ts[:10] if len(ts) >= 10 else ts


# ──────────── 提取关键数据 ────────────


class ReportBuilder:
    def __init__(self, data: dict):
        self.d = data
        self.b = data.get("blocks", data)
        self.spot = self._get("spot", [{}])[0]
        self.bs_info = self._get("basic_info_bs", [{}])[0]

    def _get(self, key: str, default=None):
        return self.b.get(key, default) if default is not None else self.b.get(key)

    # ── 基础信息 ──
    def stock_name(self) -> str:
        return self.spot.get("名称", self.bs_info.get("code_name", "—"))

    def stock_code(self) -> str:
        code = self.bs_info.get("code", self.spot.get("代码", ""))
        return code.replace("sh.", "").replace("sz.", "")

    def ipo_date(self) -> str:
        return self.bs_info.get("ipoDate", "—")

    def sector(self) -> str:
        # try to get from akshare basic info
        bi = self._get("basic_info", [{}])[0] or self._get("basic_info_ak", [{}])[0]
        return bi.get("行业分类(证监会)", "—")

    def total_shares(self) -> str:
        profit = self._get("fin_bs", {}).get("bs_profit", [])
        if profit:
            try:
                ts = float(profit[-1].get("totalShare", 0))
                return f"{ts/1e8:.2f}"
            except:
                pass
        return "—"

    # ── 行情 ──
    def price(self) -> str:
        return f"{self.spot.get('最新价', '—'):.2f}" if isinstance(self.spot.get('最新价'), (int, float)) else str(self.spot.get('最新价', '—'))

    def change_pct(self) -> str:
        v = self.spot.get("涨跌幅", 0)
        return f"{v:.2f}" if isinstance(v, (int, float)) else str(v)

    def change_amt(self) -> str:
        v = self.spot.get("涨跌额", 0)
        return f"{v:.2f}" if isinstance(v, (int, float)) else str(v)

    # ── K线(前复权) ──
    def kline_series(self, max_days: int = 365) -> list:
        kline = self._get("kline_daily", [])
        # 优先前复权(adjustflag=2)
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

    # ── PE/PB ──
    def last_pe_pb(self):
        kline = self._get("kline_daily", [])
        for k in reversed(kline):
            pe = k.get("peTTM")
            pb = k.get("pbMRQ")
            if pe and pe != "" and pb and pb != "":
                try:
                    return float(pe), float(pb)
                except:
                    pass
        return None, None

    # ── 估值序列 ──
    def valuation_series(self, max_days: int = 365) -> dict:
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

    # ── 财务指标 ──
    def financial_data(self) -> dict:
        """从同花顺关键指标提取最近4期财务数据"""
        indicator = self._get("fin_bs", {}).get("ak_indicator", [])
        if not indicator:
            indicator = self._get("fin_merged", {}).get("ak_indicator", [])
        if not indicator:
            # fallback: use fin_abstract or baostock profit
            pass

        labels, revs, profits, gross, net_m = [], [], [], [], []
        for row in indicator[-5:]:
            try:
                labels.append(row["报告期"][:7] if row.get("报告期") else "—")
                rev = float(str(row.get("营业总收入", "0")).replace("亿", ""))
                revs.append(rev)
                np_ = float(str(row.get("净利润", "0")).replace("亿", ""))
                profits.append(np_)
                gm = float(str(row.get("销售毛利率", "0%")).replace("%", ""))
                gross.append(gm)
                nm = float(str(row.get("销售净利率", "0%")).replace("%", ""))
                net_m.append(nm)
            except:
                continue

        return {
            "labels": labels,
            "revenue": revs,
            "profit": profits,
            "gross": gross,
            "net": net_m,
        }

    def key_metrics(self) -> dict:
        """最近一期关键指标"""
        indicator = self._get("fin_bs", {}).get("ak_indicator", [])
        if not indicator:
            indicator = self._get("fin_merged", {}).get("ak_indicator", [])
        if not indicator:
            return {}
        latest = indicator[-1]
        result = {}
        try:
            result["毛利率"] = latest.get("销售毛利率", "—")
            result["净利率"] = latest.get("销售净利率", "—")
            result["ROE"] = latest.get("净资产收益率", "—")
            result["资产负债率"] = latest.get("资产负债率", "—")
            result["每股净资产"] = latest.get("每股净资产", "—")
            result["每股经营现金流"] = latest.get("每股经营现金流", "—")
        except:
            pass
        return result

    # ── 营收 & 利润同比 ──
    def last_year_growth(self) -> tuple:
        """(营收同比, 净利同比) 来自同花顺最新指标"""
        indicator = self._get("fin_bs", {}).get("ak_indicator", [])
        if not indicator:
            indicator = self._get("fin_merged", {}).get("ak_indicator", [])
        if indicator:
            try:
                rev_yoy = indicator[-1].get("营业总收入同比增长率", "—")
                np_yoy = indicator[-1].get("净利润同比增长率", "—")
                return rev_yoy, np_yoy
            except:
                pass
        # fallback
        growth = self._get("fin_bs", {}).get("bs_growth", [])
        if growth:
            try:
                return fmt_pct(float(growth[-1].get("YOYPn", 0)) * 100), fmt_pct(
                    float(growth[-1].get("YOYNI", 0)) * 100)
            except:
                pass
        return "—", "—"

    # ── EPS ──
    def eps_ttm(self) -> str:
        profit = self._get("fin_bs", {}).get("bs_profit", [])
        if profit:
            try:
                eps = profit[-1].get("epsTTM", 0)
                return f"{float(eps):.2f}"
            except:
                pass
        return "—"

    def eps_consensus(self) -> str:
        """从同花顺一致预期获取2026E EPS"""
        ths = self._get("ths", {})
        forecast = ths.get("ths_forecast", {})
        eps_summary = forecast.get("eps_summary", [])
        for item in eps_summary:
            if item.get("年度") == 2026:
                avg = item.get("均值", "—")
                if isinstance(avg, (int, float)):
                    return f"{avg:.2f}"
                    # Note: 数据源中均值可能为净利润而非EPS，需注意
                return str(avg)
        # fallback to research report
        research = self._get("research", [])
        if research:
            try:
                eps_26 = research[0].get("2026-盈利预测-收益", "—")
                if eps_26:
                    return f"{float(eps_26):.2f}"
            except:
                pass
        return "—"

    # ── 机构一致预期表 ──
    def consensus_table(self) -> tuple:
        """返回 (rows_html, count_str)"""
        ths = self._get("ths", {})
        forecast = ths.get("ths_forecast", {})
        consensus = forecast.get("consensus", [])
        eps_summary = forecast.get("eps_summary", [])
        count = "0"
        if eps_summary:
            count = str(eps_summary[0].get("预测机构数", "0"))

        # 提取各年度数据
        rev_map, np_map, rev_g_map, np_g_map, eps_map = {}, {}, {}, {}, {}
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

        for item in eps_summary:
            yr = item.get("年度")
            avg = item.get("均值", "—")
            if isinstance(avg, (int, float)):
                eps_map[yr] = avg

        # 当前价用于算PE
        try:
            cur_price = float(self.spot.get("最新价", 0))
        except:
            cur_price = 0

        rows = ""
        for yr in [2025, 2026, 2027]:
            rev = rev_map.get(yr, "—")
            rev_g = rev_g_map.get(yr, "—")
            np_ = np_map.get(yr, "—")
            np_g = np_g_map.get(yr, "—")
            eps = eps_map.get(yr, "—")
            if isinstance(eps, (int, float)) and cur_price > 0:
                pe = cur_price / eps
                pe_str = f"{pe:.1f}x"
            else:
                pe_str = "—"
            pe_range = "—"  # could add min/max from eps_summary

            label = f"{yr}E" if yr > 2025 else f"{yr}A"
            rev_str = str(rev) if isinstance(rev, str) else f"{float(rev)/1e8:.2f}亿" if isinstance(rev, (int, float)) and abs(rev) > 1e6 else str(rev)
            np_str = str(np_) if isinstance(np_, str) else f"{float(np_)/1e8:.2f}亿" if isinstance(np_, (int, float)) and abs(np_) > 1e6 else str(np_)
            eps_str = f"{eps:.2f}" if isinstance(eps, (int, float)) else "—"
            rows += f"<tr><td>{label}</td><td>{rev_str}</td><td>{rev_g}</td><td>{np_str}</td><td>{np_g}</td><td>{eps_str}</td><td>{pe_str}</td><td>{pe_range}</td></tr>\n"

        return rows, count

    # ── 十大股东 ──
    def shareholder_rows(self) -> str:
        top10 = self._get("top10", [])
        rows = ""
        for i, sh in enumerate(top10[:10], 1):
            name = sh.get("股东名称", "—")[:24]
            pct = sh.get("占总股本持股比例", "—")
            change = sh.get("增减", "—")
            if change not in ("不变", "新进", "—"):
                try:
                    change = f"{float(change):.1f}%"
                except:
                    pass
            rows += f"<tr><td>{i}</td><td>{name}</td><td>{pct}%</td><td>{change}</td></tr>\n"
        return rows

    # ── 资金流向 ──
    def moneyflow_data(self) -> dict:
        flow = self._get("fund_flow", [])
        flow = flow[-5:]
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

    # ── 主营构成 ──
    def revenue_breakdown(self) -> list:
        zygc = self._get("zygc", [])
        if not zygc:
            return []
        dates = set(r["报告日期"] for r in zygc)
        latest_date = max(dates) if dates else ""
        items = [r for r in zygc if r["报告日期"] == latest_date and r["主营构成"] and
                 r["主营构成"] not in ("半导体集成电路芯片的生产和研发",)]
        # 去重，保留分类型为主营产品的
        seen, result = set(), []
        for item in items:
            name = item["主营构成"]
            if name in seen:
                continue
            seen.add(name)
            if any(kw in name for kw in ("境内", "境外", "内部")):
                continue  # 排除地区分类
            try:
                ratio = float(str(item.get("收入比例", "0")).replace("%", ""))
                result.append({"name": name, "value": ratio * 100})
            except:
                result.append({"name": name, "value": 0})
        if not result:
            # fallback 用地区
            for item in items:
                name = item["主营构成"]
                if name in seen:
                    continue
                seen.add(name)
                if any(kw in name for kw in ("境内", "境外")):
                    try:
                        ratio = float(str(item.get("收入比例", "0")).replace("%", ""))
                        result.append({"name": name, "value": ratio * 100})
                    except:
                        pass
        return result[:6]

    # ── 产业链 ──
    def industry_chain_html(self) -> str:
        sector = self.sector()
        name = self.stock_name()
        if "半导" in sector:
            return """
              <div class="chain-node"><div class="node-label">上游</div><div class="node-value">晶圆代工</div></div>
              <div class="chain-arrow">→</div>
              <div class="chain-node active"><div class="node-label">★ 中游</div><div class="node-value">{NAME} (芯片设计)</div></div>
              <div class="chain-arrow">→</div>
              <div class="chain-node"><div class="node-label">下游</div><div class="node-value">终端品牌/OEM</div></div>
            """.replace("{NAME}", name)
        return f"""
          <div class="chain-node active"><div class="node-label">★ 当前位置</div><div class="node-value">{name} ({sector})</div></div>
        """

    # ── 研报 ──
    def research_items(self, max_n: int = 5) -> str:
        research = self._get("research", [])
        items = ""
        for r in research[:max_n]:
            title = r.get("报告名称", "—")[:50]
            org = r.get("机构", "—")
            rating = r.get("东财评级", "—")
            date = fmt_date(r.get("日期", ""))
            items += f"""
            <div class="report-item">
              <div>
                <div class="report-title">{title}</div>
                <div class="report-org">{org} ｜ {date}</div>
              </div>
              <div class="report-rating">★ {rating}</div>
            </div>
            """
        if not items:
            items = '<div style="color:#64748b;padding:16px;text-align:center;">暂无近期研报数据</div>'
        return items

    # ── 评分系统 ──
    def scores(self) -> tuple:
        """返回 (score_items_html, radar_data_dict)"""
        # 基于财务数据动态评分
        metrics = self.key_metrics()

        # 盈利能力
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

        # 成长性 - from growth data
        _, rev_yoy = self.last_year_growth()
        try:
            rev_yoy_v = float(str(rev_yoy).replace("%", ""))
        except:
            rev_yoy_v = 0

        # 财务健康 - 负债率
        try:
            debt = float(str(metrics.get("资产负债率", "100%")).replace("%", ""))
            health = 100 - debt  # 越高越好
        except:
            health = 50

        # 估值 - 与行业PE比较
        pe, _ = self.last_pe_pb()
        if pe and pe > 0:
            if pe < 30:
                val_score = 80
            elif pe < 50:
                val_score = 60
            elif pe < 80:
                val_score = 40
            else:
                val_score = 25
        else:
            val_score = 50

        # 产业地位 - 毛利率接近或行业地位
        if gp >= 40:
            pos_score = 85
        elif gp >= 30:
            pos_score = 65
        elif gp >= 20:
            pos_score = 45
        else:
            pos_score = 30

        # 利润增长
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
            "成长性": {"value": min(100, max(0, int(rev_yoy_v * 2))), "desc": f"营收增{rev_yoy}"},
            "财务健康": {"value": min(100, max(0, int(health))), "desc": f"负债率{debt:.1f}%"},
            "估值合理": {"value": val_score, "desc": f"PE {pe if pe else '—'}x"},
            "产业地位": {"value": min(100, pos_score), "desc": f"毛利率{gp:.1f}%"},
        }

        radar = {
            "indicators": [{"name": k, "max": 100} for k in scores],
            "values": [v["value"] for v in scores.values()]
        }

        items_html = ""
        letters = list("ABCDE")
        for i, (k, v) in enumerate(scores.items()):
            val = v["value"]
            if val >= 80:
                letter = "A"
            elif val >= 60:
                letter = "B"
            elif val >= 40:
                letter = "C"
            elif val >= 20:
                letter = "D"
            else:
                letter = "E"
            items_html += f"""
            <div class="score-item">
              <div class="score-label">{k}</div>
              <div class="score-value score-{letter}">{letter}</div>
              <div class="score-desc">{v['desc']}</div>
            </div>
            """
        return items_html, radar

    # ── 市场容量估算 ──
    def market_cap(self) -> str:
        try:
            price = float(self.spot.get("最新价", 0))
            shares = float(self.total_shares())
            return fmt_num(price * shares * 1e8)
        except:
            return "—"


def build_report(data_path: str) -> str:
    data = load_data(data_path)
    rb = ReportBuilder(data)

    # 提取所有数据
    stock_name = rb.stock_name()
    stock_code = rb.stock_code()
    ipo_date = rb.ipo_date()
    sector = rb.sector()
    total_shares = rb.total_shares()
    price_str = rb.price()
    change_pct = rb.change_pct()
    change_amt = rb.change_amt()
    change_cls = "up" if float(change_pct) >= 0 else "down"

    pe_ttm, pb_mrq = rb.last_pe_pb()
    mcap = rb.market_cap()

    fin = rb.financial_data()
    rev_yoy, prof_yoy = rb.last_year_growth()
    metrics = rb.key_metrics()

    # Format financial data for display
    revenue_str = f"{fin['revenue'][-1]:.2f}亿" if fin.get("revenue") and len(fin["revenue"]) > 0 else "—"
    profit_str = f"{fin['profit'][-1]:.2f}亿" if fin.get("profit") and len(fin["profit"]) > 0 else "—"
    gp_str = metrics.get("毛利率", "—")
    np_str = metrics.get("净利率", "—")
    roe_str = metrics.get("ROE", "—")
    debt_str = metrics.get("资产负债率", "—")
    eps_ttm_str = rb.eps_ttm()
    eps_con_str = rb.eps_consensus()

    # K线
    kline_data = rb.kline_series(365)
    kline_json = json.dumps(kline_data)
    kh_start = max(0, 100 - min(120, len(kline_data)//3)) if kline_data else 0

    # 估值序列
    val_data = rb.valuation_series(365)
    val_json = json.dumps(val_data)

    # 财务JSON
    rev_json = json.dumps({"labels": fin["labels"], "revenue": fin["revenue"], "profit": fin["profit"]})
    margin_json = json.dumps({"labels": fin["labels"], "gross": fin["gross"], "net": fin["net"]})

    # 评分
    score_items, radar_data = rb.scores()
    radar_json = json.dumps(radar_data)

    # 产业链
    chain_html = rb.industry_chain_html()

    # 主营构成
    rev_breakdown = rb.revenue_breakdown()
    rev_bd_json = json.dumps(rev_breakdown)

    # 一致预期
    consensus_rows, consensus_count = rb.consensus_table()

    # 十大股东
    sh_rows = rb.shareholder_rows()

    # 资金流向
    mf_data = rb.moneyflow_data()
    mf_json = json.dumps(mf_data)

    # 研报
    research_items = rb.research_items()

    report_date = dt.datetime.now().strftime("%Y-%m-%d %H:%M")

    # 渲染 HTML
    html = HTML_TEMPLATE.format(
        STOCK_NAME=stock_name,
        STOCK_CODE=stock_code,
        IPO_DATE=ipo_date,
        STOCK_SECTOR=sector,
        TOTAL_SHARES=total_shares,
        PRICE=price_str,
        CHANGE_PCT=change_pct,
        CHANGE_AMT=change_amt,
        CHANGE_CLS=change_cls,
        REPORT_DATE=report_date,
        MARKET_CAP=mcap,
        PE_TTM=f"{pe_ttm:.1f}x" if pe_ttm else "—",
        PE_YQ=f"{(float(rb.price())/float(eps_con_str)):.1f}x 2026E" if eps_con_str != "—" and rb.price() != "—" else "",
        PB_MRQ=f"{pb_mrq:.2f}" if pb_mrq else "—",
        REVENUE=revenue_str,
        REVENUE_YOY=str(rev_yoy),
        NET_PROFIT=profit_str,
        PROFIT_YOY=str(prof_yoy),
        GROSS_MARGIN=str(gp_str),
        NET_MARGIN=str(np_str),
        ROE=str(roe_str),
        DEBT_RATIO=str(debt_str),
        EPS_TTM=eps_ttm_str,
        EPS_CONSENSUS=eps_con_str,
        KLINE_DATA=kline_json,
        KH_START=kh_start,
        REVENUE_DATA=rev_json,
        MARGIN_DATA=margin_json,
        VALUATION_DATA=val_json,
        SCORE_ITEMS=score_items,
        RADAR_DATA=radar_json,
        CHAIN_HTML=chain_html,
        REVENUE_BREAKDOWN=rev_bd_json,
        CONSENSUS_ROWS=consensus_rows,
        CONSENSUS_COUNT=consensus_count,
        SHAREHOLDER_ROWS=sh_rows,
        MONEYFLOW_DATA=mf_json,
        RESEARCH_ITEMS=research_items,
    )
    return html


def main():
    parser = argparse.ArgumentParser(description="Phase 3：HTML 可视化报告生成器")
    parser.add_argument("json_path", nargs="?", default="", help="Phase 1 JSON 数据文件路径")
    parser.add_argument("-o", "--output", default="", help="输出 HTML 文件路径（可选）")
    args = parser.parse_args()

    json_path = args.json_path
    if not json_path:
        # 查找最新的 JSON 文件
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

    # 确定输出文件名
    if args.output:
        out_path = args.output
    else:
        # 从 JSON 文件名推断 Stock name
        base = os.path.basename(json_path)
        code = base.split("_")[1] if "_" in base else "unknown"
        code = code.replace(".json", "").replace("_ths", "")
        # Try to read stock name from JSON
        try:
            with open(json_path) as f:
                d = json.load(f)
            rb = ReportBuilder(d)
            name = rb.stock_name()
        except:
            name = f"股票_{code}"
        out_dir = os.path.join(os.path.dirname(__file__), "output")
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, f"个股研究-{name}.html")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"✅ HTML 报告已生成: {out_path}")
    print(f"   ({os.path.getsize(out_path) / 1024:.1f} KB)")

    # 自动上传到QQ media目录
    qq_dir = "/root/.openclaw/media/qqbot"
    if os.path.isdir(qq_dir):
        qq_path = os.path.join(qq_dir, f"个股研究-{name}.html")
        with open(qq_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"✅ 已同步到 QQ 媒体目录: {qq_path}")


if __name__ == "__main__":
    main()
