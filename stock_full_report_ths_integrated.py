"""
个股深度分析系统 — 三源整合版（BaoStock + akshare + thsdk）
==========================================================
在 hybrid 混合版基础上，新增同花顺 SDK（thsdk）数据源：
  ✅ 分钟K线（1m/5m/15m/30m/60m/120m）
  ✅ 盘口深度（五档盘口 + 买卖委托深度）
  ✅ 大单流向（特大单/大单主力净流入）
  ✅ 日内分时（当日逐笔）
  ✅ 历史分时（近一年任意交易日回溯）
  ✅ 集合竞价异动扫描
  ✅ 同花顺一致预期EPS（机构预测）
  ✅ 实时资讯快讯
  ✅ 板块/指数行情
  ✅ 问财NLP选股

用法
  python stock_full_report_ths_integrated.py 688099                        # 三源整合（默认）
  python stock_full_report_ths_integrated.py 688099 --mode bs-only         # 仅BaoStock
  python stock_full_report_ths_integrated.py 688099 --mode ak-only         # 仅akshare
  python stock_full_report_ths_integrated.py 688099 --mode ths-only         # 仅thsdk（快速扫描）
  python stock_full_report_ths_integrated.py 688099 --mode ba+ths          # BaoStock + thsdk（无akshare）
  python stock_full_report_ths_integrated.py 688099 --no-ths               # 关闭thsdk
  python stock_full_report_ths_integrated.py 688099 --only-ths             # 同上 --mode ths-only

输出
  output/data_{代码}_ths.json  — 与纯 akshare 版格式兼容，新增 ths_* 块
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
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
_has_ths = False

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

try:
    from thsdk import THS
    _has_ths = True
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


def _ths_wrapper(label: str, func) -> list[dict] | None:
    """thsdk 查询封装，with THS() as ths 上下文由外部管理。"""
    if not _has_ths:
        return None
    try:
        t0 = time.perf_counter()
        resp = func
        elapsed = time.perf_counter() - t0
        if not resp:
            print(f"  ✗ [ths] {label:40s} {resp.error if hasattr(resp, 'error') else '无返回'}")
            return None
        if hasattr(resp, 'df') and resp.df is not None and not resp.df.empty:
            rows = len(resp.df)
            print(f"  ✓ [ths] {label:40s} {rows} 行 · {elapsed:.1f}s")
            df = resp.df.copy()
            # datetime -> str
            for c in df.columns:
                if pd.api.types.is_datetime64_any_dtype(df[c]):
                    df[c] = df[c].astype(str)
            return json.loads(df.to_json(orient="records", force_ascii=False))
        else:
            print(f"  ✓ [ths] {label:40s} 0 行(空数据) · {elapsed:.1f}s")
            return []
    except Exception as e:
        print(f"  ✗ [ths] {label:40s} {type(e).__name__}: {str(e)[:60]}")
        return None


def _code_to_ths(code: str) -> str:
    """6位A股代码 → 同花顺 THSCODE。"""
    raw = code.strip()
    for prefix in ["sh", "sz", "bj"]:
        if raw.startswith(prefix):
            raw = raw[len(prefix):]
            break
    if raw.startswith(("60", "68")):
        return f"USHA{raw}"
    if raw.startswith(("00", "30", "20")):
        return f"USZA{raw}"
    return f"USHA{raw}"


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
#  同花顺一致预期EPS（直连 basic.10jqka.com.cn）
# ============================================================

def ths_eps_forecast(code: str) -> list[dict]:
    """
    同花顺机构一致预期EPS。
    直连 basic.10jqka.com.cn，解析HTML表格。
    返回机构逐家预测数据 + 汇总统计。
    """
    import requests
    from io import StringIO

    url = f"https://basic.10jqka.com.cn/new/{code}/worth.html"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Referer": "https://basic.10jqka.com.cn/",
    }
    try:
        r = requests.get(url, headers=headers, timeout=15)
        r.encoding = "gbk"
        dfs = pd.read_html(StringIO(r.text))

        result = {}

        # 汇总统计表 — 净利润
        for df in dfs:
            cols = [str(c) for c in df.columns]
            if "预测机构数" in cols and "净利润" in str(df.iloc[:, 0].tolist()):
                result["net_profit_summary"] = _df_to_records(df)
                break

        # 汇总统计表 — EPS
        for df in dfs:
            cols = [str(c) for c in df.columns]
            if "预测机构数" in cols and ("每股收益" in str(df.iloc[:, 0].tolist()) or "均值" in cols):
                result["eps_summary"] = _df_to_records(df)
                if len(result) >= 2:
                    break

        # 机构逐家预测
        for df in dfs:
            cols = [str(c) for c in df.columns]
            if "研究机构" in cols and "预测年报净利润" in str(df.iloc[:, 0].tolist()):
                result["institution_forecast"] = _df_to_records(df)
                break

        # 综合预期表
        for df in dfs:
            cols_str = str(df.columns.tolist())
            if "2023" in cols_str and "营业收入" in str(df.iloc[:, 0].tolist()):
                result["consensus"] = _df_to_records(df)
                break

        if result:
            print(f"  ✓ [ths] 同花顺一致预期          {len(result)} 个数据块")
        else:
            print(f"  ✗ [ths] 同花顺一致预期          未找到数据")

        return result

    except Exception as e:
        print(f"  ✗ [ths] 同花顺一致预期          {type(e).__name__}: {str(e)[:60]}")
        return {}


def to_ths_code(code_str: str) -> str | None:
    """wencai 返回代码 → THSCODE。"""
    try:
        c, market = str(code_str).split('.')
        mapping = {'SH': 'USHA', 'SZ': 'USZA', 'BJ': 'USTM'}
        prefix = mapping.get(market.upper(), '')
        return f"{prefix}{c}" if prefix else None
    except Exception:
        return None


# ============================================================
#  thsdk 数据收集
# ============================================================

def collect_ths_block(code: str) -> dict[str, Any]:
    """
    使用 thsdk 收集同花顺特有数据。
    返回 dict[str, list[dict] | dict]，供合并到 blocks。
    """
    ths_code = _code_to_ths(code)
    result: dict[str, Any] = {}

    if not _has_ths:
        print("  ✗ [ths] thsdk 未安装，跳过")
        return result

    with THS() as ths:
        # ── 1. 实时行情（综合） ──────────────────────────
        resp = ths.market_data_cn(ths_code, "汇总")
        result["ths_market_data"] = _ths_wrapper("实时行情(汇总)", resp)

        # ── 2. 分钟K线多周期 ─────────────────────────────
        for interval, label in [("1m", "1分钟K线"), ("5m", "5分钟K线"),
                                  ("15m", "15分钟K线"), ("30m", "30分钟K线"),
                                  ("60m", "60分钟K线"), ("120m", "120分钟K线")]:
            try:
                resp = ths.klines(ths_code, interval=interval, count=120)
                result[f"ths_kline_{interval}"] = _ths_wrapper(label, resp)
            except Exception:
                pass

        # ── 3. 日K线（前复权） ──────────────────────────
        try:
            resp = ths.klines(ths_code, interval="day", count=250, adjust="forward")
            result["ths_kline_day"] = _ths_wrapper("日K线(前复权250日)", resp)
        except Exception:
            pass

        # ── 4. 日内分时 ────────────────────────────────
        resp = ths.intraday_data(ths_code)
        result["ths_intraday"] = _ths_wrapper("日内分时", resp)

        # ── 5. 五档盘口 ────────────────────────────────
        resp = ths.depth(ths_code)
        result["ths_depth"] = _ths_wrapper("五档盘口", resp)

        # ── 6. 买方/卖方深度 ──────────────────────────
        resp = ths.order_book_bid(ths_code)
        result["ths_order_bid"] = _ths_wrapper("买方深度", resp)
        resp = ths.order_book_ask(ths_code)
        result["ths_order_ask"] = _ths_wrapper("卖方深度", resp)

        # ── 7. 大单流向 ────────────────────────────────
        resp = ths.big_order_flow(ths_code)
        result["ths_big_order_flow"] = _ths_wrapper("大单流向", resp)

        # ── 8. 集合竞价快照 ──────────────────────────
        resp = ths.call_auction(ths_code)
        result["ths_call_auction"] = _ths_wrapper("集合竞价快照", resp)

        # ── 9. Tick数据（3秒级） ──────────────────────
        resp = ths.tick_level1(ths_code)
        result["ths_tick"] = _ths_wrapper("3秒Tick", resp)

    # ── 10. 同花顺一致预期（独立HTTP，非thsdk） ──────────
    try:
        forecast = ths_eps_forecast(code)
        if forecast:
            result["ths_forecast"] = forecast
    except Exception as e:
        print(f"  ✗ [ths] 一致预期获取失败: {e}")

    # ── 11. 实时资讯 ──────────────────────────────────────
    with THS() as ths:
        resp = ths.news()
        news_data = _ths_wrapper("实时资讯", resp)
        # 解析 Properties
        if news_data:
            for item in news_data[:20]:
                props_str = item.get("Properties", "")
                if props_str:
                    props = dict(re.findall(r'(\w+)=([^\n]+)', props_str))
                    item["source"] = props.get("source", "")
                    item["summary"] = props.get("summ", "")
            result["ths_news"] = news_data[:50]
        else:
            result["ths_news"] = []

    return result


# ============================================================
#  数据收集器（三源整合）
# ============================================================

@dataclass
class StockReportData:
    code: str
    prefixed: str
    bs_code: str
    market: str
    data_mode: str = "ths-enhanced"
    generated_at: str = field(default_factory=lambda: dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    blocks: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


def collect(code: str, max_kline_years: int = 3,
            mode: str = "ths-enhanced",
            no_ths: bool = False) -> StockReportData:
    """
    mode 参数：
      ths-enhanced — BaoStock + akshare + thsdk（推荐，三源全开）
      hybrid       — BaoStock + akshare（原hybrid行为，thsdk可选关闭）
      bs-only      — 仅 BaoStock
      ak-only      — 仅 akshare
      ths-only     — 仅 thsdk（快速扫描）
      ba+ths       — BaoStock + thsdk（无akshare）
    """
    prefixed, market, bs_code = detect_market(code)
    data = StockReportData(code=code, prefixed=prefixed, bs_code=bs_code,
                           market=market, data_mode=mode)

    today = dt.date.today()
    last_trade = _last_trade_day(today + dt.timedelta(days=1))
    today_s = today.strftime("%Y%m%d")
    today_fmt = today.strftime("%Y-%m-%d")
    kline_start = (today - dt.timedelta(days=int(365.25 * max_kline_years))).strftime("%Y-%m-%d")
    month_ago_s = (today - dt.timedelta(days=40)).strftime("%Y%m%d")

    use_bs = mode in ("ths-enhanced", "hybrid", "bs-only", "ba+ths")
    use_ak = mode in ("ths-enhanced", "hybrid", "ak-only")
    use_ths = _has_ths and mode in ("ths-enhanced", "ths-only", "ba+ths") and not no_ths

    mode_label = {
        "ths-enhanced": "三源整合(bs+ak+ths)",
        "hybrid": "baostock核心 + akshare补充",
        "bs-only": "纯baostock",
        "ak-only": "纯akshare",
        "ths-only": "纯thsdk(快速扫描)",
        "ba+ths": "baostock+thsdk(无akshare)",
    }

    print(f"📊 [{mode_label.get(mode, mode)}] 采集 {code}（{prefixed}）")
    print(f"   启用: bs={use_bs} ak={use_ak} ths={use_ths}")
    print(f"   K线年限：{max_kline_years} 年")
    print()

    # =============================================================
    #  [THS BLOCK] 同花顺 SDK 数据 — 独立块，与原始13块平行
    # =============================================================
    if use_ths:
        print("━━━ [THS] 同花顺 SDK 数据采集 ━━━")
        ths_data = collect_ths_block(code)
        data.blocks["ths"] = ths_data
        n_ths = sum(1 for v in ths_data.values() if isinstance(v, (list, dict)) and v)
        print(f"  → THS数据块 {n_ths} 个完成\n")
    else:
        data.blocks["ths"] = {}

    # =============================================================
    #  1. 基础信息 — baostock（更准）+ akshare（补充）
    # =============================================================
    if mode == "ths-only":
        data.blocks["basic_info"] = []
        data.blocks["spot"] = []
        data.blocks["share_structure"] = []
        data.blocks["zygc"] = []
        data.blocks["kline_daily"] = []
        data.blocks["kline_minute"] = []
        data.blocks["fund_flow"] = []
        data.blocks["lhb"] = []
        data.blocks["fin_bs"] = {}
        data.blocks["fin_merged"] = {}
        data.blocks["balance_sheet"] = []
        data.blocks["income_statement"] = []
        data.blocks["cashflow"] = []
        data.blocks["yjyg"] = []
        data.blocks["yjkb"] = []
        data.blocks["top10"] = []
        data.blocks["top10_free"] = []
        data.blocks["gdhs"] = []
        data.blocks["share_hold_change"] = []
        data.blocks["dividend"] = []
        data.blocks["share_alloc"] = []
        data.blocks["release"] = []
        data.blocks["notice"] = []
        data.blocks["news"] = []
        data.blocks["research"] = []
        data.blocks["recommend"] = []
        data.blocks["fund_hold"] = []
        data.blocks["margin"] = []
        return data

    print("━━━ [1/13] 基础信息 ━━━")
    basic_info = {}

    if use_bs:
        df = _bs_query("公司概况", "query_stock_basic", code=bs_code)
        data.blocks["basic_info_bs"] = _df_to_records(df)
        if df is not None and not df.empty:
            row = df.iloc[0]
            basic_info["股票名称"] = str(row.get("code_name", ""))
            basic_info["上市日期"] = str(row.get("ipoDate", ""))
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

    if use_ak:
        df = _safe_call_ak(ak.stock_zh_a_gbjg_em,
                           symbol=f"{code}.{market.upper()}", label="股本结构变动")
        data.blocks["share_structure"] = _df_to_records(df)
    else:
        data.blocks["share_structure"] = []

    # =============================================================
    #  2. 主营业务构成
    # =============================================================
    print("━━━ [2/13] 主营业务构成 ━━━")
    if use_ak:
        df = _safe_call_ak(ak.stock_zygc_em,
                           symbol=f"{market.upper()}{code}", label="主营构成(东财)")
        data.blocks["zygc"] = _df_to_records(df)
    else:
        data.blocks["zygc"] = []

    # =============================================================
    #  3. 行情 K 线
    # =============================================================
    print("━━━ [3/13] 行情 K 线 ━━━")
    kline_daily = []
    if use_bs:
        rs = _bs_query("日K(后复权,含PE/PB)", "query_history_k_data_plus",
                       code=bs_code,
                       fields="date,code,open,high,low,close,preclose,volume,amount,"
                              "adjustflag,turn,tradestatus,pctChg,peTTM,pbMRQ,psTTM,pcfNcfTTM,isST",
                       start_date=kline_start, end_date=today_fmt,
                       frequency="d", adjustflag="2")
        if rs is not None:
            kline_daily.extend(_df_to_records(rs))
        else:
            df = _safe_call_ak(ak.stock_zh_a_daily, symbol=prefixed,
                               start_date=kline_start.replace("-", ""),
                               end_date=today_s, adjust="qfq",
                               label="日K（akshare 兜底）")
            kline_daily = _df_to_records(df)
    elif use_ak:
        df = _safe_call_ak(ak.stock_zh_a_daily, symbol=prefixed,
                           start_date=kline_start.replace("-", ""),
                           end_date=today_s, adjust="qfq",
                           label="新浪-日K（前复权）")
        kline_daily = _df_to_records(df)

    data.blocks["kline_daily"] = kline_daily

    if use_ak:
        df = _safe_call_ak(ak.stock_zh_a_minute, symbol=prefixed, period="1", adjust="",
                           label="1分钟分时（最近5日）")
        data.blocks["kline_minute"] = _df_to_records(df)
    else:
        data.blocks["kline_minute"] = []

    # =============================================================
    #  4. 资金流向
    # =============================================================
    print("━━━ [4/13] 资金流向 ━━━")
    if use_ak:
        df = _safe_call_ak(ak.stock_individual_fund_flow, stock=code, market=market,
                           label="个股资金流向(近100日)")
        data.blocks["fund_flow"] = _df_to_records(df)
    else:
        data.blocks["fund_flow"] = []

    # =============================================================
    #  5. 龙虎榜
    # =============================================================
    print("━━━ [5/13] 龙虎榜 ━━━")
    if use_ak:
        df = _safe_call_ak(ak.stock_lhb_detail_em,
                           start_date=month_ago_s, end_date=today_s,
                           label="龙虎榜近30日")
        data.blocks["lhb"] = _df_to_records(_filter_by_code(df, code))
    else:
        data.blocks["lhb"] = []

    # =============================================================
    #  6. 财务核心指标
    # =============================================================
    print("━━━ [6/13] 财务核心指标 ━━━")
    fin_merged = {"bs_profit": [], "bs_growth": [], "bs_operation": [],
                  "bs_balance": [], "bs_cashflow": [], "bs_dupont": [],
                  "ak_fin_abstract": [], "ak_indicator": []}

    if use_bs:
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

    # =============================================================
    #  7. 三大报表
    # =============================================================
    print("━━━ [7/13] 三大报表 ━━━")
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
    #  8. 业绩预告/快报
    # =============================================================
    print("━━━ [8/13] 业绩预告/快报 ━━━")
    yjyg_all, yjkb_all = [], []
    if use_ak:
        for p in ["20240331", "20240630", "20240930", "20241231"]:
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
    #  9. 股东结构
    # =============================================================
    print("━━━ [9/13] 股东结构 ━━━")
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
    #  10. 分红/解禁
    # =============================================================
    print("━━━ [10/13] 分红 / 解禁 ━━━")
    dividend = []
    if use_bs:
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
    #  11. 公告/新闻/研报
    # =============================================================
    print("━━━ [11/13] 公告 / 新闻 / 研报 ━━━")
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
    #  12. 机构评级 / 基金持仓
    # =============================================================
    print("━━━ [12/13] 机构评级 / 基金持仓 ━━━")
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
    #  13. 融资融券
    # =============================================================
    print("━━━ [13/13] 融资融券 ━━━")
    if use_ak:
        if market == "sh":
            df = _safe_call_ak(ak.stock_margin_detail_sse, date=month_ago_s,
                               label=f"上交所融资融券({month_ago_s})")
        else:
            df = _safe_call_ak(ak.stock_margin_detail_szse, date=month_ago_s,
                               label=f"深交所融资融券({month_ago_s})")
        data.blocks["margin"] = _df_to_records(_filter_by_code(df, code))
    else:
        data.blocks["margin"] = []

    return data


# ============================================================
#  THS问财查询（独立功能）
# ============================================================

def wencai_query(condition: str, limit: int = 30) -> list[dict]:
    """问财自然语言查询。"""
    if not _has_ths:
        print("[X] thsdk not installed, cannot query wencai")
        return []
    with THS() as ths:
        resp = ths.wencai_nlp(condition)
        if not resp or resp.df is None or resp.df.empty:
            print(f"[问财] 无结果: {condition}")
            return []
        df = resp.df.head(limit).copy()
        # 转换代码为 THSCODE
        if "股票代码" in df.columns:
            df["ths_code"] = df["股票代码"].apply(to_ths_code)
        records = _df_to_records(df)
        print(f"  ✓ [ths] 问财查询: {len(records)} 条")
        return records


# ============================================================
#  THS板块/指数查询（独立功能）
# ============================================================

def sector_index_query() -> dict:
    """板块涨幅排名 + 主要指数行情。"""
    result = {}
    if not _has_ths:
        return result
    with THS() as ths:
        # 行业板块涨幅
        resp = ths.ths_industry()
        if resp and resp.data:
            result["industry_list"] = [{"code": r["代码"], "name": r["名称"]}
                                        for r in resp.data[:100]]
        # 概念板块
        resp = ths.ths_concept()
        if resp and resp.data:
            result["concept_list"] = [{"code": r["代码"], "name": r["名称"]}
                                       for r in resp.data[:100]]
        # 主要指数行情
        indices = ["USHI000001", "USHI000300", "USHI000905",
                   "USHI000852", "USHI000016", "USHI000688", "USHI000510"]
        resp = ths.market_data_index(indices)
        result["index_data"] = _ths_wrapper("主要指数行情", resp)
    return result


# ============================================================
#  Main
# ============================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="个股深度分析系统 — 三源整合版（BaoStock+akshare+thsdk）")
    parser.add_argument("code", nargs="?", help="6 位 A 股代码")
    parser.add_argument("--mode", choices=["ths-enhanced", "hybrid", "bs-only",
                                            "ak-only", "ths-only", "ba+ths"],
                        default="ths-enhanced",
                        help="数据源模式（默认 ths-enhanced=三源全开）")
    parser.add_argument("--no-ths", action="store_true",
                        help="关闭 thsdk（回退到原 hybrid 行为）")
    parser.add_argument("--max-kline-years", type=int, default=3,
                        help="日 K 拉取年限（默认 3 年）")
    parser.add_argument("--only-ths", action="store_true",
                        help="同 --mode ths-only")
    parser.add_argument("--wencai", type=str, default=None,
                        help="问财查询条件（如 '连续3日主力净流入，非ST'）")
    parser.add_argument("--sector", action="store_true",
                        help="查询板块/指数行情")
    parser.add_argument("--save", action="store_true", default=True,
                        help="保存到 JSON 文件（默认保存）")
    args = parser.parse_args()

    # 特殊模式
    if args.only_ths:
        args.mode = "ths-only"

    # 问财查询独立入口
    if args.wencai:
        records = wencai_query(args.wencai)
        print(json.dumps(records, ensure_ascii=False, indent=2))
        return

    # 板块查询独立入口
    if args.sector:
        sector_data = sector_index_query()
        print(json.dumps(sector_data, ensure_ascii=False, indent=2, default=str))
        return

    # 个股数据采集
    code = args.code or input("请输入 6 位 A 股代码：").strip()
    if not code:
        print("[X] 未输入股票代码", file=sys.stderr)
        sys.exit(1)

    try:
        prefixed, market, bs_code = detect_market(code)
    except ValueError as e:
        print(f"[X] {e}", file=sys.stderr)
        sys.exit(1)

    t0 = time.perf_counter()
    data = collect(code, max_kline_years=args.max_kline_years,
                   mode=args.mode, no_ths=args.no_ths)
    elapsed = time.perf_counter() - t0

    n_blocks = sum(1 for v in data.blocks.values() if isinstance(v, (list, dict)) and v)
    n_total_rows = sum(len(v) for v in data.blocks.values() if isinstance(v, list))
    # count rows inside dict blocks
    for v in data.blocks.values():
        if isinstance(v, dict):
            for subv in v.values():
                if isinstance(subv, list):
                    n_total_rows += len(subv)
                elif isinstance(subv, dict):
                    for subsubv in subv.values():
                        if isinstance(subsubv, list):
                            n_total_rows += len(subsubv)

    print(f"\n✅ 数据采集完成：{n_blocks} 个数据块，"
          f"共 ~{n_total_rows} 行，用时 {elapsed:.1f}s")

    if args.save:
        output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
        os.makedirs(output_dir, exist_ok=True)
        json_path = os.path.join(output_dir, f"data_{code}_ths.json")
        json_payload = {"blocks": data.blocks, "data_mode": data.data_mode}
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(json_payload, f, ensure_ascii=False, default=str)
        print(f"📊 JSON数据已保存：{json_path}")
        print(f"   含 thsdk 数据块: {list(data.blocks.get('ths', {}).keys())}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n已中断")
    except Exception:
        traceback.print_exc()
        sys.exit(1)
