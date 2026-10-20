import io
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Major Projects Labour-Market Requirements",
    page_icon="🧰",
    layout="wide",
)

REQUIRED_COLS = [
    "IOIC", "PROV", "NOC3DIG", "emp", "totalemp_ind", "occshare",
    "direct_all_wage", "indirect_all_wage", "induced_all_wage",
    "direct_within_wage", "indirect_within_wage", "induced_within_wage",
    "direct_all_job", "indirect_all_job", "induced_all_job",
    "direct_within_job", "indirect_within_job", "induced_within_job",
    "totalemp_occ",
]

NUMERIC_COLS = [c for c in REQUIRED_COLS if c not in {"IOIC", "PROV", "NOC3DIG"}]
MULTIPLIER_COLS = [
    "direct_all_wage", "indirect_all_wage", "induced_all_wage",
    "direct_within_wage", "indirect_within_wage", "induced_within_wage",
    "direct_all_job", "indirect_all_job", "induced_all_job",
    "direct_within_job", "indirect_within_job", "induced_within_job",
]


def read_coefficients(uploaded_file):
    """Read CSV or Excel coefficient data."""
    suffix = Path(uploaded_file.name).suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(uploaded_file)
    if suffix in {".xlsx", ".xlsm"}:
        return pd.read_excel(uploaded_file, engine="openpyxl")
    raise ValueError("Upload a .csv, .xlsx, or .xlsm file.")


def prepare_coefficients(raw):
    """Clean and validate the coefficient dataset."""
    df = raw.copy()
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    for col in ["IOIC", "PROV", "NOC3DIG"]:
        df[col] = df[col].astype("string").str.strip()

    df[NUMERIC_COLS] = df[NUMERIC_COLS].apply(pd.to_numeric, errors="coerce")
    df["zero_industry_employment"] = df["totalemp_ind"].fillna(0).eq(0)
    df.loc[df["zero_industry_employment"], "occshare"] = np.nan

    share_check = (
        df.loc[~df["zero_industry_employment"]]
        .groupby(["PROV", "IOIC"], as_index=False)
        .agg(sum_occshare=("occshare", "sum"), totalemp_ind=("totalemp_ind", "first"))
    )
    share_check["share_error"] = (share_check["sum_occshare"] - 1).abs()
    bad_shares = share_check.loc[share_check["share_error"] > 0.01].copy()

    # Verify that repeated industry-level multipliers are constant within PROV x IOIC.
    multiplier_inconsistency = (
        df.groupby(["PROV", "IOIC"])[MULTIPLIER_COLS]
        .nunique(dropna=False)
        .reset_index()
    )
    inconsistent_mask = multiplier_inconsistency[MULTIPLIER_COLS].gt(1).any(axis=1)
    inconsistent_multipliers = multiplier_inconsistency.loc[inconsistent_mask].copy()

    industry_data = (
        df[["PROV", "IOIC", "totalemp_ind"] + MULTIPLIER_COLS]
        .drop_duplicates(subset=["PROV", "IOIC"])
        .copy()
    )

    occ_data = df[
        ["PROV", "IOIC", "NOC3DIG", "emp", "occshare", "totalemp_occ", "zero_industry_employment"]
    ].copy()

    return df, industry_data, occ_data, bad_shares, inconsistent_multipliers


def run_scenario(scenario, industry_data, occ_data, geography="within"):
    """Run the labour-demand scenario. Investment is entered in $ millions."""
    scenario = scenario.copy()
    required = ["PROV", "IOIC", "investment_millions"]
    missing = [c for c in required if c not in scenario.columns]
    if missing:
        raise ValueError(f"Scenario is missing columns: {missing}")

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
        ["PROV", "IOIC", "totalemp_ind"] + list(rename.keys())
    ].rename(columns=rename)

    merged = scenario.merge(multipliers, on=["PROV", "IOIC"], how="left", indicator=True)
    unmatched = merged.loc[merged["_merge"].ne("both"), ["PROV", "IOIC", "investment_millions"]].copy()
    if not unmatched.empty:
        raise ValueError(
            "Scenario contains province x IOIC combinations not found in the coefficient data:\n"
            + unmatched.to_string(index=False)
        )

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

    detailed = industry[
        ["PROV", "IOIC", "investment_millions", "investment_dollars", "direct_jobs"]
    ].merge(occ_data, on=["PROV", "IOIC"], how="left")

    zero_inputs = detailed.loc[
        detailed["zero_industry_employment"].eq(True), ["PROV", "IOIC", "investment_millions"]
    ].drop_duplicates()

    detailed["new_jobs"] = detailed["direct_jobs"] * detailed["occshare"]
    occupation = (
        detailed.dropna(subset=["NOC3DIG", "new_jobs"])
        .groupby(["PROV", "NOC3DIG"], as_index=False)
        .agg(new_jobs=("new_jobs", "sum"), totalemp_occ=("totalemp_occ", "first"))
    )
    occupation["employment_change_pct"] = np.where(
        occupation["totalemp_occ"].gt(0),
        occupation["new_jobs"] / occupation["totalemp_occ"] * 100,
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


def to_excel_bytes(sheets):
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for name, frame in sheets.items():
            frame.to_excel(writer, sheet_name=name[:31], index=False)
    buffer.seek(0)
    return buffer.getvalue()


def reset_scenario():
    st.session_state.scenario_rows = pd.DataFrame(
        columns=["PROV", "IOIC", "investment_millions"]
    )
    st.session_state.results = None


# ---------- Header ----------
st.title("Major Projects Labour-Market Requirements")
st.caption(
    "Translate provincial IOIC investment shocks into employment, labour income, "
    "and direct occupational requirements."
)

with st.expander("Method and interpretation", expanded=False):
    st.markdown(
        """
- Investment inputs are in **millions of dollars**.
- Job multipliers are applied per **$1 million** of final demand.
- Wage multipliers are applied per **$1** of final demand.
- Industry totals report direct, indirect, and induced effects.
- Occupational requirements allocate **direct jobs only** using each province-industry's occupation shares.
- `employment_change_pct` compares new direct demand with existing provincial employment in that NOC group.
- The tool is a scenario assessment calculator, not a forecast of realized employment or shortages.
        """
    )

# ============================================================
# LOAD COEFFICIENT DATA
# ============================================================

DATA_FILE = "io_noc_coefficients.xlsx"

@st.cache_data
def load_data():
    return pd.read_excel(
        DATA_FILE,
        engine="openpyxl"
    )

raw = load_data()

# Run the same cleaning/validation function as before
df, industry_data, occ_data, bad_shares, inconsistent_multipliers = (
    prepare_coefficients(raw)
)

# Stop the app if validation fails
if bad_shares.empty:
    st.sidebar.success("Occupation-share validation passed.")
else:
    st.sidebar.error(
        f"{len(bad_shares)} province-industry cells fail "
        "the occupation-share check."
    )

    with st.expander("View occupation-share validation failures"):
        st.dataframe(
            bad_shares,
            hide_index=True,
            use_container_width=True
        )

if not inconsistent_multipliers.empty:

    st.sidebar.error(
        "Some multipliers vary within the same "
        "province-industry cell."
    )

    with st.expander("View inconsistent multiplier cells"):
        st.dataframe(
            inconsistent_multipliers,
            hide_index=True,
            use_container_width=True
        )

if (
    not bad_shares.empty
    or not inconsistent_multipliers.empty
):
    st.warning(
        "Correct the coefficient data before running a scenario."
    )

    st.stop()
    
# ---------- Scenario builder ----------
st.sidebar.header("2. Add investment shocks")
provinces = sorted(industry_data["PROV"].dropna().astype(str).unique())
selected_prov = st.sidebar.selectbox("Province", provinces)
valid_ioics = sorted(
    industry_data.loc[industry_data["PROV"].eq(selected_prov), "IOIC"]
    .dropna().astype(str).unique()
)
selected_ioic = st.sidebar.selectbox("IOIC industry", valid_ioics)
investment_m = st.sidebar.number_input(
    "Investment ($ millions)", min_value=0.0, value=100.0, step=10.0, format="%.1f"
)

b1, b2 = st.sidebar.columns(2)
if b1.button("Add shock", width="stretch"):
    new_row = pd.DataFrame({
        "PROV": [selected_prov],
        "IOIC": [selected_ioic],
        "investment_millions": [investment_m],
    })
    st.session_state.scenario_rows = pd.concat(
        [st.session_state.scenario_rows, new_row], ignore_index=True
    )
    st.session_state.results = None
    st.rerun()

if b2.button("Clear", width="stretch"):
    reset_scenario()
    st.rerun()

st.subheader("Scenario inputs")
if st.session_state.scenario_rows.empty:
    st.info("Add one or more province-industry investment shocks from the sidebar.")
else:
    edited = st.data_editor(
        st.session_state.scenario_rows,
        hide_index=True,
        num_rows="dynamic",
        width="stretch",
        column_config={
            "PROV": st.column_config.TextColumn("Province", disabled=True),
            "IOIC": st.column_config.TextColumn("IOIC", disabled=True),
            "investment_millions": st.column_config.NumberColumn(
                "Investment ($M)", min_value=0.0, step=10.0, format="%.1f"
            ),
        },
        key="scenario_editor",
    )
    st.session_state.scenario_rows = edited

    geography_label = st.radio(
        "Geographic scope for multipliers",
        ["Within province", "All provinces"],
        horizontal=True,
        help="Within province measures effects occurring in the selected province. All provinces includes Canadian effects outside it.",
    )
    geography = "within" if geography_label == "Within province" else "all"

    if st.button("Run scenario", type="primary", width="stretch"):
        try:
            st.session_state.results = run_scenario(
                st.session_state.scenario_rows,
                industry_data,
                occ_data,
                geography=geography,
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
cols = st.columns(4)
cols[0].metric("Investment", f"${summary['Investment ($M)']:,.1f}M")
cols[1].metric("Direct jobs", f"{summary['Direct jobs']:,.0f}")
cols[2].metric("Total jobs", f"{summary['Total jobs']:,.0f}")
cols[3].metric("Total labour income", f"${summary['Total labour income']/1_000_000:,.1f}M")

if not results["zero_inputs"].empty:
    st.warning(
        "One or more shocked industries have zero baseline employment, so their direct jobs could not be allocated to occupations."
    )
    st.dataframe(results["zero_inputs"], hide_index=True, width="stretch")

industry_tab, occupation_tab, downloads_tab = st.tabs(
    ["Industry effects", "Occupational requirements", "Downloads"]
)

with industry_tab:
    display_industry = results["industry"][[
        "PROV", "IOIC", "investment_millions", "direct_jobs", "indirect_jobs",
        "induced_jobs", "total_jobs", "direct_labour_income", "total_labour_income"
    ]].copy()
    st.dataframe(
        display_industry,
        hide_index=True,
        width="stretch",
        column_config={
            "investment_millions": st.column_config.NumberColumn("Investment ($M)", format="%.1f"),
            "direct_jobs": st.column_config.NumberColumn("Direct jobs", format="%.1f"),
            "indirect_jobs": st.column_config.NumberColumn("Indirect jobs", format="%.1f"),
            "induced_jobs": st.column_config.NumberColumn("Induced jobs", format="%.1f"),
            "total_jobs": st.column_config.NumberColumn("Total jobs", format="%.1f"),
            "direct_labour_income": st.column_config.NumberColumn("Direct labour income", format="$%.0f"),
            "total_labour_income": st.column_config.NumberColumn("Total labour income", format="$%.0f"),
        },
    )

with occupation_tab:
    occ = results["occupation"].copy()
    province_filter = st.multiselect(
        "Province filter", sorted(occ["PROV"].unique()), default=sorted(occ["PROV"].unique())
    )
    top_n = st.slider("Number of occupations to display", 5, 40, 15)
    metric_choice = st.radio(
        "Rank by", ["Employment pressure (%)", "New direct jobs"], horizontal=True
    )

    filtered = occ.loc[occ["PROV"].isin(province_filter)].copy()
    rank_col = "employment_change_pct" if metric_choice == "Employment pressure (%)" else "new_jobs"
    chart = (
        filtered.dropna(subset=[rank_col])
        .nlargest(top_n, rank_col)
        .assign(label=lambda x: x["PROV"] + " | NOC " + x["NOC3DIG"].astype(str))
        .set_index("label")[[rank_col]]
    )
    if not chart.empty:
        st.bar_chart(chart)

    st.dataframe(
        filtered[["PROV", "NOC3DIG", "new_jobs", "totalemp_occ", "employment_change_pct", "pressure_rank"]],
        hide_index=True,
        width="stretch",
        column_config={
            "new_jobs": st.column_config.NumberColumn("New direct jobs", format="%.1f"),
            "totalemp_occ": st.column_config.NumberColumn("Existing occupation employment", format="%.0f"),
            "employment_change_pct": st.column_config.NumberColumn("Employment pressure", format="%.2f%%"),
            "pressure_rank": st.column_config.NumberColumn("Provincial pressure rank", format="%.0f"),
        },
    )
    st.caption(
        "Occupational results allocate direct jobs only. Indirect and induced jobs are shown in industry totals but are not assigned the shocked industry's occupation mix."
    )

with downloads_tab:
    workbook = to_excel_bytes({
        "Scenario inputs": st.session_state.scenario_rows,
        "Industry results": results["industry"],
        "Occupation results": results["occupation"],
        "Occupation detail": results["detailed"],
    })
    st.download_button(
        "Download complete results (.xlsx)",
        data=workbook,
        file_name="major_projects_labour_results.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        width="stretch",
    )
    st.download_button(
        "Download occupation results (.csv)",
        data=results["occupation"].to_csv(index=False).encode("utf-8"),
        file_name="occupation_results.csv",
        mime="text/csv",
        width="stretch",
    )
