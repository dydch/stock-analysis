"""静态图表渲染模块 — 使用matplotlib生成PNG图表，无JS依赖"""
import io, base64, os
os.environ["MPLBACKEND"] = "Agg"
import matplotlib
matplotlib.use("Agg")

# Register Noto Sans CJK SC font
FONT_PATH = "/usr/share/fonts/truetype/NotoSansCJKSC-Regular.ttf"
if os.path.exists(FONT_PATH):
    import matplotlib.font_manager as fm
    fm.fontManager.addfont(FONT_PATH)

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

# Theme colors
BG = "#1a2338"
TEXT = "#e0e4ed"
SUBTLE = "#8892b0"
DIM = "#64748b"
GRID = "#1e293b"
BORDER = "#2a3550"
COLORS = ["#3b82f6", "#22c55e", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899", "#14b8a6", "#f97316"]

plt.rcParams.update({
    "font.family": "Noto Sans CJK SC",
    "font.sans-serif": ["Noto Sans CJK SC", "DejaVu Sans"],
    "axes.unicode_minus": False,
    "figure.facecolor": BG,
    "axes.facecolor": BG,
    "axes.edgecolor": BORDER,
    "axes.labelcolor": SUBTLE,
    "text.color": TEXT,
    "xtick.color": DIM,
    "ytick.color": DIM,
    "grid.color": GRID,
    "grid.alpha": 0.3,
})


def _img(fig, dpi=110):
    """Save matplotlib figure to base64 PNG string."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight",
                facecolor=BG, edgecolor="none", transparent=False)
    plt.close(fig)
    buf.seek(0)
    return "data:image/png;base64," + base64.b64encode(buf.read()).decode()


def bar_chart(labels, values, title="", ylabel="", colors=None,
              width=5.5, height=2.8, show_values=True, fmt="{:.1f}%"):
    """Simple bar chart."""
    fig, ax = plt.subplots(figsize=(width, height))
    n = len(labels)
    if colors is None:
        colors = COLORS
    elif len(colors) < n:
        colors = colors * (n // len(colors) + 1)
    bars = ax.bar(range(n), values, color=colors[:n], width=0.6, edgecolor="none")
    ax.set_xticks(range(n))
    ax.set_xticklabels(labels, rotation=20, ha="right", fontsize=8)
    if show_values:
        for b, v in zip(bars, values):
            ax.text(b.get_x() + b.get_width() / 2,
                    b.get_height() + max(values) * 0.02,
                    fmt.format(v) if isinstance(v, float) else str(v),
                    ha="center", va="bottom", fontsize=8, color=SUBTLE)
    ax.set_title(title, fontsize=11, fontweight="bold", pad=8)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=9)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.1f"))
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    plt.tight_layout()
    return _img(fig)


def grouped_bar_chart(labels, series_list, title="", ylabel="", width=5.5, height=2.8):
    """Grouped bar chart (e.g. two series: 营收, 净利润)."""
    fig, ax = plt.subplots(figsize=(width, height))
    n = len(labels)
    n_series = len(series_list)
    bar_w = 0.7 / n_series
    for i, (name, vals) in enumerate(series_list):
        x = np.arange(n) + (i - (n_series - 1) / 2) * bar_w
        bars = ax.bar(x, vals, bar_w, label=name, color=COLORS[i % len(COLORS)])
        for b, v in zip(bars, vals):
            if v != 0:
                ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.1,
                        f"{v:.1f}", ha="center", fontsize=6.5, color=SUBTLE)
    ax.set_xticks(np.arange(n))
    ax.set_xticklabels(labels, rotation=20, ha="right", fontsize=8)
    ax.set_title(title, fontsize=11, fontweight="bold", pad=8)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=9)
    ax.legend(fontsize=7, loc="upper left", framealpha=0.7)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    plt.tight_layout()
    return _img(fig)


def line_chart(labels, series_list, title="", ylabel="", width=5.5, height=2.8,
               show_dots=True):
    """Line chart with one or more series."""
    fig, ax = plt.subplots(figsize=(width, height))
    for i, (name, vals) in enumerate(series_list):
        c = COLORS[i % len(COLORS)]
        marker = "o" if show_dots else None
        ax.plot(range(len(vals)), vals, label=name, color=c, marker=marker,
                markersize=3, linewidth=1.5)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=20, ha="right", fontsize=8)
    ax.set_title(title, fontsize=11, fontweight="bold", pad=8)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=9)
    ax.legend(fontsize=7, loc="upper left", framealpha=0.7)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    plt.tight_layout()
    return _img(fig)


def pie_chart(items, title="", width=4.5, height=3.0):
    """Pie chart from list of {name, value} dicts."""
    fig, ax = plt.subplots(figsize=(width, height))
    names = [it["name"] for it in items if it.get("value", 0) > 0]
    vals = [it["value"] for it in items if it.get("value", 0) > 0]
    if not vals:
        plt.close(fig)
        return ""
    wedges, _, autotexts = ax.pie(
        vals, labels=None, autopct="%1.1f%%",
        colors=COLORS[:len(vals)],
        startangle=90, pctdistance=0.75,
        textprops={"fontsize": 7, "color": SUBTLE})
    ax.legend(wedges,
              [f"{n[:12]} ({v:.1f}%)" for n, v in zip(names, vals)],
              loc="lower center", bbox_to_anchor=(0.5, -0.15),
              ncol=2, fontsize=6.5, framealpha=0.5)
    ax.set_title(title, fontsize=11, fontweight="bold", pad=8)
    plt.tight_layout()
    return _img(fig)


def dual_axis_chart(labels, series_left, series_right, title="",
                    ylabel_left="", ylabel_right="", width=5.5, height=2.8):
    """Dual y-axis chart (left: bars, right: line)."""
    fig, ax1 = plt.subplots(figsize=(width, height))
    n = len(labels)
    n_left = len(series_left)
    for i, (name, vals) in enumerate(series_left):
        offset = (i - (n_left - 1) / 2) * 0.25
        ax1.bar(np.arange(n) + offset, vals, 0.25, label=name,
                color=COLORS[i % len(COLORS)])
    ax1.set_ylabel(ylabel_left, fontsize=9, color=SUBTLE)
    ax1.tick_params(axis="y", colors=SUBTLE)
    ax1.set_xticks(range(n))
    ax1.set_xticklabels(labels, rotation=20, ha="right", fontsize=8)

    ax2 = ax1.twinx()
    for i, (name, vals) in enumerate(series_right):
        ax2.plot(vals, label=name, color=COLORS[(i+2) % len(COLORS)],
                 marker="o", markersize=3, linewidth=1.5)
    ax2.set_ylabel(ylabel_right, fontsize=9, color=SUBTLE)
    ax2.tick_params(axis="y", colors=SUBTLE)

    ax1.set_title(title, fontsize=11, fontweight="bold", pad=8)
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, fontsize=7,
               loc="upper left", framealpha=0.7)
    ax1.spines["top"].set_visible(False)
    plt.tight_layout()
    return _img(fig)


def radar_chart(categories, values, title="", width=3.5, height=3.5):
    """Radar chart for scores."""
    n = len(categories)
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False).tolist()
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(width, height), subplot_kw=dict(polar=True))
    vals = values + values[:1]
    ax.fill(angles, vals, alpha=0.15, color=COLORS[0])
    ax.plot(angles, vals, color=COLORS[0], linewidth=1.5)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories, fontsize=7, color=SUBTLE)
    ax.set_ylim(0, 100)
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(["20", "40", "60", "80", "100"],
                       fontsize=6, color=DIM)
    ax.set_title(title, fontsize=11, fontweight="bold", pad=12)
    ax.spines["polar"].set_color(BORDER)
    plt.tight_layout()
    return _img(fig)


def kline_chart(dates, opens, highs, lows, closes, volumes,
                title="", width=6.5, height=3.5):
    """Simple K-line visualization using mplfinance."""
    try:
        import mplfinance as mpf
        import pandas as pd
        df = pd.DataFrame({
            "Open": opens, "High": highs, "Low": lows,
            "Close": closes, "Volume": volumes
        }, index=pd.DatetimeIndex(dates))
        mc = mpf.make_marketcolors(up="#22c55e", down="#ef4444",
                                   edge={"up": "#22c55e", "down": "#ef4444"},
                                   volume={"up": "#22c55e80", "down": "#ef444480"})
        s = mpf.make_mpf_style(marketcolors=mc, facecolor=BG,
                               gridcolor=GRID, gridaxis="both",
                               y_on_right=False)
        fig, axes = mpf.plot(df, type="candle", style=s, volume=True,
                             figsize=(width, height), returnfig=True,
                             xrotation=20, tight_layout=True)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=110, bbox_inches="tight",
                    facecolor=BG)
        plt.close(fig)
        buf.seek(0)
        return "data:image/png;base64," + base64.b64encode(buf.read()).decode()
    except Exception as e:
        # Fallback: simple line chart
        return line_chart([d[:7] if len(d) > 7 else d for d in dates[-60:]],
                          [("收盘价", closes[-60:])],
                          title=title, width=width, height=height)[0]
