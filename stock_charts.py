"""静态图表渲染模块 — 使用matplotlib生成PNG图表，无JS依赖，支持双主题"""
import io, base64, os
os.environ["MPLBACKEND"] = "Agg"
import matplotlib
matplotlib.use("Agg")

FONT_PATH = "/usr/share/fonts/truetype/NotoSansCJKSC-Regular.ttf"
import matplotlib.font_manager as fm
if os.path.exists(FONT_PATH):
    fm.fontManager.addfont(FONT_PATH)
else:
    from fontTools.ttLib import TTFont
    src = '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
    if os.path.exists(src):
        font = TTFont(src, fontNumber=2)
        font.save(FONT_PATH)
        font.close()
        fm.fontManager.addfont(FONT_PATH)
        import subprocess
        subprocess.run(['fc-cache', '-f'], capture_output=True)

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
from matplotlib.font_manager import FontProperties

FONT = FontProperties(fname=FONT_PATH)

plt.rcParams.update({
    "font.family": "Noto Sans CJK SC",
    "font.sans-serif": ["Noto Sans CJK SC"],
    "axes.unicode_minus": False,
})

# ── 双主题配色 ──
THEMES = {
    "dark": {
        "bg": "#141b2d",
        "text": "#e0e4ed",
        "sub": "#94a3b8",
        "dim": "#64748b",
        "grid": "#0f172a",
        "border": "#334155",
    },
    "light": {
        "bg": "#ffffff",
        "text": "#334155",
        "sub": "#64748b",
        "dim": "#94a3b8",
        "grid": "#f1f5f9",
        "border": "#e2e8f0",
    },
}

COLORS = ["#3b82f6", "#22c55e", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899", "#14b8a6", "#f97316"]


def _img(fig, dpi=150):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight",
                facecolor=None, edgecolor="none", transparent=True,
                pad_inches=0.1)
    plt.close(fig)
    buf.seek(0)
    return "data:image/png;base64," + base64.b64encode(buf.read()).decode()


def _apply_theme(ax, t):
    """Apply color scheme from theme dict."""
    ax.set_facecolor(t["bg"])
    ax.tick_params(axis="x", colors=t["sub"])
    ax.tick_params(axis="y", colors=t["sub"])
    ax.spines["bottom"].set_color(t["border"])
    ax.spines["left"].set_color(t["border"])
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(True, color=t["grid"], alpha=0.4, linewidth=0.5)


def _base_fig(width, height):
    fig, ax = plt.subplots(figsize=(width, height))
    fig.patch.set_alpha(0.0)
    return fig, ax


def bar_chart(labels, values, title="", theme="dark", width=5, height=2.2, ylabel="", fmt=None):
    t = THEMES[theme]
    fig, ax = _base_fig(width, height)
    n = len(labels)
    bars = ax.bar(range(n), values, color=COLORS[:n], width=0.6, edgecolor="none")
    ax.set_xticks(range(n))
    ax.set_xticklabels(labels, fontproperties=FONT, rotation=20, ha="right", fontsize=7)
    for b, v in zip(bars, values):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + max(values)*0.02,
                f"{v:.1f}" if isinstance(v, float) else str(v),
                ha="center", va="bottom", fontsize=6.5, color=t["sub"], fontproperties=FONT)
    ax.set_title(title, fontproperties=FONT, fontsize=10, fontweight="bold", pad=6, color=t["text"])
    _apply_theme(ax, t)
    plt.tight_layout()
    return _img(fig)


def grouped_bar_chart(labels, series_list, title="", theme="dark", width=5, height=2.2):
    t = THEMES[theme]
    fig, ax = _base_fig(width, height)
    n = len(labels)
    ns = len(series_list)
    bw = 0.7 / ns
    for i, (name, vals) in enumerate(series_list):
        x = np.arange(n) + (i - (ns - 1) / 2) * bw
        bars = ax.bar(x, vals, bw, label=name, color=COLORS[i])
        for b, v in zip(bars, vals):
            if v != 0:
                ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.1,
                        f"{v:.1f}", ha="center", fontsize=5.5, color=t["sub"], fontproperties=FONT)
    ax.set_xticks(np.arange(n))
    ax.set_xticklabels(labels, fontproperties=FONT, rotation=20, ha="right", fontsize=7)
    ax.set_title(title, fontproperties=FONT, fontsize=10, fontweight="bold", pad=6, color=t["text"])
    ax.legend(fontsize=6, loc="upper left", framealpha=0.7, prop=FONT)
    _apply_theme(ax, t)
    plt.tight_layout()
    return _img(fig)


def line_chart(labels, series_list, title="", theme="dark", width=5, height=2.2):
    t = THEMES[theme]
    fig, ax = _base_fig(width, height)
    for i, (name, vals) in enumerate(series_list):
        ax.plot(range(len(vals)), vals, label=name, color=COLORS[i],
                marker="o", markersize=2.5, linewidth=1.2)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, fontproperties=FONT, rotation=20, ha="right", fontsize=7)
    ax.set_title(title, fontproperties=FONT, fontsize=10, fontweight="bold", pad=6, color=t["text"])
    ax.legend(fontsize=6, loc="upper left", framealpha=0.7, prop=FONT)
    _apply_theme(ax, t)
    plt.tight_layout()
    return _img(fig)


def pie_chart(items, title="", theme="dark", width=4, height=2.6):
    t = THEMES[theme]
    fig, ax = _base_fig(width, height)
    names = [it["name"] for it in items if it.get("value", 0) > 0]
    vals = [it["value"] for it in items if it.get("value", 0) > 0]
    if not vals:
        plt.close(fig)
        return ""
    wedges, _, autotexts = ax.pie(
        vals, labels=None, autopct="%1.1f%%",
        colors=COLORS[:len(vals)], startangle=90, pctdistance=0.72,
        textprops={"fontsize": 6, "color": t["text"]})
    ax.legend(wedges,
              [f"{n[:10]} ({v:.1f}%)" for n, v in zip(names, vals)],
              loc="lower center", bbox_to_anchor=(0.5, -0.1),
              ncol=2, fontsize=5.5, framealpha=0.4, prop=FONT)
    ax.set_title(title, fontproperties=FONT, fontsize=10, fontweight="bold", pad=6, color=t["text"])
    fig.set_facecolor(t["bg"])
    plt.tight_layout()
    return _img(fig)


def dual_axis_chart(labels, series_left, series_right, title="", theme="dark", width=5, height=2.2,
                    ylabel_left="", ylabel_right=""):
    t = THEMES[theme]
    fig, ax1 = _base_fig(width, height)
    n = len(labels)
    nl = len(series_left)
    for i, (name, vals) in enumerate(series_left):
        off = (i - (nl - 1) / 2) * 0.25
        ax1.bar(np.arange(n) + off, vals, 0.25, label=name, color=COLORS[i])
    ax1.set_ylabel(ax1.get_ylabel(), fontproperties=FONT, fontsize=8, color=t["sub"])
    ax1.set_xticks(range(n))
    ax1.set_xticklabels(labels, fontproperties=FONT, rotation=20, ha="right", fontsize=7)
    ax2 = ax1.twinx()
    for i, (name, vals) in enumerate(series_right):
        ax2.plot(vals, label=name, color=COLORS[(i+2) % len(COLORS)],
                 marker="o", markersize=2.5, linewidth=1.2)
    ax2.set_ylabel(ax2.get_ylabel(), fontproperties=FONT, fontsize=8, color=t["sub"])
    ax2.tick_params(axis="y", colors=t["sub"])
    ax1.set_title(title, fontproperties=FONT, fontsize=10, fontweight="bold", pad=6, color=t["text"])
    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, fontsize=6, loc="upper left", framealpha=0.7, prop=FONT)
    _apply_theme(ax1, t)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_color(t["border"])
    plt.tight_layout()
    return _img(fig)


def radar_chart(categories, values, title="", theme="dark", width=2.8, height=2.8):
    t = THEMES[theme]
    n = len(categories)
    angles = np.linspace(0, 2*np.pi, n, endpoint=False).tolist() + [0]
    fig, ax = plt.subplots(figsize=(width, height), subplot_kw=dict(polar=True))
    fig.patch.set_alpha(0.0)
    ax.set_facecolor(t["bg"])
    vals = values + values[:1]
    ax.fill(angles, vals, alpha=0.15, color=COLORS[0])
    ax.plot(angles, vals, color=COLORS[0], linewidth=1.5)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories, fontproperties=FONT, fontsize=6.5, color=t["sub"])
    ax.set_ylim(0, 100)
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(["20","40","60","80","100"], fontsize=5.5, color=t["dim"])
    ax.set_title(title, fontproperties=FONT, fontsize=10, fontweight="bold", pad=8, color=t["text"])
    ax.spines["polar"].set_color(t["border"])
    plt.tight_layout()
    return _img(fig)


def kline_chart(dates, opens, highs, lows, closes, volumes,
                title="", theme="dark", width=5.5, height=2.8):
    t = THEMES[theme]
    try:
        import mplfinance as mpf
        import pandas as pd
        df = pd.DataFrame({
            "Open": opens, "High": highs, "Low": lows,
            "Close": closes, "Volume": volumes
        }, index=pd.DatetimeIndex(dates))
        mc = mpf.make_marketcolors(
            up="#22c55e" if theme=="dark" else "#16a34a",
            down="#ef4444" if theme=="dark" else "#dc2626",
            edge={"up": "#22c55e", "down": "#ef4444"},
            wick={"up": t["text"], "down": t["text"]},
            volume={"up": "#22c55e60", "down": "#ef444460"})
        s = mpf.make_mpf_style(marketcolors=mc, facecolor=t["bg"],
                               gridcolor=t["grid"], gridaxis="both",
                               y_on_right=False)
        fig, axes = mpf.plot(df, type="candle", style=s, volume=True,
                             figsize=(width, height), returnfig=True,
                             xrotation=20, tight_layout=True)
        for ax in axes:
            ax.set_facecolor(t["bg"])
            ax.tick_params(colors=t["sub"])
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                    facecolor=t["bg"], transparent=False)
        plt.close(fig)
        buf.seek(0)
        return "data:image/png;base64," + base64.b64encode(buf.read()).decode()
    except Exception:
        # Fallback to line
        return line_chart([d[:7] for d in dates[-60:]],
                          [("收盘价", closes[-60:])],
                          title=title, theme=theme)
