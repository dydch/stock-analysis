#!/usr/bin/env python3
"""
stock_html_inject_ai.py — 后置注入 [AI] 内容到 HTML 报告

用法：
    python3 stock_html_inject_ai.py <html_path> --content-file <json_or_txt>

单独替换：
    python3 stock_html_inject_ai.py <html_path> --s1 "内容" --s2 "内容" ...
"""

import re, sys, json, os

def inject_section(html: str, placeholder: str, content: str) -> str:
    """Replace first occurrence of placeholder with content inside a div."""
    if not content:
        return html
    return html.replace(placeholder, content, 1)

def build_s1_html(economy: str, industry: str, policy: str) -> str:
    return f"""
    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;">
        <div class="card" style="border-left:3px solid var(--hl);">
            <div style="color:var(--hl);font-size:11px;font-weight:600;">📌 经济阶段</div>
            <div style="font-size:13px;margin-top:6px;">{economy}</div>
        </div>
        <div class="card" style="border-left:3px solid var(--down);">
            <div style="color:var(--down);font-size:11px;font-weight:600;">🏭 行业周期</div>
            <div style="font-size:13px;margin-top:6px;">{industry}</div>
        </div>
        <div class="card" style="border-left:3px solid var(--orange);">
            <div style="color:var(--orange);font-size:11px;font-weight:600;">📜 政策方向</div>
            <div style="font-size:13px;margin-top:6px;">{policy}</div>
        </div>
    </div>"""

def build_s2_html(competition: str, advantage: str) -> str:
    return f"""
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:14px;">
        <div class="card">
            <div style="color:var(--down);font-size:11px;font-weight:600;">🏆 竞争格局</div>
            <div style="font-size:13px;margin-top:4px;">{competition}</div>
        </div>
        <div class="card">
            <div style="color:var(--hl);font-size:11px;font-weight:600;">🎯 核心竞争优势</div>
            <div style="font-size:13px;margin-top:4px;">{advantage}</div>
        </div>
    </div>"""

PLACEHOLDER_AI = "AI分析师将在此补充分析..."

def main():
    if len(sys.argv) < 2:
        print("用法: python3 stock_html_inject_ai.py <html_path> [--s1 ...] [--s2 ...]")
        sys.exit(1)

    html_path = sys.argv[1]
    if not os.path.exists(html_path):
        print(f"❌ 文件不存在: {html_path}")
        sys.exit(1)

    # 支持从内容文件读取
    content = {}
    args = sys.argv[2:]
    i = 0
    while i < len(args):
        if args[i].startswith("--s") and len(args[i]) in (3,4):
            key = args[i][2:]  # "1", "2", "7", "8"
            i += 1
            val = args[i] if i < len(args) else ""
            content[key] = val
        elif args[i] == "--content-file":
            i += 1
            if i < len(args):
                with open(args[i], 'r') as f:
                    content.update(json.load(f))
        i += 1

    with open(html_path, 'r', encoding='utf-8') as f:
        html = f.read()

    # S1 - 宏观周期
    if '1' in content:
        parts = content['1'].split('||')
        if len(parts) >= 3:
            s1_html = build_s1_html(parts[0], parts[1], parts[2])
        else:
            s1_html = f'<div style="font-size:13px;">{content["1"]}</div>'
        html = html.replace(PLACEHOLDER_AI, s1_html, 1)

    # S2 - 产业链
    if '2' in content:
        parts = content['2'].split('||')
        if len(parts) >= 2:
            s2_html = build_s2_html(parts[0], parts[1])
        else:
            s2_html = f'<div style="font-size:13px;">{content["2"]}</div>'
        html = html.replace(PLACEHOLDER_AI, s2_html, 1)

    # S7/S8 - 直接替换剩余占位符
    for section in ['7', '8']:
        if section in content:
            html = inject_section(html, PLACEHOLDER_AI, 
                f'<div style="font-size:13px;">{content[section]}</div>')

    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"✅ [AI] 内容已注入: {html_path}")

if __name__ == "__main__":
    main()
