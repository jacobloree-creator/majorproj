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
    return demand, labour, demographics, wages, noc_titles, vacancies


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
    raw, labour, demographics, wages, noc_titles, vacancies = load_data()

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

except Exception as exc:
    st.error(f"Could not prepare the data: {exc}")
    st.stop()


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

provinces = (
    industry_data["PROV"]
    .dropna()
    .astype(str)
    .drop_duplicates()
    .tolist()
)


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
        key="static_province",
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
                            "Investment ($M)", format="%.1f"
                        ),
                        "direct_jobs": st.column_config.NumberColumn(
                            "Direct jobs", format="%.0f"
                        ),
                        "indirect_jobs": st.column_config.NumberColumn(
                            "Indirect jobs", format="%.0f"
                        ),
                        "induced_jobs": st.column_config.NumberColumn(
                            "Induced jobs", format="%.0f"
                        ),
                        "total_jobs": st.column_config.NumberColumn(
                            "Total jobs", format="%.0f"
                        ),
                        "total_labour_income": st.column_config.NumberColumn(
                            "Total labour income", format="$%.0f"
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
                            "New direct jobs", format="%.0f"
                        ),
                        "totalemp_occ": st.column_config.NumberColumn(
                            "Existing employment", format="%.0f"
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
                            "New direct jobs", format="%.0f"
                        ),
                        "employed": st.column_config.NumberColumn(
                            "Employed", format="%.0f"
                        ),
                        "unemployed": st.column_config.NumberColumn(
                            "Unemployed", format="%.0f"
                        ),
                        "unemprate": st.column_config.NumberColumn(
                            "Unemployment rate (%)", format="%.2f"
                        ),
                        "vacancies": st.column_config.NumberColumn(
                            "Vacancies", format="%.0f"
                        ),
                        "vacancy rate": st.column_config.NumberColumn(
                            "Vacancy rate (%)", format="%.2f"
                        ),
                        "earn_mean": st.column_config.NumberColumn(
                            "Average hourly wage", format="$%.2f"
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
    st.sidebar.header("Project timeline")

    project_name = st.sidebar.text_input(
        "Project name",
        value="Project 1",
        key="timeline_project_name",
    )

    timeline_prov = st.sidebar.selectbox(
        "Province",
        provinces,
        key="timeline_province",
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
                    format="%.1f",
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

        if st.button("Run project pipeline", type="primary", width="stretch"):
            try:
                st.session_state["timeline_results"] = run_timeline_scenario(
                    st.session_state["timeline_rows"],
                    industry_data,
                    occ_data,
                    supply_data,
                    noc_titles,
                    timeline_geography,
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

            overview_tab, peak_tab, occupation_time_tab, projects_tab, timeline_download_tab = st.tabs(
                [
                    "Annual overview",
                    "Peak occupational pressures",
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
                            "Investment ($M)", format="%.1f"
                        ),
                        "direct_jobs": st.column_config.NumberColumn(
                            "Direct jobs", format="%.0f"
                        ),
                        "indirect_jobs": st.column_config.NumberColumn(
                            "Indirect jobs", format="%.0f"
                        ),
                        "induced_jobs": st.column_config.NumberColumn(
                            "Induced jobs", format="%.0f"
                        ),
                        "total_jobs": st.column_config.NumberColumn(
                            "Total jobs", format="%.0f"
                        ),
                        "direct_labour_income": st.column_config.NumberColumn(
                            "Direct labour income", format="$%.0f"
                        ),
                        "total_labour_income": st.column_config.NumberColumn(
                            "Total labour income", format="$%.0f"
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
                                "Peak direct jobs", format="%.0f"
                            ),
                            "peak_pressure_pct": st.column_config.NumberColumn(
                                "Peak demand / workforce (%)", format="%.2f"
                            ),
                            "unemprate": st.column_config.NumberColumn(
                                "Unemployment rate (%)", format="%.2f"
                            ),
                            "vacancies": st.column_config.NumberColumn(
                                "Vacancies", format="%.0f"
                            ),
                            "vacancy_rate": st.column_config.NumberColumn(
                                "Vacancy rate (%)", format="%.2f"
                            ),
                            "highageshare": st.column_config.NumberColumn(
                                "High-age share (%)", format="%.2f"
                            ),
                            "earn_mean": st.column_config.NumberColumn(
                                "Average hourly wage", format="$%.2f"
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
                            "New direct jobs", format="%.0f"
                        ),
                        "employment_change_pct": st.column_config.NumberColumn(
                            "Demand / workforce (%)", format="%.2f"
                        ),
                        "unemprate": st.column_config.NumberColumn(
                            "Unemployment rate (%)", format="%.2f"
                        ),
                        "vacancies": st.column_config.NumberColumn(
                            "Vacancies", format="%.0f"
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
                            "Direct jobs", format="%.0f"
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
                        "Industry by project": timeline_results["industry_by_project"],
                        "Occupation by project": timeline_results["occupation_by_project"],
                    }
                )

                st.download_button(
                    "Download complete timeline results (.xlsx)",
                    timeline_workbook,
                    "lamp_project_timeline_results.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    width="stretch",
                )
