# -*- coding: utf-8 -*-
"""Reproduce the CCE adjacent-vintage and banking analysis.

The primary statistic is an adjacent-vintage premium, not an annualized return:
KAU vintages differ by one compliance label, but contract timing, convenience
yield, transaction costs, and stale quotes prevent a literal yield interpretation.

Outputs
-------
outputs/runs/carry_analysis_cce_v2.0.json
outputs/supplementary/carry_pairs_cce.csv
outputs/supplementary/carry_summary_by_year_cce.csv
"""

import csv
import json
import os
import random
import statistics
import unicodedata

import openpyxl


XLSX = "data/ets_data.xlsx"
OUT_JSON = "outputs/runs/carry_analysis_cce_v2.0.json"
OUT_PAIRS = "outputs/supplementary/carry_pairs_cce.csv"
OUT_YEAR = "outputs/supplementary/carry_summary_by_year_cce.csv"
BENCHMARK = 0.055
BOOTSTRAP_DRAWS = 5000
SEED = 20260801


def sheet_by_name(workbook, name):
    target = unicodedata.normalize("NFC", name)
    actual = next(
        sheet
        for sheet in workbook.sheetnames
        if unicodedata.normalize("NFC", sheet) == target
    )
    return workbook[actual]


def mean(values):
    return statistics.fmean(values) if values else None


def percentile(sorted_values, probability):
    if not sorted_values:
        return None
    position = (len(sorted_values) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = position - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def cluster_bootstrap_ci(rows, statistic):
    """Date-cluster bootstrap; all pairs from a sampled date move together."""
    by_date = {}
    for row in rows:
        by_date.setdefault(row["date"], []).append(row)
    dates = sorted(by_date)
    rng = random.Random(SEED)
    estimates = []
    for _ in range(BOOTSTRAP_DRAWS):
        sample = []
        for sampled_date in rng.choices(dates, k=len(dates)):
            sample.extend(by_date[sampled_date])
        estimates.append(statistic([row["vintage_premium"] for row in sample]))
    estimates.sort()
    return [percentile(estimates, 0.025), percentile(estimates, 0.975)]


def summarize(rows):
    premiums = [row["vintage_premium"] for row in rows]
    weights = [row["volume_front"] + row["volume_next"] for row in rows]
    weight_total = sum(weights)
    return {
        "n_pairs": len(rows),
        "n_dates": len({row["date"] for row in rows}),
        "median_pct": round(100 * statistics.median(premiums), 3),
        "mean_pct": round(100 * mean(premiums), 3),
        "sd_pct": round(100 * statistics.stdev(premiums), 3) if len(rows) > 1 else None,
        "p10_pct": round(100 * percentile(sorted(premiums), 0.10), 3),
        "p90_pct": round(100 * percentile(sorted(premiums), 0.90), 3),
        "share_below_5_5_pct": round(sum(p < BENCHMARK for p in premiums) / len(rows), 4),
        "volume_weighted_mean_pct": (
            round(100 * sum(p * w for p, w in zip(premiums, weights)) / weight_total, 3)
            if weight_total > 0
            else None
        ),
    }


workbook = openpyxl.load_workbook(XLSX, read_only=True, data_only=True)

# KAU daily closes and volumes.
market = sheet_by_name(workbook, "market").iter_rows(values_only=True)
next(market)
daily, kau_quotes = {}, 0
for row in market:
    date, instrument, close, volume = str(row[0])[:10], row[1], row[2], row[8]
    if (
        isinstance(instrument, str)
        and instrument.startswith("KAU")
        and len(instrument) == 5
        and close is not None
    ):
        kau_quotes += 1
        daily.setdefault(date, {})[int(instrument[3:])] = (
            float(close),
            float(volume or 0),
        )

pairs = []
for date in sorted(daily):
    vintages = daily[date]
    for vintage in sorted(vintages):
        if vintage + 1 not in vintages:
            continue
        price_front, volume_front = vintages[vintage]
        price_next, volume_next = vintages[vintage + 1]
        if price_front <= 0:
            continue
        premium = price_next / price_front - 1
        pairs.append(
            {
                "date": date,
                "calendar_year": int(date[:4]),
                "vintage_front": vintage,
                "vintage_next": vintage + 1,
                "close_front_krw": price_front,
                "close_next_krw": price_next,
                "volume_front": volume_front,
                "volume_next": volume_next,
                "vintage_premium": premium,
                "both_traded": int(volume_front > 0 and volume_next > 0),
                "within_pm40pct": int(-0.40 <= premium <= 0.40),
            }
        )

traded = [row for row in pairs if row["both_traded"]]
trimmed = [row for row in pairs if row["within_pm40pct"]]

# Annual descriptive results for the liquidity-filtered sample.
year_rows = []
for year in sorted({row["calendar_year"] for row in traded}):
    rows = [row for row in traded if row["calendar_year"] == year]
    year_rows.append({"calendar_year": year, **summarize(rows)})


def year_sum(sheet_name, value_columns):
    totals = {}
    rows = sheet_by_name(workbook, sheet_name).iter_rows(values_only=True)
    next(rows)
    for row in rows:
        if row[4] is None:
            continue
        year = int(row[4])
        totals[year] = totals.get(year, 0.0) + sum(
            float(row[column] or 0.0) for column in value_columns
        )
    return totals


bank = year_sum("배출권이월량", [5, 6])
verified = year_sum("인증배출량", [5])
banking_ratio = {
    year: bank[year] / verified[year]
    for year in sorted(bank)
    if year in verified and verified[year] > 0
}
workbook.close()

all_summary = summarize(pairs)
traded_summary = summarize(traded)
mean_ci = cluster_bootstrap_ci(traded, statistics.fmean)
median_ci = cluster_bootstrap_ci(traded, statistics.median)
traded_summary["date_cluster_bootstrap_mean_ci95_pct"] = [
    round(100 * value, 3) for value in mean_ci
]
traded_summary["date_cluster_bootstrap_median_ci95_pct"] = [
    round(100 * value, 3) for value in median_ci
]

stats = {
    "meta": {
        "version": "CCE 2.0",
        "benchmark_pct": 5.5,
        "bootstrap_draws": BOOTSTRAP_DRAWS,
        "bootstrap_seed": SEED,
        "interpretation": (
            "The adjacent-vintage premium is descriptive. It is not a pure annualized "
            "financing return because convenience yield, transaction costs, compliance "
            "timing, risk, and stale closes are not separately identified."
        ),
    },
    "kau_vintage_day_quotes": kau_quotes,
    "all_quote_pairs": all_summary,
    "both_traded_pairs": traded_summary,
    "legacy_pm40pct_display_sample_n": len(trimmed),
    "annual_both_traded": year_rows,
    "years_with_median_below_5_5_pct": sum(
        row["median_pct"] < 5.5 for row in year_rows
    ),
    "years_observed": len(year_rows),
    "banking_ratio": {year: round(value, 6) for year, value in banking_ratio.items()},
    "banking_ratio_2015_21_mean": round(
        mean([banking_ratio[year] for year in range(2015, 2022)]), 6
    ),
    "bank_2024_Mt": round(bank[2024] / 1e6, 6),
    "verified_emissions_2024_Mt": round(verified[2024] / 1e6, 6),
}

assert stats["kau_vintage_day_quotes"] == 8513
assert stats["all_quote_pairs"]["n_pairs"] == 5693
assert stats["both_traded_pairs"]["n_pairs"] == 253
assert stats["legacy_pm40pct_display_sample_n"] == 5444
assert abs(stats["bank_2024_Mt"] - 92.140327) < 1e-6
assert round(stats["banking_ratio"][2024], 3) == 0.168

os.makedirs(os.path.dirname(OUT_PAIRS), exist_ok=True)
with open(OUT_PAIRS, "w", newline="", encoding="utf-8") as file:
    writer = csv.DictWriter(file, fieldnames=list(pairs[0]))
    writer.writeheader()
    writer.writerows(pairs)

with open(OUT_YEAR, "w", newline="", encoding="utf-8") as file:
    writer = csv.DictWriter(file, fieldnames=list(year_rows[0]))
    writer.writeheader()
    writer.writerows(year_rows)

with open(OUT_JSON, "w", encoding="utf-8") as file:
    json.dump(stats, file, ensure_ascii=False, indent=2)

print(json.dumps({key: value for key, value in stats.items() if key != "banking_ratio"}, indent=2))
print("saved:", OUT_JSON, OUT_PAIRS, OUT_YEAR)
