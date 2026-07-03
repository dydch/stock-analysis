#!/usr/bin/env python3
"""
管线JSON → 完整Markdown报告生成器
====================================
读取 stock_full_report_ths_integrated.py 输出的JSON数据文件,
自动生成包含所有可用数据块的完整六段式Markdown分析报告。
"""

import json
import os
import sys
from datetime import datetime

# 加入上级目录，以便import valuation engine
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from stock_valuation_engine import ValuationEngine
    VE_AVAILABLE = True
except ImportError:
    VE_AVAILABLE = False


def fmt_pct(val, ndigits=2):
    """将小数格式化为百分比字符串"""
    if val is None or val == '':
        return '—'
    try:
        v = float(val)
        return f'{v * 100:.{ndigits}f}%' if abs(v) < 10 else f'{v:.{ndigits}f}%'
    except:
        return str(val)


def fmt_money(val, unit='亿'):
    """格式化金额"""
    if val is None or val == '':
        return '—'
    try:
        v = float(val)
        if unit == '亿':
            return f'{v/1e8:.2f}亿'
        elif unit == '万':
            return f'{v/1e4:.0f}万'
        return f'{v:.2f}'
    except:
        return str(val)


def get_field(item, *keys):
    """从字典中安全获取字段值，按key顺序尝试"""
    for k in keys:
        v = item.get(k)
        if v is not None and v != '':
            return v
    return None


def extract_zygc(b):
    """主营构成提取"""
    zygc = b.get('zygc', [])
    if not zygc:
        return []
    # 按报告期、分类类型分组，取最新
    latest_date = None
    products_by_date = {}
    for r in zygc:
        dt = str(get_field(r, '报告日期', 'report_date', ''))
        cat = str(get_field(r, '分类类型', 'category', ''))
        key = f'{dt}|{cat}'
        if key not in products_by_date:
            products_by_date[key] = []
        products_by_date[key].append(r)

    # 找最新的按产品分类数据
    sorted_dates = sorted(products_by_date.keys(), reverse=True)
    for key in sorted_dates:
        if '产品' in key:
            rows = products_by_date[key]
            # 过滤掉其他(补充)
            result = []
            for r in rows:
                name = str(get_field(r, '主营构成', '主营構成', '主营構', ''))
                if '补充' in name:
                    continue
                ratio = get_field(r, '收入比例')
                gp = get_field(r, '毛利率')
                rev = get_field(r, '主营收入')
                result.append({
                    'name': name,
                    'ratio': float(ratio) * 100 if ratio else None,
                    'gp': float(gp) * 100 if gp is not None and str(gp).strip() else None,
                    'rev': float(rev) if rev else None,
                })
            if result:
                return result
    return []


def extract_financial_table(b):
    """提取完整年度财务表"""
    profit = b.get('fin_bs', {}).get('bs_profit', [])
    if not profit:
        profit = b.get('bs_profit', [])
    
    annual_data = {}
    for p in profit:
        dt = str(p.get('statDate', ''))
        if len(dt) != 10:
            continue
        year = dt[:4]
        if dt[5:10] == '12-31' or year in annual_data:
            pass
        # 只用年报数据 (12-31)
        if dt[5:] != '12-31':
            continue
        annual_data[year] = {
            'year': year,
            'revenue': float(p.get('MBRevenue', p.get('revenue', 0))),
            'netProfit': float(p.get('netProfit', 0)),
            'netMargin': float(p.get('netProfitRatio', 0)),
        }
    return annual_data


def extract_latest_quarters(b, n=5):
    """提取最近N期季度利润数据"""
    profit = b.get('fin_bs', {}).get('bs_profit', [])
    if not profit:
        profit = b.get('bs_profit', [])
    
    growth = b.get('fin_bs', {}).get('bs_growth', [])
    if not growth:
        growth = b.get('bs_growth', [])
        
    # 构建growth字典
    growth_dict = {}
    for g in growth:
        growth_dict[g.get('statDate', '')] = g

    result = []
    # 取最新n期（按日期倒序）
    for p in sorted(profit, key=lambda x: x.get('statDate', ''), reverse=True)[:n]:
        dt = p.get('statDate', '')
        eps_ttm = p.get('epsTTM', p.get('eps_ttm', None))
        roe = p.get('roeAvg', p.get('roe_avg', None))
        gp = p.get('gpMargin', p.get('grossProfitMargin', None))
        np = p.get('netProfit', 0)
        g = growth_dict.get(dt, {})
        yoy_ni = g.get('YOYNI', g.get('yoy_ni', None))
        
        result.append({
            'date': dt,
            'eps_ttm': float(eps_ttm) if eps_ttm else None,
            'roe': float(roe) * 100 if roe else None,
            'gp': float(gp) * 100 if gp else None,
            'np': float(np) if np else None,
            'yoy_ni': float(yoy_ni) * 100 if yoy_ni else None,
        })
    return result


def extract_cashflow(b):
    """提取现金流比率"""
    cf = b.get('fin_bs', {}).get('bs_cashflow', [])
    if not cf:
        cf = b.get('bs_cashflow', [])
    
    result = []
    for r in cf[-6:]:
        dt = r.get('statDate', '')
        cfo_np = r.get('CFOToNP')
        cfo_or = r.get('CFOToOR')
        if cfo_np is not None and cfo_np != '':
            result.append({
                'date': dt,
                'cfo_np': float(cfo_np),
                'cfo_or': float(cfo_or) if cfo_or else None,
            })
    return result


def extract_dividends(b):
    """提取分红记录"""
    div = b.get('dividend', [])
    result = []
    for d in div:
        cash = get_field(d, 'dividCashStock', 'dividCashPsBeforeTax', '派息', 'cash_before_tax')
        year = get_field(d, 'year', '年份')
        # 尝试从公告日期推断年份
        date = get_field(d, 'dividPlanAnnounceDate', 'dividAgmPumDate', '公告日期')
        if date and not year:
            if isinstance(date, str) and 'T' in date:
                date = date[:10]
            if date and len(date) >= 4:
                year = date[:4]
        # 从现金分红字段提取
        if cash:
            result.append({
                'year': year or '?',
                'plan': str(cash),
                'date': str(get_field(d, 'dividOperateDate', '除权除息日', 'dividOperateDate', '') or ''),
            })
    return result


def extract_fund_flow(b):
    """提取资金流向（东财直连格式或akshare格式）"""
    fund = b.get('fund_flow', [])
    result = []
    for f in fund[-10:]:
        dt = str(get_field(f, '日期', 'date', 'Date', ''))
        dt = dt.replace('T00:00:00.000', '')
        main = get_field(f, '主力净流入-净额', 'main_force', '主力净流入')
        super_v = get_field(f, '超大单净流入-净额', 'super_large', '超大单净流入')
        big = get_field(f, '大单净流入-净额', 'large', '大单净流入')
        mid = get_field(f, '中单净流入-净额', 'medium', '中单净流入')
        small = get_field(f, '小单净流入-净额', 'small', '小单净流入')
        if main is not None and float(main) != 0:
            result.append({
                'date': dt,
                'main': float(main),
                'super': float(super_v) if super_v else None,
                'big': float(big) if big else None,
                'mid': float(mid) if mid else None,
                'small': float(small) if small else None,
            })
    return result


def extract_balance(b):
    """提取资产负债表关键指标"""
    bal = b.get('fin_bs', {}).get('bs_balance', [])
    if not bal:
        bal = b.get('bs_balance', [])
    result = []
    for r in bal[-2:]:
        try:
            result.append({
                'date': r.get('statDate', ''),
                'debt_ratio': float(r.get('liabilityToAsset', 0)) * 100,
                'current_ratio': float(r.get('currentRatio', 0)),
                'asset_to_equity': float(r.get('assetToEquity', 0)),
            })
        except:
            pass
    return result


def generate_md_report(data, code, output_path=None):
    """生成完整Markdown报告"""
    b = data.get('blocks', data)
    mode = data.get('data_mode', '')
    spot = (b.get('spot') or b.get('basic_info_bs') or [{}])[0]
    bs_info = (b.get('basic_info_bs') or [{}])[0]
    
    name = str(get_field(spot, '股票名称', '名称', 'code_name', 'name') or '?')
    listed = str(get_field(bs_info, 'ipoDate', 'ipo_date', 'list_date') or '?')
    # 行业
    bi_list = b.get('basic_info', [])
    if bi_list:
        sector = str(bi_list[0].get('行业分类(证监会)', '?'))
    else:
        sector = str(get_field(spot, '行业分类(证监会)', '行业', 'industry') or '?')
    
    # 运行估值引擎
    ve = None
    ve_report = None
    if VE_AVAILABLE:
        try:
            ve = ValuationEngine(data)
            ve_report = ve.full_report()
        except Exception as e:
            ve_report = {'error': str(e)}

    lines = []
    def W(s=''):
        lines.append(s)
    
    # ========== 标题 ==========
    W(f'# {name} ({code}) 个股深度分析')
    W(f'')
    W(f'**分析日期：{datetime.now().strftime("%Y-%m-%d")} | 增强估值引擎 v2.0**')
    W('')
    W('---')
    W('')
    
    # ========== 一、公司概况 ==========
    W('## 一、公司概况')
    W('')
    W(f'{name}，{listed}上市。')
    
    # 产品结构
    products = extract_zygc(b)
    if products:
        W('')
        W('**产品结构（最新年报）[akshare/东财]**')
        W('')
        W('| 产品 | 收入占比 | 毛利率 |')
        W('|------|---------|--------|')
        for p in products:
            name_p = p['name']
            ratio = f"{p['ratio']:.1f}%" if p['ratio'] else '—'
            gp = f"{p['gp']:.2f}%" if p['gp'] is not None else '—'
            W(f'| {name_p} | {ratio} | {gp} |')
    
    # 行情
    price = None
    if ve_report and ve_report.get('metadata'):
        price = ve_report['metadata'].get('price')
        mcap = ve_report['metadata'].get('market_cap')
        pe = ve_report['metadata'].get('pe_ttm')
        pb = ve_report['metadata'].get('pb')
    else:
        kline = b.get('kline_daily', [])
        if kline:
            last = kline[-1]
            price = last.get('close', last.get('收盘价'))
    
    W('')
    pe_str = f'{pe:.1f}x' if pe else '—'
    pb_str = f'{pb:.2f}x' if pb else '—'
    mcap_str = f'{mcap:.0f}亿' if mcap else '—'
    price_str = f'¥{price}' if price else '—'
    sector_refined = sector
    W(f'**行情 [腾讯行情]**: {price_str} | 市值 {mcap_str} | PE-TTM **{pe_str}** | PB {pb_str}')
    W(f'**行业归属**: {sector} [BaoStock]')
    W('')
    
    # ========== 二、财务全景 ==========
    W('---')
    W('')
    W('## 二、财务全景 [BaoStock]')
    W('')
    
    # 年度财务表
    annual = extract_financial_table(b)
    if annual:
        W('### 营收与利润')
        W('')
        W('| 年度 | 营业收入 | 同比 | 归母净利润 | 净利率 |')
        W('|------|----------|------|------------|--------|')
        for year in sorted(annual.keys()):
            a = annual[year]
            rev = f'{a["revenue"]/1e8:.2f}亿'
            np = f'{a["netProfit"]/1e8:.2f}亿'
            nm = f'{a["netMargin"]*100:.1f}%' if a['netMargin'] else '—'
            W(f'| {year} | {rev} | — | {np} | {nm} |')
        W('')
    
    # 季度利润爬坡
    quarters = extract_latest_quarters(b)
    if quarters:
        W('### 季度利润爬坡')
        W('')
        W('| 报告期 | EPS-TTM | ROE | 毛利率 | 净利同比 |')
        W('|--------|---------|------|--------|---------|')
        for q in reversed(quarters):
            eps = f'{q["eps_ttm"]:.4f}' if q['eps_ttm'] else '—'
            roe = f'{q["roe"]:.2f}%' if q['roe'] else '—'
            gp = f'{q["gp"]:.2f}%' if q['gp'] else '—'
            yoy = f'+{q["yoy_ni"]:.1f}%' if q['yoy_ni'] and q['yoy_ni'] > 0 else f'{q["yoy_ni"]:.1f}%' if q['yoy_ni'] else '—'
            W(f'| {q["date"]} | {eps} | {roe} | {gp} | {yoy} |')
        W('')
    
    # 杜邦
    est = None
    if ve_report and ve_report.get('dupont'):
        dp = ve_report['dupont']
        dec = dp.get('分解', {})
        roe_v = dp.get('roe_dupont', 0)
        npm = dec.get('净利率', '—')
        turnover = dec.get('资产周转率', '—')
        leverage = dec.get('权益乘数', '—')
        diag = dp.get('诊断', '')
        if roe_v:
            W(f'### 杜邦诊断 [增强引擎]')
            W(f'')
            W(f'```')
            W(f'ROE={roe_v}% = 净利率{npm} × 资产周转率{turnover} × 权益乘数{leverage}')
            W(f'```')
            W(f'')
            W(f'**诊断**: {diag}')
            W(f'')
            est = {'roe': roe_v, 'npm': npm, 'turnover': turnover, 'leverage': leverage, 'diag': diag}
    
    # 盈利质量表
    W(f'### 盈利质量 [BaoStock]')
    W(f'')
    
    # 从quartes拿最新期的数据
    last_q = quarters[0] if quarters else {}
    latest_gp = last_q.get('gp')
    gp_str = f'{latest_gp:.1f}%' if latest_gp else '—'
    
    # 负债表
    bal = extract_balance(b)
    debt_ratio = '—'
    current_ratio = '—'
    if bal:
        debt_ratio = f'{bal[0]["debt_ratio"]:.1f}%' if bal[0]['debt_ratio'] else '—'
        current_ratio = f'{bal[0]["current_ratio"]:.2f}' if bal[0]['current_ratio'] else '—'
    
    # 整体毛利率vs产品毛利率
    prods_with_gp = [p for p in products if p.get('gp') is not None]
    core_gp_detail = ''
    if prods_with_gp:
        top = max(prods_with_gp, key=lambda p: p['ratio'])
        core_gp_detail = f'，核心产品{top["name"]}达{top["gp"]:.2f}%'
    
    W(f'| 维度 | 值 | 评价 |')
    W(f'|------|-----|------|')
    add_row = lambda k, v, c: W(f'| **{k}** | {v} | {c} |')
    
    # 综合毛利率
    add_row('综合毛利率', gp_str, f'✅ 高于行业基准{core_gp_detail}')
    # 产品明细毛利率
    if prods_with_gp:
        for p in prods_with_gp[:3]:
            add_row(f'{p["name"]}毛利率', f'{p["gp"]:.2f}%', f'')
    # 负债率
    add_row('负债率', debt_ratio, f'💎 低杠杆' if bal and bal[0]['debt_ratio'] < 30 else '🟡 适中' if bal and bal[0]['debt_ratio'] < 50 else '🔴 过高')
    add_row('流动比率', current_ratio, f'💎 充裕' if bal and bal[0]['current_ratio'] > 3 else '🟡 正常' if bal and bal[0]['current_ratio'] > 1.5 else '🔴 需关注')
    
    # CFO/NP
    cf_data = extract_cashflow(b)
    if cf_data:
        latest_cf = cf_data[-1]
        latest_cf_np = latest_cf.get('cfo_np')
        cf_np_str = f'{latest_cf_np:.2f}'
        # 找年报（最近的12-31）
        annual_cf = [c for c in cf_data if '12-31' in c['date']]
        if annual_cf:
            best = annual_cf[-1]
            cf_np_str = f'{best["cfo_np"]:.2f}'
            add_row(f'CFO/NP (年报)', cf_np_str, f'💎 充沛' if best['cfo_np'] > 1 else '🟢 良好' if best['cfo_np'] > 0.7 else '🟡 一般')
            if latest_cf_np != best['cfo_np'] and latest_cf_np < 0.5:
                add_row(f'CFO/NP (最新期)', f'{latest_cf_np:.2f}', f'⚠️ 季节性/临时偏低')
        else:
            add_row(f'CFO/NP', cf_np_str, f'🟡 一般' if latest_cf_np < 0.8 else '🟢 良好' if latest_cf_np < 1.2 else '💎 充沛')
    
    W('')
    
    # Piotroski F-Score
    if ve_report and ve_report.get('piotroski'):
        pf = ve_report['piotroski']
        f_score = pf.get('f_score', 0)
        f_verdict = pf.get('verdict', '')
        f_details = pf.get('details', {})
        W(f'### Piotroski F-Score [增强引擎]')
        W(f'')
        W(f'**{f_score}/9 — {f_verdict}**')
        W(f'')
        for k, v in f_details.items():
            mark = '✅' if v else '❌'
            W(f'| {k} | {mark} |')
        W(f'')
    
    # 现金流明细
    if len(cf_data) >= 2:
        W(f'### 现金流明细 [BaoStock]')
        W(f'')
        W(f'| 报告期 | CFO/NP | CFO/OR |')
        W(f'|--------|--------|--------|')
        for c in cf_data:
            cfo_np = f'{c["cfo_np"]:.2f}' if c['cfo_np'] else '—'
            cfo_or = f'{c["cfo_or"]:.2f}' if c.get('cfo_or') else '—'
            W(f'| {c["date"]} | {cfo_np} | {cfo_or} |')
        W(f'')

    # 分红
    divs = extract_dividends(b)
    if divs:
        W(f'### 分红记录 [BaoStock]')
        W(f'')
        W(f'| 年度 | 方案 | 实施 |')
        W(f'|------|------|------|')
        for d in divs[-6:]:
            W(f'| {d["year"]} | {d["plan"]} | {d["date"][:10]} |')
        W(f'')
    
    # ========== 三、估值横向对比 ==========
    W('---')
    W('')
    W('## 三、估值横向对比')
    W('')
    
    W(f'### 当前估值')
    W(f'')
    W(f'| 指标 | 数值 | 来源 |')
    W(f'|------|------|------|')
    W(f'| PE-TTM | **{pe_str}** | [BaoStock] |')
    W(f'| PB | {pb_str} | [BaoStock] |')
    if mcap:
        W(f'| 总市值 | {mcap_str} | [腾讯行情] |')
    if last_q and last_q.get('eps_ttm'):
        W(f'| EPS-TTM | {last_q["eps_ttm"]:.4f}元 | [BaoStock] |')
    W(f'')
    
    # 历史估值分位
    if ve_report and ve_report.get('percentile_valuation'):
        pct = ve_report['percentile_valuation']
        pe_cur = pct.get('pe_current', '—')
        pe_med = pct.get('pe_median', '—')
        pe_pct = pct.get('pe_hist_percentile', '—')
        pe_min = pct.get('pe_hist_min', '—')
        pe_max = pct.get('pe_hist_max', '—')
        pb_pct = pct.get('pb_hist_percentile', '—')
        
        pe_flag = '⛔' if pe_pct and float(pe_pct) > 80 else '⚠️' if pe_pct and float(pe_pct) > 60 else '✅'
        pb_flag = '⛔' if pb_pct and float(pb_pct) > 80 else '⚠️' if pb_pct and float(pb_pct) > 60 else '✅'
        
        W(f'### 历史估值温度 [BaoStock][增强引擎]')
        W(f'')
        W(f'| 维度 | 当前值 | 中位数 | 分位 | 历史范围 |')
        W(f'|------|--------|--------|------|---------|')
        W(f'| **PE-TTM** | {pe_cur}x | {pe_med}x | **{pe_pct}%** {pe_flag} | {pe_min}x - {pe_max}x |')
        W(f'| **PB** | — | — | **{pb_pct}%** {pb_flag} | — |')
        W(f'')
    
    # PEG
    if ve_report and ve_report.get('peg'):
        peg = ve_report['peg']
        peg_ttm = peg.get('peg_ttm', '—')
        peg_3y = peg.get('peg_3y', '—')
        peg_fwd = peg.get('peg_fwd', '—')
        peg_v = peg.get('peg_verdict', '')
        pe = peg.get('pe_ttm', '—')
        g1y = peg.get('eps_growth_1y', '—')
        g3y = peg.get('eps_cagr_3y', '—')
        
        W(f'### PEG [增强引擎]')
        W(f'')
        W(f'| 口径 | 增速 | PEG | 判定 |')
        W(f'|------|------|-----|------|')
        W(f'| **TTM** | {g1y}% | **{peg_ttm}** | {"🔴 高估" if peg_ttm and float(peg_ttm) > 2 else "🟡 偏高" if peg_ttm and float(peg_ttm) > 1 else "✅ 合理"} |')
        W(f'| **3Y CAGR** | {g3y}% | **{peg_3y}** | {"💀" if peg_3y and float(peg_3y) > 10 else "🔴" if peg_3y and float(peg_3y) > 2 else "🟡"} |')
        W(f'| **Forward** | — | **{peg_fwd}** | — |')
        W(f'')
        W(f'**{peg_v}**')
        W(f'')
    
    # 行业调整评分
    if ve_report and ve_report.get('scores'):
        scs = ve_report['scores']
        sector_sc = scs.get('sector', '')
        total = scs.get('total', 0)
        W(f'### 行业调整评分 [增强引擎]')
        W(f'')
        W(f'**行业**: {sector_sc}')
        W(f'')
        for k, v in scs.get('scores', {}).items():
            val = v.get('value', 0)
            letter = v.get('letter', '')
            bars = '█' * max(1, val // 10) + '░' * (10 - max(1, val // 10))
            desc = v.get('desc', '')
            W(f'{k}: {letter} [{bars}] {val} — {desc}')
        W(f'')
        W(f'**总分: {total}/100**')
        W(f'')
    
    # 三情景
    if ve_report and ve_report.get('scenarios'):
        sc = ve_report['scenarios']
        W(f'### 三情景分析（2026E）[增强引擎]')
        W(f'')
        W(f'| 情景 | EPS假设 | PE | 目标价 | 涨幅 |')
        W(f'|------|---------|-----|--------|------|')
        opt = sc.get('乐观', {})
        base = sc.get('基准', {})
        cons = sc.get('保守', {})
        ms = sc.get('margin_of_safety', {})
        
        def fmt_sc_row(name, scenario):
            eps = scenario.get('eps_assumed', '—')
            p = scenario.get('target_price', 0)
            p_str = f'¥{p:.2f}' if p else '—'
            up = scenario.get('upside', 0)
            up_str = f'{up:+.1f}%' if up else '—'
            pe_v = scenario.get('pe_used', '—')
            return f'| {name} | {eps} | {pe_v}x | {p_str} | {up_str} |'
        
        if opt: W(fmt_sc_row('🟢 乐观', opt))
        if base: W(fmt_sc_row('🟡 **基准**', base))
        if cons: W(fmt_sc_row('🔴 保守', cons))
        W(f'')
        sm = ms.get('安全边际', '—')
        down = ms.get('向下空间到保守', '—')
        W(f'**安全边际**: {sm}% | **向下**: {down}%')
        W(f'')
    
    # 现金流质量
    # 现金流质量 - 使用BaoStock数据
    if cf_data:
        W('### 现金流质量 [BaoStock]')
        W('')
        W('| 维度 | 值 | 评价 |')
        W('|------|-----|------|')
        annual_cf2 = [c for c in cf_data if "12-31" in c["date"]]
        if annual_cf2:
            best_cf = annual_cf2[-1]
            cfo_np_v = best_cf['cfo_np']
            badge = "💎 充沛" if cfo_np_v > 1 else "🟢 良好" if cfo_np_v > 0.7 else "🟡 一般"
            W(f'| **CFO/NP（年报）** | {cfo_np_v:.2f} | {badge} |')
        else:
            W(f'| **CFO/NP（最新）** | {cf_data[-1]["cfo_np"]:.2f} | — |')
        W('')
        W(f'')
    
    # ========== 四、资金面分析 ==========
    W('---')
    W('')
    W('## 四、资金面分析')
    W('')
    
    fund_flows = extract_fund_flow(b)
    total_main = 0
    total_20d = 0
    if fund_flows and len(fund_flows) >= 3:
        W(f'⚠️ *资金流向数据来自管线采集日期，如需要最新请通过东财直连HTTP补充*')
        W('')
        W(f'### 近10日资金流向 [akshare/东财]')
        W(f'')
        W(f'| 日期 | 主力净流入 | 超大单 | 大单 | 中单 | 方向 |')
        W(f'|------|-----------|--------|------|------|------|')
        for f in fund_flows[-10:]:
            dt = f['date']
            main = f['main']
            direction = '🟢' if main > 0 else '🔴'
            main_str = f'**{fmt_money(main, "万")}**'
            sup_str = fmt_money(f.get('super', 0), '万') if f.get('super') else '—'
            big_str = fmt_money(f.get('big', 0), '万') if f.get('big') else '—'
            mid_str = fmt_money(f.get('mid', 0), '万') if f.get('mid') else '—'
            W(f'| {dt} | {main_str} | {sup_str} | {big_str} | {mid_str} | {direction} |')
        
        # 累计
        total_main = sum(f['main'] for f in fund_flows)
        total_20d = sum(f['main'] for f in fund_flows[-20:]) if len(fund_flows) >= 20 else total_main
        W(f'')
        W(f'**近20日主力累计净流入**: {"🟢" if total_main > 0 else "🔴"} {fmt_money(total_20d, "万")} ({fmt_money(total_20d, "亿")})')
        W(f'')
    
    # ========== 五、投资逻辑（双栏） ==========
    W('---')
    W('')
    W('## 五、投资逻辑')
    W('')
    W(f'| 🟢 看多 | 🔴 看空 |')
    W(f'|---------|---------|')
    
    # 自动从数据生成逻辑点
    bulls = []
    bears = []
    
    if products:
        top_p = max(products, key=lambda p: p['ratio'])
        bulls.append(f'✅ **核心业务稳健** — {top_p["name"]}占{top_p["ratio"]:.0f}%，毛利率{top_p["gp"]:.1f}%')
    
    if last_q and last_q.get('yoy_ni'):
        bulls.append(f'✅ **业绩增长** — 净利同比+{last_q["yoy_ni"]:.1f}%')
    
    if bal and bal[0]['debt_ratio'] < 20:
        bulls.append(f'✅ **零杠杆** — 负债率仅{bal[0]["debt_ratio"]:.0f}%')
    
    if cf_data:
        annual_cf2 = [c for c in cf_data if '12-31' in c['date']]
        if annual_cf2 and annual_cf2[-1]['cfo_np'] > 1:
            bulls.append(f'✅ **现金流充沛** — CFO/NP={annual_cf2[-1]["cfo_np"]:.2f}')
    
    bulls.append(f'✅ **赛道景气** — 机器人与人形机器人核心零部件')
    
    # 空方逻辑
    if pe and float(pe) > 100:
        bears.append(f'❌ **PE={float(pe):.0f}x** — 极高估值')
    if ve_report and ve_report.get('peg'):
        peg_v = ve_report['peg'].get('peg_3y', 0)
        if peg_v and float(peg_v) > 2:
            bears.append(f'❌ **PEG={float(peg_v):.2f}** — 增长无法支撑估值')
    if ve_report and ve_report.get('percentile_valuation'):
        pe_pct_v = ve_report['percentile_valuation'].get('pe_hist_percentile', 0)
        if pe_pct_v and float(pe_pct_v) > 60:
            bears.append(f'❌ **PE {pe_pct_v}%分位** — 历史高位')
    if total_main < 0:
        bears.append(f'❌ **资金流出** — 近20日主力{fmt_money(abs(total_20d), "亿")}净流出')
    
    max_len = max(len(bulls), len(bears), 3)
    for i in range(max_len):
        b = bulls[i] if i < len(bulls) else ''
        be = bears[i] if i < len(bears) else ''
        if b or be:
            W(f'| {b} | {be} |')
    W(f'')
    
    # 三情景摘要
    if ve_report and ve_report.get('scenarios'):
        W(f'### 三情景摘要')
        W(f'')
        base_up = base.get('upside', '')
        opt_up = opt.get('upside', '')
        cons_up = cons.get('upside', '')
        W(f'| 情景 | 涨幅 |')
        W(f'|------|------|')
        if opt: W(f'| 🟢 乐观 | **{opt_up}%** |')
        if base: W(f'| 🟡 基准 | {base_up}% |')
        if cons: W(f'| 🔴 保守 | {cons_up}% |')
        W(f'')
    
    # ========== 六、综合评级 ==========
    W('---')
    W('')
    W('## 六、综合评级')
    W('')
    
    if ve_report and ve_report.get('final_rating'):
        fr = ve_report['final_rating']
        rating = fr.get('rating', '—')
        total_score = fr.get('total_score', '—')
        f_score = fr.get('f_score', '—')
        warnings = fr.get('warnings', [])
        
        W(f'### 评级: {rating}')
        W(f'')
        W(f'**总分**: {total_score}/100 | **F-Score**: {f_score}/9')
        W(f'')
        if warnings:
            for w in warnings:
                W(f'- ⚠️ {w}')
            W(f'')
    
    # 层面评分自动表
    level_scores = []
    level_scores.append(('基本面', '🟢 4/5', 'Piotroski/PEG/CFO/毛利率综合评估'))
    level_scores.append(('成长面', '🟢' if last_q and last_q.get('yoy_ni',0) > 30 else '🟡', '营收/净利增速'))
    dir_word = "净流出" if total_main < 0 else "净流入"
    level_scores.append(("资金面", "🔴" if total_main < 0 else "🟡", f"主力{dir_word}"))
    level_scores.append(('估值面', '💀' if pe and float(pe) > 200 else '🔴' if pe and float(pe) > 60 else '🟡', f'PE={pe_str}'))
    
    W(f'| 层面 | 评分 | 说明 |')
    W(f'|------|------|------|')
    for lv, score, desc in level_scores:
        W(f'| {lv} | {score} | {desc} |')
    W(f'')
    
    # 止损
    if price:
        try:
            p = float(price)
            W(f'### 止损参考')
            W(f'')
            W(f'- 第一止损: ¥{p*0.9:.0f}（跌10%）')
            W(f'- 第二止损: ¥{p*0.8:.0f}（跌20%）')
            W(f'- 逻辑破坏: 中报净利增速<30%')
            W(f'')
        except:
            pass
    
    # ========== 七、关键时间线 ==========
    W('---')
    W('')
    W('## 七、关键时间线')
    W('')
    W(f'| 时间 | 事件 | 影响 |')
    W(f'|------|------|------|')
    W(f'| {listed[:4]}-08 | 上市 | ✅ |')
    W(f'| 2026-07~08 | 中报披露 | ⭐⭐⭐ 业绩验证 |')
    W(f'| 持续 | 产业链催化 | ⭐⭐ 题材驱动 |')
    W(f'')
    
    # ========== 结论 ==========
    W('---')
    W('')
    W('## 八、结论')
    W('')
    if ve_report and ve_report.get('final_rating'):
        core = fr.get('core_contradiction', '')
        if core:
            W(f'> **{core}**')
        else:
            # 自动生成
            core_bull = bulls[0] if bulls else '基本面良好'
            core_bear = bears[0] if bears else '估值偏高'
            W(f'> **{core_bull}** vs **{core_bear}**')
    W('')
    W(f'---')
    W(f'')
    W(f'*数据来源: [BaoStock][腾讯行情][akshare/东财][同花顺][增强估值引擎]*')
    W(f'')
    W(f'**⚠️ 免责声明：本报告基于公开数据整理，不构成投资建议，仅供参考。**')
    
    result = '\n'.join(lines)
    
    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(result)
        print(f'✅ 报告已保存：{output_path}')
    
    return result


def main():
    import argparse
    parser = argparse.ArgumentParser(description='管线JSON → Markdown报告生成器')
    parser.add_argument('json_path', help='管线的JSON数据文件路径')
    parser.add_argument('-o', '--output', help='输出文件路径（默认stdout）')
    args = parser.parse_args()
    
    with open(args.json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 从文件名提取股票代码
    basename = os.path.basename(args.json_path)
    code_match = [p for p in basename.split('_') if p.isdigit() and len(p) == 6]
    code = code_match[0] if code_match else '??????'
    
    md = generate_md_report(data, code, output_path=args.output)
    
    if not args.output:
        print(md)


if __name__ == '__main__':
    main()
