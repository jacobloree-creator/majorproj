# -*- coding: utf-8 -*-
"""
Created on Fri Nov 20 10:07:44 2026

@author: jloree
"""

import io
from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st


# ============================================================
# APP CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="LAMP: Labour Analysis of Major Projects",
    page_icon="🧰",
    layout="wide",
)

APP_DIR = Path(__file__).parent

DEMAND_FILE = APP_DIR / "io_noc_coefficients.xlsx"
LABOUR_FILE = APP_DIR / "unemployment.xlsx"
DEMOGRAPHICS_FILE = APP_DIR / "demographics.xlsx"
WAGES_FILE = APP_DIR / "wages.xlsx"
NOC_TITLES_FILE = APP_DIR / "noc_titles.xlsx"
VACANCIES_FILE = APP_DIR / "vacancies.xlsx"
COPS_FILE = APP_DIR / "cops flows.xlsx"
CANADA_MULTIPLIERS_FILE = APP_DIR / "canada_multipliers.xlsx"

REQUIRED_DEMAND_COLS = [
    "IOIC", "PROV", "NOC3DIG", "emp", "totalemp_ind", "occshare",
    "direct_all_wage", "indirect_all_wage", "induced_all_wage",
    "direct_within_wage", "indirect_within_wage", "induced_within_wage",
    "direct_all_job", "indirect_all_job", "induced_all_job",
    "direct_within_job", "indirect_within_job", "induced_within_job",
    "totalemp_occ",
]

REQUIRED_LABOUR_COLS = [
    "PROV", "NOC3DIG", "employed", "unemployed", "unemprate"
]

REQUIRED_DEMOGRAPHICS_COLS = [
    "PROV", "NOC3DIG", "highageshare"
]

REQUIRED_WAGE_COLS = [
    "PROV", "NOC3DIG", "earn_mean"
]

REQUIRED_NOC_TITLE_COLS = [
    "NOC3DIG", "title"
]

# The source workbook uses a space in "vacancy rate".
REQUIRED_VACANCY_COLS = [
    "PROV", "NOC3DIG", "vacancies", "vacancy rate"
]

COPS_FLOW_TYPES = [
    "expansiondemand",
    "retirement_outflow",
    "emigration_outflow",
    "school_inflow",
    "immigrant_inflow",
    "other_inflow",
]

REQUIRED_COPS_COLS = [
    "noc3dig",
    "type",
]
REQUIRED_CANADA_MULTIPLIER_COLS = [
    "PROV",
    "IOIC",
    "direct_all_job",
    "indirect_all_job",
    "induced_all_job",
    "direct_all_wage",
    "indirect_all_wage",
    "induced_all_wage",
]

NUMERIC_DEMAND_COLS = [
    c for c in REQUIRED_DEMAND_COLS
    if c not in {"IOIC", "PROV", "NOC3DIG"}
]

MULTIPLIER_COLS = [
    "direct_all_wage", "indirect_all_wage", "induced_all_wage",
    "direct_within_wage", "indirect_within_wage", "induced_within_wage",
    "direct_all_job", "indirect_all_job", "induced_all_job",
    "direct_within_job", "indirect_within_job", "induced_within_job",
]

FISCAL_YEARS = [
    "2026-27", "2027-28", "2028-29", "2029-30", "2030-31",
    "2031-32", "2032-33", "2033-34", "2034-35", "2035-36",
    "2036-37", "2037-38", "2038-39", "2039-40", "2040-41",
]


# ============================================================
# DATA HELPERS
# ============================================================

def clean_keys(frame):
    frame = frame.copy()
    frame["PROV"] = frame["PROV"].astype("string").str.strip()
    frame["NOC3DIG"] = frame["NOC3DIG"].astype("string").str.strip()
    return frame


def require_columns(frame, required, label):
    missing = [c for c in required if c not in frame.columns]
    if missing:
        raise ValueError(f"{label} is missing required columns: {missing}")


@st.cache_data
def load_data():
    demand = pd.read_excel(DEMAND_FILE, engine="openpyxl")
    labour = pd.read_excel(LABOUR_FILE, engine="openpyxl")
    demographics = pd.read_excel(DEMOGRAPHICS_FILE, engine="openpyxl")
    wages = pd.read_excel(WAGES_FILE, engine="openpyxl")
    noc_titles = pd.read_excel(NOC_TITLES_FILE, engine="openpyxl")
    vacancies = pd.read_excel(VACANCIES_FILE, engine="openpyxl")
    cops = pd.read_excel(COPS_FILE, engine="openpyxl")
    canada_multipliers = pd.read_excel(
        CANADA_MULTIPLIERS_FILE,
        engine="openpyxl",
    )
    return (
        demand,
        labour,
        demographics,
        wages,
        noc_titles,
        vacancies,
        cops,
        canada_multipliers,
    )


def prepare_coefficients(raw):
    df = raw.copy()
    require_columns(df, REQUIRED_DEMAND_COLS, DEMAND_FILE.name)

    for col in ["IOIC", "PROV", "NOC3DIG"]:
        df[col] = df[col].astype("string").str.strip()

    df[NUMERIC_DEMAND_COLS] = df[NUMERIC_DEMAND_COLS].apply(
        pd.to_numeric,
        errors="coerce",
    )

    df["zero_industry_employment"] = df["totalemp_ind"].fillna(0).eq(0)
    df.loc[df["zero_industry_employment"], "occshare"] = np.nan

    share_check = (
        df.loc[~df["zero_industry_employment"]]
        .groupby(["PROV", "IOIC"], as_index=False)
        .agg(
            sum_occshare=("occshare", "sum"),
            totalemp_ind=("totalemp_ind", "first"),
        )
    )
    share_check["share_error"] = (share_check["sum_occshare"] - 1).abs()
    bad_shares = share_check.loc[share_check["share_error"] > 0.01].copy()

    check = (
        df.groupby(["PROV", "IOIC"])[MULTIPLIER_COLS]
        .nunique(dropna=False)
        .reset_index()
    )
    inconsistent = check.loc[
        check[MULTIPLIER_COLS].gt(1).any(axis=1)
    ].copy()

    industry_data = (
        df[["PROV", "IOIC", "totalemp_ind"] + MULTIPLIER_COLS]
        .drop_duplicates(subset=["PROV", "IOIC"])
        .copy()
    )

    occ_data = df[
        [
            "PROV", "IOIC", "NOC3DIG", "emp", "occshare",
            "totalemp_occ", "zero_industry_employment",
        ]
    ].copy()

    
    return df, industry_data, occ_data, bad_shares, inconsistent


def prepare_supply(labour, demographics, wages, vacancies):
    require_columns(labour, REQUIRED_LABOUR_COLS, LABOUR_FILE.name)
    require_columns(
        demographics,
        REQUIRED_DEMOGRAPHICS_COLS,
        DEMOGRAPHICS_FILE.name,
    )
    require_columns(wages, REQUIRED_WAGE_COLS, WAGES_FILE.name)
    require_columns(vacancies, REQUIRED_VACANCY_COLS, VACANCIES_FILE.name)

    labour = clean_keys(labour)
    demographics = clean_keys(demographics)
    wages = clean_keys(wages)
    vacancies = clean_keys(vacancies)

    labour[["employed", "unemployed", "unemprate"]] = labour[
        ["employed", "unemployed", "unemprate"]
    ].apply(pd.to_numeric, errors="coerce")

    demographics["highageshare"] = pd.to_numeric(
        demographics["highageshare"],
        errors="coerce",
    )

    wages["earn_mean"] = pd.to_numeric(
        wages["earn_mean"],
        errors="coerce",
    )

    vacancies[["vacancies", "vacancy rate"]] = vacancies[
        ["vacancies", "vacancy rate"]
    ].apply(pd.to_numeric, errors="coerce")

    # In this source, zero vacancy observations reflect sample-size
    # suppression rather than confirmed zero vacancies.
    vacancies["vacancy_suppressed"] = vacancies["vacancies"].eq(0)
    vacancies.loc[
        vacancies["vacancy_suppressed"],
        ["vacancies", "vacancy rate"],
    ] = np.nan

    # Convert proportions to percentage points.
    labour["unemprate"] = labour["unemprate"] * 100
    demographics["highageshare"] = demographics["highageshare"] * 100

    # If vacancy rate is stored as 0-1, convert to percentage points.
    # This protects against accidentally multiplying an already-percent rate.
    valid_vacancy_rates = vacancies["vacancy rate"].dropna()
    if not valid_vacancy_rates.empty and valid_vacancy_rates.max() <= 1:
        vacancies["vacancy rate"] = vacancies["vacancy rate"] * 100

    for data, name in [
        (labour, "unemployment.xlsx"),
        (demographics, "demographics.xlsx"),
        (wages, "wages.xlsx"),
        (vacancies, "vacancies.xlsx"),
    ]:
        duplicates = data.duplicated(["PROV", "NOC3DIG"])
        if duplicates.any():
            dupes = data.loc[
                data.duplicated(["PROV", "NOC3DIG"], keep=False),
                ["PROV", "NOC3DIG"],
            ]
            raise ValueError(
                f"Duplicate PROV x NOC3DIG rows in {name}:\n"
                + dupes.to_string(index=False)
            )

    supply = labour.merge(
        demographics,
        on=["PROV", "NOC3DIG"],
        how="outer",
        validate="one_to_one",
    )

    supply = supply.merge(
        wages[["PROV", "NOC3DIG", "earn_mean"]],
        on=["PROV", "NOC3DIG"],
        how="outer",
        validate="one_to_one",
    )

    supply = supply.merge(
        vacancies[
            [
                "PROV", "NOC3DIG", "vacancies", "vacancy rate",
                "vacancy_suppressed",
            ]
        ],
        on=["PROV", "NOC3DIG"],
        how="outer",
        validate="one_to_one",
    )

    return supply


def prepare_noc_titles(noc_titles):
    require_columns(noc_titles, REQUIRED_NOC_TITLE_COLS, NOC_TITLES_FILE.name)

    noc_titles = noc_titles.copy()
    noc_titles["NOC3DIG"] = (
        noc_titles["NOC3DIG"].astype("string").str.strip()
    )
    noc_titles["title"] = (
        noc_titles["title"].astype("string").str.strip()
    )

    if noc_titles["NOC3DIG"].duplicated().any():
        duplicates = noc_titles.loc[
            noc_titles["NOC3DIG"].duplicated(keep=False),
            ["NOC3DIG", "title"],
        ]
        raise ValueError(
            "Duplicate NOC3DIG codes in noc_titles.xlsx:\n"
            + duplicates.to_string(index=False)
        )

    return noc_titles

def prepare_cops(raw_cops):
    """
    Convert national COPS flows from wide format:

        noc3dig | type | year2025 | year2026 | ...

    to long format:

        NOC3DIG | calendar_year | fiscal_year | flow variables
    """
    cops = raw_cops.copy()

    require_columns(
        cops,
        REQUIRED_COPS_COLS,
        COPS_FILE.name,
    )

    # --------------------------------------------------------
    # Clean the NOC field
    # --------------------------------------------------------

    cops["NOC3DIG"] = (
        cops["noc3dig"]
        .astype("string")
        .str.strip()
        .str.replace(r"\.0$", "", regex=True)
        .str.zfill(3)
    )

    cops["type"] = (
        cops["type"]
        .astype("string")
        .str.strip()
        .str.lower()
    )

    # --------------------------------------------------------
    # Validate flow types
    # --------------------------------------------------------

    unexpected_types = sorted(
        set(cops["type"].dropna())
        - set(COPS_FLOW_TYPES)
    )

    if unexpected_types:
        raise ValueError(
            "Unexpected flow type(s) in "
            f"{COPS_FILE.name}: {unexpected_types}"
        )

    missing_types = sorted(
        set(COPS_FLOW_TYPES)
        - set(cops["type"].dropna())
    )

    if missing_types:
        raise ValueError(
            "Missing required COPS flow type(s): "
            f"{missing_types}"
        )

    # --------------------------------------------------------
    # Identify year columns
    # --------------------------------------------------------

    year_cols = [
        col for col in cops.columns
        if str(col).lower().startswith("year")
    ]

    if not year_cols:
        raise ValueError(
            f"{COPS_FILE.name} has no columns beginning with 'year'."
        )

    # --------------------------------------------------------
    # Convert annual values to numeric
    # --------------------------------------------------------

    cops[year_cols] = cops[year_cols].apply(
        pd.to_numeric,
        errors="coerce",
    )

    if cops[year_cols].isna().any().any():
        bad_rows = cops.loc[
            cops[year_cols].isna().any(axis=1),
            ["NOC3DIG", "type"],
        ]

        raise ValueError(
            "COPS contains missing or non-numeric annual values:\n"
            + bad_rows.head(20).to_string(index=False)
        )

    # --------------------------------------------------------
    # Confirm one row per NOC x flow type
    # --------------------------------------------------------

    duplicates = cops.duplicated(
        ["NOC3DIG", "type"],
        keep=False,
    )

    if duplicates.any():
        duplicate_rows = cops.loc[
            duplicates,
            ["NOC3DIG", "type"],
        ]

        raise ValueError(
            "Duplicate NOC x flow-type rows in COPS:\n"
            + duplicate_rows.to_string(index=False)
        )

    # --------------------------------------------------------
    # Reshape to long
    # --------------------------------------------------------

    cops_long = cops.melt(
        id_vars=["NOC3DIG", "type"],
        value_vars=year_cols,
        var_name="year_column",
        value_name="flow_value",
    )

    cops_long["calendar_year"] = (
        cops_long["year_column"]
        .astype(str)
        .str.extract(r"(\d{4})", expand=False)
    )

    cops_long["calendar_year"] = pd.to_numeric(
        cops_long["calendar_year"],
        errors="raise",
    ).astype(int)

    # Map calendar year 2026 to fiscal year 2026-27.
    cops_long["fiscal_year"] = (
        cops_long["calendar_year"].astype(str)
        + "-"
        + (
            (cops_long["calendar_year"] + 1) % 100
        )
        .astype(str)
        .str.zfill(2)
    )

    # --------------------------------------------------------
    # Put each flow in its own column
    # --------------------------------------------------------

    cops_prepared = (
        cops_long
        .pivot(
            index=[
                "NOC3DIG",
                "calendar_year",
                "fiscal_year",
            ],
            columns="type",
            values="flow_value",
        )
        .reset_index()
    )

    cops_prepared.columns.name = None

    # --------------------------------------------------------
    # Derived national measures
    # --------------------------------------------------------

    cops_prepared["total_inflows"] = cops_prepared[
        [
            "school_inflow",
            "immigrant_inflow",
            "other_inflow",
        ]
    ].sum(axis=1)

    cops_prepared["replacement_demand"] = cops_prepared[
        [
            "retirement_outflow",
            "emigration_outflow",
        ]
    ].sum(axis=1)

    cops_prepared["total_baseline_openings"] = (
        cops_prepared["expansiondemand"]
        + cops_prepared["replacement_demand"]
    )

    cops_prepared["baseline_balance"] = (
        cops_prepared["total_inflows"]
        - cops_prepared["total_baseline_openings"]
    )

    return cops_prepared

def weighted_mean(values, weights):
    """Return a weighted mean using rows where both inputs are available."""
    valid = values.notna() & weights.notna() & weights.gt(0)
    if not valid.any():
        return np.nan
    return np.average(values.loc[valid], weights=weights.loc[valid])


def prepare_canada_multipliers(raw_canada):
    """Prepare official Canada-level all-provinces multipliers."""
    canada = raw_canada.copy()
    require_columns(
        canada,
        REQUIRED_CANADA_MULTIPLIER_COLS,
        CANADA_MULTIPLIERS_FILE.name,
    )

    canada = canada[REQUIRED_CANADA_MULTIPLIER_COLS].copy()
    canada["PROV"] = canada["PROV"].astype("string").str.strip().str.upper()
    canada["IOIC"] = canada["IOIC"].astype("string").str.strip()

    if not canada["PROV"].eq("CA").all():
        raise ValueError(
            f"{CANADA_MULTIPLIERS_FILE.name} must use PROV='CA' for every row."
        )

    numeric_cols = [
        c for c in REQUIRED_CANADA_MULTIPLIER_COLS
        if c not in {"PROV", "IOIC"}
    ]
    canada[numeric_cols] = canada[numeric_cols].apply(
        pd.to_numeric,
        errors="coerce",
    )

    if canada[numeric_cols].isna().any().any():
        bad = canada.loc[
            canada[numeric_cols].isna().any(axis=1),
            ["PROV", "IOIC"],
        ]
        raise ValueError(
            "Canada multipliers contain missing or non-numeric values:\n"
            + bad.to_string(index=False)
        )

    if canada["IOIC"].duplicated().any():
        dupes = canada.loc[
            canada["IOIC"].duplicated(keep=False),
            ["PROV", "IOIC"],
        ]
        raise ValueError(
            "Duplicate Canada multiplier industries:\n"
            + dupes.to_string(index=False)
        )

    # Canada has no separate within-province concept. Mirroring the official
    # all-provinces fields lets mixed provincial/Canada plans run while the UI
    # clearly identifies CA as a Canada benchmark.
    for effect in ["job", "wage"]:
        for channel in ["direct", "indirect", "induced"]:
            canada[f"{channel}_within_{effect}"] = canada[
                f"{channel}_all_{effect}"
            ]

    return canada


def make_canada_occ_data(provincial_occ):
    """Aggregate ten-province industry-occupation employment to PROV='CA'."""
    source = provincial_occ.loc[
        provincial_occ["PROV"].ne("CA")
    ].copy()

    source["emp"] = pd.to_numeric(source["emp"], errors="coerce")
    source["totalemp_occ"] = pd.to_numeric(
        source["totalemp_occ"],
        errors="coerce",
    )

    canada = (
        source.groupby(["IOIC", "NOC3DIG"], as_index=False)
        .agg(emp=("emp", "sum"))
    )
    canada["totalemp_ind"] = (
        canada.groupby("IOIC")["emp"].transform("sum")
    )
    canada["occshare"] = np.where(
        canada["totalemp_ind"].gt(0),
        canada["emp"] / canada["totalemp_ind"],
        np.nan,
    )

    # totalemp_occ is repeated across industries in the source. Retain one
    # observation per province x occupation before summing the ten provinces.
    national_occ_totals = (
        source[["PROV", "NOC3DIG", "totalemp_occ"]]
        .drop_duplicates(["PROV", "NOC3DIG"])
        .groupby("NOC3DIG", as_index=False)
        .agg(totalemp_occ=("totalemp_occ", "sum"))
    )
    canada = canada.merge(
        national_occ_totals,
        on="NOC3DIG",
        how="left",
        validate="many_to_one",
    )
    canada["PROV"] = "CA"
    canada["zero_industry_employment"] = canada["totalemp_ind"].fillna(0).eq(0)

    return canada[
        [
            "PROV",
            "IOIC",
            "NOC3DIG",
            "emp",
            "occshare",
            "totalemp_occ",
            "zero_industry_employment",
        ]
    ]


def make_canada_supply_data(provincial_supply):
    """Create a ten-province national labour-market benchmark by occupation."""
    source = provincial_supply.loc[
        provincial_supply["PROV"].ne("CA")
    ].copy()

    numeric_cols = [
        "employed",
        "unemployed",
        "unemprate",
        "highageshare",
        "earn_mean",
        "vacancies",
        "vacancy rate",
    ]
    for col in numeric_cols:
        source[col] = pd.to_numeric(source[col], errors="coerce")

    rows = []
    for noc, group in source.groupby("NOC3DIG", dropna=False):
        employed = group["employed"].sum(min_count=1)
        unemployed = group["unemployed"].sum(min_count=1)
        labour_force = employed + unemployed
        unemprate = (
            unemployed / labour_force * 100
            if pd.notna(labour_force) and labour_force > 0
            else np.nan
        )

        rows.append(
            {
                "PROV": "CA",
                "NOC3DIG": noc,
                "employed": employed,
                "unemployed": unemployed,
                "unemprate": unemprate,
                "highageshare": weighted_mean(
                    group["highageshare"],
                    group["employed"],
                ),
                "earn_mean": weighted_mean(
                    group["earn_mean"],
                    group["employed"],
                ),
                "vacancies": group["vacancies"].sum(min_count=1),
                "vacancy rate": weighted_mean(
                    group["vacancy rate"],
                    group["employed"],
                ),
                "vacancy_suppressed": group["vacancies"].notna().sum() == 0,
            }
        )

    return pd.DataFrame(rows)


def append_canada_benchmark(
    industry_data,
    occ_data,
    supply_data,
    canada_multipliers,
):
    """Append official Canada multipliers and ten-province aggregates."""
    canada_occ = make_canada_occ_data(occ_data)
    canada_supply = make_canada_supply_data(supply_data)

    canada_industry_totals = (
        canada_occ.groupby("IOIC", as_index=False)
        .agg(totalemp_ind=("emp", "sum"))
    )

    canada_industry = canada_multipliers.merge(
        canada_industry_totals,
        on="IOIC",
        how="left",
        validate="one_to_one",
    )

    industry_cols = ["PROV", "IOIC", "totalemp_ind"] + MULTIPLIER_COLS
    canada_industry = canada_industry[industry_cols]

    industry_out = pd.concat(
        [industry_data, canada_industry],
        ignore_index=True,
    )
    occ_out = pd.concat([occ_data, canada_occ], ignore_index=True)
    supply_out = pd.concat([supply_data, canada_supply], ignore_index=True)

    unmatched_canada_industries = canada_industry.loc[
        canada_industry["totalemp_ind"].isna(),
        ["PROV", "IOIC"],
    ].copy()

    provincial_industries = set(
        occ_data["IOIC"].dropna().astype(str).str.strip()
    )
    multiplier_industries = set(
        canada_multipliers["IOIC"].dropna().astype(str).str.strip()
    )
    missing_canada_multipliers = sorted(
        provincial_industries - multiplier_industries
    )

    return (
        industry_out,
        occ_out,
        supply_out,
        unmatched_canada_industries,
        missing_canada_multipliers,
    )

# ============================================================
# CORE STATIC LAMP ENGINE
# ============================================================

def run_scenario(
    scenario,
    industry_data,
    occ_data,
    supply_data,
    noc_titles,
    geography="within",
):
    scenario = scenario.copy()

    for col in ["PROV", "IOIC"]:
        scenario[col] = scenario[col].astype("string").str.strip()

    scenario["investment_millions"] = pd.to_numeric(
        scenario["investment_millions"],
        errors="coerce",
    )

    if scenario["investment_millions"].isna().any():
        raise ValueError(
            "Scenario contains missing or non-numeric investment values."
        )

    if scenario["investment_millions"].lt(0).any():
        raise ValueError("Investment values cannot be negative.")

    scenario = (
        scenario.loc[scenario["investment_millions"].gt(0)]
        .groupby(["PROV", "IOIC"], as_index=False)["investment_millions"]
        .sum()
    )

    if scenario.empty:
        raise ValueError("Add at least one positive investment shock.")

    scenario["investment_dollars"] = (
        scenario["investment_millions"] * 1_000_000
    )

    if geography == "within":
        rename = {
            "direct_within_job": "direct_job_multiplier",
            "indirect_within_job": "indirect_job_multiplier",
            "induced_within_job": "induced_job_multiplier",
            "direct_within_wage": "direct_wage_multiplier",
            "indirect_within_wage": "indirect_wage_multiplier",
            "induced_within_wage": "induced_wage_multiplier",
        }
    elif geography == "all":
        rename = {
            "direct_all_job": "direct_job_multiplier",
            "indirect_all_job": "indirect_job_multiplier",
            "induced_all_job": "induced_job_multiplier",
            "direct_all_wage": "direct_wage_multiplier",
            "indirect_all_wage": "indirect_wage_multiplier",
            "induced_all_wage": "induced_wage_multiplier",
        }
    else:
        raise ValueError("geography must be 'within' or 'all'.")

    multipliers = industry_data[
        ["PROV", "IOIC", "totalemp_ind"] + list(rename)
    ].rename(columns=rename)

    merged = scenario.merge(
        multipliers,
        on=["PROV", "IOIC"],
        how="left",
        indicator=True,
    )

    unmatched = merged.loc[
        merged["_merge"].ne("both"),
        ["PROV", "IOIC", "investment_millions"],
    ]

    if not unmatched.empty:
        raise ValueError(
            "Unmatched province x industry combinations:\n"
            + unmatched.to_string(index=False)
        )

    industry = merged.drop(columns="_merge").copy()

    industry["direct_jobs"] = (
        industry["investment_millions"] * industry["direct_job_multiplier"]
    )
    industry["indirect_jobs"] = (
        industry["investment_millions"] * industry["indirect_job_multiplier"]
    )
    industry["induced_jobs"] = (
        industry["investment_millions"] * industry["induced_job_multiplier"]
    )
    industry["total_jobs"] = industry[
        ["direct_jobs", "indirect_jobs", "induced_jobs"]
    ].sum(axis=1)

    industry["direct_labour_income"] = (
        industry["investment_dollars"] * industry["direct_wage_multiplier"]
    )
    industry["indirect_labour_income"] = (
        industry["investment_dollars"] * industry["indirect_wage_multiplier"]
    )
    industry["induced_labour_income"] = (
        industry["investment_dollars"] * industry["induced_wage_multiplier"]
    )
    industry["total_labour_income"] = industry[
        [
            "direct_labour_income",
            "indirect_labour_income",
            "induced_labour_income",
        ]
    ].sum(axis=1)

    detailed = industry[
        ["PROV", "IOIC", "investment_millions", "direct_jobs"]
    ].merge(
        occ_data,
        on=["PROV", "IOIC"],
        how="left",
    )

    zero_inputs = detailed.loc[
        detailed["zero_industry_employment"].eq(True),
        ["PROV", "IOIC", "investment_millions"],
    ].drop_duplicates()

    detailed["new_jobs"] = detailed["direct_jobs"] * detailed["occshare"]

    occupation = (
        detailed.dropna(subset=["NOC3DIG", "new_jobs"])
        .groupby(["PROV", "NOC3DIG"], as_index=False)
        .agg(
            new_jobs=("new_jobs", "sum"),
            totalemp_occ=("totalemp_occ", "first"),
        )
    )

    occupation = occupation.loc[occupation["new_jobs"].gt(0)].copy()

    occupation["employment_change_pct"] = np.where(
        occupation["totalemp_occ"].gt(0),
        occupation["new_jobs"] / occupation["totalemp_occ"] * 100,
        np.nan,
    )

    occupation = occupation.merge(
        supply_data,
        on=["PROV", "NOC3DIG"],
        how="left",
        validate="one_to_one",
    )

    occupation = occupation.merge(
        noc_titles,
        on="NOC3DIG",
        how="left",
        validate="many_to_one",
    )

    occupation["supply_employment_change_pct"] = np.where(
        occupation["employed"].gt(0),
        occupation["new_jobs"] / occupation["employed"] * 100,
        np.nan,
    )

    occupation["pressure_rank"] = (
        occupation.groupby("PROV")["employment_change_pct"]
        .rank(method="min", ascending=False)
    )

    occupation = occupation.sort_values(
        ["PROV", "employment_change_pct", "new_jobs"],
        ascending=[True, False, False],
    ).reset_index(drop=True)

    summary = {
        "Investment ($M)": industry["investment_millions"].sum(),
        "Direct jobs": industry["direct_jobs"].sum(),
        "Indirect jobs": industry["indirect_jobs"].sum(),
        "Induced jobs": industry["induced_jobs"].sum(),
        "Total jobs": industry["total_jobs"].sum(),
        "Direct labour income": industry["direct_labour_income"].sum(),
        "Total labour income": industry["total_labour_income"].sum(),
    }

    return {
        "summary": summary,
        "industry": industry,
        "occupation": occupation,
        "detailed": detailed,
        "zero_inputs": zero_inputs,
    }


# ============================================================
# TIMELINE / PROJECT PIPELINE ENGINE
# ============================================================

def run_timeline_scenario(
    timeline,
    industry_data,
    occ_data,
    supply_data,
    noc_titles,
    provincial_cops,
    geography="within",
):
    timeline = timeline.copy()

    required = [
        "project_name",
        "PROV",
        "fiscal_year",
        "IOIC",
        "investment_millions",
    ]
    missing = [c for c in required if c not in timeline.columns]
    if missing:
        raise ValueError(f"Timeline is missing columns: {missing}")

    for col in ["project_name", "PROV", "fiscal_year", "IOIC"]:
        timeline[col] = timeline[col].astype("string").str.strip()

    timeline["investment_millions"] = pd.to_numeric(
        timeline["investment_millions"],
        errors="coerce",
    )

    if timeline["investment_millions"].isna().any():
        raise ValueError(
            "Timeline contains missing or non-numeric investment values."
        )

    if timeline["investment_millions"].lt(0).any():
        raise ValueError("Investment values cannot be negative.")

    timeline = timeline.loc[timeline["investment_millions"].gt(0)].copy()

    if timeline.empty:
        raise ValueError("Add at least one positive annual investment.")

    # Preserve fiscal-year order for display.
    fiscal_order = [
        fy for fy in FISCAL_YEARS
        if fy in timeline["fiscal_year"].dropna().unique().tolist()
    ]
    extra_years = [
        fy for fy in timeline["fiscal_year"].dropna().unique().tolist()
        if fy not in fiscal_order
    ]
    fiscal_order += extra_years

    industry_results = []
    occupation_results = []

    groups = timeline.groupby(
        ["project_name", "fiscal_year"],
        sort=False,
    )

    for (project_name, fiscal_year), project_year in groups:
        scenario = project_year[
            ["PROV", "IOIC", "investment_millions"]
        ].copy()

        result = run_scenario(
            scenario,
            industry_data,
            occ_data,
            supply_data,
            noc_titles,
            geography,
        )

        industry_part = result["industry"].copy()
        industry_part["project_name"] = project_name
        industry_part["fiscal_year"] = fiscal_year
        industry_results.append(industry_part)

        occupation_part = result["occupation"].copy()
        occupation_part["project_name"] = project_name
        occupation_part["fiscal_year"] = fiscal_year
        occupation_results.append(occupation_part)

    industry_by_project = pd.concat(industry_results, ignore_index=True)
    occupation_by_project = pd.concat(occupation_results, ignore_index=True)

    annual_industry = (
        industry_by_project
        .groupby("fiscal_year", as_index=False)
        .agg(
            investment_millions=("investment_millions", "sum"),
            direct_jobs=("direct_jobs", "sum"),
            indirect_jobs=("indirect_jobs", "sum"),
            induced_jobs=("induced_jobs", "sum"),
            total_jobs=("total_jobs", "sum"),
            direct_labour_income=("direct_labour_income", "sum"),
            total_labour_income=("total_labour_income", "sum"),
        )
    )

    annual_industry["fiscal_year"] = pd.Categorical(
        annual_industry["fiscal_year"],
        categories=fiscal_order,
        ordered=True,
    )
    annual_industry = annual_industry.sort_values("fiscal_year").reset_index(drop=True)
    annual_industry["fiscal_year"] = annual_industry["fiscal_year"].astype(str)

    # Sum project contributions before merging the static labour-market context.
    annual_occ = (
        occupation_by_project
        .groupby(["PROV", "fiscal_year", "NOC3DIG"], as_index=False)
        .agg(
            new_jobs=("new_jobs", "sum"),
            totalemp_occ=("totalemp_occ", "first"),
            employed=("employed", "first"),
            unemployed=("unemployed", "first"),
            unemprate=("unemprate", "first"),
            vacancies=("vacancies", "first"),
            vacancy_rate=("vacancy rate", "first"),
            vacancy_suppressed=("vacancy_suppressed", "first"),
            earn_mean=("earn_mean", "first"),
            highageshare=("highageshare", "first"),
            title=("title", "first"),
        )
    )

    annual_occ["employment_change_pct"] = np.where(
        annual_occ["totalemp_occ"].gt(0),
        annual_occ["new_jobs"] / annual_occ["totalemp_occ"] * 100,
        np.nan,
    )

    annual_occ["supply_employment_change_pct"] = np.where(
        annual_occ["employed"].gt(0),
        annual_occ["new_jobs"] / annual_occ["employed"] * 100,
        np.nan,
    )

        # ========================================================
    # MERGE COPS BASELINE FLOWS
    # ========================================================

    cops_merge_cols = [
        "PROV",
        "NOC3DIG",
        "fiscal_year",
        "provincial_employment_share",
        "expansiondemand",
        "retirement_outflow",
        "emigration_outflow",
        "school_inflow",
        "immigrant_inflow",
        "other_inflow",
        "total_inflows",
        "replacement_demand",
        "total_baseline_openings",
        "baseline_balance",
    ]

    annual_occ = annual_occ.merge(
        provincial_cops[cops_merge_cols],
        on=["PROV", "NOC3DIG", "fiscal_year"],
        how="left",
        validate="many_to_one",
    )

    # COPS baseline after adding incremental LAMP requirements.
    annual_occ["post_project_balance"] = (
        annual_occ["baseline_balance"]
        - annual_occ["new_jobs"]
    )

    # Positive values indicate an estimated deficit/pressure.
    annual_occ["baseline_gap"] = (
        -annual_occ["baseline_balance"]
    ).clip(lower=0)

    annual_occ["post_project_gap"] = (
        -annual_occ["post_project_balance"]
    ).clip(lower=0)

    # Amount by which LAMP worsens an existing deficit or creates
    # an entirely new deficit.
    annual_occ["incremental_gap_due_to_projects"] = (
        annual_occ["post_project_gap"]
        - annual_occ["baseline_gap"]
    ).clip(lower=0)

    annual_occ["post_project_balance_pct"] = np.where(
        annual_occ["employed"].gt(0),
        annual_occ["post_project_balance"]
        / annual_occ["employed"]
        * 100,
        np.nan,
    )

    annual_occ["post_project_gap_pct"] = np.where(
        annual_occ["employed"].gt(0),
        annual_occ["post_project_gap"]
        / annual_occ["employed"]
        * 100,
        np.nan,
    )

    annual_occ["balance_status"] = np.select(
        [
            annual_occ["baseline_balance"].ge(0)
            & annual_occ["post_project_balance"].lt(0),

            annual_occ["baseline_balance"].lt(0)
            & annual_occ["post_project_balance"].lt(
                annual_occ["baseline_balance"]
            ),

            annual_occ["post_project_balance"].ge(0),
        ],
        [
            "Moves into deficit with projects",
            "Existing deficit worsens",
            "Projected inflows cover openings",
        ],
        default="Missing COPS projection",
    )

    annual_occ["cops_available"] = (
        annual_occ["baseline_balance"].notna()
    )

    annual_occ["fiscal_year"] = pd.Categorical(
        annual_occ["fiscal_year"],
        categories=fiscal_order,
        ordered=True,
    )
    annual_occ = annual_occ.sort_values(
        ["fiscal_year", "PROV", "employment_change_pct"],
        ascending=[True, True, False],
    ).reset_index(drop=True)
    annual_occ["fiscal_year"] = annual_occ["fiscal_year"].astype(str)

    valid_peak = annual_occ.dropna(subset=["employment_change_pct"]).copy()

    if valid_peak.empty:
        peak_occ = pd.DataFrame()
    else:
        peak_index = (
            valid_peak.groupby(["PROV", "NOC3DIG"])["employment_change_pct"]
            .idxmax()
        )
        peak_occ = (
            valid_peak.loc[peak_index]
            .copy()
            .rename(
                columns={
                    "fiscal_year": "peak_fiscal_year",
                    "new_jobs": "peak_new_jobs",
                    "employment_change_pct": "peak_pressure_pct",
                    "supply_employment_change_pct": "peak_supply_pressure_pct",
                }
            )
            .sort_values("peak_pressure_pct", ascending=False)
            .reset_index(drop=True)
        )

        # ========================================================
    # PEAK COPS-ADJUSTED LABOUR PRESSURE
    # ========================================================

    valid_cops_peak = annual_occ.dropna(
        subset=["post_project_gap_pct"]
    ).copy()

    if valid_cops_peak.empty:
        cops_peak_occ = pd.DataFrame()
    else:
        cops_peak_index = (
            valid_cops_peak
            .groupby(["PROV", "NOC3DIG"])["post_project_gap_pct"]
            .idxmax()
        )

        cops_peak_occ = (
            valid_cops_peak.loc[cops_peak_index]
            .copy()
            .rename(
                columns={
                    "fiscal_year": "peak_cops_fiscal_year",
                    "new_jobs": "peak_lamp_demand",
                    "baseline_balance": "peak_baseline_balance",
                    "post_project_balance": "peak_post_project_balance",
                    "post_project_gap": "peak_post_project_gap",
                    "post_project_gap_pct": "peak_post_project_gap_pct",
                }
            )
            .sort_values(
                "peak_post_project_gap_pct",
                ascending=False,
            )
            .reset_index(drop=True)
        )

    # Project-level contribution to each province x occupation x year.
    project_occ = occupation_by_project[
        [
            "project_name", "PROV", "fiscal_year", "NOC3DIG", "title",
            "new_jobs", "employment_change_pct",
        ]
    ].copy()

    summary = {
        "Total investment ($M)": timeline["investment_millions"].sum(),
        "Number of projects": timeline["project_name"].nunique(),
        "Number of fiscal years": timeline["fiscal_year"].nunique(),
        "Peak direct jobs": annual_industry["direct_jobs"].max(),
        "Peak direct jobs FY": annual_industry.loc[
            annual_industry["direct_jobs"].idxmax(), "fiscal_year"
        ],
    }

    return {
        "summary": summary,
        "timeline_inputs": timeline,
        "industry_by_project": industry_by_project,
        "occupation_by_project": occupation_by_project,
        "annual_industry": annual_industry,
        "annual_occupation": annual_occ,
        "peak_occupation": peak_occ,
        "cops_peak_occupation": cops_peak_occ,
        "project_occupation": project_occ,
        "fiscal_order": fiscal_order,
    }


# ============================================================
# DOWNLOAD HELPER
# ============================================================

def to_excel_bytes(sheets):
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for name, frame in sheets.items():
            frame.to_excel(writer, sheet_name=name[:31], index=False)
    return buffer.getvalue()

# ============================================================
# PROJECT PLAN SAVE / LOAD HELPERS
# ============================================================

PLAN_COLUMNS = [
    "project_name",
    "PROV",
    "fiscal_year",
    "IOIC",
    "investment_millions",
]


def make_plan_template(industry_data):
    """
    Create a blank Excel template with a second sheet containing
    all valid province x IOIC combinations.
    """
    blank_plan = pd.DataFrame(columns=PLAN_COLUMNS)

    valid_industries = (
        industry_data[["PROV", "IOIC"]]
        .dropna()
        .drop_duplicates()
        .sort_values(["PROV", "IOIC"])
        .reset_index(drop=True)
    )

    return to_excel_bytes(
        {
            "Project plan": blank_plan,
            "Valid industries": valid_industries,
        }
    )


def make_saved_plan(plan, industry_data):
    """
    Save the current plan along with the valid IOIC reference sheet.
    """
    valid_industries = (
        industry_data[["PROV", "IOIC"]]
        .dropna()
        .drop_duplicates()
        .sort_values(["PROV", "IOIC"])
        .reset_index(drop=True)
    )

    return to_excel_bytes(
        {
            "Project plan": plan[PLAN_COLUMNS],
            "Valid industries": valid_industries,
        }
    )

def make_provincial_cops(cops_data, supply_data):
    """
    Allocate national COPS flows to the ten provinces by current employment
    share, then append an unallocated national CA benchmark.
    """
    provincial_supply = supply_data.loc[
        supply_data["PROV"].ne("CA")
    ].copy()

    employment = provincial_supply[
        ["PROV", "NOC3DIG", "employed"]
    ].copy()
    employment["employed"] = pd.to_numeric(
        employment["employed"],
        errors="coerce",
    )
    employment["national_employment"] = (
        employment.groupby("NOC3DIG")["employed"].transform("sum")
    )
    employment["provincial_employment_share"] = np.where(
        employment["national_employment"].gt(0),
        employment["employed"] / employment["national_employment"],
        np.nan,
    )

    provincial_cops = employment[
        [
            "PROV",
            "NOC3DIG",
            "provincial_employment_share",
            "national_employment",
        ]
    ].merge(
        cops_data,
        on="NOC3DIG",
        how="inner",
        validate="many_to_many",
    )

    flow_cols = [
        "expansiondemand",
        "retirement_outflow",
        "emigration_outflow",
        "school_inflow",
        "immigrant_inflow",
        "other_inflow",
        "total_inflows",
        "replacement_demand",
        "total_baseline_openings",
        "baseline_balance",
    ]
    for col in flow_cols:
        provincial_cops[col] = (
            provincial_cops[col]
            * provincial_cops["provincial_employment_share"]
        )

    national_employment = (
        provincial_supply.groupby("NOC3DIG", as_index=False)
        .agg(national_employment=("employed", "sum"))
    )
    canada_cops = cops_data.merge(
        national_employment,
        on="NOC3DIG",
        how="left",
        validate="many_to_one",
    )
    canada_cops["PROV"] = "CA"
    canada_cops["provincial_employment_share"] = 1.0

    return pd.concat(
        [provincial_cops, canada_cops],
        ignore_index=True,
        sort=False,
    )

def validate_uploaded_plan(plan, industry_data):
    """
    Validate an uploaded LAMP project plan.

    Returns:
        cleaned_plan
        errors
    """
    errors = []

    # --------------------------------------------------------
    # 1. Required columns
    # --------------------------------------------------------

    missing = [c for c in PLAN_COLUMNS if c not in plan.columns]

    if missing:
        errors.append(
            "Missing required columns: "
            + ", ".join(missing)
        )
        return plan, errors

    plan = plan[PLAN_COLUMNS].copy()

    # --------------------------------------------------------
    # 2. Clean text fields
    # --------------------------------------------------------

    for col in [
        "project_name",
        "PROV",
        "fiscal_year",
        "IOIC",
    ]:
        plan[col] = (
            plan[col]
            .astype("string")
            .str.strip()
        )

    # Remove completely blank rows
    plan = plan.dropna(how="all").copy()

    # --------------------------------------------------------
    # 3. Investment
    # --------------------------------------------------------

    plan["investment_millions"] = pd.to_numeric(
        plan["investment_millions"],
        errors="coerce",
    )

    bad_investment = plan[
        plan["investment_millions"].isna()
        | plan["investment_millions"].lt(0)
    ]

    if not bad_investment.empty:
        rows = (bad_investment.index + 2).tolist()

        errors.append(
            "Investment must be numeric and non-negative. "
            f"Check Excel row(s): {rows}"
        )

    # --------------------------------------------------------
    # 4. Project names
    # --------------------------------------------------------

    bad_project = plan[
        plan["project_name"].isna()
        | plan["project_name"].eq("")
    ]

    if not bad_project.empty:
        rows = (bad_project.index + 2).tolist()

        errors.append(
            "Project name cannot be blank. "
            f"Check Excel row(s): {rows}"
        )

    # --------------------------------------------------------
    # 5. Provinces
    # --------------------------------------------------------

    valid_provinces = set(
        industry_data["PROV"]
        .dropna()
        .astype(str)
        .str.strip()
    )

    bad_province = plan[
        ~plan["PROV"].isin(valid_provinces)
    ]

    if not bad_province.empty:
        invalid = (
            bad_province["PROV"]
            .dropna()
            .unique()
            .tolist()
        )

        errors.append(
            "Invalid province code(s): "
            + ", ".join(map(str, invalid))
        )

    # --------------------------------------------------------
    # 6. Fiscal years
    # --------------------------------------------------------

    bad_year = plan[
        ~plan["fiscal_year"].isin(FISCAL_YEARS)
    ]

    if not bad_year.empty:
        invalid = (
            bad_year["fiscal_year"]
            .dropna()
            .unique()
            .tolist()
        )

        errors.append(
            "Invalid fiscal year(s): "
            + ", ".join(map(str, invalid))
        )

    # --------------------------------------------------------
    # 7. Province x IOIC combinations
    # --------------------------------------------------------

    valid_combinations = (
        industry_data[["PROV", "IOIC"]]
        .dropna()
        .drop_duplicates()
        .copy()
    )

    valid_combinations["PROV"] = (
        valid_combinations["PROV"]
        .astype("string")
        .str.strip()
    )

    valid_combinations["IOIC"] = (
        valid_combinations["IOIC"]
        .astype("string")
        .str.strip()
    )

    combination_check = plan.merge(
        valid_combinations.assign(valid_combination=True),
        on=["PROV", "IOIC"],
        how="left",
    )

    bad_ioic = combination_check[
        combination_check["valid_combination"].isna()
    ]

    if not bad_ioic.empty:
        invalid = (
            bad_ioic[["PROV", "IOIC"]]
            .drop_duplicates()
        )

        invalid_text = "; ".join(
            f"{row.PROV} × {row.IOIC}"
            for row in invalid.itertuples()
        )

        errors.append(
            "Invalid province × industry combination(s): "
            + invalid_text
            + ". Use the 'Valid industries' sheet in the template."
        )

    return plan, errors
    
# ============================================================
# SESSION STATE
# ============================================================

def reset_static_scenario():
    st.session_state["scenario_rows"] = pd.DataFrame(
        columns=["PROV", "IOIC", "investment_millions"]
    )
    st.session_state["results"] = None


def reset_timeline_scenario():
    st.session_state["timeline_rows"] = pd.DataFrame(
        columns=[
            "project_name",
            "PROV",
            "fiscal_year",
            "IOIC",
            "investment_millions",
        ]
    )
    st.session_state["timeline_results"] = None


if "scenario_rows" not in st.session_state:
    reset_static_scenario()
if "results" not in st.session_state:
    st.session_state["results"] = None
if "timeline_rows" not in st.session_state:
    reset_timeline_scenario()
if "timeline_results" not in st.session_state:
    st.session_state["timeline_results"] = None


# ============================================================
# LOAD AND PREPARE DATA
# ============================================================

try:
    (
        raw,
        labour,
        demographics,
        wages,
        noc_titles,
        vacancies,
        raw_cops,
        raw_canada_multipliers,
    ) = load_data()

    (
        df,
        industry_data,
        occ_data,
        bad_shares,
        inconsistent_multipliers,
    ) = prepare_coefficients(raw)

    supply_data = prepare_supply(
        labour,
        demographics,
        wages,
        vacancies,
    )

    noc_titles = prepare_noc_titles(noc_titles)
    cops_data = prepare_cops(raw_cops)
    canada_multipliers = prepare_canada_multipliers(
        raw_canada_multipliers
    )
    (
        industry_data,
        occ_data,
        supply_data,
        unmatched_canada_industries,
        missing_canada_multipliers,
    ) = append_canada_benchmark(
        industry_data,
        occ_data,
        supply_data,
        canada_multipliers,
    )
    provincial_cops = make_provincial_cops(cops_data, supply_data)
except Exception as exc:
    st.error(f"Could not prepare the data: {exc}")
    st.stop()

    # ============================================================
# COPS VALIDATION
# ============================================================

# ------------------------------------------------------------
# 1. Check that provincial allocation shares sum to one
# ------------------------------------------------------------

cops_share_check = (
    provincial_cops.loc[
        provincial_cops["PROV"].ne("CA"),
        ["NOC3DIG", "PROV", "provincial_employment_share"],
    ]
    .drop_duplicates()
    .groupby("NOC3DIG", as_index=False)
    .agg(
        share_sum=("provincial_employment_share", "sum")
    )
)

bad_cops_shares = cops_share_check.loc[
    ~np.isclose(
        cops_share_check["share_sum"],
        1,
        atol=0.001,
    )
]

# ------------------------------------------------------------
# 2. Check whether any LAMP occupations are missing from COPS
# ------------------------------------------------------------

lamp_nocs = set(
    occ_data["NOC3DIG"]
    .dropna()
    .astype(str)
    .str.strip()
)

cops_nocs = set(
    cops_data["NOC3DIG"]
    .dropna()
    .astype(str)
    .str.strip()
)

missing_cops_nocs = sorted(
    lamp_nocs - cops_nocs
)

# ============================================================
# HEADER AND GLOBAL VALIDATION
# ============================================================

st.title("LAMP: Labour Analysis of Major Projects")
st.caption(
    "Translate provincial industry investment shocks into employment, "
    "direct occupational requirements, labour-market context, and annual "
    "project-pipeline pressures."
)

with st.expander("Method and interpretation"):
    st.markdown(
        """
- Investment is entered in **millions of dollars**.
- Industry results include direct, indirect, and induced jobs and labour income.
- Occupational requirements allocate **direct jobs only** using province-industry occupational shares.
- Supply-side indicators are merged at the **province × NOC3DIG** level.
- Static scenarios treat the investment shock as occurring at one point in time.
- Project timeline scenarios treat annual funding/expenditure as generating labour requirements in that fiscal year.
- Timeline pressure measures use the current workforce as a fixed capacity benchmark across fiscal years.
- Employment pressure is a demand exposure measure, **not a shortage estimate**.
- COPS provides annual national occupational inflows and baseline labour demand.
- COPS national flows are allocated to provinces using current provincial employment shares within each occupation.
- Baseline COPS balance equals projected inflows less expansion demand, retirements, and emigration.
- The post-project balance subtracts LAMP direct occupational requirements from the baseline COPS balance.
- COPS "other inflows" include occupational mobility, net re-entry, and other adjustments and are not interpreted as an independently available worker pool.
- COPS-adjusted balances are accounting pressure indicators, not equilibrium shortage forecasts.
- **Canada benchmark** uses official Canada-level all-provinces multipliers and occupational/labour-market aggregates constructed from the ten provincial source files.
- Canada has no separate "within province" multiplier. CA rows always use the official all-provinces multiplier values.
- The Canada benchmark excludes the territories from the aggregated employment, unemployment, wage, vacancy, demographic, and occupational-share inputs.
        """
    )

if bad_shares.empty:
    st.sidebar.success("Occupation-share validation passed.")
else:
    st.sidebar.error("Occupation-share validation failed.")
    st.dataframe(bad_shares, hide_index=True, width="stretch")
    st.stop()

if not inconsistent_multipliers.empty:
    st.sidebar.error("Multipliers vary within some province-industry cells.")
    st.dataframe(inconsistent_multipliers, hide_index=True, width="stretch")
    st.stop()
    
# COPS provincial allocation validation

if bad_cops_shares.empty:
    st.sidebar.success("COPS provincial allocation validation passed.")
else:
    st.sidebar.warning(
        f"{len(bad_cops_shares):,} COPS occupation groups "
        "could not be fully allocated across provinces."
    )


# COPS / LAMP occupation matching validation

if not missing_cops_nocs:
    st.sidebar.success("LAMP-COPS occupation matching passed.")
else:
    st.sidebar.warning(
        f"{len(missing_cops_nocs):,} LAMP occupation groups "
        "have no matching COPS flow data."
    )

if unmatched_canada_industries.empty:
    st.sidebar.success("Canada multiplier-industry matching passed.")
else:
    st.sidebar.warning(
        f"{len(unmatched_canada_industries):,} Canada multiplier industries "
        "have no matching ten-province occupational structure."
    )

if missing_canada_multipliers:
    st.sidebar.warning(
        f"{len(missing_canada_multipliers):,} industries in the provincial "
        "occupational data have no Canada-level multiplier."
    )

provinces = (
    industry_data["PROV"]
    .dropna()
    .astype(str)
    .drop_duplicates()
    .tolist()
)
provinces = sorted(
    provinces,
    key=lambda code: (code != "CA", code),
)
province_labels = {
    "CA": "Canada benchmark (10-province labour context)",
}


# ============================================================
# MODE SELECTOR
# ============================================================

scenario_mode = st.radio(
    "Analysis mode",
    ["Static scenario", "Project timeline"],
    horizontal=True,
)


# ============================================================
# STATIC SCENARIO MODE
# ============================================================

if scenario_mode == "Static scenario":
    st.sidebar.header("Static scenario")

    selected_prov = st.sidebar.selectbox(
        "Province",
        provinces,
        format_func=lambda code: province_labels.get(code, code),
        key="static_province",
    )

    if selected_prov == "CA":
        st.sidebar.caption(
            "Canada benchmark uses official national all-provinces multipliers "
            "and labour-market aggregates from the ten provinces."
        )

    valid_ioics = (
        industry_data.loc[
            industry_data["PROV"].eq(selected_prov),
            "IOIC",
        ]
        .dropna()
        .astype(str)
        .drop_duplicates()
        .tolist()
    )

    selected_ioic = st.sidebar.selectbox(
        "Industry",
        valid_ioics,
        key="static_industry",
    )

    investment_m = st.sidebar.number_input(
        "Investment ($ millions)",
        min_value=0.0,
        value=100.0,
        step=10.0,
        key="static_investment",
    )

    c1, c2 = st.sidebar.columns(2)

    if c1.button("Add shock", width="stretch"):
        new_row = pd.DataFrame(
            {
                "PROV": [selected_prov],
                "IOIC": [selected_ioic],
                "investment_millions": [investment_m],
            }
        )
        st.session_state["scenario_rows"] = pd.concat(
            [st.session_state["scenario_rows"], new_row],
            ignore_index=True,
        )
        st.session_state["results"] = None
        st.rerun()

    if c2.button("Clear", width="stretch"):
        reset_static_scenario()
        st.rerun()

    st.subheader("Scenario inputs")

    if st.session_state["scenario_rows"].empty:
        st.info("Add one or more province-industry investment shocks from the sidebar.")
    else:
        edited = st.data_editor(
            st.session_state["scenario_rows"],
            hide_index=True,
            num_rows="dynamic",
            width="stretch",
            column_config={
                "PROV": st.column_config.TextColumn("Province", disabled=True),
                "IOIC": st.column_config.TextColumn("Industry", disabled=True),
                "investment_millions": st.column_config.NumberColumn(
                    "Investment ($M)",
                    min_value=0.0,
                    step=10.0,
                    format="%.1f",
                ),
            },
            key="static_editor",
        )
        st.session_state["scenario_rows"] = edited

        scope = st.radio(
            "Geographic scope for multipliers",
            ["Within province", "All provinces"],
            horizontal=True,
            key="static_scope",
        )
        geography = "within" if scope == "Within province" else "all"
        if st.session_state["scenario_rows"]["PROV"].eq("CA").any():
            st.caption(
                "Canada benchmark rows use official all-provinces multipliers "
                "regardless of this scope selection."
            )

        if st.button("Run static scenario", type="primary", width="stretch"):
            try:
                st.session_state["results"] = run_scenario(
                    st.session_state["scenario_rows"],
                    industry_data,
                    occ_data,
                    supply_data,
                    noc_titles,
                    geography,
                )
            except Exception as exc:
                st.error(str(exc))

        results = st.session_state.get("results")

        if results is not None:
            st.divider()
            st.header("Scenario results")

            summary = results["summary"]
            metrics = st.columns(4)
            metrics[0].metric(
                "Investment",
                f"${summary['Investment ($M)']:,.1f}M",
            )
            metrics[1].metric(
                "Direct jobs",
                f"{summary['Direct jobs']:,.0f}",
            )
            metrics[2].metric(
                "Total jobs",
                f"{summary['Total jobs']:,.0f}",
            )
            metrics[3].metric(
                "Total labour income",
                f"${summary['Total labour income'] / 1_000_000:,.1f}M",
            )

            industry_tab, occupation_tab, supply_tab, downloads_tab = st.tabs(
                [
                    "Industry effects",
                    "Occupational requirements",
                    "Supply-side context",
                    "Downloads",
                ]
            )

            with industry_tab:
                cols = [
                    "PROV",
                    "IOIC",
                    "investment_millions",
                    "direct_jobs",
                    "indirect_jobs",
                    "induced_jobs",
                    "total_jobs",
                    "total_labour_income",
                ]
                st.dataframe(
                    results["industry"][cols],
                    hide_index=True,
                    width="stretch",
                    column_config={
                        "PROV": "Province",
                        "IOIC": "Industry",
                        "investment_millions": st.column_config.NumberColumn(
                            "Investment ($M)", format="%,.1f"
                        ),
                        "direct_jobs": st.column_config.NumberColumn(
                            "Direct jobs", format="%,.0f"
                        ),
                        "indirect_jobs": st.column_config.NumberColumn(
                            "Indirect jobs", format="%,.0f"
                        ),
                        "induced_jobs": st.column_config.NumberColumn(
                            "Induced jobs", format="%,.0f"
                        ),
                        "total_jobs": st.column_config.NumberColumn(
                            "Total jobs", format="%,.0f"
                        ),
                        "total_labour_income": st.column_config.NumberColumn(
                            "Total labour income", format="$%,.0f"
                        ),
                    },
                )

            with occupation_tab:
                occ = results["occupation"].copy()
                show = occ[
                    [
                        "PROV",
                        "NOC3DIG",
                        "title",
                        "new_jobs",
                        "totalemp_occ",
                        "employment_change_pct",
                        "pressure_rank",
                    ]
                ].copy()

                st.dataframe(
                    show,
                    hide_index=True,
                    width="stretch",
                    column_config={
                        "PROV": "Province",
                        "NOC3DIG": "NOC",
                        "title": "Occupation",
                        "new_jobs": st.column_config.NumberColumn(
                            "New direct jobs", format="%,.0f"
                        ),
                        "totalemp_occ": st.column_config.NumberColumn(
                            "Existing employment", format="%,.0f"
                        ),
                        "employment_change_pct": st.column_config.NumberColumn(
                            "Employment demand increase (%)", format="%.2f"
                        ),
                        "pressure_rank": st.column_config.NumberColumn(
                            "Pressure rank", format="%.0f"
                        ),
                    },
                )

                chart = (
                    occ.dropna(subset=["employment_change_pct"])
                    .nlargest(15, "employment_change_pct")
                    .copy()
                )
                chart["label"] = (
                    chart["PROV"]
                    + " | NOC "
                    + chart["NOC3DIG"].astype(str)
                    + " | "
                    + chart["title"].fillna("Unknown occupation")
                )

                if not chart.empty:
                    bar_chart = (
                        alt.Chart(chart)
                        .mark_bar()
                        .encode(
                            x=alt.X(
                                "employment_change_pct:Q",
                                title="Increase in occupational employment demand (%)",
                            ),
                            y=alt.Y(
                                "label:N",
                                sort="-x",
                                title=None,
                                axis=alt.Axis(labelLimit=550),
                            ),
                            tooltip=[
                                alt.Tooltip("PROV:N", title="Province"),
                                alt.Tooltip("NOC3DIG:N", title="NOC"),
                                alt.Tooltip("title:N", title="Occupation"),
                                alt.Tooltip(
                                    "new_jobs:Q",
                                    title="New direct jobs",
                                    format=",.0f",
                                ),
                                alt.Tooltip(
                                    "employment_change_pct:Q",
                                    title="Employment pressure (%)",
                                    format=".2f",
                                ),
                            ],
                        )
                        .properties(height=500)
                    )
                    st.altair_chart(bar_chart, width="stretch")

            with supply_tab:
                supply_view = results["occupation"][
                    [
                        "PROV",
                        "NOC3DIG",
                        "title",
                        "new_jobs",
                        "employed",
                        "unemployed",
                        "unemprate",
                        "vacancies",
                        "vacancy rate",
                        "earn_mean",
                        "highageshare",
                        "supply_employment_change_pct",
                    ]
                ].copy()

                st.dataframe(
                    supply_view,
                    hide_index=True,
                    width="stretch",
                    column_config={
                        "PROV": "Province",
                        "NOC3DIG": "NOC",
                        "title": "Occupation",
                        "new_jobs": st.column_config.NumberColumn(
                            "New direct jobs", format="%,.0f"
                        ),
                        "employed": st.column_config.NumberColumn(
                            "Employed", format="%,.0f"
                        ),
                        "unemployed": st.column_config.NumberColumn(
                            "Unemployed", format="%,.0f"
                        ),
                        "unemprate": st.column_config.NumberColumn(
                            "Unemployment rate (%)", format="%.2f"
                        ),
                        "vacancies": st.column_config.NumberColumn(
                            "Vacancies", format="%,.0f"
                        ),
                        "vacancy rate": st.column_config.NumberColumn(
                            "Vacancy rate (%)", format="%.2f"
                        ),
                        "earn_mean": st.column_config.NumberColumn(
                            "Average hourly wage", format="$%,.0f"
                        ),
                        "highageshare": st.column_config.NumberColumn(
                            "High-age share (%)", format="%.2f"
                        ),
                        "supply_employment_change_pct": st.column_config.NumberColumn(
                            "Demand / employed (%)", format="%.2f"
                        ),
                    },
                )
                st.caption(
                    "Supply-side indicators provide context for labour availability. "
                    "They are not combined into a shortage score. Suppressed vacancy "
                    "observations are shown as missing rather than zero."
                )

            with downloads_tab:
                workbook = to_excel_bytes(
                    {
                        "Scenario inputs": st.session_state["scenario_rows"],
                        "Industry results": results["industry"],
                        "Occupation and supply": results["occupation"],
                        "Supply source": supply_data,
                        "Canada multipliers": canada_multipliers,
                    }
                )
                st.download_button(
                    "Download complete static results (.xlsx)",
                    workbook,
                    "lamp_static_results.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    width="stretch",
                )


# ============================================================
# PROJECT TIMELINE MODE
# ============================================================

if scenario_mode == "Project timeline":
    st.sidebar.subheader("Saved plans")

    st.sidebar.subheader("Project plans")

    # Blank template
    blank_template = make_plan_template(industry_data)

    st.sidebar.download_button(
        "Download blank plan template",
        data=blank_template,
        file_name="lamp_project_plan_template.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        width="stretch",
    )

    # Save current plan
    if not st.session_state["timeline_rows"].empty:
        saved_plan = make_saved_plan(
            st.session_state["timeline_rows"],
            industry_data,
        )

        st.sidebar.download_button(
            "Save current plan",
            data=saved_plan,
            file_name="lamp_saved_project_plan.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
        )

 # Upload a saved plan
    uploaded_plan = st.sidebar.file_uploader(
        "Load project plan",
        type=["xlsx"],
        key="timeline_plan_upload",
    )

    if uploaded_plan is not None:
        try:
            uploaded_df = pd.read_excel(
                uploaded_plan,
                sheet_name="Project plan",
                engine="openpyxl",
            )

            cleaned_plan, plan_errors = validate_uploaded_plan(
                uploaded_df,
                industry_data,
            )

            if plan_errors:
                st.sidebar.error(
                    "The uploaded plan has validation errors."
                )

                for error in plan_errors:
                    st.sidebar.warning(error)

            else:
                st.sidebar.success(
                    f"Plan validated: "
                    f"{len(cleaned_plan):,} expenditure rows, "
                    f"{cleaned_plan['project_name'].nunique():,} projects."
                )

                if st.sidebar.button(
                    "Import plan",
                    type="primary",
                    width="stretch",
                    key="import_timeline_plan",
                ):
                    st.session_state["timeline_rows"] = cleaned_plan.copy()
                    st.session_state["timeline_results"] = None
                    st.rerun()

        except ValueError as exc:
            st.sidebar.error(
                "Could not find the 'Project plan' sheet "
                f"in the uploaded workbook: {exc}"
            )

        except Exception as exc:
            st.sidebar.error(
                f"Could not read the uploaded plan: {exc}"
            )

    st.sidebar.divider()   
    project_name = st.sidebar.text_input(
        "Project name",
        value="Project 1",
        key="timeline_project_name",
    )

    timeline_prov = st.sidebar.selectbox(
        "Province",
        provinces,
        format_func=lambda code: province_labels.get(code, code),
        key="timeline_province",
    )

    if timeline_prov == "CA":
        st.sidebar.caption(
            "Canada benchmark uses official national all-provinces multipliers "
            "and labour-market aggregates from the ten provinces."
        )

    timeline_ioics = (
        industry_data.loc[
            industry_data["PROV"].eq(timeline_prov),
            "IOIC",
        ]
        .dropna()
        .astype(str)
        .drop_duplicates()
        .tolist()
    )

    timeline_ioic = st.sidebar.selectbox(
        "Industry",
        timeline_ioics,
        key="timeline_industry",
    )

    timeline_year = st.sidebar.selectbox(
        "Fiscal year",
        FISCAL_YEARS,
        key="timeline_year",
    )

    timeline_investment = st.sidebar.number_input(
        "Annual investment ($ millions)",
        min_value=0.0,
        value=100.0,
        step=10.0,
        key="timeline_investment",
    )

    b1, b2 = st.sidebar.columns(2)

    if b1.button("Add year", width="stretch"):
        new_row = pd.DataFrame(
            {
                "project_name": [project_name],
                "PROV": [timeline_prov],
                "fiscal_year": [timeline_year],
                "IOIC": [timeline_ioic],
                "investment_millions": [timeline_investment],
            }
        )
        st.session_state["timeline_rows"] = pd.concat(
            [st.session_state["timeline_rows"], new_row],
            ignore_index=True,
        )
        st.session_state["timeline_results"] = None
        st.rerun()

    if b2.button("Clear timeline", width="stretch"):
        reset_timeline_scenario()
        st.rerun()

    st.header("Project pipeline")
    st.caption(
        "Add one row for each project × fiscal year × industry expenditure. "
        "Multiple projects and multiple industries can be entered in the same year."
    )

    if st.session_state["timeline_rows"].empty:
        st.info("Add annual project expenditures from the sidebar.")
    else:
        timeline_editor = st.data_editor(
            st.session_state["timeline_rows"],
            hide_index=True,
            num_rows="dynamic",
            width="stretch",
            column_config={
                "project_name": st.column_config.TextColumn("Project"),
                "PROV": st.column_config.TextColumn("Province"),
                "fiscal_year": st.column_config.TextColumn("Fiscal year"),
                "IOIC": st.column_config.TextColumn("Industry"),
                "investment_millions": st.column_config.NumberColumn(
                    "Investment ($M)",
                    min_value=0.0,
                    format="%,.1f",
                ),
            },
            key="timeline_editor",
        )
        st.session_state["timeline_rows"] = timeline_editor

        timeline_scope = st.radio(
            "Geographic scope for multipliers",
            ["Within province", "All provinces"],
            horizontal=True,
            key="timeline_scope",
        )
        timeline_geography = (
            "within" if timeline_scope == "Within province" else "all"
        )
        if st.session_state["timeline_rows"]["PROV"].eq("CA").any():
            st.caption(
                "Canada benchmark rows use official all-provinces multipliers "
                "regardless of this scope selection."
            )

        if st.button("Run project pipeline", type="primary", width="stretch"):
            try:
                st.session_state["timeline_results"] = run_timeline_scenario(
                    timeline=st.session_state["timeline_rows"],
                    industry_data=industry_data,
                    occ_data=occ_data,
                    supply_data=supply_data,
                    noc_titles=noc_titles,
                    provincial_cops=provincial_cops,
                    geography=timeline_geography,
                )
            except Exception as exc:
                st.error(str(exc))

        timeline_results = st.session_state.get("timeline_results")

        if timeline_results is not None:
            st.divider()
            st.header("Project pipeline results")

            timeline_summary = timeline_results["summary"]
            tm = st.columns(4)
            tm[0].metric(
                "Total investment",
                f"${timeline_summary['Total investment ($M)']:,.1f}M",
            )
            tm[1].metric(
                "Projects",
                f"{timeline_summary['Number of projects']:,.0f}",
            )
            tm[2].metric(
                "Peak direct jobs",
                f"{timeline_summary['Peak direct jobs']:,.0f}",
            )
            tm[3].metric(
                "Peak direct-jobs year",
                str(timeline_summary["Peak direct jobs FY"]),
            )

            annual = timeline_results["annual_industry"].copy()
            fiscal_order = timeline_results["fiscal_order"]
            annual_occ = timeline_results["annual_occupation"].copy()

            missing_cops_years = sorted(
                annual_occ.loc[
                    ~annual_occ["cops_available"],
                    "fiscal_year",
                ]
                .dropna()
                .unique()
                .tolist()
            )

            if missing_cops_years:
                st.warning(
                    "COPS projections are unavailable for: "
                    + ", ".join(missing_cops_years)
                    + ". Labour-balance results are shown as missing for "
                    "those years."
                )

            overview_tab, peak_tab, cops_tab, occupation_time_tab, projects_tab, timeline_download_tab = st.tabs(
                [
                    "Annual overview",
                    "Peak occupational pressures",
                    "COPS labour balance",
                    "Occupation over time",
                    "Project contributions",
                    "Downloads",
                ]
            )

            with overview_tab:
                st.subheader("Annual investment")

                investment_chart = (
                    alt.Chart(annual)
                    .mark_bar()
                    .encode(
                        x=alt.X(
                            "fiscal_year:N",
                            title="Fiscal year",
                            sort=fiscal_order,
                        ),
                        y=alt.Y(
                            "investment_millions:Q",
                            title="Investment ($M)",
                        ),
                        tooltip=[
                            alt.Tooltip("fiscal_year:N", title="Fiscal year"),
                            alt.Tooltip(
                                "investment_millions:Q",
                                title="Investment ($M)",
                                format=",.0f",
                            ),
                        ],
                    )
                )
                st.altair_chart(investment_chart, width="stretch")

                st.subheader("Annual employment requirements")

                jobs_long = annual.melt(
                    id_vars="fiscal_year",
                    value_vars=["direct_jobs", "total_jobs"],
                    var_name="job_type",
                    value_name="jobs",
                )
                jobs_long["job_type"] = jobs_long["job_type"].map(
                    {
                        "direct_jobs": "Direct jobs",
                        "total_jobs": "Total jobs",
                    }
                )

                jobs_chart = (
                    alt.Chart(jobs_long)
                    .mark_line(point=True)
                    .encode(
                        x=alt.X(
                            "fiscal_year:N",
                            title="Fiscal year",
                            sort=fiscal_order,
                        ),
                        y=alt.Y("jobs:Q", title="Jobs"),
                        color=alt.Color("job_type:N", title=None),
                        tooltip=[
                            alt.Tooltip("fiscal_year:N", title="Fiscal year"),
                            alt.Tooltip("job_type:N", title="Effect"),
                            alt.Tooltip("jobs:Q", title="Jobs", format=",.0f"),
                        ],
                    )
                )
                st.altair_chart(jobs_chart, width="stretch")

                st.dataframe(
                    annual,
                    hide_index=True,
                    width="stretch",
                    column_config={
                        "fiscal_year": "Fiscal year",
                        "investment_millions": st.column_config.NumberColumn(
                            "Investment ($M)", format="%,.1f"
                        ),
                        "direct_jobs": st.column_config.NumberColumn(
                            "Direct jobs", format="%,.0f"
                        ),
                        "indirect_jobs": st.column_config.NumberColumn(
                            "Indirect jobs", format="%,.0f"
                        ),
                        "induced_jobs": st.column_config.NumberColumn(
                            "Induced jobs", format="%,.0f"
                        ),
                        "total_jobs": st.column_config.NumberColumn(
                            "Total jobs", format="%,.0f"
                        ),
                        "direct_labour_income": st.column_config.NumberColumn(
                            "Direct labour income", format="$%,.0f"
                        ),
                        "total_labour_income": st.column_config.NumberColumn(
                            "Total labour income", format="$%,.0f"
                        ),
                    },
                )

            with peak_tab:
                peak = timeline_results["peak_occupation"].copy()

                if peak.empty:
                    st.info("No occupational peak pressures could be calculated.")
                else:
                    st.subheader("Peak occupational pressures")
                    st.caption(
                        "For each province × occupation, this table reports the fiscal "
                        "year with the largest direct demand relative to the current workforce."
                    )

                    peak_display = peak[
                        [
                            "PROV",
                            "NOC3DIG",
                            "title",
                            "peak_fiscal_year",
                            "peak_new_jobs",
                            "peak_pressure_pct",
                            "unemprate",
                            "vacancies",
                            "vacancy_rate",
                            "highageshare",
                            "earn_mean",
                        ]
                    ].copy()

                    st.dataframe(
                        peak_display,
                        hide_index=True,
                        width="stretch",
                        column_config={
                            "PROV": "Province",
                            "NOC3DIG": "NOC",
                            "title": "Occupation",
                            "peak_fiscal_year": "Peak fiscal year",
                            "peak_new_jobs": st.column_config.NumberColumn(
                                "Peak direct jobs", format="%,.0f"
                            ),
                            "peak_pressure_pct": st.column_config.NumberColumn(
                                "Peak demand / workforce (%)", format="%.2f"
                            ),
                            "unemprate": st.column_config.NumberColumn(
                                "Unemployment rate (%)", format="%.2f"
                            ),
                            "vacancies": st.column_config.NumberColumn(
                                "Vacancies", format="%,.0f"
                            ),
                            "vacancy_rate": st.column_config.NumberColumn(
                                "Vacancy rate (%)", format="%.2f"
                            ),
                            "highageshare": st.column_config.NumberColumn(
                                "High-age share (%)", format="%.2f"
                            ),
                            "earn_mean": st.column_config.NumberColumn(
                                "Average hourly wage", format="$%,.0f"
                            ),
                        },
                    )

                    peak_chart = peak.nlargest(15, "peak_pressure_pct").copy()
                    peak_chart["label"] = (
                        peak_chart["PROV"]
                        + " | NOC "
                        + peak_chart["NOC3DIG"].astype(str)
                        + " | "
                        + peak_chart["title"].fillna("Unknown occupation")
                    )

                    peak_bar = (
                        alt.Chart(peak_chart)
                        .mark_bar()
                        .encode(
                            x=alt.X(
                                "peak_pressure_pct:Q",
                                title="Peak demand / existing workforce (%)",
                            ),
                            y=alt.Y(
                                "label:N",
                                sort="-x",
                                title=None,
                                axis=alt.Axis(labelLimit=550),
                            ),
                            tooltip=[
                                alt.Tooltip("peak_fiscal_year:N", title="Peak FY"),
                                alt.Tooltip(
                                    "peak_new_jobs:Q",
                                    title="Peak direct jobs",
                                    format=",.0f",
                                ),
                                alt.Tooltip(
                                    "peak_pressure_pct:Q",
                                    title="Peak pressure (%)",
                                    format=".2f",
                                ),
                            ],
                        )
                        .properties(height=500)
                    )
                    st.altair_chart(peak_bar, width="stretch")

            with cops_tab:

    # ========================================================
    # COPS DATA
    # ========================================================

                cops_view = timeline_results["annual_occupation"].copy()

    # Keep only rows with COPS data
                cops_view = cops_view.loc[
                    cops_view["cops_available"].eq(True)
                ].copy()

                if cops_view.empty:
                    st.info(
                        "No COPS projections are available for the fiscal years "
                        "included in this project scenario."
                    )

                else:

        # ====================================================
        # TABLE
        # ====================================================

                    st.subheader("Labour-market balance with project demand")

                    st.caption(
                        "National COPS flows are used directly for CA and allocated "
                        "to provinces based on each province's current share of "
                        "ten-province employment in the occupation. "
                        "A negative balance indicates that projected openings and LAMP "
                        "requirements exceed projected inflows. This is an accounting "
                        "pressure indicator, not a behavioural shortage forecast."
                    )

                    status_options = [
                        "All occupations",
                        "Moves into deficit with projects",
                        "Existing deficit worsens",
                        "Projected inflows cover openings",
                    ]

                    selected_status = st.selectbox(
                        "Balance status",
                        status_options,
                        key="cops_balance_status",
                    )

                    if selected_status != "All occupations":
                        cops_view = cops_view.loc[
                            cops_view["balance_status"].eq(selected_status)
                        ].copy()

                    cops_display = cops_view[
                        [
                            "PROV",
                            "fiscal_year",
                            "NOC3DIG",
                            "title",
                            "school_inflow",
                            "immigrant_inflow",
                            "other_inflow",
                            "total_inflows",
                            "total_baseline_openings",
                            "baseline_balance",
                            "new_jobs",
                            "post_project_balance",
                            "post_project_gap",
                            "post_project_gap_pct",
                            "balance_status",
                        ]
                    ].sort_values(
                        ["post_project_gap", "new_jobs"],
                        ascending=[False, False],
                    )

                    st.dataframe(
                        cops_display,
                        hide_index=True,
                        width="stretch",
                        column_config={
                            "PROV": "Province",
                            "fiscal_year": "Fiscal year",
                            "NOC3DIG": "NOC",
                            "title": "Occupation",

                            "school_inflow": st.column_config.NumberColumn(
                                "School inflow",
                                format="%,.0f",
                            ),

                            "immigrant_inflow": st.column_config.NumberColumn(
                                "Immigrant inflow",
                                format="%,.0f",
                            ),

                            "other_inflow": st.column_config.NumberColumn(
                                "Other inflow",
                                format="%,.0f",
                            ),

                            "total_inflows": st.column_config.NumberColumn(
                                "Total projected inflows",
                                format="%,.0f",
                            ),

                            "total_baseline_openings": st.column_config.NumberColumn(
                                "Baseline openings",
                                format="%,.0f",
                            ),

                            "baseline_balance": st.column_config.NumberColumn(
                                "Baseline balance",
                                format="%,.0f",
                            ),

                            "new_jobs": st.column_config.NumberColumn(
                                "LAMP direct demand",
                                format="%,.0f",
                            ),

                            "post_project_balance": st.column_config.NumberColumn(
                                "Balance with projects",
                                format="%,.0f",
                            ),

                            "post_project_gap": st.column_config.NumberColumn(
                                "Potential gap",
                                format="%,.0f",
                            ),

                            "post_project_gap_pct": st.column_config.NumberColumn(
                                "Potential gap / workforce (%)",
                                format="%.2f",
                            ),

                            "balance_status": "Status",
                        },
                    )

        # ====================================================
        # CHART
        # ====================================================

                    st.subheader("Effect of projects on occupational balance")

                    available_cops_years = (
                        cops_view["fiscal_year"]
                        .dropna()
                        .drop_duplicates()
                        .tolist()
                    )

                    if available_cops_years:

                        selected_cops_year = st.selectbox(
                            "Fiscal year",
                            available_cops_years,
                            key="cops_year_selector",
                    )

                    chart_data = (
                        cops_view.loc[
                            cops_view["fiscal_year"].eq(selected_cops_year)
                            & cops_view["post_project_balance"].notna()
                        ]
                        .nsmallest(
                            15,
                            "post_project_balance",
                            )
                        .copy()
                    )

                    chart_data["total_demand_with_lamp"] = (
                        chart_data["total_baseline_openings"]
                        + chart_data["new_jobs"]
                    )

                    if chart_data.empty:

                        st.info(
                            "No COPS balance results are available for "
                            f"{selected_cops_year}."
                        )

                    else:

                        chart_data["label"] = (
                            chart_data["PROV"]
                            + " | NOC "
                            + chart_data["NOC3DIG"].astype(str)
                            + " | "
                            + chart_data["title"].fillna(
                                "Unknown occupation"
                        )
                )

                    balance_long = chart_data.melt(
                        id_vars=[
                            "label",
                            "PROV",
                            "NOC3DIG",
                            "title",
                            "fiscal_year",
                            "total_inflows",
                            "total_baseline_openings",
                            "new_jobs",
                            "total_demand_with_lamp",
                        ],
                        value_vars=[
                            "baseline_balance",
                            "post_project_balance",
                        ],
                        var_name="balance_type",
                        value_name="workers",
                    )

                    balance_long["balance_type"] = (
                        balance_long["balance_type"].map(
                            {
                                "baseline_balance":
                                    "COPS baseline",
                                    "post_project_balance":
                                        "With LAMP projects",
                            }
                        )
                    )

                    balance_chart = (
                        alt.Chart(balance_long)
                        .mark_bar()
                        .encode(
                            x=alt.X(
                                "workers:Q",
                                title="Projected labour-market balance (workers)",
                                stack=None,
                            ),

                            y=alt.Y(
                                "label:N",
                                title=None,
                                axis=alt.Axis(
                                    labelLimit=550
                                ),
                            ),

                            yOffset=alt.YOffset(
                                "balance_type:N"
                            ),

                            color=alt.Color(
                                "balance_type:N",
                                title=None,
                            ),

                            tooltip=[
                                alt.Tooltip(
                                    "PROV:N",
                                    title="Province",
                                ),
                                alt.Tooltip(
                                    "NOC3DIG:N",
                                    title="NOC",
                                ),
                                alt.Tooltip(
                                    "title:N",
                                    title="Occupation",
                                ),
                                alt.Tooltip(
                                    "balance_type:N",
                                    title="Scenario",
                                ),
                                alt.Tooltip(
                                    "total_inflows:Q",
                                    title="Projected inflows",
                                    format=",.0f",
                                ),
                                alt.Tooltip(
                                    "total_baseline_openings:Q",
                                    title="Baseline demand",
                                    format=",.0f",
                                ),
                                alt.Tooltip(
                                    "new_jobs:Q",
                                    title="Additional LAMP demand",
                                    format=",.0f",
                                ),
                                alt.Tooltip(
                                    "total_demand_with_lamp:Q",
                                    title="Total demand with LAMP",
                                    format=",.0f",
                                ),
                                alt.Tooltip(
                                    "workers:Q",
                                    title="Balance",
                                    format=",.0f",
                                ),
                            ],
                        )
                        .properties(
                            height=500
                        )
                    )

                    st.altair_chart(
                        balance_chart,
                        width="stretch",
                    )
            with occupation_time_tab:
                annual_occ = timeline_results["annual_occupation"].copy()
                annual_occ["display_name"] = (
                    "NOC "
                    + annual_occ["NOC3DIG"].astype(str)
                    + " | "
                    + annual_occ["title"].fillna("Unknown occupation")
                )

                occupation_options = (
                    annual_occ[["NOC3DIG", "display_name"]]
                    .drop_duplicates()
                    .sort_values("display_name")
                )

                selected_noc_name = st.selectbox(
                    "Occupation",
                    occupation_options["display_name"].tolist(),
                    key="timeline_noc_selector",
                )

                selected_noc = occupation_options.loc[
                    occupation_options["display_name"].eq(selected_noc_name),
                    "NOC3DIG",
                ].iloc[0]

                noc_time = annual_occ.loc[
                    annual_occ["NOC3DIG"].eq(selected_noc)
                ].copy()

                pressure_chart = (
                    alt.Chart(noc_time)
                    .mark_line(point=True)
                    .encode(
                        x=alt.X(
                            "fiscal_year:N",
                            title="Fiscal year",
                            sort=fiscal_order,
                        ),
                        y=alt.Y(
                            "employment_change_pct:Q",
                            title="New direct demand / existing workforce (%)",
                        ),
                        color=alt.Color("PROV:N", title="Province"),
                        tooltip=[
                            alt.Tooltip("PROV:N", title="Province"),
                            alt.Tooltip("fiscal_year:N", title="Fiscal year"),
                            alt.Tooltip(
                                "new_jobs:Q",
                                title="New direct jobs",
                                format=",.0f",
                            ),
                            alt.Tooltip(
                                "employment_change_pct:Q",
                                title="Pressure (%)",
                                format=".2f",
                            ),
                        ],
                    )
                )
                st.altair_chart(pressure_chart, width="stretch")

                st.dataframe(
                    noc_time[
                        [
                            "PROV",
                            "fiscal_year",
                            "NOC3DIG",
                            "title",
                            "new_jobs",
                            "employment_change_pct",
                            "unemprate",
                            "vacancies",
                            "vacancy_rate",
                            "highageshare",
                        ]
                    ],
                    hide_index=True,
                    width="stretch",
                    column_config={
                        "PROV": "Province",
                        "fiscal_year": "Fiscal year",
                        "NOC3DIG": "NOC",
                        "title": "Occupation",
                        "new_jobs": st.column_config.NumberColumn(
                            "New direct jobs", format="%,.0f"
                        ),
                        "employment_change_pct": st.column_config.NumberColumn(
                            "Demand / workforce (%)", format="%.2f"
                        ),
                        "unemprate": st.column_config.NumberColumn(
                            "Unemployment rate (%)", format="%.2f"
                        ),
                        "vacancies": st.column_config.NumberColumn(
                            "Vacancies", format="%,.0f"
                        ),
                        "vacancy_rate": st.column_config.NumberColumn(
                            "Vacancy rate (%)", format="%.2f"
                        ),
                        "highageshare": st.column_config.NumberColumn(
                            "High-age share (%)", format="%.2f"
                        ),
                    },
                )

            with projects_tab:
                project_occ = timeline_results["project_occupation"].copy()

                st.subheader("Project contributions to occupational demand")

                project_occ["display_name"] = (
                    "NOC "
                    + project_occ["NOC3DIG"].astype(str)
                    + " | "
                    + project_occ["title"].fillna("Unknown occupation")
                )

                project_noc_options = (
                    project_occ[["NOC3DIG", "display_name"]]
                    .drop_duplicates()
                    .sort_values("display_name")
                )

                contribution_noc_name = st.selectbox(
                    "Occupation to decompose",
                    project_noc_options["display_name"].tolist(),
                    key="project_contribution_noc",
                )

                contribution_noc = project_noc_options.loc[
                    project_noc_options["display_name"].eq(contribution_noc_name),
                    "NOC3DIG",
                ].iloc[0]

                contribution_data = project_occ.loc[
                    project_occ["NOC3DIG"].eq(contribution_noc)
                ].copy()

                contribution_chart = (
                    alt.Chart(contribution_data)
                    .mark_bar()
                    .encode(
                        x=alt.X(
                            "fiscal_year:N",
                            title="Fiscal year",
                            sort=fiscal_order,
                        ),
                        y=alt.Y(
                            "new_jobs:Q",
                            title="Direct occupational jobs",
                        ),
                        color=alt.Color(
                            "project_name:N",
                            title="Project",
                        ),
                        tooltip=[
                            alt.Tooltip("project_name:N", title="Project"),
                            alt.Tooltip("PROV:N", title="Province"),
                            alt.Tooltip("fiscal_year:N", title="Fiscal year"),
                            alt.Tooltip(
                                "new_jobs:Q",
                                title="Direct jobs",
                                format=",.0f",
                            ),
                        ],
                    )
                )
                st.altair_chart(contribution_chart, width="stretch")

                st.dataframe(
                    contribution_data[
                        [
                            "project_name",
                            "PROV",
                            "fiscal_year",
                            "NOC3DIG",
                            "title",
                            "new_jobs",
                        ]
                    ],
                    hide_index=True,
                    width="stretch",
                    column_config={
                        "project_name": "Project",
                        "PROV": "Province",
                        "fiscal_year": "Fiscal year",
                        "NOC3DIG": "NOC",
                        "title": "Occupation",
                        "new_jobs": st.column_config.NumberColumn(
                            "Direct jobs", format="%,.0f"
                        ),
                    },
                )

            with timeline_download_tab:
                timeline_workbook = to_excel_bytes(
                    {
                        "Timeline inputs": timeline_results["timeline_inputs"],
                        "Annual industry": timeline_results["annual_industry"],
                        "Annual occupations": timeline_results["annual_occupation"],
                        "Peak occupations": timeline_results["peak_occupation"],
                        "COPS balance peaks": timeline_results["cops_peak_occupation"],
                        "Industry by project": timeline_results["industry_by_project"],
                        "Occupation by project": timeline_results["occupation_by_project"],
                        "Provincial and CA COPS": provincial_cops,
                        "Canada multipliers": canada_multipliers,
                    }
                )

                st.download_button(
                    "Download complete timeline results (.xlsx)",
                    timeline_workbook,
                    "lamp_project_timeline_results.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    width="stretch",
                )
