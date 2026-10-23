import io
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
import altair as alt

st.set_page_config(
    page_title="Major Projects Labour-Market Requirements",
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
REQUIRED_LABOUR_COLS = ["PROV", "NOC3DIG", "employed", "unemployed", "unemprate"]
REQUIRED_DEMOGRAPHICS_COLS = ["PROV", "NOC3DIG", "highageshare"]
REQUIRED_WAGE_COLS = ["PROV", "NOC3DIG", "earn_mean",]
REQUIRED_NOC_TITLE_COLS = ["NOC3DIG", "title"]
REQUIRED_VACANCY_COLS = ["PROV", "NOC3DIG", "vacancies", "vacancy rate"]

NUMERIC_DEMAND_COLS = [c for c in REQUIRED_DEMAND_COLS if c not in {"IOIC", "PROV", "NOC3DIG"}]
MULTIPLIER_COLS = [
    "direct_all_wage", "indirect_all_wage", "induced_all_wage",
    "direct_within_wage", "indirect_within_wage", "induced_within_wage",
    "direct_all_job", "indirect_all_job", "induced_all_job",
    "direct_within_job", "indirect_within_job", "induced_within_job",
]


def clean_keys(frame):
    frame = frame.copy()
    frame["PROV"] = frame["PROV"].astype("string").str.strip()
    frame["NOC3DIG"] = frame["NOC3DIG"].astype("string").str.strip()
    return frame


@st.cache_data
def load_data():
    demand = pd.read_excel(DEMAND_FILE, engine="openpyxl")
    labour = pd.read_excel(LABOUR_FILE, engine="openpyxl")
    demographics = pd.read_excel(DEMOGRAPHICS_FILE, engine="openpyxl")
    wages = pd.read_excel(WAGES_FILE, engine="openpyxl")
    noc_titles = pd.read_excel(NOC_TITLES_FILE, engine="openpyxl")
    vacancies = pd.read_excel(VACANCIES_FILE, engine="openpyxl")
    return demand, labour, demographics, wages, noc_titles, vacancies


def require_columns(frame, required, label):
    missing = [c for c in required if c not in frame.columns]
    if missing:
        raise ValueError(f"{label} is missing required columns: {missing}")


def prepare_coefficients(raw):
    df = raw.copy()
    require_columns(df, REQUIRED_DEMAND_COLS, DEMAND_FILE.name)

    for col in ["IOIC", "PROV", "NOC3DIG"]:
        df[col] = df[col].astype("string").str.strip()
    df[NUMERIC_DEMAND_COLS] = df[NUMERIC_DEMAND_COLS].apply(pd.to_numeric, errors="coerce")

    df["zero_industry_employment"] = df["totalemp_ind"].fillna(0).eq(0)
    df.loc[df["zero_industry_employment"], "occshare"] = np.nan

    share_check = (
        df.loc[~df["zero_industry_employment"]]
        .groupby(["PROV", "IOIC"], as_index=False)
        .agg(sum_occshare=("occshare", "sum"), totalemp_ind=("totalemp_ind", "first"))
    )
    share_check["share_error"] = (share_check["sum_occshare"] - 1).abs()
    bad_shares = share_check.loc[share_check["share_error"] > 0.01].copy()

    check = (
        df.groupby(["PROV", "IOIC"])[MULTIPLIER_COLS]
        .nunique(dropna=False)
        .reset_index()
    )
    inconsistent = check.loc[check[MULTIPLIER_COLS].gt(1).any(axis=1)].copy()

    industry_data = (
        df[["PROV", "IOIC", "totalemp_ind"] + MULTIPLIER_COLS]
        .drop_duplicates(subset=["PROV", "IOIC"])
        .copy()
    )
    occ_data = df[
        ["PROV", "IOIC", "NOC3DIG", "emp", "occshare", "totalemp_occ", "zero_industry_employment"]
    ].copy()
    return df, industry_data, occ_data, bad_shares, inconsistent


def prepare_supply(
    labour,
    demographics,
    wages,
    vacancies
):

    # Check required columns
    require_columns(
        labour,
        REQUIRED_LABOUR_COLS,
        LABOUR_FILE.name
    )

    require_columns(
        demographics,
        REQUIRED_DEMOGRAPHICS_COLS,
        DEMOGRAPHICS_FILE.name
    )

    require_columns(
        wages,
        REQUIRED_WAGE_COLS,
        WAGES_FILE.name
    )

    require_columns(
        vacancies,
        REQUIRED_VACANCY_COLS,
        VACANCIES_FILE.name
    )

    # Clean merge keys
    labour = clean_keys(labour)
    demographics = clean_keys(demographics)
    wages = clean_keys(wages)
    vacancies = clean_keys(vacancies)
    # Convert variables to numeric
    labour[
        [
            "employed",
            "unemployed",
            "unemprate",
        ]
    ] = labour[
        [
            "employed",
            "unemployed",
            "unemprate",
        ]
    ].apply(
        pd.to_numeric,
        errors="coerce"
    )

    demographics["highageshare"] = pd.to_numeric(
        demographics["highageshare"],
        errors="coerce"
    )

    wages["earn_mean"] = pd.to_numeric(
        wages["earn_mean"],
        errors="coerce"
    )

    vacancies[["vacancies", "vacancy rate"]] = (
        vacancies[
            ["vacancies", "vacancy rate"]
        ].apply(
            pd.to_numeric,
            errors="coerce"
        )
    )

# Flag suppressed / unreliable observations
    vacancies["vacancy_suppressed"] = (
        vacancies["vacancies"] == 0
    )

    vacancies.loc[
        vacancies["vacancy_suppressed"],
        ["vacancies", "vacancy rate"]
    ] = np.nan
    
    # Convert proportions to percentages
    labour["unemprate"] = (
        labour["unemprate"] * 100
    )

    demographics["highageshare"] = (
        demographics["highageshare"] * 100
    )

    # Check for duplicate PROV x NOC cells
    for data, name in [
        (labour, "unemployment.xlsx"),
        (demographics, "demographics.xlsx"),
        (wages, "wages.xlsx"),
    ]:

        duplicates = data.duplicated(
            ["PROV", "NOC3DIG"]
        )

        if duplicates.any():

            dupes = data.loc[
                data.duplicated(
                    ["PROV", "NOC3DIG"],
                    keep=False
                ),
                [
                    "PROV",
                    "NOC3DIG",
                ]
            ]

            raise ValueError(
                f"Duplicate PROV x NOC3DIG rows in {name}:\n"
                + dupes.to_string(index=False)
            )

    # Merge unemployment + demographics
    supply = labour.merge(
        demographics,
        on=[
            "PROV",
            "NOC3DIG"
        ],
        how="outer",
        validate="one_to_one"
    )

    # Merge wages
    supply = supply.merge(
        wages[
            [
                "PROV",
                "NOC3DIG",
                "earn_mean"
            ]
        ],
        on=[
            "PROV",
            "NOC3DIG"
        ],
        how="outer",
        validate="one_to_one"
    )

    supply = supply.merge(
        vacancies,
        on=["PROV", "NOC3DIG"],
        how="outer",
        validate="one_to_one"
    )
    return supply

def prepare_noc_titles(noc_titles):

    require_columns(
        noc_titles,
        REQUIRED_NOC_TITLE_COLS,
        NOC_TITLES_FILE.name
    )

    noc_titles = noc_titles.copy()

    noc_titles["NOC3DIG"] = (
        noc_titles["NOC3DIG"]
        .astype("string")
        .str.strip()
    )

    noc_titles["title"] = (
        noc_titles["title"]
        .astype("string")
        .str.strip()
    )

    # Each NOC code should have exactly one title
    if noc_titles["NOC3DIG"].duplicated().any():

        duplicates = noc_titles.loc[
            noc_titles["NOC3DIG"].duplicated(
                keep=False
            ),
            [
                "NOC3DIG",
                "title"
            ]
        ]

        raise ValueError(
            "Duplicate NOC3DIG codes in noc_titles.xlsx:\n"
            + duplicates.to_string(index=False)
        )

    return noc_titles

def run_scenario(scenario, industry_data, occ_data, supply_data, noc_titles, geography="within"):
    scenario = scenario.copy()
    for col in ["PROV", "IOIC"]:
        scenario[col] = scenario[col].astype("string").str.strip()
    scenario["investment_millions"] = pd.to_numeric(scenario["investment_millions"], errors="coerce")

    if scenario["investment_millions"].isna().any():
        raise ValueError("Scenario contains missing or non-numeric investment values.")
    if scenario["investment_millions"].lt(0).any():
        raise ValueError("Investment values cannot be negative.")

    scenario = (
        scenario.loc[scenario["investment_millions"].gt(0)]
        .groupby(["PROV", "IOIC"], as_index=False)["investment_millions"]
        .sum()
    )
    if scenario.empty:
        raise ValueError("Add at least one positive investment shock.")
    scenario["investment_dollars"] = scenario["investment_millions"] * 1_000_000

    if geography == "within":
        rename = {
            "direct_within_job": "direct_job_multiplier",
            "indirect_within_job": "indirect_job_multiplier",
            "induced_within_job": "induced_job_multiplier",
            "direct_within_wage": "direct_wage_multiplier",
            "indirect_within_wage": "indirect_wage_multiplier",
            "induced_within_wage": "induced_wage_multiplier",
        }
    else:
        rename = {
            "direct_all_job": "direct_job_multiplier",
            "indirect_all_job": "indirect_job_multiplier",
            "induced_all_job": "induced_job_multiplier",
            "direct_all_wage": "direct_wage_multiplier",
            "indirect_all_wage": "indirect_wage_multiplier",
            "induced_all_wage": "induced_wage_multiplier",
        }

    multipliers = industry_data[["PROV", "IOIC", "totalemp_ind"] + list(rename)].rename(columns=rename)
    merged = scenario.merge(multipliers, on=["PROV", "IOIC"], how="left", indicator=True)
    unmatched = merged.loc[merged["_merge"].ne("both"), ["PROV", "IOIC", "investment_millions"]]
    if not unmatched.empty:
        raise ValueError("Unmatched province x industry combinations:\n" + unmatched.to_string(index=False))

    industry = merged.drop(columns="_merge").copy()
    industry["direct_jobs"] = industry["investment_millions"] * industry["direct_job_multiplier"]
    industry["indirect_jobs"] = industry["investment_millions"] * industry["indirect_job_multiplier"]
    industry["induced_jobs"] = industry["investment_millions"] * industry["induced_job_multiplier"]
    industry["total_jobs"] = industry[["direct_jobs", "indirect_jobs", "induced_jobs"]].sum(axis=1)
    industry["direct_labour_income"] = industry["investment_dollars"] * industry["direct_wage_multiplier"]
    industry["indirect_labour_income"] = industry["investment_dollars"] * industry["indirect_wage_multiplier"]
    industry["induced_labour_income"] = industry["investment_dollars"] * industry["induced_wage_multiplier"]
    industry["total_labour_income"] = industry[
        ["direct_labour_income", "indirect_labour_income", "induced_labour_income"]
    ].sum(axis=1)

    detailed = industry[["PROV", "IOIC", "investment_millions", "direct_jobs"]].merge(
        occ_data, on=["PROV", "IOIC"], how="left"
    )
    zero_inputs = detailed.loc[
        detailed["zero_industry_employment"].eq(True), ["PROV", "IOIC", "investment_millions"]
    ].drop_duplicates()
    detailed["new_jobs"] = detailed["direct_jobs"] * detailed["occshare"]

    occupation = (
        detailed.dropna(subset=["NOC3DIG", "new_jobs"])
        .groupby(["PROV", "NOC3DIG"], as_index=False)
        .agg(new_jobs=("new_jobs", "sum"), totalemp_occ=("totalemp_occ", "first"))
    )

    # Remove occupations with no new direct jobs
    occupation = occupation.loc[
        occupation["new_jobs"] > 0
    ].copy()

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
        validate="many_to_one"
    )
    # A second demand-pressure denominator using the independent supply-side employment estimate.
    occupation["supply_employment_change_pct"] = np.where(
        occupation["employed"].gt(0),
        occupation["new_jobs"] / occupation["employed"] * 100,
        np.nan,
    )
    occupation["pressure_rank"] = occupation.groupby("PROV")["employment_change_pct"].rank(
        method="min", ascending=False
    )
    occupation = occupation.sort_values(
        ["PROV", "employment_change_pct", "new_jobs"], ascending=[True, False, False]
    ).reset_index(drop=True)

    summary = {
        "Investment ($M)": industry["investment_millions"].sum(),
        "Direct jobs": industry["direct_jobs"].sum(),
        "Total jobs": industry["total_jobs"].sum(),
        "Total labour income": industry["total_labour_income"].sum(),
    }
    return {"summary": summary, "industry": industry, "occupation": occupation, "detailed": detailed, "zero_inputs": zero_inputs}


def to_excel_bytes(sheets):
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for name, frame in sheets.items():
            frame.to_excel(writer, sheet_name=name[:31], index=False)
    return buffer.getvalue()


def reset_scenario():
    st.session_state["scenario_rows"] = pd.DataFrame(columns=["PROV", "IOIC", "investment_millions"])
    st.session_state["results"] = None


# ---------- Load and prepare ----------
try:
    raw, labour, demographics, wages, noc_titles, vacancies = load_data()
    df, industry_data, occ_data, bad_shares, inconsistent_multipliers = prepare_coefficients(raw)
    supply_data = prepare_supply(
        labour,
        demographics,
        wages,
        vacancies,
    )
    noc_titles = prepare_noc_titles(
        noc_titles
    )
except Exception as exc:
    st.error(f"Could not prepare the data: {exc}")
    st.stop()

if "scenario_rows" not in st.session_state:
    st.session_state["scenario_rows"] = pd.DataFrame(columns=["PROV", "IOIC", "investment_millions"])
if "results" not in st.session_state:
    st.session_state["results"] = None

# ---------- Header ----------
st.title("Major Projects Labour-Market Requirements")
st.caption("Translate provincial industry investment shocks into employment, direct occupational requirements, and labour-market context.")

with st.expander("Method and interpretation"):
    st.markdown("""
- Investment is entered in **millions of dollars**.
- Industry results include direct, indirect, and induced jobs and labour income.
- Occupational requirements allocate **direct jobs only** using province-industry occupational shares.
- Supply-side indicators are merged at the **province × NOC3DIG** level.
- `employment_change_pct` uses employment from the occupation-industry coefficient data; `supply_employment_change_pct` uses the independent supply-side `employed` measure.
- Employment pressure is a demand exposure measure, not a shortage estimate.
""")

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

# ---------- Scenario builder ----------
st.sidebar.header("Scenario")
provinces = industry_data["PROV"].dropna().astype(str).drop_duplicates().tolist()
selected_prov = st.sidebar.selectbox("Province", provinces)
valid_ioics = (
    industry_data.loc[industry_data["PROV"].eq(selected_prov), "IOIC"]
    .dropna().astype(str).drop_duplicates().tolist()
)
selected_ioic = st.sidebar.selectbox("Industry", valid_ioics)
investment_m = st.sidebar.number_input("Investment ($ millions)", min_value=0.0, value=100.0, step=10.0)

c1, c2 = st.sidebar.columns(2)
if c1.button("Add shock", width="stretch"):
    new_row = pd.DataFrame({"PROV": [selected_prov], "IOIC": [selected_ioic], "investment_millions": [investment_m]})
    st.session_state["scenario_rows"] = pd.concat([st.session_state["scenario_rows"], new_row], ignore_index=True)
    st.session_state["results"] = None
    st.rerun()
if c2.button("Clear", width="stretch"):
    reset_scenario()
    st.rerun()

st.subheader("Scenario inputs")
if st.session_state["scenario_rows"].empty:
    st.info("Add one or more province-industry investment shocks from the sidebar.")
    st.stop()

edited = st.data_editor(
    st.session_state["scenario_rows"], hide_index=True, num_rows="dynamic", width="stretch",
    column_config={
        "PROV": st.column_config.TextColumn("Province", disabled=True),
        "IOIC": st.column_config.TextColumn("Industry", disabled=True),
        "investment_millions": st.column_config.NumberColumn("Investment ($M)", min_value=0.0, step=10.0),
    },
)
st.session_state["scenario_rows"] = edited
scope = st.radio("Geographic scope for multipliers", ["Within province", "All provinces"], horizontal=True)
geography = "within" if scope == "Within province" else "all"

if st.button("Run scenario", type="primary", width="stretch"):
    try:
        st.session_state["results"] = run_scenario(
            st.session_state["scenario_rows"], industry_data, occ_data, supply_data, noc_titles, geography
        )
    except Exception as exc:
        st.error(str(exc))

results = st.session_state.get("results")
if results is None:
    st.stop()

# ---------- Results ----------
st.divider()
st.header("Scenario results")
summary = results["summary"]
metrics = st.columns(4)
metrics[0].metric("Investment", f"${summary['Investment ($M)']:,.1f}M")
metrics[1].metric("Direct jobs", f"{summary['Direct jobs']:,.0f}")
metrics[2].metric("Total jobs", f"{summary['Total jobs']:,.0f}")
metrics[3].metric("Total labour income", f"${summary['Total labour income']/1_000_000:,.1f}M")

industry_tab, occupation_tab, supply_tab, downloads_tab = st.tabs([
    "Industry effects", "Occupational requirements", "Supply-side context", "Downloads"
])

with industry_tab:
    cols = ["PROV", "IOIC", "investment_millions", "direct_jobs", "indirect_jobs", "induced_jobs", "total_jobs", "total_labour_income"]
    st.dataframe(results["industry"][cols], hide_index=True, width="stretch")

with occupation_tab:
    occ = results["occupation"].copy()
    show = occ[["PROV", "NOC3DIG", "title", "new_jobs", "totalemp_occ", "employment_change_pct", "pressure_rank"]]
    st.dataframe(show, hide_index=True, width="stretch")
    chart = occ.dropna(subset=["employment_change_pct"]).nlargest(15, "employment_change_pct").copy()
    chart["label"] = (
        chart["PROV"]
        + " | NOC" + chart["NOC3DIG"].astype(str) + " | "
        + chart["title"].fillna(
            "NOC " + chart["NOC3DIG"].astype(str)
        )
    )

    if not chart.empty:

        bar_chart = (
            alt.Chart(chart)
            .mark_bar()
            .encode(
                x=alt.X(
                    "employment_change_pct:Q",
                    title="Increase in occupational employment demand (%)"
                ),
                y=alt.Y(
                    "label:N",
                    sort="-x",
                    title=None,
                    axis=alt.Axis(
                        labelLimit=500
                    )
                ),
                tooltip=[
                    alt.Tooltip(
                        "PROV:N",
                        title="Province"
                    ),
                    alt.Tooltip(
                        "NOC3DIG:N",
                        title="NOC"
                    ),
                    alt.Tooltip(
                        "title:N",
                        title="Occupation"
                    ),
                    alt.Tooltip(
                        "new_jobs:Q",
                        title="New direct jobs",
                        format=",.0f"
                    ),
                    alt.Tooltip(
                        "employment_change_pct:Q",
                        title="Employment pressure (%)",
                        format=".2f"
                    )
                ]
            )
            .properties(
                height=500
            )
        )

        st.altair_chart(
            bar_chart,
            width="stretch"
        )

with supply_tab:
    supply_view = results["occupation"][[
        "PROV", "NOC3DIG", "title", "new_jobs", "employed", "unemployed", "unemprate", "vacancies", "vacancy rate", "earn_mean", "highageshare",
        "supply_employment_change_pct"
    ]].copy()
    st.dataframe(
        supply_view,
        hide_index=True,
        width="stretch",
        column_config={
            "new_jobs": st.column_config.NumberColumn("New direct jobs", format="%.1f"),
            "employed": st.column_config.NumberColumn("Employed", format="%.0f"),
            "unemployed": st.column_config.NumberColumn("Unemployed", format="%.0f"),
            "unemprate": st.column_config.NumberColumn("Unemployment rate (%)", format="%.2f"),
            "vacancies": st.column_config.NumberColumn("Vacancies", format="%.0f"),
            "vacancy rate": st.column_config.NumberColumn("Vacancy rate (%)", format="%.2f"),
            "earn_mean": st.column_config.NumberColumn("Average hourly wage", format="$%.0"),
            "highageshare": st.column_config.NumberColumn("High-age share (%)", format="%.2f"),
            "supply_employment_change_pct": st.column_config.NumberColumn("Demand / employed (%)", format="%.2f"),
        },
    )
    st.caption("Supply-side indicators provide context for labour availability. They are not combined into a shortage score in this prototype.")

with downloads_tab:
    workbook = to_excel_bytes({
        "Scenario inputs": st.session_state["scenario_rows"],
        "Industry results": results["industry"],
        "Occupation and supply": results["occupation"],
        "Supply source": supply_data,
    })
    st.download_button(
        "Download complete results (.xlsx)", workbook, "major_projects_labour_results.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width="stretch"
    )
