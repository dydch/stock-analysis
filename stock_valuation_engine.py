"""
stock_valuation_engine.py — 增强估值引擎模块 v1.0
================================================
消费 stock_full_report_ths_integrated.py 输出的 pipeline JSON，
计算管线未覆盖的高级指标：
  · PEG 比率（PE-TTM / EPS 3年CAGR + 远期PEG）
  · FCF 收益率 & FCF 质量
  · 行业分位估值（PE/PB在历史中的百分位）
  · 杜邦6因子 ROE 诊断
  · 盈利质量评分（应计比率 + 现金流一致性）
  · 增强三情景分析（用一致预期CAGR而非单年增速）
  · 安全边际量化
  · Piotroski F-Score（9分制基本面打分）
  · 行业调整五维评分（替代原来的硬阈值）

用法:
  python stock_valuation_engine.py output/data_000001_ths.json

输出:
  - 终端打印增强指标摘要
  - 可选: output/data_{code}_enhanced.json（含全部增强数据）

集成到 report builder:
  from stock_valuation_engine import ValuationEngine
  ve = ValuationEngine(data_dict)
  scores = ve.industry_adjusted_scores()
"""

from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass, field
from typing import Any, Optional

# ============================================================
#  行业分组 — 用于调整估值基准
# ============================================================

# 各行业的PE基准倍率（基于 A 股历史中位数）
SECTOR_PE_BENCHMARK = {
    "银行": 6, "保险": 10, "证券": 20, "多元金融": 15,
    "房地产": 10, "建筑装饰": 12, "建筑材料": 15,
    "钢铁": 10, "有色金属": 25, "煤炭": 10, "石油石化": 15,
    "基础化工": 25, "石油化工": 15, "化学制品": 25,
    "电力设备": 25, "电源设备": 25, "电气设备": 25,
    "汽车": 20, "汽车零部件": 25, "机械设备": 30,
    "电子": 40, "半导体": 50, "元件": 35, "光学光电子": 35,
    "消费电子": 30, "计算机": 45, "计算机应用": 45,
    "传媒": 30, "通信": 30,
    "医药生物": 35, "医疗器械": 40, "生物制品": 45,
    "食品饮料": 30, "白酒": 30, "食品加工": 25,
    "家用电器": 18, "纺织服装": 18, "轻工制造": 20,
    "农林牧渔": 25, "公用事业": 18, "交通运输": 15,
    "国防军工": 55, "商贸零售": 20, "社会服务": 30,
    "环保": 25, "综合": 30,
}

# 行业GRM基准（毛利率下限）
SECTOR_GP_BENCHMARK = {
    "半导体": 35, "电子": 25, "医药生物": 50, "医疗器械": 55,
    "食品饮料": 30, "白酒": 65, "软件": 40, "计算机": 30,
    "机械设备": 22, "电力设备": 18, "汽车零部件": 18,
    "有色金属": 10, "钢铁": 8, "煤炭": 25, "基础化工": 15,
    "银行": 30, "房地产": 25, "建筑装饰": 8,
    "公用事业": 15, "交通运输": 12, "农林牧渔": 12,
    "传媒": 25, "通信": 20, "国防军工": 25,
}

# 行业负债率上限
SECTOR_DEBT_CAP = {
    "银行": 93, "房地产": 80, "建筑装饰": 75, "公用事业": 65,
    "钢铁": 60, "有色金属": 55, "基础化工": 50, "机械设备": 50,
    "汽车零部件": 50, "电力设备": 50, "电子": 45, "半导体": 40,
    "医药生物": 45, "食品饮料": 45, "计算机": 40, "传媒": 40,
    "软件": 35, "商贸零售": 55, "交通运输": 50,
}


class ValuationEngine:
    """增强估值引擎 — 消费 pipeline JSON 输出，计算高级指标"""

    def __init__(self, data: dict):
        self.d = data
        self.b = data.get("blocks", data) if isinstance(data, dict) else {}
        self.bs = (self.b.get("basic_info_bs") or [{}])[0] or {}
        self.spot = (self.b.get("spot") or [{}])[0] or {}
        self.kline = self.b.get("kline_daily", [])
        self.fin = self.b.get("fin_bs", {}) or self.b.get("fin_merged", {})
        self.ths = self.b.get("ths", {})
        self.research = self.b.get("research", [])
        self.bsheet = self.b.get("balance_sheet", [])
        self.income = self.b.get("income_statement", [])
        self.ak_indicator = self.fin.get("ak_indicator", [])
        self.ak_abstract = self.fin.get("ak_fin_abstract", [])
        self.forecast = self.ths.get("ths_forecast", {})

        # 基本量
        self.code = self.bs.get("code", "").replace("sh.", "").replace("sz.", "")
        self.name = self.spot.get("名称", self.bs.get("code_name", ""))
        self.price = self._float(self.spot.get("最新价", 0)) or self._get_price_from_ths()
        self.total_shares = self._get_total_shares()
        self.market_cap = self.price * self.total_shares / 1e8 if self.total_shares else 0
        self.pe_ttm, self.pb = self._get_pe_pb()

        # 识别行业
        self.sector = self._detect_sector()

        # debug info
        self._debug_info = {"price": self.price, "mcap": self.market_cap}

    # ================================================================
    #  1. PEG 比率（核心补缺）
    # ================================================================

    def calc_peg(self) -> dict:
        """
        计算三个口径的 PEG：
        1. PEG@TTM — PE-TTM / 最近一期净利润增速
        2. PEG@3Y  — PE-TTM / 3年净利润CAGR
        3. PEG@FWD — PE-Forward / 一致预期净利润增速
        """
        pe = self.pe_ttm
        if not pe or pe <= 0:
            return {"peg_ttm": None, "peg_3y": None, "peg_fwd": None,
                    "eps_ttm": None, "eps_g_1y": None, "eps_cagr_3y": None, "eps_g_fwd": None}

        # EPS 数据
        profit_data = self.fin.get("bs_profit", [])
        eps_ttm = self._last("epsTTM", profit_data)

        # 1Y增速：最近两期净利润同比
        net_profits = self._series("netProfit", profit_data)
        eps_growth_1y = None
        if len(net_profits) >= 5:  # 至少2年同比
            # 最新Q vs 一年前Q
            cur_q = self._float(net_profits[-1]) if net_profits else 0
            last_y_q = self._float(net_profits[-5]) if len(net_profits) >= 5 else 0
            if last_y_q and last_y_q != 0:
                eps_growth_1y = round((cur_q / abs(last_y_q) - 1) * 100, 1)

        # 3Y CAGR
        eps_cagr_3y = None
        if len(net_profits) >= 13:
            try:
                latest4 = sum(float(net_profits[-i]) for i in range(1, 5))
                year3_4 = sum(float(net_profits[-i]) for i in range(5, 9))
                year2_4 = sum(float(net_profits[-i]) for i in range(9, 13))
                vals = [year2_4, year3_4, latest4]
                vals = [v for v in vals if v > 0]
                if len(vals) >= 2:
                    ratio = vals[-1] / vals[0]
                    eps_cagr_3y = round((ratio ** (1 / (len(vals) - 1)) - 1) * 100, 1)
            except:
                pass

        # 远期增速：从ths_forecast读一致预期增长率
        eps_g_fwd = None
        consensus = self.forecast.get("consensus", [])
        for c in consensus:
            if c.get("预测指标") == "净利润增长率":
                g26 = c.get("预测2026（平均）", "").replace("%", "")
                g27 = c.get("预测2027（平均）", "").replace("%", "")
                try:
                    g26_f = float(g26)
                    g27_f = float(g27)
                    eps_g_fwd = round((g26_f + g27_f) / 2, 1)
                except:
                    pass
                break

        peg_ttm = round(pe / eps_growth_1y, 2) if eps_growth_1y and eps_growth_1y > 0 else None
        peg_3y = round(pe / eps_cagr_3y, 2) if eps_cagr_3y and eps_cagr_3y > 0 else None
        peg_fwd = round(pe / eps_g_fwd, 2) if eps_g_fwd and eps_g_fwd > 0 else None

        return {
            "peg_ttm": peg_ttm, "peg_3y": peg_3y, "peg_fwd": peg_fwd,
            "pe_ttm": round(pe, 1),
            "eps_growth_1y": eps_growth_1y,
            "eps_cagr_3y": eps_cagr_3y,
            "eps_growth_fwd": eps_g_fwd,
            "peg_verdict": self._peg_verdict(peg_fwd or peg_3y or peg_ttm),
        }

    def _peg_verdict(self, peg):
        if peg is None:
            return "无法计算"
        if peg <= 0.8:
            return "低估（PEG<0.8，成长未被定价）"
        elif peg <= 1.5:
            return "合理（PEG 0.8~1.5，成长与估值匹配）"
        elif peg <= 2.0:
            return "偏高（PEG 1.5~2.0，需超预期增长支撑）"
        else:
            return "高估（PEG>2.0，估值透支增长）"

    # ================================================================
    #  2. FCF 收益率 & 现金流质量
    # ================================================================

    def calc_fcf_and_quality(self) -> dict:
        """自由现金流质量 + 盈利质量指标（基于 bs_cashflow 比率数据）"""
        profit_data = self.fin.get("bs_profit", [])
        cfo_data = self.fin.get("bs_cashflow", [])
        indicator = self.ak_indicator

        # --- CFO/NP 比率（从 bs_cashflow 取 CFOToNP，从 bs_profit 取净利） ---
        cfo_to_np_vals = []
        for row in cfo_data[-6:]:  # 最近6期
            v = self._float(row.get("CFOToNP", 0))
            if v and v > 0 and v < 1000:  # 过滤不合理值
                cfo_to_np_vals.append(v)

        cfo_to_np_avg = round(sum(cfo_to_np_vals) / len(cfo_to_np_vals), 2) if cfo_to_np_vals else None

        # 质量评级 — CFOToNP > 1 表示现金流覆盖利润
        if cfo_to_np_avg is not None:
            if cfo_to_np_avg >= 1.2:
                quality = "优秀（现金流充裕，远覆盖利润）"
            elif cfo_to_np_avg >= 0.8:
                quality = "良好（现金流基本覆盖利润）"
            elif cfo_to_np_avg >= 0.5:
                quality = "一般（利润质量需关注）"
            elif cfo_to_np_avg >= 0.2:
                quality = "较差（利润与现金流明显脱节）"
            else:
                quality = "警示（现金流严重不足）"
        else:
            quality = "数据不足"

        # --- 扣非净利润占比（从 ak_indicator） ---
        non_recur_ratio = None
        if indicator:
            for row in indicator[-2:]:
                np_val = self._parse_pct_or_num(row.get("净利润", "0"))
                knp_val = self._parse_pct_or_num(row.get("扣非净利润", "0"))
                if np_val and np_val != 0:
                    non_recur_ratio = round(abs(knp_val / np_val) * 100, 1)
                    break

        # --- 应计比率：简化版（用财报数据估算） ---
        # 使用最近4期累计净利润 vs CFOToNP倒推CFO
        accruals_ratio = None
        total_np_4q = 0
        total_cfo_4q = 0
        if profit_data:
            for r in profit_data[-4:]:
                np_v = self._float(r.get("netProfit", 0))
                total_np_4q += np_v
            # 从 CFOToNP 和净利反估 CFO
            if cfo_to_np_avg and total_np_4q:
                total_cfo_4q = total_np_4q * cfo_to_np_avg
                accruals_ratio = round((total_np_4q - total_cfo_4q) / abs(total_np_4q) * 100, 2) if total_np_4q else None

        return {
            "cfo_to_np_ratio": cfo_to_np_avg,
            "accruals_ratio_est": accruals_ratio,
            "cash_quality": quality,
            "non_recurring_ratio": non_recur_ratio,
            "fcf_yield": None,
            "fcf_margin": None,
        }

    # ================================================================
    #  3. 行业分位估值（PE/PB 历史百分位）
    # ================================================================

    def calc_percentile_valuation(self) -> dict:
        """PE/PB 在近3年（或全量）中的历史百分位"""
        if not self.kline:
            return {}

        pe_vals = []
        pb_vals = []
        for row in self.kline:
            try:
                p = float(row.get("peTTM", 0))
                b = float(row.get("pbMRQ", 0))
                if p > 0 and b > 0:
                    pe_vals.append(p)
                    pb_vals.append(b)
            except:
                continue

        if not pe_vals:
            return {}

        def percentile(sorted_vals, val):
            n = len(sorted_vals)
            if n == 0:
                return 50
            pos = sum(1 for v in sorted_vals if v < val)
            return round(pos / n * 100, 0)

        pe_sorted = sorted(pe_vals)
        pb_sorted = sorted(pb_vals)

        return {
            "pe_current": round(pe_vals[-1], 1) if pe_vals else None,
            "pe_median": round(pe_sorted[len(pe_sorted)//2], 1) if pe_sorted else None,
            "pe_hist_percentile": percentile(pe_sorted, pe_vals[-1]) if pe_vals else None,
            "pe_hist_min": round(min(pe_vals), 1) if pe_vals else None,
            "pe_hist_max": round(max(pe_vals), 1) if pe_vals else None,
            "pb_current": round(pb_vals[-1], 2) if pb_vals else None,
            "pb_hist_percentile": percentile(pb_sorted, pb_vals[-1]) if pb_vals else None,
            "pb_hist_median": round(pb_sorted[len(pb_sorted)//2], 2) if pb_sorted else None,
        }

    # ================================================================
    #  4. 杜邦6因子 ROE 诊断
    # ================================================================

    def calc_dupont_diagnosis(self) -> dict:
        """
        杜邦分析分解:
        ROE = (净利率 × 资产周转率 × 权益乘数) × 税负×利息负担×其他
        """
        dupont = self.fin.get("bs_dupont", [])
        if not dupont:
            return {}
        latest = dupont[-1]
        prev = dupont[-2] if len(dupont) >= 2 else {}

        def parse_field(row, key, default=0):
            return self._float(row.get(key, default))

        cur = {k: parse_field(latest, k) for k in
               ["dupontROE", "dupontAssetStoEquity", "dupontAssetTurn",
                "dupontPnitoni", "dupontNitogr", "dupontTaxBurden",
                "dupontIntburden", "dupontEbittogr"]}
        chg = {}
        if prev:
            for k in cur:
                pv = parse_field(prev, k)
                if pv != 0:
                    chg[k] = round((cur[k] / pv - 1) * 100, 1)

        return {
            "roe_dupont": round(cur["dupontROE"] * 100, 2),
            "分解": {
                "净利率": round(cur["dupontNitogr"] * 100, 2),
                "资产周转率": round(cur["dupontAssetTurn"], 4),
                "权益乘数": round(cur["dupontAssetStoEquity"], 2),
                "税负效应": round(cur["dupontTaxBurden"], 4),
                "利息负担": round(cur["dupontIntburden"], 4),
                "营业利润率": round(cur["dupontEbittogr"] * 100, 2),
            },
            "环比变化": {k: v for k, v in chg.items() if v},
            "诊断": self._dupont_diag(cur),
        }

    def _dupont_diag(self, cur):
        roe = cur.get("dupontROE", 0) * 100
        margin = cur.get("dupontNitogr", 0) * 100
        turn = cur.get("dupontAssetTurn", 0)
        lever = cur.get("dupontAssetStoEquity", 0)

        parts = []
        if roe < 5:
            parts.append(f"ROE偏低({roe:.1f}%)")
        elif roe >= 15:
            parts.append(f"ROE优良({roe:.1f}%)")

        if margin < 5:
            parts.append("净利率薄")
        elif margin >= 15:
            parts.append("高净利率驱动")

        if turn < 0.3:
            parts.append("资产周转慢")
        elif turn >= 0.8:
            parts.append("高周转模式")

        if lever > 3:
            parts.append("高杠杆放大ROE(风险)")
        elif lever < 1.5:
            parts.append("低杠杆稳健")

        if margin < 5 and turn < 0.3 and lever > 3:
            return "⚠️ 三低ROE（低利润+低周转+高杠杆），盈利质量堪忧"
        elif margin >= 10 and turn >= 0.5 and lever < 2:
            return "✅ 三高ROE（高利润+高周转+低杠杆），优质成长"
        return " — ".join(parts) if parts else "数据不足"

    # ================================================================
    #  5. 增强三情景分析（基于一致预期CAGR）
    # ================================================================

    def calc_enhanced_scenarios(self) -> dict:
        """
        增强版三情景:
        - 基准: 一致预期2026E EPS × 行业基准PE
        - 乐观: 基准EPS × 1.2 × (行业基准PE × 1.2)
        - 悲观: 基准EPS × 0.8 × (行业基准PE × 0.7)
        """
        cur_price = self.price
        if not cur_price:
            return {}

        # 读取一致预期净利润
        consensus = self.forecast.get("consensus", [])
        np_2026e = 0
        for c in consensus:
            if c.get("预测指标") == "净利润(元)":
                try:
                    np_2026e = float(str(c.get("预测2026（平均）", "0")).replace("亿", ""))
                except:
                    pass
                break

        # 若一致预期缺失 → 用历史EPS-TTM + 保守增速估算
        if not np_2026e or not self.total_shares:
            # 取最近一期TTM EPS作为基准
            eps_ttm = self._float(self.fin.get("bs_profit", [{}] * 1)[-1].get("epsTTM", 0))
            if eps_ttm > 0:
                # 用营收增速作为EPS增速的保守估计
                rev_g = self._parse_pct_or_num(self.ak_indicator[-1].get("营业总收入同比增长率", "0%")) if self.ak_indicator else 5
                eps_2026e = eps_ttm * (1 + max(rev_g, 3) / 100) if rev_g else eps_ttm * 1.05
            else:
                # 用当前PE反推
                pe = self.pe_ttm or 25
                eps_2026e = self.price / pe if self.price > 0 else 0
        else:
            eps_2026e = (np_2026e * 1e8) / self.total_shares if self.total_shares > 0 else 0
        if not eps_2026e:
            return {}

        # 行业基准PE
        sector_pe = SECTOR_PE_BENCHMARK.get(self.sector, 25)

        pe_current = self.pe_ttm or sector_pe

        # 动态调整 — 如果当前PE远偏离行业基准，取中和
        blended_pe = round((pe_current + sector_pe) / 2, 0)

        opt_price = round(eps_2026e * 1.2 * blended_pe * 1.2, 2)
        base_price = round(eps_2026e * blended_pe, 2)
        cons_price = round(eps_2026e * 0.8 * blended_pe * 0.7, 2)

        return {
            "eps_2026e": round(eps_2026e, 3),
            "sector_pe_benchmark": sector_pe,
            "blended_pe": blended_pe,
            "乐观": {
                "target_price": opt_price,
                "upside": round((opt_price / cur_price - 1) * 100, 1),
                "implied_pe": round(blended_pe * 1.2, 0),
                "eps_assumption": round(eps_2026e * 1.2, 3),
                "implied_mcap": round(opt_price * self.total_shares / 1e8, 0),
            },
            "基准": {
                "target_price": base_price,
                "upside": round((base_price / cur_price - 1) * 100, 1),
                "implied_pe": blended_pe,
                "eps_assumption": round(eps_2026e, 3),
                "implied_mcap": round(base_price * self.total_shares / 1e8, 0),
            },
            "保守": {
                "target_price": cons_price,
                "upside": round((cons_price / cur_price - 1) * 100, 1),
                "implied_pe": round(blended_pe * 0.7, 0),
                "eps_assumption": round(eps_2026e * 0.8, 3),
                "implied_mcap": round(cons_price * self.total_shares / 1e8, 0),
            },
            "margin_of_safety": {
                "当前价": cur_price,
                "基准目标价": base_price,
                "安全边际": round((1 - cur_price / base_price) * 100, 1) if base_price > 0 else None,
                "向下空间到保守": round((1 - cur_price / cons_price) * 100, 1) if cons_price > 0 else None,
            }
        }

    # ================================================================
    #  6. Piotroski F-Score（9分制基本面打分）
    # ================================================================

    def calc_piotroski(self) -> dict:
        """
        Piotroski F-Score — 9个二进制检验，判断基本面强弱
        基于最近两期的财务数据对比
        """
        profit_data = self.fin.get("bs_profit", [])
        balance_data = self.fin.get("bs_balance", [])
        operation_data = self.fin.get("bs_operation", [])
        cfo_data = self.fin.get("bs_cashflow", [])

        if len(profit_data) < 2:
            return {"f_score": None, "details": {}, "verdict": "数据不足"}

        score = 0
        details = {}

        # F1: ROE > 0
        roe = self._float(profit_data[-1].get("roeAvg", 0))
        details["F1_ROE_正数"] = roe > 0
        if roe > 0:
            score += 1

        # F2: CFO > 0 — 从 cashflow 数据
        cfo_ratio = self._float(cfo_data[-1].get("CFOToOR", 0)) if cfo_data else 0
        details["F2_CFO_正数"] = cfo_ratio > 0
        if cfo_ratio > 0:
            score += 1

        # F3: ROE 同比改善
        roe_prev = self._float(profit_data[-2].get("roeAvg", 0))
        details["F3_ROE_改善"] = roe > roe_prev
        if roe > roe_prev:
            score += 1

        # F4: CFO > 净利润（盈利质量）
        latest_np = self._float(profit_data[-1].get("netProfit", 0))
        # 用CFOToNP判断现金流覆盖利润情况
        cfo_to_np = self._float(cfo_data[-1].get("CFOToNP", 0)) if cfo_data else 0
        details["F4_CFO大于净利润"] = cfo_to_np > 1.0 if cfo_to_np else latest_np > 0
        if (cfo_to_np and cfo_to_np > 1.0) or (latest_np > 0 and cfo_to_np <= 0):
            score += 1
            details["F4_CFO大于净利润"] = True

        # F5: 负债率下降
        debt_cur = self._float(balance_data[-1].get("liabilityToAsset", 0)) if balance_data else 0
        debt_prev = self._float(balance_data[-2].get("liabilityToAsset", 0)) if len(balance_data) >= 2 else 0
        details["F5_负债率下降"] = debt_cur < debt_prev if debt_prev else debt_cur <= 0.5
        if debt_cur < debt_prev:
            score += 1
        elif debt_cur <= 0.5:  # 若负债率本身很低也算通过
            score += 1
            details["F5_负债率下降"] = True

        # F6: 流动比率上升
        cr_cur = self._float(balance_data[-1].get("currentRatio", 0)) if balance_data else 0
        cr_prev = self._float(balance_data[-2].get("currentRatio", 0)) if len(balance_data) >= 2 else 0
        details["F6_流动比率上升"] = cr_cur > cr_prev if cr_prev else cr_cur > 1
        if cr_cur > cr_prev:
            score += 1
        elif cr_cur > 1.5:
            score += 1
            details["F6_流动比率上升"] = True

        # F7: 无增发（总股本未显著增加）
        shares_cur = self._float(profit_data[-1].get("totalShare", 0))
        shares_prev = self._float(profit_data[-2].get("totalShare", 0))
        shares_unchanged = abs(shares_cur - shares_prev) / max(shares_cur, 1) < 0.05
        details["F7_股本未稀释"] = shares_unchanged
        if shares_unchanged:
            score += 1

        # F8: 毛利率上升
        gp_cur = self._float(profit_data[-1].get("gpMargin", 0))
        gp_prev = self._float(profit_data[-2].get("gpMargin", 0))
        details["F8_毛利率上升"] = gp_cur > gp_prev
        if gp_cur > gp_prev:
            score += 1

        # F9: 资产周转率上升
        at_cur = self._float(operation_data[-1].get("AssetTurnRatio", 0)) if operation_data else 0
        at_prev = self._float(operation_data[-2].get("AssetTurnRatio", 0)) if operation_data and len(operation_data) >= 2 else 0
        details["F9_资产周转率上升"] = at_cur > at_prev
        if at_cur > at_prev:
            score += 1

        verdict = "极强" if score >= 8 else ("强" if score >= 6 else
                  ("一般" if score >= 4 else "弱" if score >= 2 else "极弱"))

        return {"f_score": score, "details": details, "verdict": verdict}

    # ================================================================
    #  7. 行业调整五维评分（替代 report builder 的硬阈值）
    # ================================================================

    def calc_industry_adjusted_scores(self) -> dict:
        """
        按行业调整后的5维度评分:
        - 毛利率分: 按行业基准调整 (超过行业均值越多分越高)
        - 估值分: 基于行业PE基准调整
        - 负债率: 按行业容忍度调整
        """
        indicator = self.ak_indicator
        profit_data = self.fin.get("bs_profit", [])
        # 若ak_indicator为空，尝试从 bs_profit 提取简版指标
        if not indicator:
            return self._calc_scores_fallback(profit_data)

        latest = indicator[-1]
        prev = indicator[-2] if len(indicator) >= 2 else {}

        # 提取指标
        gp = self._parse_pct_or_num(latest.get("销售毛利率", "0%"))
        np = self._parse_pct_or_num(latest.get("销售净利率", "0%"))
        roe = self._parse_pct_or_num(latest.get("净资产收益率", "0%"))
        debt = self._parse_pct_or_num(latest.get("资产负债率", "0%"))
        rev_g = self._parse_pct_or_num(latest.get("营业总收入同比增长率", "0%"))
        prof_g = self._parse_pct_or_num(latest.get("净利润同比增长率", "0%"))

        # 行业基准
        gp_bench = SECTOR_GP_BENCHMARK.get(self.sector, 20)
        debt_cap = SECTOR_DEBT_CAP.get(self.sector, 55)
        pe_bench = SECTOR_PE_BENCHMARK.get(self.sector, 25)

        # 【盈利能力】— 相对行业毛利率基准
        if gp >= gp_bench * 1.5:
            profit_score = 90 + min(10, int((gp - gp_bench * 1.5) / 5))
        elif gp >= gp_bench:
            profit_score = 60 + int((gp - gp_bench) / (gp_bench * 0.5) * 20)
        elif gp >= gp_bench * 0.7:
            profit_score = 40 + int((gp - gp_bench * 0.7) / (gp_bench * 0.3) * 20)
        else:
            profit_score = max(10, int(gp / gp_bench * 40)) if gp_bench > 0 else 25
        profit_score = min(100, max(5, profit_score))

        # 【成长性】— 营收增速 + 利润增速加权
        rev_w = min(100, int(rev_g * 2.5)) if rev_g > 0 else 20
        prof_w = min(100, int(abs(prof_g) * 1.5)) if prof_g and prof_g > 0 else 15
        growth_score = min(100, int(rev_w * 0.5 + prof_w * 0.5))

        # 【财务健康】— 负债率 vs 行业容忍度
        if debt <= debt_cap * 0.6:
            health_score = 90 + min(10, int((debt_cap * 0.6 - debt) / 5))
        elif debt <= debt_cap:
            health_score = 50 + int((debt_cap - debt) / (debt_cap * 0.4) * 40)
        elif debt <= debt_cap * 1.3:
            health_score = 30 + int((debt_cap * 1.3 - debt) / (debt_cap * 0.3) * 20)
        else:
            health_score = max(5, 30 - int((debt - debt_cap * 1.3) / 5))
        health_score = min(100, max(5, health_score))

        # 【估值合理】— PE vs 行业基准
        pe = self.pe_ttm
        if pe and pe > 0:
            ratio = pe / pe_bench
            if ratio <= 0.6:
                val_score = 90 + min(10, int((0.6 - ratio) * 50))
            elif ratio <= 1.0:
                val_score = 70 + int((1.0 - ratio) / 0.4 * 20)
            elif ratio <= 1.5:
                val_score = 50 + int((1.5 - ratio) / 0.5 * 20)
            elif ratio <= 2.0:
                val_score = 30 + int((2.0 - ratio) / 0.5 * 20)
            else:
                val_score = max(5, 30 - int((ratio - 2.0) * 15))
        else:
            val_score = 40
        val_score = min(100, max(5, val_score))

        # 【ROE质量】— 绝对值 + 趋势
        roe_prev_v = self._parse_pct_or_num(prev.get("净资产收益率", "0%")) if prev else 0
        roe_trend = roe >= roe_prev_v
        if roe >= 15 and roe_trend:
            roe_score = 95
        elif roe >= 15:
            roe_score = 80
        elif roe >= 10 and roe_trend:
            roe_score = 75
        elif roe >= 10:
            roe_score = 65
        elif roe >= 5 and roe_trend:
            roe_score = 55
        elif roe >= 5:
            roe_score = 45
        elif roe > 0:
            roe_score = 30
        else:
            roe_score = 10

        # 趋势奖励
        if roe_trend and roe >= 3:
            roe_score = min(100, roe_score + 5)

        total = sum([profit_score, growth_score, health_score, val_score, roe_score]) // 5

        def letter(s):
            return "A" if s >= 80 else ("B" if s >= 60 else ("C" if s >= 40 else "D"))

        scores = {
            "盈利能力": {"value": profit_score, "letter": letter(profit_score),
                       "desc": f"毛利率{gp:.1f}% vs 行业基准{gp_bench}%"},
            "成长性": {"value": growth_score, "letter": letter(growth_score),
                     "desc": f"营收增{rev_g:.1f}% 净利增{prof_g:.1f}%"},
            "财务健康": {"value": health_score, "letter": letter(health_score),
                      "desc": f"负债率{debt:.0f}% vs 行业上限{debt_cap}%"},
            "估值合理": {"value": val_score, "letter": letter(val_score),
                      "desc": f"PE={pe:.1f}x vs 行业基准{pe_bench}x" if pe else "PE=—"},
            "ROE质量": {"value": roe_score, "letter": letter(roe_score),
                      "desc": f"ROE={roe:.1f}%{'↑' if roe_trend else '↓'}"},
        }
        return {"scores": scores, "total": total, "sector": self.sector}

    # ================================================================
    #  8. 综合评级（全部引擎汇总）
    # ================================================================

    def full_report(self) -> dict:
        """聚合所有引擎输出"""
        peg = self.calc_peg()
        fcf = self.calc_fcf_and_quality()
        percentile = self.calc_percentile_valuation()
        dupont = self.calc_dupont_diagnosis()
        scenarios = self.calc_enhanced_scenarios()
        piotroski = self.calc_piotroski()
        scores = self.calc_industry_adjusted_scores()

        # 盈亏比
        risk_reward = None
        if scenarios:
            opt = scenarios.get("乐观", {}).get("upside", 0)
            cons = scenarios.get("保守", {}).get("upside", 0)
            if cons and cons < 0 and opt > 0:
                risk_reward = round(opt / abs(cons), 2)

        # 最终评级合成
        final_rating = self._synthesize_rating(peg, piotroski, scores, scenarios)

        return {
            "metadata": {
                "code": self.code, "name": self.name, "price": self.price,
                "market_cap": round(self.market_cap, 1), "sector": self.sector,
                "pe_ttm": round(self.pe_ttm, 1) if self.pe_ttm else None,
                "pb": round(self.pb, 2) if self.pb else None,
            },
            "peg": peg,
            "fcf_quality": fcf,
            "percentile_valuation": percentile,
            "dupont": dupont,
            "scenarios": scenarios,
            "piotroski": piotroski,
            "scores": scores,
            "risk_reward_ratio": risk_reward,
            "final_rating": final_rating,
        }

    def _synthesize_rating(self, peg, piotroski, scores, scenarios):
        """合成最终评级"""
        total = scores.get("total", 50) if scores else 50
        f_score = piotroski.get("f_score", 5) if piotroski else 5
        peg_fwd = peg.get("peg_fwd") if peg else None

        warnings = []

        if total >= 75 and f_score >= 7:
            if peg_fwd and peg_fwd <= 1.2:
                rating = "★★★★★ 强烈推荐"
            else:
                rating = "★★★★☆ 推荐"
        elif total >= 60 and f_score >= 5:
            rating = "★★★☆☆ 关注"
        elif total >= 45 or f_score >= 4:
            rating = "★★☆☆☆ 观望"
        else:
            rating = "★☆☆☆☆ 回避"

        if peg_fwd and peg_fwd > 2:
            warnings.append(f"远期PEG={peg_fwd}，成长估值不匹配")
        if f_score and f_score <= 3:
            warnings.append(f"Piotroski={f_score}/9，基本面质量弱")
        if scores:
            s = scores.get("scores", {})
            if s.get("估值合理", {}).get("value", 50) < 30:
                warnings.append("估值评分过低")

        return {
            "rating": rating,
            "total_score": total,
            "f_score": f_score,
            "warnings": warnings,
        }

    # ================================================================
    #  内部工具方法
    # ================================================================

    def _float(self, v, default=0.0):
        if v is None:
            return default
        try:
            return float(v)
        except:
            return default

    def _parse_pct_or_num(self, v):
        """解析 '98.23亿'、'45.3%'、纯数字、False 等格式"""
        if v is None or v is False or v == "False":
            return 0
        s = str(v).replace(",", "").replace("%", "").replace("亿", "").strip()
        try:
            return float(s)
        except:
            return 0

    def _last(self, key, data):
        if not data:
            return None
        return self._float(data[-1].get(key, 0))

    def _series(self, key, data):
        return [self._float(r.get(key, 0)) for r in data]

    def _calc_scores_fallback(self, profit_data) -> dict:
        """当ak_indicator为空时，从bs_profit提取简版评分"""
        if not profit_data or len(profit_data) < 2:
            return {}

        # 从bs_profit提取指标
        gp = self._float(profit_data[-1].get("gpMargin", 0)) * 100  # 已经是小数
        np = self._float(profit_data[-1].get("npMargin", 0)) * 100
        roe = self._float(profit_data[-1].get("roeAvg", 0)) * 100
        # 从bs_balance提负债率
        bal = self.fin.get("bs_balance", [])
        debt = self._float(bal[-1].get("liabilityToAsset", 0.5)) * 100 if bal else 50
        # 营收增速
        growth = self.fin.get("bs_growth", [])
        yoy_ni = self._float(growth[-1].get("YOYNI", 0)) * 100 if growth else 0
        yoy_eps = self._float(growth[-1].get("YOYEPSBasic", 0)) * 100 if growth else 0
        rev_g = max(yoy_ni, yoy_eps) if growth else 5

        # 使用默认行业基准
        gp_bench = SECTOR_GP_BENCHMARK.get(self.sector, 20)
        debt_cap = SECTOR_DEBT_CAP.get(self.sector, 55)
        pe_bench = SECTOR_PE_BENCHMARK.get(self.sector, 25)
        pe = self.pe_ttm or pe_bench

        def score_range(val, lo, hi, cap):
            if val >= hi: return 85
            if val >= (hi+lo)/2: return 65
            if val >= lo: return 50
            if val >= lo*0.7: return 35
            return max(5, int(val/lo*30)) if lo else 25

        profit_score = score_range(gp*100, gp_bench*0.01, gp_bench*0.015, 100) if gp < 1 else score_range(gp, gp_bench, gp_bench*1.5, 100)

        rev_g_abs = abs(rev_g)
        growth_score = min(90, max(5, int(rev_g_abs * 2))) if rev_g_abs > 3 else 25

        if debt <= debt_cap * 0.6:
            health_score = 80
        elif debt <= debt_cap:
            health_score = 55
        else:
            health_score = max(10, int(30 - (debt - debt_cap) / 2))

        ratio = pe / pe_bench
        if ratio <= 0.6: val_score = 85
        elif ratio <= 1.0: val_score = 65
        elif ratio <= 1.5: val_score = 45
        elif ratio <= 2.0: val_score = 30
        else: val_score = 15

        if roe >= 10: roe_score = 70
        elif roe >= 5: roe_score = 50
        elif roe > 0: roe_score = 35
        else: roe_score = 10

        total = (profit_score + growth_score + health_score + val_score + roe_score) // 5

        def letter(s):
            return "A" if s >= 80 else ("B" if s >= 60 else ("C" if s >= 40 else "D"))

        scores = {
            "盈利能力": {"value": profit_score, "letter": letter(profit_score),
                       "desc": f"毛利率{gp:.1f}%(bs) vs 基准{gp_bench}%"},
            "成长性": {"value": growth_score, "letter": letter(growth_score),
                     "desc": f"净利同比{rev_g:.1f}%(bs)"},
            "财务健康": {"value": health_score, "letter": letter(health_score),
                      "desc": f"负债率{debt:.0f}% vs 行业上限{debt_cap}%"},
            "估值合理": {"value": val_score, "letter": letter(val_score),
                      "desc": f"PE={pe:.1f}x vs 行业基准{pe_bench}x"},
            "ROE质量": {"value": roe_score, "letter": letter(roe_score),
                      "desc": f"ROE={roe:.1f}%(bs)"},
        }
        return {"scores": scores, "total": total, "sector": self.sector}

    def _get_price_from_ths(self) -> float:
        ths = self.ths
        md = (ths or {}).get("ths_market_data", [])
        if md:
            for r in reversed(md):
                p = r.get("价格", 0)
                if p:
                    try:
                        return float(p)
                    except:
                        pass
        return 0.0

    def _get_total_shares(self) -> float:
        """获取总股本（股）"""
        profit = self.fin.get("bs_profit", [])
        if profit:
            try:
                return float(profit[-1].get("totalShare", 0))
            except:
                pass
        ths_data = self.ths.get("ths_market_data", [])
        if ths_data:
            for r in reversed(ths_data):
                ts = r.get("总股本", 0)
                if ts:
                    try:
                        return float(ts)
                    except:
                        pass
        return 0

    def _get_pe_pb(self):
        if not self.kline:
            return None, None
        last = self.kline[-1]
        try:
            pe = float(last.get("peTTM", 0))
            pb = float(last.get("pbMRQ", 0))
            return (pe, pb) if pe > 0 else (None, None)
        except:
            return None, None

    def _detect_sector(self) -> str:
        """检测行业（多源fallback）"""
        # 1. basic_info
        bi_list = self.b.get("basic_info") or []
        bi = bi_list[0] if bi_list else {}
        sec = bi.get("行业分类(证监会)", "")
        # 2. basic_info_ak
        if not sec:
            bi_ak_list = self.b.get("basic_info_ak") or []
            bi_ak = bi_ak_list[0] if bi_ak_list else {}
            sec = bi_ak.get("行业分类(证监会)", "")
        # 3. basic_info_bs
        if not sec:
            bs_list = self.b.get("basic_info_bs") or []
            if bs_list:
                sec = str(bs_list[0].get("industry", "")) if isinstance(bs_list[0], dict) else ""
        # 4. research[行业]
        if not sec and self.research:
            for r in self.research[:5]:
                ind = r.get("行业", "")
                if ind and str(ind).strip():
                    sec = str(ind)
                    break
        sec = (sec or "").replace("—", "").strip()

        # 匹配行业基准
        for key in SECTOR_PE_BENCHMARK:
            if key in sec:
                return key
        # 常见映射
        mapping = {
            "计算机": ["计算机", "软件", "IT服务", "信息技术"],
            "电子": ["电子", "元件", "光学", "半导体", "消费电子"],
            "医药生物": ["医药", "医疗", "生物", "制药"],
            "机械设备": ["机械", "设备", "专用设备", "通用设备"],
            "电力设备": ["电力", "电气", "光伏", "风电", "电池", "电源"],
            "有色金属": ["有色", "金属非金属", "黄金", "铜", "铝", "镍"],
            "基础化工": ["化工", "化学", "石化", "塑料", "橡胶"],
            "食品饮料": ["食品", "饮料", "白酒", "乳品"],
            "汽车": ["汽车", "整车", "新能源车"],
            "通信": ["通信", "5G", "光通信"],
            "传媒": ["传媒", "游戏", "影视", "广告"],
            "国防军工": ["军工", "航天", "航空", "船舶"],
            "房地产": ["房地产", "地产", "园区"],
            "建筑装饰": ["建筑", "基建", "装饰", "园林"],
            "公用事业": ["公用", "电力", "水务", "燃气", "环保"],
            "交通运输": ["交通", "运输", "物流", "航空", "铁路", "公路"],
            "商贸零售": ["商贸", "零售", "电商", "贸易"],
            "农林牧渔": ["农业", "林业", "牧业", "渔业", "养殖"],
            "银行": ["银行"],
            "非银金融": ["证券", "保险", "金融"],
            "煤炭": ["煤炭", "煤"],
            "钢铁": ["钢铁"],
        }
        for sector, keywords in mapping.items():
            for kw in keywords:
                if kw in sec:
                    return sector
        return "综合"


# ================================================================
#  命令行入口
# ================================================================

def main():
    if len(sys.argv) < 2:
        print("用法: python stock_valuation_engine.py <pipeline_json_path> [--json]")
        print("  --json    输出完整JSON到 stdout")
        sys.exit(1)

    path = sys.argv[1]

    with open(path) as f:
        data = json.load(f) if isinstance(json.load(f), dict) else {}

    ve = ValuationEngine(data)
    report = ve.full_report()

    output_json = "--json" in sys.argv

    if output_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        m = report["metadata"]
        print(f"\n{'='*60}")
        print(f" 📊 增强估值引擎报告")
        print(f" {'='*60}")
        print(f" {m['name']}({m['code']}) | {m['sector']}")
        print(f" 价格:{m['price']} 市值:{m['market_cap']}亿")
        print(f" PE-TTM:{m['pe_ttm']}x PB:{m['pb']}x")
        print()

        p = report["peg"]
        print(f" ── PEG ──")
        print(f"  PE-TTM: {p.get('pe_ttm','—')}x")
        print(f"  1Y增速: {p.get('eps_growth_1y','—')}%  |  3Y CAGR: {p.get('eps_cagr_3y','—')}%  |  FWD增速: {p.get('eps_growth_fwd','—')}%")
        print(f"  PEG-TTM: {p.get('peg_ttm','—')}  |  PEG-3Y: {p.get('peg_3y','—')}  |  PEG-FWD: {p.get('peg_fwd','—')}")
        print(f"  判定: {p.get('peg_verdict','—')}")

        print()
        pct = report["percentile_valuation"]
        if pct:
            print(f" ── 历史分位 ──")
            print(f"  PE: 当前{pct.get('pe_current','—')}x | 中位{pct.get('pe_median','—')}x | 历史{pct.get('pe_hist_min','—')}-{pct.get('pe_hist_max','—')} | 分位{pct.get('pe_hist_percentile','—')}%")
            print(f"  PB: 当前{pct.get('pb_current','—')}x | 中位{pct.get('pb_hist_median','—')}x | 分位{pct.get('pb_hist_percentile','—')}%")

        print()
        dp = report["dupont"]
        if dp:
            print(f" ── 杜邦诊断 ──")
            dec = dp.get("分解", {})
            print(f"  ROE={dp.get('roe_dupont','—')}% = 净利率{dec.get('净利率','—')}% × 周转率{dec.get('资产周转率','—')} × 杠杆{dec.get('权益乘数','—')}")
            print(f"  {dp.get('诊断','—')}")

        print()
        pf = report["piotroski"]
        if pf:
            print(f" ── Piotroski F-Score ──")
            print(f"  {pf.get('f_score','—')}/9 — {pf.get('verdict','—')}")

        print()
        sc = report["scenarios"]
        if sc:
            print(f" ── 增强三情景（行业基准PE={sc.get('sector_pe_benchmark','?')}x, 混合PE={sc.get('blended_pe','?')}x）──")
            opt = sc.get("乐观", {})
            base = sc.get("基准", {})
            cons = sc.get("保守", {})
            print(f"  🟢 乐观: ¥{opt.get('target_price','?')} ({opt.get('upside','?')}%) | PE≈{opt.get('implied_pe','?')}x")
            print(f"  🟡 基准: ¥{base.get('target_price','?')} ({base.get('upside','?')}%) | PE≈{base.get('implied_pe','?')}x")
            print(f"  🔴 保守: ¥{cons.get('target_price','?')} ({cons.get('upside','?')}%) | PE≈{cons.get('implied_pe','?')}x")
            ms = sc.get("margin_of_safety", {})
            print(f"  安全边际: {ms.get('安全边际','?')}%")

        print()
        fq = report["fcf_quality"]
        if fq:
            print(f" ── 现金流质量 ──")
            print(f"  CFO/NP比率: {fq.get('cfo_ratio_avg','?')} | 质量: {fq.get('cash_quality','?')}")
            print(f"  扣非占比: {fq.get('non_recurring_ratio','?')}%")

        print()
        sc_s = report["scores"]
        if sc_s:
            print(f" ── 行业调整评分（{sc_s.get('sector','?')}）──")
            for k, v in sc_s.get("scores", {}).items():
                bar = "█" * (v.get("value", 0) // 10) + "░" * (10 - v.get("value", 0) // 10)
                print(f"  {k}: {v.get('letter','?')} [{bar}] {v.get('value',0)} — {v.get('desc','?')}")
            print(f"  ─────────────")
            print(f"  总分: {sc_s.get('total','?')}/100")

        print()
        fr = report["final_rating"]
        if fr:
            print(f" ── 综合评级 ──")
            print(f"  {fr.get('rating','?')}")
            print(f"  总分={fr.get('total_score','?')} F-Score={fr.get('f_score','?')}")
            if fr.get("warnings"):
                for w in fr["warnings"]:
                    print(f"  ⚠️ {w}")

        print(f" {'='*60}")


if __name__ == "__main__":
    main()
