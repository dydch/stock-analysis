"""
个股数据采集（Phase 1）— 混合版
================================
baostock（核心：K线/财务）+ akshare（补充：新闻/股东/资金流向等）双数据源。

相较纯 akshare 版优势：
  ✅ K 线数据更准确（baostock 直接来自交易所）
  ✅ 财务数据结构化、季度分明（ROE/毛利率/净利率等）
  ✅ 包含 PE/PB 等估值指标
  ✅ baostock 不重复调用，降低被 ban 风险

用法
  python stock_full_report_hybrid.py 000034            # 默认混合模式
  python stock_full_report_hybrid.py 000034 --ak-only  # 纯 akshare（原版行为）
  python stock_full_report_hybrid.py 000034 --bs-only  # 纯 baostock（仅支持的数据）

输出
  output/data_{代码}.json  — 与纯 akshare 版格式兼容
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time
import traceback
from dataclasses import dataclass, field
from typing import Any, Callable

import pandas as pd

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# ============================================================
#  数据源导入
# ============================================================

_has_ak = False
_has_bs = False

try:
    import akshare as ak
    _has_ak = True
except ImportError:
    pass

try:
    import baostock as bs
    _has_bs = True
except ImportError:
    pass

# ============================================================
#  通用工具
# ============================================================

def detect_market(code: str) -> tuple[str, str, str]:
    """
    返回 (prefixed, market, bs_code)
    - prefixed: 'sh600519' / 'sz000066'（akshare 格式）
    - market: 'sh' / 'sz' / 'bj'
    - bs_code: 'sh.600519' / 'sz.000034'（baostock 格式）
    """
    raw = code.strip()
    # 剔除已有前缀
    for prefix in ["sh", "sz", "bj"]:
        if raw.startswith(prefix):
            raw = raw[len(prefix):]
            break
    if not raw.isdigit() or len(raw) != 6:
        raise ValueError(f"非法的 A 股代码：{raw}")
    if raw.startswith(("60", "68", "11", "12", "5")):
        return f"sh{raw}", "sh", f"sh.{raw}"
    if raw.startswith(("00", "30", "20", "15", "16", "18")):
        return f"sz{raw}", "sz", f"sz.{raw}"
    if raw.startswith(("4", "8", "92")):
        return f"bj{raw}", "bj", f"bj.{raw}"
    return f"sh{raw}", "sh", f"sh.{raw}"


def _last_trade_day(d: dt.date) -> dt.date:
    d = d - dt.timedelta(days=1)
    while d.weekday() >= 5:
        d -= dt.timedelta(days=1)
    return d


def _filter_by_code(df: pd.DataFrame, code: str) -> pd.DataFrame:
    """按代码列过滤行。"""
    if df is None or df.empty:
        return pd.DataFrame()
    candidate_cols = ["代码", "股票代码", "证券代码", "symbol", "code"]
    target_col = next((c for c in candidate_cols if c in df.columns), None)
    if target_col is None:
        return df
    series = df[target_col].astype(str).str.strip()
    mask = (series == code) | series.str.endswith(code)
    return df[mask].reset_index(drop=True)


def _safe_call_ak(fn: Callable, *args, retries: int = 3, label: str = "", **kwargs) -> pd.DataFrame | None:
    """带重试的 akshare 调用。"""
    if not _has_ak:
        return None
    backoff = (0.5, 1.5, 3.0)
    for attempt in range(retries + 1):
        try:
            t0 = time.perf_counter()
            res = fn(*args, **kwargs)
            elapsed = time.perf_counter() - t0
            rows = len(res) if isinstance(res, pd.DataFrame) else "?"
            print(f"  ✓ [ak] {label:40s} {rows} 行 · {elapsed:.1f}s")
            return res
        except Exception as e:
            err_brief = f"{type(e).__name__}: {e}"[:90]
            transient = any(k in str(e) for k in ("Connection", "Timeout", "Disconnected", "Proxy"))
            if attempt < retries and transient:
                time.sleep(backoff[min(attempt, len(backoff) - 1)])
                continue
            print(f"  ✗ [ak] {label:40s} {err_brief}")
            return None


def _bs_query(label: str, func_name: str, **kwargs) -> pd.DataFrame | None:
    """baostock 查询封装，自动处理 login/logout。"""
    if not _has_bs:
        return None
    try:
        t0 = time.perf_counter()
        lg = bs.login()
        if lg.error_code != "0":
            print(f"  ✗ [bs] {label:40s} login failed: {lg.error_msg}")
            return None
        func = getattr(bs, func_name)
        rs = func(**kwargs)
        if rs.error_code != "0":
            print(f"  ✗ [bs] {label:40s} {rs.error_msg}")
            bs.logout()
            return None
        df = rs.get_data()
        elapsed = time.perf_counter() - t0
        rows = len(df)
        print(f"  ✓ [bs] {label:40s} {rows} 行 · {elapsed:.1f}s")
        bs.logout()
        return df
    except Exception as e:
        print(f"  ✗ [bs] {label:40s} {type(e).__name__}: {str(e)[:60]}")
        try:
            bs.logout()
        except Exception:
            pass
        return None


def _df_to_records(df: pd.DataFrame | None, max_rows: int | None = None) -> list[dict]:
    """DataFrame -> list[dict]，处理 NaN/Timestamp。"""
    if df is None or df.empty:
        return []
    out = df.head(max_rows) if max_rows else df
    out = out.copy()
    for c in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[c]):
            out[c] = out[c].dt.strftime("%Y-%m-%d %H:%M:%S").where(out[c].notna(), None)
    records = json.loads(out.to_json(orient="records", force_ascii=False, date_format="iso"))
    return records


# ============================================================
#  数据收集器
# ============================================================

@dataclass
class StockReportData:
    code: str
    prefixed: str
    bs_code: str
    market: str
    data_mode: str = "hybrid"
    generated_at: str = field(default_factory=lambda: dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    blocks: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


def collect(code: str, max_kline_years: int = 3, mode: str = "hybrid") -> StockReportData:
    """
    mode 参数：
      hybrid — baostock 核心 + akshare 补充（推荐）
      bs-only — 仅 baostock（数据有限）
      ak-only — 仅 akshare（原版行为）
    """
    prefixed, market, bs_code = detect_market(code)
    data = StockReportData(code=code, prefixed=prefixed, bs_code=bs_code,
                           market=market, data_mode=mode)

    today = dt.date.today()
    last_trade = _last_trade_day(today + dt.timedelta(days=1))
    last_trade_prev = _last_trade_day(last_trade)
    today_s = today.strftime("%Y%m%d")
    last_trade_prev_s = last_trade_prev.strftime("%Y%m%d")
    today_fmt = today.strftime("%Y-%m-%d")
    kline_start = (today - dt.timedelta(days=int(365.25 * max_kline_years))).strftime("%Y-%m-%d")
    month_ago_s = (today - dt.timedelta(days=40)).strftime("%Y%m%d")

    use_bs = mode in ("hybrid", "bs-only")
    use_ak = mode in ("hybrid", "ak-only")

    # =============================================================
    #  1. 基础信息 — baostock（更准）+ akshare（补充）
    # =============================================================
    print("[1/13] 基础信息")
    basic_info = {}

    if use_bs:
        df = _bs_query("公司概况", "query_stock_basic", code=bs_code)
        data.blocks["basic_info_bs"] = _df_to_records(df)
        if df is not None and not df.empty:
            row = df.iloc[0]
            basic_info["股票名称"] = str(row.get("code_name", ""))
            basic_info["上市日期"] = str(row.get("ipoDate", ""))

        # 行业分类
        df_industry = _bs_query("行业分类(证监会)", "query_stock_industry")
        if df_industry is not None and not df_industry.empty:
            ind_row = df_industry[df_industry["code"] == bs_code]
            if not ind_row.empty:
                basic_info["行业分类(证监会)"] = str(ind_row.iloc[0].get("industry", ""))

    if use_ak:
        df = _safe_call_ak(ak.stock_individual_basic_info_xq,
                           symbol=prefixed.upper(), label="雪球-公司概况")
        if df is not None and not df.empty:
            recs = _df_to_records(df)
            if recs:
                basic_info.update({k: v for k, v in recs[0].items()})
        df = _safe_call_ak(ak.stock_zh_a_spot, label="新浪-全市场快照")
        if df is not None:
            df_self = df[df["代码"].astype(str) == prefixed]
            if df_self.empty:
                df_self = df[df["代码"].astype(str).str.endswith(code)]
            data.blocks["spot"] = _df_to_records(df_self)
        else:
            data.blocks["spot"] = []
        data.blocks["basic_info_ak"] = [basic_info] if basic_info else []

    data.blocks["basic_info"] = [basic_info] if basic_info else []

    # 股本结构 — 仅 akshare
    if use_ak:
        df = _safe_call_ak(ak.stock_zh_a_gbjg_em,
                           symbol=f"{code}.{market.upper()}", label="股本结构变动")
        data.blocks["share_structure"] = _df_to_records(df)
    else:
        data.blocks["share_structure"] = []

    # =============================================================
    #  2. 主营业务构成 — 仅 akshare（baostock 无此数据）
    # =============================================================
    print("[2/13] 主营业务构成")
    if use_ak:
        df = _safe_call_ak(ak.stock_zygc_em,
                           symbol=f"{market.upper()}{code}", label="主营构成(东财)")
        data.blocks["zygc"] = _df_to_records(df)
    else:
        data.blocks["zygc"] = []

    # =============================================================
    #  3. 行情 K 线 — baostock 为主（更准）, akshare 兜底
    # =============================================================
    print("[3/13] 行情 K 线")
    kline_daily = []
    if use_bs:
        # 后复权 K 线（含 PE/PB）
        rs = _bs_query("日K(后复权,含PE/PB)", "query_history_k_data_plus",
                       code=bs_code,
                       fields="date,code,open,high,low,close,preclose,volume,amount,"
                              "adjustflag,turn,tradestatus,pctChg,peTTM,pbMRQ,psTTM,pcfNcfTTM,isST",
                       start_date=kline_start, end_date=today_fmt,
                       frequency="d", adjustflag="2")
        if rs is not None:
            kline_daily.extend(_df_to_records(rs))
        else:
            # baostock 失败，fallback 到 akshare
            df = _safe_call_ak(ak.stock_zh_a_daily, symbol=prefixed,
                               start_date=kline_start.replace("-", ""),
                               end_date=today_s, adjust="qfq",
                               label=f"日K（akshare 兜底）")
            kline_daily = _df_to_records(df)
    elif use_ak:
        df = _safe_call_ak(ak.stock_zh_a_daily, symbol=prefixed,
                           start_date=kline_start.replace("-", ""),
                           end_date=today_s, adjust="qfq",
                           label=f"新浪-日K（{max_kline_years}年前复权）")
        kline_daily = _df_to_records(df)
    data.blocks["kline_daily"] = kline_daily

    # 分钟 K 线 — 仅 akshare
    if use_ak:
        df = _safe_call_ak(ak.stock_zh_a_minute, symbol=prefixed, period="1", adjust="",
                           label="1分钟分时（最近5日）")
        data.blocks["kline_minute"] = _df_to_records(df)
    else:
        data.blocks["kline_minute"] = []

    # =============================================================
    #  4. 资金流向 — 仅 akshare
    # =============================================================
    print("[4/13] 资金流向")
    if use_ak:
        df = _safe_call_ak(ak.stock_individual_fund_flow, stock=code, market=market,
                           label="个股资金流向(近100日)")
        data.blocks["fund_flow"] = _df_to_records(df)
    else:
        data.blocks["fund_flow"] = []

    # =============================================================
    #  5. 龙虎榜 — 仅 akshare
    # =============================================================
    print("[5/13] 龙虎榜")
    if use_ak:
        df = _safe_call_ak(ak.stock_lhb_detail_em,
                           start_date=month_ago_s, end_date=today_s,
                           label="龙虎榜近30日")
        data.blocks["lhb"] = _df_to_records(_filter_by_code(df, code))
    else:
        data.blocks["lhb"] = []

    # =============================================================
    #  6. 财务核心指标 — baostock (更准/结构化) + akshare 补充
    # =============================================================
    print("[6/13] 财务核心指标")

    # baostock 盈利能力 + 成长能力 + 营运能力 + 偿债能力 + 杜邦
    fin_merged = {"bs_profit": [], "bs_growth": [], "bs_operation": [],
                  "bs_balance": [], "bs_cashflow": [], "bs_dupont": [],
                  "ak_fin_abstract": [], "ak_indicator": []}

    if use_bs:
        # 最近 8 个季度
        for year, quarter in [(2023,1),(2023,2),(2023,3),(2023,4),
                              (2024,1),(2024,2),(2024,3),(2024,4),
                              (2025,1),(2025,2),(2025,3),(2025,4),
                              (2026,1)]:
            for qtype, key in [("query_profit_data", "bs_profit"),
                               ("query_growth_data", "bs_growth"),
                               ("query_operation_data", "bs_operation"),
                               ("query_balance_data", "bs_balance"),
                               ("query_cash_flow_data", "bs_cashflow"),
                               ("query_dupont_data", "bs_dupont")]:
                rs = _bs_query(f"{qtype.split('_')[-1]}({year}Q{quarter})",
                               qtype, code=bs_code, year=year, quarter=quarter)
                if rs is not None and not rs.empty:
                    fin_merged[key].extend(_df_to_records(rs))

    data.blocks["fin_bs"] = fin_merged

    if use_ak:
        df = _safe_call_ak(ak.stock_financial_abstract, symbol=code,
                           label="财务摘要（按报告期）")
        fin_merged["ak_fin_abstract"] = _df_to_records(df)
        df = _safe_call_ak(ak.stock_financial_abstract_ths, symbol=code, indicator="按报告期",
                           label="同花顺-关键指标")
        fin_merged["ak_indicator"] = _df_to_records(df)

    data.blocks["fin_merged"] = fin_merged

    # 三大报表 — 仅 akshare（baostock 只有汇总财务指标，没有完整三大报表）
    print("[7/13] 三大报表")
    if use_ak:
        for sheet_name, key in [("资产负债表", "balance_sheet"),
                                 ("利润表", "income_statement"),
                                 ("现金流量表", "cashflow")]:
            df = _safe_call_ak(ak.stock_financial_report_sina, stock=prefixed,
                               symbol=sheet_name, label=sheet_name)
            data.blocks[key] = _df_to_records(df)
    else:
        data.blocks["balance_sheet"] = []
        data.blocks["income_statement"] = []
        data.blocks["cashflow"] = []

    # =============================================================
    #  8. 业绩预告/快报 — 仅 akshare
    # =============================================================
    print("[8/13] 业绩预告/快报")
    yjyg_all, yjkb_all = [], []
    if use_ak:
        yj_periods = ["20240331", "20240630", "20240930", "20241231"]
        for p in yj_periods:
            df = _safe_call_ak(ak.stock_yjyg_em, date=p, label=f"业绩预告 {p}")
            rows = _filter_by_code(df, code)
            if not rows.empty:
                yjyg_all.extend(_df_to_records(rows))
            df = _safe_call_ak(ak.stock_yjkb_em, date=p, label=f"业绩快报 {p}")
            rows = _filter_by_code(df, code)
            if not rows.empty:
                yjkb_all.extend(_df_to_records(rows))
    data.blocks["yjyg"] = yjyg_all
    data.blocks["yjkb"] = yjkb_all

    # =============================================================
    #  9. 股东结构 — 仅 akshare
    # =============================================================
    print("[9/13] 股东结构")
    if use_ak:
        df = _safe_call_ak(ak.stock_gdfx_top_10_em, symbol=prefixed,
                           label="十大股东（最新）")
        data.blocks["top10"] = _df_to_records(df)
        df = _safe_call_ak(ak.stock_gdfx_free_top_10_em, symbol=prefixed,
                           label="十大流通股东（最新）")
        data.blocks["top10_free"] = _df_to_records(df)
        df = _safe_call_ak(ak.stock_zh_a_gdhs_detail_em, symbol=code,
                           label="股东户数变动")
        data.blocks["gdhs"] = _df_to_records(df)
        if market == "sh":
            df = _safe_call_ak(ak.stock_share_hold_change_sse, symbol=code,
                               label="高管持股变动（上交所）")
        else:
            df = _safe_call_ak(ak.stock_share_hold_change_szse, symbol=code,
                               label="高管持股变动（深交所）")
        data.blocks["share_hold_change"] = _df_to_records(df)
    else:
        data.blocks["top10"] = []
        data.blocks["top10_free"] = []
        data.blocks["gdhs"] = []
        data.blocks["share_hold_change"] = []

    # =============================================================
    #  10. 分红/解禁 — baostock 分红 + akshare 补充
    # =============================================================
    print("[10/13] 分红 / 解禁")
    dividend = []
    if use_bs:
        # 最近5年分红
        for y in ["2021", "2022", "2023", "2024", "2025"]:
            rs = _bs_query(f"分红({y})", "query_dividend_data",
                          code=bs_code, year=y, yearType="report")
            if rs is not None and not rs.empty:
                dividend.extend(_df_to_records(rs))
    data.blocks["dividend"] = dividend

    if use_ak:
        df = _safe_call_ak(ak.stock_history_dividend_detail, symbol=code, indicator="分红",
                           label="历史分红(ak补充)")
        if df is not None and not df.empty:
            dividend.extend(_df_to_records(df))
        # 去重
        seen = set()
        unique = []
        for d in dividend:
            k = json.dumps(d, sort_keys=True)
            if k not in seen:
                seen.add(k)
                unique.append(d)
        data.blocks["dividend"] = unique

        df = _safe_call_ak(ak.stock_history_dividend_detail, symbol=code, indicator="配股",
                           label="历史送转")
        data.blocks["share_alloc"] = _df_to_records(df)
        df = _safe_call_ak(ak.stock_restricted_release_queue_em, symbol=code,
                           label="限售解禁排队")
        data.blocks["release"] = _df_to_records(df)
    else:
        data.blocks["share_alloc"] = []
        data.blocks["release"] = []

    # =============================================================
    #  11. 公告/新闻/研报 — 仅 akshare
    # =============================================================
    print("[11/13] 公告 / 新闻 / 研报")
    if use_ak:
        df = _safe_call_ak(ak.stock_notice_report, symbol="全部", date=today_s,
                           label=f"当日公告({today_s})")
        data.blocks["notice"] = _df_to_records(_filter_by_code(df, code))
        df = _safe_call_ak(ak.stock_news_em, symbol=code, label="个股新闻")
        data.blocks["news"] = _df_to_records(df)
        df = _safe_call_ak(ak.stock_research_report_em, symbol=code, label="研究报告")
        data.blocks["research"] = _df_to_records(df)
    else:
        data.blocks["notice"] = []
        data.blocks["news"] = []
        data.blocks["research"] = []

    # =============================================================
    #  12. 机构评级 / 基金持仓 — 仅 akshare
    # =============================================================
    print("[12/13] 机构评级 / 基金持仓")
    if use_ak:
        df = _safe_call_ak(ak.stock_institute_recommend, symbol="股票综合评级",
                           label="机构推荐评级（全市场）")
        data.blocks["recommend"] = _df_to_records(_filter_by_code(df, code))
        df = _safe_call_ak(ak.stock_report_fund_hold_detail, symbol=code, date="20240331",
                           label="基金持仓（2024Q1）")
        data.blocks["fund_hold"] = _df_to_records(df)
    else:
        data.blocks["recommend"] = []
        data.blocks["fund_hold"] = []

    # =============================================================
    #  13. 融资融券 — 仅 akshare
    # =============================================================
    print("[13/13] 融资融券")
    if use_ak:
        if market == "sh":
            df = _safe_call_ak(ak.stock_margin_detail_sse, date=last_trade_prev_s,
                               label=f"上交所融资融券({last_trade_prev_s})")
        else:
            df = _safe_call_ak(ak.stock_margin_detail_szse, date=last_trade_prev_s,
                               label=f"深交所融资融券({last_trade_prev_s})")
        data.blocks["margin"] = _df_to_records(_filter_by_code(df, code))
    else:
        data.blocks["margin"] = []

    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="个股数据采集（混合版：baostock+akshare）")
    parser.add_argument("code", nargs="?", help="6 位 A 股代码")
    parser.add_argument("--mode", choices=["hybrid", "bs-only", "ak-only"],
                        default="hybrid",
                        help="数据源模式（默认 hybrid，核心数据用 baostock）")
    parser.add_argument("--max-kline-years", type=int, default=3,
                        help="日 K 拉取年限（默认 3 年）")
    args = parser.parse_args()

    code = args.code or input("请输入 6 位 A 股代码：").strip()
    if not code:
        print("[X] 未输入股票代码", file=sys.stderr)
        sys.exit(1)

    try:
        prefixed, market, bs_code = detect_market(code)
    except ValueError as e:
        print(f"[X] {e}", file=sys.stderr)
        sys.exit(1)

    mode_label = {"hybrid": "baostock核心 + akshare补充",
                  "bs-only": "纯baostock",
                  "ak-only": "纯akshare（原版）"}

    print(f"📊 生成 {code}（{prefixed}）的全量数据报告")
    print(f"   数据模式：{mode_label[args.mode]}")
    print(f"   K 线年限：{args.max_kline_years} 年")
    print()

    t0 = time.perf_counter()
    data = collect(code, max_kline_years=args.max_kline_years, mode=args.mode)
    elapsed = time.perf_counter() - t0

    n_blocks = sum(1 for v in data.blocks.values() if isinstance(v, list) and v)
    n_total_rows = sum(len(v) for v in data.blocks.values() if isinstance(v, list))
    print(f"\n✅ 数据收集完成：{n_blocks}/{len(data.blocks)} 个数据块，"
          f"共 {n_total_rows} 行，用时 {elapsed:.1f}s")

    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
    os.makedirs(output_dir, exist_ok=True)
    json_path = os.path.join(output_dir, f"data_{code}_hybrid.json")
    json_payload = {"blocks": data.blocks, "data_mode": data.data_mode}
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_payload, f, ensure_ascii=False, default=str)
    print(f"📊 JSON数据已保存：{json_path}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n已中断")
    except Exception:
        traceback.print_exc()
        sys.exit(1)
