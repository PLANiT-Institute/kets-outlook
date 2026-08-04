# -*- coding: utf-8 -*-
"""보고서 그림 5종 재생성 — 전 그림이 outputs/runs JSON·supplementary CSV에서 재현되도록.

입력: outputs/runs/msr_results_v1.0.json, escalator_floor_cce_v2.0.json,
      carry_analysis_cce_v2.0.json, outputs/supplementary/carry_pairs_cce.csv
출력: docs/figures/fig{1..5}_*.png (300dpi, 흑백에서도 선종·마커로 구분)
실행: PYTHONPATH=. python3 scripts/build_figures.py
스타일: 기존 게재본(docx 추출본)과 시각 동등. 문턱 = 보고서 점추정 2035:97,500 / 2037:94,500
        + 국지 점선 연장(기울기 −1,500원/년, 2026까지 역외삽 금지 — 원 보고서 곡선 형태와 상충).
"""
import csv
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

NAVY = "#1f4e79"
BLUE_MID = "#2e6da4"
BLUE_Light = "#8ab4d8"
RED = "#c0392b"
GREY = "#808080"

MSR = json.load(open("outputs/runs/msr_results_v1.0.json"))
ESC = json.load(open("outputs/runs/escalator_floor_cce_v2.0.json"))
CAR = json.load(open("outputs/runs/carry_analysis_cce_v2.0.json"))

P0 = {r["year"]: r["kau"] for r in MSR["packages"]["P0"]["path"]}
# 게재본 관례: 균형가격은 3앵커(2026/2030/2040) 보간으로 표시 (fig5 범례에 명시)
ANCH = {2026: P0[2026], 2030: P0[2030], 2040: P0[2040]}
def interp_anchor(y):
    if y <= 2030:
        return ANCH[2026] + (ANCH[2030] - ANCH[2026]) * (y - 2026) / 4
    return ANCH[2030] + (ANCH[2040] - ANCH[2030]) * (y - 2030) / 10

YEARS = list(range(2026, 2041))
EQ = [interp_anchor(y) for y in YEARS]
TH = {2035: 97500, 2037: 94500}
TH_SLOPE = (TH[2037] - TH[2035]) / 2  # −1,500원/년


def style(ax):
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(labelsize=11)


def kfmt(ax):
    ax.yaxis.set_major_formatter(lambda v, _: f"{v/1000:.0f}k")


def draw_threshold(ax, label=True, ext_to=2040):
    ax.plot([2035, 2037], [TH[2035], TH[2037]], color=RED, lw=4, solid_capstyle="round", zorder=5)
    ax.plot([2035, 2037], [TH[2035], TH[2037]], "o", color=RED, ms=9, zorder=6)
    ax.plot([2034, 2035], [TH[2035] - TH_SLOPE, TH[2035]], ls=":", color=RED, alpha=0.55, lw=2)
    xs = list(range(2037, ext_to + 1))
    ax.plot(xs, [TH[2037] + TH_SLOPE * (x - 2037) for x in xs], ls=":", color=RED, alpha=0.55, lw=2)


# ── Figure 1: 균형가격 vs 문턱 ──────────────────────────────────────────
fig, ax = plt.subplots(figsize=(6.2, 4.0), dpi=300)
ax.plot(YEARS, EQ, "-o", color=NAVY, lw=3.5, ms=5.5)
draw_threshold(ax)
ax.set_title("The cap alone leaves the equilibrium price\nshort of the transition threshold",
             loc="left", fontsize=11.5)
ax.set_xlabel("Year", fontsize=12)
ax.set_ylabel("Carbon price (KRW/tCO$_2$, real 2026)", fontsize=12)
ax.set_ylim(0, 120000)
kfmt(ax)
ax.annotate("Steel H$_2$-DRI threshold\n$\\bullet$=report values (2035: 97,500 / 2037: 94,500)",
            xy=(2036, 96000), xytext=(2028.2, 106000), fontsize=9.5, color=RED,
            arrowprops=dict(arrowstyle="->", color=RED, lw=1))
ax.annotate("Model equilibrium price\n(current cap path only)",
            xy=(2037.5, interp_anchor(2037.5)), xytext=(2031.5, 33000), fontsize=10, color=NAVY,
            arrowprops=dict(arrowstyle="->", color=NAVY, lw=1))
ax.text(0.98, 0.03, "higher = stronger investment signal", transform=ax.transAxes,
        ha="right", fontsize=9, color=GREY, style="italic")
style(ax)
fig.tight_layout()
fig.savefig("docs/figures/fig1_gap.png")
plt.close(fig)

# ── Figure 2: 최저가격 경로 5종 vs 철강 문턱 ────────────────────────────
fig, ax = plt.subplots(figsize=(6.4, 4.2), dpi=300)
combos = [("40k_7pct", "40,000 · 7%", NAVY, "-"),
          ("45k_7pct", "45,000 · 7%", BLUE_MID, "-"),
          ("50k_7pct", "50,000 · 7%", BLUE_Light, "-"),
          ("45k_5.5pct", "45,000 · 5.5%", "#aaaaaa", "--"),
          ("50k_5.5pct", "50,000 · 5.5%", "#777777", "--")]
ax.axvspan(2028, 2030, color="#f5e6b8", alpha=0.6, zorder=0)
ax.text(2029, 6000, "investment\ndecision window", ha="center", fontsize=9.5, color="#8a6d1a")
labels = []
for key, lab, col, ls in combos:
    fl = {int(y): v for y, v in ESC[key]["floor"].items()}
    ax.plot(YEARS, [fl[y] for y in YEARS], ls=ls, color=col, lw=3 if ls == "-" else 2, zorder=3)
    labels.append([fl[2040], lab, col])
    if "7pct" in key and ESC[key]["steel_threshold_year"]:
        sy = int(ESC[key]["steel_threshold_year"])
        ax.plot(sy, fl[sy], marker="v", color=col, ms=11, zorder=6)
# 우측 라벨 겹침 방지: 위에서부터 최소 9,000원 간격 강제
labels.sort(reverse=True)
ys = []
for y0, _, _ in labels:
    ys.append(y0 if not ys else min(y0, ys[-1] - 9000))
for (y0, lab, col), y in zip(labels, ys):
    ax.text(2040.4, y, lab, fontsize=9, color=col, va="center")
draw_threshold(ax, ext_to=2040)
ax.set_xticks(range(2026, 2044, 2))
ax.set_title("Announced reserve-price paths reach\nthe steel threshold in 2036–2039",
             loc="left", fontsize=11.5)
ax.text(2030, 128000, "▼  first year 7% path crosses threshold", fontsize=9.5, color=GREY)
ax.text(2030, 121000, "Steel H$_2$-DRI threshold\n$\\bullet$=report values (2035/2037)",
        fontsize=9.5, color=RED, va="top")
ax.set_xlabel("Year", fontsize=12)
ax.set_ylabel("Auction reserve price (KRW/tCO$_2$, real 2026)", fontsize=12)
ax.set_xlim(2025.5, 2044)
ax.set_ylim(0, 135000)
kfmt(ax)
style(ax)
fig.tight_layout()
fig.savefig("docs/figures/fig2_floorpaths.png")
plt.close(fig)

# ── Figure 3: 출발가격별 누적 필요보류량 ────────────────────────────────────
fig, ax = plt.subplots(figsize=(5.6, 3.8), dpi=300)
keys = ["40k_7pct", "45k_7pct", "50k_7pct"]
vals = [round(ESC[k]["cum_required_withholding_Mt"]) for k in keys]
cols = [BLUE_Light, BLUE_MID, NAVY]
bars = ax.bar(range(3), vals, width=0.55, color=cols)
for i, (b, v) in enumerate(zip(bars, vals)):
    ax.text(b.get_x() + b.get_width() / 2, v + 10, f"{v}", ha="center",
            fontsize=13, fontweight="bold", color=cols[i])
ax.set_xticks(range(3))
ax.set_xticklabels(["40,000\nKRW", "45,000\nKRW", "50,000\nKRW"], fontsize=11)
ax.set_title("Higher starting price → more supply must be withheld", loc="left", fontsize=11)
ax.set_xlabel("2026 starting reserve price (real, +7%/yr)", fontsize=11)
ax.set_ylabel("Cumulative cancellation\n2026–2040 (Mt CO$_2$)", fontsize=11)
ax.set_ylim(0, 560)
ax.text(0.5, 0.965, "annual cancellation ≈ 50 Mt at most, always within auction volume",
        transform=ax.transAxes, ha="center", fontsize=8.5, color=GREY, style="italic")
style(ax)
fig.tight_layout()
fig.savefig("docs/figures/fig3_cancellation.png")
plt.close(fig)

# ── Figure 4: 캐리 분포 + 이월재고 비율 ─────────────────────────────────
pairs = list(csv.DictReader(open("outputs/supplementary/carry_pairs_cce.csv")))
all_c = [100 * float(p["vintage_premium"]) for p in pairs]
tr_c = [100 * float(p["vintage_premium"]) for p in pairs if p["both_traded"] == "1"]
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9.2, 3.9), dpi=300)
bins = [x * 2.0 for x in range(-21, 32)]
ax1.hist(all_c, bins=bins, density=True, color="#b8b8b8", alpha=0.85,
         label=f"All quote days (n={len(all_c)})")
ax1.hist(tr_c, bins=bins, density=True, histtype="step", color=RED, lw=2.2,
         label=f"Both vintages traded (n={len(tr_c)})")
ax1.axvline(0, color="#555555", lw=0.8)
ax1.axvline(5.5, color=BLUE_MID, ls="--", lw=2)
ax1.set_ylim(0, 0.34)
ax1.text(6.5, 0.16, "banking-equilibrium\n5.5%", fontsize=9.5, color=BLUE_MID)
ax1.set_title("Near-zero carry is largely a stale-quote artifact", loc="left", fontsize=12)
ax1.set_xlabel("Annualized adjacent-vintage carry (%)", fontsize=11)
ax1.set_ylabel("Density", fontsize=11)
ax1.set_xlim(-42, 62)
ax1.legend(fontsize=8.5, frameon=False, loc="upper right", bbox_to_anchor=(1.0, 0.98))
style(ax1)
ratio = {int(y): v for y, v in CAR["banking_ratio"].items()}
yrs = sorted(ratio)
ax2.plot(yrs, [ratio[y] for y in yrs], "-o", color=BLUE_MID, lw=2.5, ms=7)
mean_1521 = CAR["banking_ratio_2015_21_mean"]
ax2.axhline(mean_1521, ls=":", color=GREY, lw=1.5)
ax2.text(2015.2, mean_1521 + 0.004, f"2015–21 mean {mean_1521:.2f}", fontsize=9.5, color=GREY)
ax2.annotate(f"{ratio[max(yrs)]:.2f}", xy=(max(yrs), ratio[max(yrs)]),
             xytext=(-14, 8), textcoords="offset points",
             fontsize=12, fontweight="bold", color=BLUE_MID)
ax2.set_title("Banked stock has roughly quadrupled\nrelative to its 2015–21 average",
              loc="left", fontsize=12)
ax2.set_xlabel("Year", fontsize=11)
ax2.set_ylabel("Banked stock / verified emissions", fontsize=11)
style(ax2)
fig.tight_layout()
fig.savefig("docs/figures/fig4_empirics.png")
plt.close(fig)

# ── Figure 5: 45k·7% 하한의 binding 시각화 ─────────────────────────────
fig, ax = plt.subplots(figsize=(6.4, 4.3), dpi=300)
fl = {int(y): v for y, v in ESC["45k_7pct"]["floor"].items()}
floor = [fl[y] for y in YEARS]
ax.plot(YEARS, EQ, "--", color=BLUE_MID, lw=2.5,
        label="Equilibrium price without a floor (model; 3 anchor points, interpolated)")
ax.plot(list(ANCH), list(ANCH.values()), "o", color=BLUE_MID, ms=8)
ax.plot(YEARS, floor, "-", color=RED, lw=4,
        label="Realized price = reserve floor (45,000 · 7%), which binds every year")
ax.fill_between(YEARS, EQ, floor, color=RED, alpha=0.07)
jump = fl[2026] - ANCH[2026]
ax.annotate("", xy=(2026, fl[2026]), xytext=(2026, ANCH[2026]),
            arrowprops=dict(arrowstyle="<->", color="#333333", lw=1.5))
ax.text(2026.4, 34000, f"Introduction jump\n{ANCH[2026]:,.0f} → {fl[2026]:,.0f}  (+{100*jump/ANCH[2026]:.0f}%)",
        fontsize=11, fontweight="bold")
gap40 = fl[2040] - ANCH[2040]
ax.annotate("", xy=(2040, fl[2040]), xytext=(2040, ANCH[2040]),
            arrowprops=dict(arrowstyle="<->", color=GREY, lw=1.5))
ax.text(2039.6, 88000, f"floor lifts price\n{gap40:,.0f} above\nequilibrium by 2040",
        ha="right", fontsize=10, color=GREY, style="italic")
ax.set_title("The floor is a binding price path, not a slack backstop", loc="left", fontsize=12.5)
ax.set_xlabel("Year", fontsize=12)
ax.set_ylabel("Carbon price (KRW/tCO$_2$, real 2026)", fontsize=12)
kfmt(ax)
ax.legend(fontsize=9, frameon=False, loc="upper left")
style(ax)
fig.tight_layout()
fig.savefig("docs/figures/fig5_arbitrage.png")
plt.close(fig)

print("saved 5 figures to docs/figures/")
