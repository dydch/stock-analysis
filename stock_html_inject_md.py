#!/usr/bin/env python3
"""从 MD 分析报告注入文本内容到 HTML"""
import re, sys, os

def escape(text):
    return text.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('"','&quot;')


def extract_md_table(md, keyword):
    """从MD表格中提取键值对，如 S0 项目表"""
    section = sec(md, keyword)
    if not section:
        return {}
    kv = {}
    for line in section.split('\n'):
        m = re.match(r'\|\s*(.+?)\s*\|\s*(.+?)\s*\|', line)
        if m:
            k = m.group(1).strip()
            v = m.group(2).strip()
            kv[k] = v
    return kv


def extract_scenarios(md):
    """从S4情景分析表中提取{悲观/基准/乐观: {np, pe, target}}"""
    s4 = sec(md, 'S4')
    if not s4:
        return {}
    scenarios = {}
    for line in s4.split('\n'):
        cells = [c.strip() for c in line.split('|')[1:-1]]
        if len(cells) >= 6:
            for kw, label in [('悲观','pess'), ('基准','base'), ('乐观','opt')]:
                if kw in cells[0]:
                    scenarios[label] = {
                        'prob': cells[1].strip('%'),
                        'np': cells[2].strip(),
                        'pe': cells[3].strip().replace('x',''),
                        'target': cells[4].strip().replace('¥',''),
                        'room': cells[5].strip()
                    }
    return scenarios


def extract_stops(md):
    """从S5提取止损价"""
    stops = re.findall(r'(?:止损|跌破).*?¥(\d+\.?\d*)', md)
    return stops

def sec(md, keyword):
    """提取MD中 ## 标题包含关键词时标题下方的内容"""
    escaped = re.escape(keyword)
    pat = rf'##.*?{escaped}.*?\n(.+?)(?=\n##[^#]|\Z)'
    m = re.search(pat, md, re.DOTALL)
    if m:
        return m.group(1).strip()
    return ""

def pop_ph(html, text):
    """Replace the first occurrence of the placeholder and return updated html"""
    PH = "AI分析师将在此补充分析..."
    return html.replace(PH, escape(text), 1)

def md_inject(html, md):
    """替换 HTML 中的占位符与缺失数值为 MD 文本内容"""
    PH = "AI分析师将在此补充分析..."

    # ── 数值回退：从MD提取 → 补HTML缺失数值 ──
    def fix_numeric(html, md):
        """从MD修复HTML中缺失的数值"""
        s0 = extract_md_table(md, 'S0')  # 如 最新收盘价 ¥633.68
        scenarios = extract_scenarios(md)
        stops = extract_stops(md)
        score = re.search(r'总分[：:≤>]*\s*(\d+)/100', md)

        # 1. 修复价格: 如果HTML价格部分显示 ¥0 或空
        price_kv = s0.get('最新收盘价', '')
        price_m = re.search(r'(\d+\.?\d*)', price_kv)
        if price_m and re.search(r'¥0[^\d<]|¥$|¥N/A|股价[^\d]*N/A|暂无数据|\$N/A', html):
            html = re.sub(r'¥0[^\d<]', f'¥{price_m.group(1)}', html)
            html = re.sub(r'¥N/A', f'¥{price_m.group(1)}', html)

        # 2. 修复评分
        if score and ('/100' not in html or re.search(r'0/100|N/A/100', html)):
            html = re.sub(r'(总计|总分|得分).*?\d+/100', f'总分 {score.group(1)}/100', html, count=1)

        # 3. 修复情景目标价
        for label, data in scenarios.items():
            target = data.get('target', '')
            if not target:
                continue
            # 只在已有情景行但价格异常时修复
            pat_price = rf'{label}.*?¥(?:N/A|0[^\d])'
            if re.search(pat_price, html, re.IGNORECASE):
                html = re.sub(pat_price, f'{data.get("prob","?")}% × {data.get("np","?")} · ¥{target}', html, count=1)
            # 修复目标价单元格为 0 或 N/A
            pat_target = rf'¥\d+[^\d<].*?[-+]?[\d.]+%'
            # 简化：直接替换场景行中的 0.00 目标价
            for bad in [f'¥0.00', f'¥0.0', f'¥0', f'¥N/A']:
                html = html.replace(bad, f'¥{target}', 1)

        # 4. 修复止损价
        if stops:
            for idx, sp in enumerate(stops):
                marker = '第一止损' if idx == 0 else '硬性止损'
                pat = rf'{marker}.*?¥(?:N/A|0[^\d])'
                if re.search(pat, html):
                    html = re.sub(pat, f'{marker}：跌破¥{sp}', html, count=1)

        return html

    html = fix_numeric(html, md)

    if PH not in html:
        return html

    # ── S1 宏观周期 ──
    s1 = sec(md, "S1")
    if s1:
        blocks = re.split(r'\n{2,}', s1)
        for b in blocks:
            b = b.strip()
            if not b:
                continue
            text = re.sub(r'\*\*[^*]+\*\*[：:]*\s*', '', b).strip()
            # Only replace if we got meaningful text
            if text and '经济' in b:
                html = pop_ph(html, text)
            elif text and '行业' in b:
                html = pop_ph(html, text)
            elif text and '政策' in b:
                html = pop_ph(html, text)

    # ── S2 产业链: 竞争格局 ──
    s2 = sec(md, "S2")
    if s2:
        parts = re.split(r'\n{2,}', s2)
        landscape = ""
        for p in parts:
            stripped = p.strip()
            if '竞争格局' in stripped[:30]:
                landscape = re.sub(r'\*\*[^*]+\*\*[：:]*\s*', '', stripped).strip()
        if landscape:
            html = pop_ph(html, landscape)

    # ── S7 对标分析: 竞争优势 + 增长引擎 + 同行表 ──
    s7 = sec(md, "S7")
    if s7:
        # Split by double newline to find blocks
        blocks = re.split(r'\n{2,}', s7)
        
        # 竞争优势分析
        for b in blocks:
            stripped = b.strip()
            if '竞争优势分析' in stripped[:40]:
                t = re.sub(r'\*\*[^*]+\*\*[：:]*\s*', '', stripped).strip()
                if t:
                    html = pop_ph(html, t)
                    break
        else:
            # Fallback: 拓荆的核心竞争力
            for line in s7.split('\n'):
                stripped = line.strip()
                if '拓荆的核心竞争力' in stripped or '核心竞争力' in stripped[:50]:
                    t = re.sub(r'\*\*[^*]+\*\*[：:]*\s*', '', stripped).strip()
                    if t:
                        html = pop_ph(html, t)
                        break

        # 增长引擎判断
        for b in blocks:
            stripped = b.strip()
            if '增长引擎判断' in stripped[:40]:
                t = re.sub(r'\*\*[^*]+\*\*[：:]*\s*', '', stripped).strip()
                if t:
                    html = pop_ph(html, t)
                    break
        else:
            # Fallback: 增长引擎比较（含后续的 bullet list）
            engine_parts = []
            in_engine = False
            for line in s7.split('\n'):
                s = line.strip()
                if '增长引擎' in s[:50]:
                    in_engine = True
                    t = re.sub(r'\*\*[^*]+\*\*[：:]*\s*', '', s).strip()
                    if t and not t.startswith('增长引擎判断'):
                        engine_parts.append(t)
                elif in_engine:
                    if s.startswith('#') or s.startswith('---') or (s and s[0].isupper() and '：' in s):
                        break
                    if s:
                        engine_parts.append(re.sub(r'\*\*', '', s))
            if engine_parts:
                html = pop_ph(html, '\n'.join(engine_parts))

        # Extract growth engine comparison text from MD
        peer_engine = '—'
        engine_lines = []
        in_engine = False
        for line in s7.split('\n'):
            s = line.strip()
            if '增长引擎比较' in s[:50]:
                in_engine = True
                continue
            elif in_engine:
                if s.startswith('#') or s.startswith('---') or (s and s[0].isupper() and '：' in s):
                    break
                if s:
                    engine_lines.append(re.sub(r'\*\*', '', s).strip(' -'))
        if engine_lines:
            peer_engine = '; '.join(engine_lines)[:80]

        # 同行对比表（6列：公司, PE, ROE, 毛利率, 营收增速, 市值）
        peer_table_md = re.search(r'\|\s*标的\s*\|.*?\n\|.*?\n((?:\|.*?\n)+)', s7)
        if peer_table_md:
            rows_lines = peer_table_md.group(1).strip().split('\n')
            peer_html = ''
            for rl in rows_lines:
                cells = [c.strip().replace('**','').strip() for c in rl.split('|')[1:-1]]
                if len(cells) >= 6:
                    is_self = '拓荆' in cells[0]
                    hl = ' style="background:color-mix(in srgb, var(--hl) 8%, var(--card));border-left:3px solid var(--hl);font-weight:600"' if is_self else ''
                    # MD cols: [标的, PE, 营收CAGR, 毛利率, ROE, 市值]
                    # HTML: [公司, PE, ROE, 毛利率, 营收增速, 市值]
                    row = f'<tr{hl}><td>{escape(cells[0])}</td><td>{escape(cells[1])}</td><td>{escape(cells[4])}</td><td>{escape(cells[3])}</td><td>{escape(cells[2])}</td><td>{escape(cells[5])}</td></tr>'
                    peer_html += row + '\n            '
            if peer_html:
                tbody_start = html.find('<tbody>', html.find('class="peer-table"'))
                if tbody_start >= 0:
                    tbody_end = html.find('</tbody>', tbody_start) + len('</tbody>')
                    new_tbody = f'<tbody>\n            {peer_html}</tbody>'
                    html = html[:tbody_start] + new_tbody + html[tbody_end:]

    # ── S8 跟踪计划: 复盘计划 + 综合结论 ──
    s8 = sec(md, "S8")
    if s8:
        # 复盘计划
        review_match = re.search(r'###\s*复盘计划\n(.+?)(?=\n###\s|\Z)', s8, re.DOTALL)
        if review_match:
            t = review_match.group(1).strip()
            if t:
                html = pop_ph(html, t)
        else:
            # Fallback: find all lines after "复盘计划" heading
            lines = s8.split('\n')
            review_parts = []
            in_review = False
            for line in lines:
                if '复盘计划' in line:
                    in_review = True
                    continue
                if in_review:
                    if line.startswith('#') or '综合' in line or line.startswith('---'):
                        break
                    if line.strip():
                        review_parts.append(line.strip())
            if review_parts:
                html = pop_ph(html, '\n'.join(review_parts))

        # 综合结论
        conclusion_parts = []
        in_conclusion = False
        for line in s8.split('\n'):
            if '综合结论' in line:
                in_conclusion = True
                continue
            if in_conclusion:
                if line.startswith('#') or line.startswith('---'):
                    break
                if line.strip():
                    conclusion_parts.append(line.strip().replace('**', ''))
        if conclusion_parts:
            html = pop_ph(html, '\n'.join(conclusion_parts))

    return html

if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print("用法: python stock_html_inject_md.py <html_file> [md_file]")
        sys.exit(1)
    html_path = args[0]
    if len(args) >= 2:
        md_path = args[1]
    else:
        base = os.path.splitext(html_path)[0].replace("个股研究-", "个股研究8步-")
        md_path = base + ".md"
        if not os.path.exists(md_path):
            md_path = html_path.replace(".html", ".md")

    html = open(html_path, encoding="utf-8").read()
    before = html.count("AI分析师将在此补充分析...")
    if os.path.exists(md_path):
        md = open(md_path, encoding="utf-8").read()
        html = md_inject(html, md)
        after = html.count("AI分析师将在此补充分析...")
        open(html_path, "w", encoding="utf-8").write(html)
        print(f"✅ MD注入: 占位符 {before} → {after}")
    else:
        print(f"⚠️ MD文件不存在: {md_path}")
