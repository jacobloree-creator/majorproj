# LAMP: Labour Analysis of Major Projects

LAMP is a Streamlit-based scenario assessment tool for estimating the labour-market requirements associated with major investment projects in Canada.

The application translates project expenditures into:

- direct, indirect, and induced employment;
- labour income;
- direct occupational requirements;
- annual project-pipeline labour demand;
- occupation-level labour-market pressure;
- projected labour-market balances using Canadian Occupational Projection System (COPS) flows;
- potential occupational mobility pathways; and
- user-defined scenarios for how occupational mobility could help meet project labour requirements.

LAMP is designed primarily for analysis of major infrastructure, construction, electricity, mining-development, and other capital-intensive projects.

The model is an analytical scenario tool, not a forecast of realized employment or labour shortages.

---

# What LAMP does

LAMP currently supports two analysis modes.

## 1. Static scenarios

Users can:

1. select a province or the Canada benchmark;
2. select one or more Input-Output Industry Classification (IOIC) industries;
3. enter an investment or final-demand shock in millions of dollars;
4. choose between within-province and all-provinces multiplier effects;
5. estimate direct, indirect, induced, and total employment effects;
6. estimate direct and total labour-income effects;
7. allocate direct employment requirements across three-digit NOC occupational groups;
8. compare occupational requirements with the existing workforce;
9. examine unemployment, vacancies, wages, and demographic indicators; and
10. download complete scenario results.

## 2. Project timeline scenarios

Users can build multi-project, multi-year expenditure profiles containing:

```text
project × province × fiscal year × industry × expenditure
```

The timeline module estimates:

- annual investment;
- annual direct, indirect, induced, and total employment;
- total direct job-years;
- peak direct employment and peak fiscal year;
- annual occupational requirements;
- peak occupational pressure;
- individual project contributions to occupational demand;
- COPS-adjusted labour-market balances;
- potential occupational mobility sources; and
- mobility-response scenarios.

Project plans can be saved to and loaded from Excel, allowing scenarios to be modified without re-entering project expenditures manually.

---

# Core methodology

## Industry employment

For province \(r\), IOIC industry \(i\), and year \(t\):

```text
direct_jobs[i,r,t]
    = investment_millions[i,r,t]
    × direct_job_multiplier[i,r]
```

Job multipliers are expressed as jobs per $1 million of final demand.

Equivalent calculations are made for indirect and induced employment.

```text
total_jobs
    = direct_jobs
    + indirect_jobs
    + induced_jobs
```

---

# Labour income

Labour-income multipliers are expressed as dollars of labour income per $1 of final demand.

```text
direct_labour_income[i,r,t]
    = investment_dollars[i,r,t]
    × direct_wage_multiplier[i,r]
```

Equivalent calculations are made for indirect and induced labour income.

---

# Occupational requirements

Occupational requirements are calculated for **direct employment only**.

Direct industry employment is allocated to occupations using observed province × industry occupational employment shares:

```text
new_jobs[o,i,r,t]
    = direct_jobs[i,r,t]
    × occupation_share[o,i,r]
```

Requirements are then summed across industries and projects:

```text
new_jobs[o,r,t]
    = Σ new_jobs[o,i,r,t]
```

Indirect and induced employment are not assigned the occupational composition of the directly affected industry because these jobs arise in other industries.

---

# Occupational workforce pressure

LAMP compares new direct occupational demand with the existing occupational workforce.

```text
employment_pressure[o,r,t]
    = 100
    × new_jobs[o,r,t]
    / existing_employment[o,r]
```

This is a **demand-exposure indicator**, not a shortage probability.

For example, an estimated requirement of 500 workers in an occupation with 5,000 existing workers represents a 10% increase in demand relative to the current workforce.

That does not imply that 500 jobs will remain unfilled.

---

# Project timelines and job-years

Timeline scenarios treat annual project expenditure as generating labour requirements in the corresponding fiscal year.

Peak direct employment is:

```text
peak_direct_jobs
    = max(direct_jobs[t])
```

Total direct job-years are:

```text
direct_job_years
    = Σ direct_jobs[t]
```

Job-years should not be interpreted as unique workers.

For example, 1,000 direct jobs maintained for three years represent approximately 3,000 direct job-years, but the same workers may contribute employment in multiple years.

---

# Canada benchmark

LAMP includes a `CA` or **Canada benchmark** option.

Canada-level multiplier effects use official Canada-level all-provinces multipliers.

National occupational and labour-market context is constructed by aggregating the ten provincial source datasets.

For occupational composition:

```text
CA employment[i,o]
    = Σ provincial employment[i,o]
```

and:

```text
CA occupation_share[i,o]
    = CA employment[i,o]
    / CA industry_employment[i]
```

National:

- employment;
- unemployment; and
- vacancies

are summed across provinces.

The following variables are constructed as employment-weighted national benchmarks where required:

- average hourly wages;
- vacancy rates; and
- older-worker shares.

The Canada labour-market benchmark currently represents the **ten provinces only**. Territorial labour-market observations are not included in these aggregated supply indicators.

The Canada option is therefore best interpreted as a **national labour-market benchmark**, particularly when direct territorial estimates are unavailable. It should not be interpreted as evidence that nationally available workers are immediately available to remote projects.

Canada has no separate "within province" multiplier concept. Canada benchmark rows therefore use Canada-level all-provinces multipliers regardless of the selected multiplier-scope option.

---

# Labour-market context

LAMP merges occupational requirements with province × three-digit NOC indicators including:

- employment;
- unemployment;
- unemployment rate;
- vacancies;
- vacancy rate;
- average hourly wage; and
- older-worker share.

These indicators provide context for workforce availability but are not combined into a deterministic shortage score.

Suppressed vacancy observations are treated as missing rather than as zero vacancies.

---

# COPS labour-market balances

LAMP incorporates annual occupational flows from the Canadian Occupational Projection System (COPS).

COPS inputs include:

## Projected inflows

- school leavers;
- immigrants; and
- other inflows.

COPS "other inflows" include occupational mobility, net labour-force re-entry, and other adjustments.

## Projected demand and outflows

- expansion demand;
- retirements; and
- emigration.

LAMP constructs:

```text
total_inflows
    = school_inflow
    + immigrant_inflow
    + other_inflow
```

Replacement demand is:

```text
replacement_demand
    = retirement_outflow
    + emigration_outflow
```

Baseline projected openings are:

```text
baseline_openings
    = expansion_demand
    + replacement_demand
```

The COPS baseline balance is:

```text
baseline_balance
    = total_inflows
    - baseline_openings
```

LAMP then adds major-project occupational demand:

```text
post_project_balance
    = baseline_balance
    - LAMP_direct_demand
```

A negative value indicates that projected openings plus LAMP requirements exceed projected inflows under this accounting framework.

The difference between the COPS baseline balance and the post-project balance is the additional occupational demand generated by the project pipeline.

## Provincial COPS allocation

COPS flows are national.

For provincial analysis, LAMP allocates national occupational flows using each province's current share of ten-province employment in that occupation.

For Canada benchmark scenarios, national COPS flows are used directly.

These results are **accounting pressure indicators**, not equilibrium forecasts of vacancies or unfilled positions.

---

# Occupational mobility diagnostics

LAMP uses an empirical occupational transition matrix to identify potential occupational sources of workers.

The mobility input combines:

- empirical U.S. occupation-to-occupation transition patterns; and
- Canadian occupational skill-distance measures.

The empirical transition matrix was originally estimated at the five-digit occupational level and subsequently aggregated to three-digit NOC groups.

Five-digit transitions occurring within the same three-digit NOC are excluded from the LAMP between-occupation mobility model.

For each three-digit origin occupation \(i\) and destination occupation \(j\), LAMP retains:

```text
historical_transition_rate[i,j]
```

and a conditional destination share:

```text
P(destination j | leaving three-digit origin i)
```

Skill distance provides a separate measure of occupational similarity.

---

# Historical mobility benchmark

For each potential origin occupation:

```text
historical_mobility_benchmark[i,j,r]
    = employment[i,r]
    × historical_transition_rate[i,j]
```

This answers:

> What would the scale of movement between these occupations look like if the empirical U.S. transition relationship were applied to the Canadian or provincial origin workforce?

It does **not** mean that these workers are available to a project.

Historical mobility reflects normal career changes, quits, retraining, industry changes, geographic mobility, and other labour-market processes.

---

# Mobility evidence classifications

Potential occupational pathways are classified using two separate signals:

1. empirical source strength; and
2. Canadian skill proximity.

The current classification uses the 75th percentile as the threshold for a relatively strong signal.

| Classification | Empirical mobility | Skill proximity | Interpretation |
|---|---|---|---|
| Strong potential source | High | High | Both observed transitions and skill similarity support the pathway |
| Empirically observed | High | Lower | Workers make the transition relatively frequently even though measured skill similarity is weaker |
| Skill-compatible | Lower | High | Skills suggest a plausible transition but the observed transition is less common |
| Weak source | Lower | Lower | Neither indicator provides strong evidence for the pathway |

These classifications describe the **strength of evidence for a mobility pathway**, not worker availability.

Potential source occupations are also evaluated against their own COPS labour-market conditions.

This prevents the model from automatically interpreting an occupation under substantial projected labour-market pressure as an unconstrained source of workers.

---

# Mobility scenarios

LAMP includes an experimental occupational-mobility scenario module.

This module allows users to simulate how much project labour demand might potentially be met through increased occupational switching.

The simulation contains three user-selected assumptions.

## 1. Eligible mobility pathways

Users may restrict recruitment to:

- Strong potential sources only;
- Strong plus empirically supported sources;
- all non-weak pathways; or
- all observed pathways.

## 2. Source-capacity rule

Users can select:

### COPS-surplus capped

Workers may be drawn only from occupations with a positive projected COPS balance, and simulated recruitment cannot exceed that surplus.

### Non-deficit origins

Workers may be drawn from occupations not projected to be in deficit. Recruitment is not mechanically capped at the size of the projected surplus.

### Unrestricted

Workers may be drawn from all mobility pathways, including source occupations projected to be under labour-market pressure.

This option is best interpreted as a high-mobility or displacement stress test.

## 3. Induced mobility response

Users select an assumed response between 0% and 100% of the historical mobility benchmark.

For source occupation \(i\) and destination occupation \(j\):

```text
uncapped_induced_reallocation[i,j]
    = historical_mobility_benchmark[i,j]
    × assumed_response_rate
```

For example, if the historical mobility benchmark is 120 workers and the user selects a 25% response:

```text
120 × 0.25 = 30 workers
```

The model interprets 30 as **potential induced occupational reallocation under the selected scenario**.

The default response assumption is illustrative. It is not an estimated Canadian behavioural elasticity.

---

# Mobility scenario constraints

Simulated occupational recruitment is subject to two important constraints.

## Source capacity

Under the COPS-surplus-capped scenario:

```text
potential_reallocation[i,j]
    = min(
        induced_reallocation[i,j],
        projected_source_surplus[i]
      )
```

This prevents the scenario from solving one projected shortage by mechanically creating another.

## Destination demand

Total simulated reallocation cannot exceed LAMP occupational demand:

```text
actual_reallocation[j]
    <= LAMP_demand[j]
```

Where potential recruitment exceeds destination demand, source contributions are scaled proportionally.

The model then reports:

```text
remaining_requirement[j]
    = LAMP_demand[j]
    - actual_reallocation[j]
```

The remaining requirement would need to be met through other adjustment channels or remain unfilled.

Possible channels include:

- workers already in the destination occupation changing industries or employers;
- unemployment;
- labour-force re-entry;
- school and apprenticeship entrants;
- immigration;
- interprovincial mobility;
- temporary or rotational workers;
- additional wage responses; or
- project timing adjustments.

---

# Interpreting mobility scenarios

Mobility scenarios are **not forecasts**.

They combine:

- empirical historical transition relationships;
- Canadian workforce size;
- Canadian skill similarity;
- projected COPS conditions; and
- explicit user-selected behavioural assumptions.

Results should therefore be described using language such as:

> Under the selected assumptions, occupational mobility could potentially meet X% of the project's direct occupational requirement.

They should not be described as:

> X workers will switch occupations.

The mobility module is intended primarily for sensitivity analysis and identifying plausible labour-adjustment channels.

---

# Project-plan workflow

Large project pipelines do not need to be entered manually through the Streamlit sidebar.

Users can:

1. download a blank project-plan template;
2. enter project expenditures in Excel;
3. reference the supplied list of valid province × IOIC combinations;
4. upload the completed plan;
5. modify the imported plan in Streamlit;
6. run the project pipeline;
7. save the modified plan; and
8. download complete analytical results.

The required project-plan structure is:

```text
project_name
PROV
fiscal_year
IOIC
investment_millions
```

LAMP validates uploaded plans before importing them.

---

# Output tabs

Timeline scenarios currently provide:

## Annual overview

- annual investment;
- direct employment;
- total employment;
- labour income; and
- annual project-pipeline profile.

## Peak occupational pressures

Shows the year in which each occupation experiences its largest project demand relative to the existing workforce.

## COPS labour balance

Compares:

- projected inflows;
- baseline occupational demand;
- additional LAMP demand;
- COPS baseline balance; and
- balance after adding the project pipeline.

## Potential worker sources

Identifies empirically observed and skill-compatible occupational pathways into occupations required by the project pipeline.

Outputs include:

- source employment;
- historical transition rates;
- historical mobility benchmarks;
- skill distance;
- skill-closeness percentile;
- empirical-source percentile;
- evidence classification;
- source COPS balance; and
- source labour-market condition.

## Mobility scenarios

Allows users to vary:

- eligible mobility pathways;
- source-capacity assumptions; and
- assumed induced-mobility response.

Outputs include:

- LAMP direct demand;
- eligible historical mobility benchmark;
- potential induced occupational reallocation;
- share of demand potentially met;
- source contributions;
- source balance after simulated recruitment; and
- remaining labour requirement.

## Occupation over time

Shows annual occupational demand and workforce pressure across the project schedule.

## Project contributions

Decomposes occupational demand by individual project.

## Downloads

Exports detailed scenario inputs and results to Excel.

---

# Data files

The current application uses the following input files:

```text
io_noc_coefficients.xlsx
unemployment.xlsx
demographics.xlsx
wages.xlsx
noc_titles.xlsx
vacancies.xlsx
cops flows.xlsx
canada_multipliers.xlsx
switching_benchmarks_lamp_normalized.xlsx
```

## `io_noc_coefficients.xlsx`

Contains province × IOIC × three-digit NOC employment structure and provincial input-output multipliers.

Required fields include:

```text
IOIC
PROV
NOC3DIG
emp
totalemp_ind
occshare

direct_all_wage
indirect_all_wage
induced_all_wage

direct_within_wage
indirect_within_wage
induced_within_wage

direct_all_job
indirect_all_job
induced_all_job

direct_within_job
indirect_within_job
induced_within_job

totalemp_occ
```

## `unemployment.xlsx`

Required fields:

```text
PROV
NOC3DIG
employed
unemployed
unemprate
```

## `demographics.xlsx`

Required fields:

```text
PROV
NOC3DIG
highageshare
```

## `wages.xlsx`

Required fields:

```text
PROV
NOC3DIG
earn_mean
```

## `vacancies.xlsx`

Required fields:

```text
PROV
NOC3DIG
vacancies
vacancy rate
```

## `noc_titles.xlsx`

Required fields:

```text
NOC3DIG
title
```

## `cops flows.xlsx`

Contains annual national three-digit occupational flows including:

```text
noc3dig
type
year2025
year2026
...
```

Required flow types are:

```text
expansiondemand
retirement_outflow
emigration_outflow
school_inflow
immigrant_inflow
other_inflow
```

## `canada_multipliers.xlsx`

Contains official Canada-level all-provinces industry multipliers:

```text
PROV
IOIC

direct_all_job
indirect_all_job
induced_all_job

direct_all_wage
indirect_all_wage
induced_all_wage
```

Job multipliers are jobs per $1 million of final demand.

Wage multipliers are dollars of labour income per $1 of final demand.

Correct multiplier units are critical.

## `switching_benchmarks_lamp_normalized.xlsx`

Contains the normalized occupational mobility matrix.

Core fields include:

```text
origin_NOC3DIG
destination_NOC3DIG

skill_distance
between_3digit_switch

origin_between3_exit_rate_pct
lamp_destination_share

historical_between3_transition_rate

destination_rank_within_origin
source_rank_for_destination

skill_closeness_percentile_origin
```

The source workbook also retains the original empirical transition measures for reproducibility.

---

# Data validation

At startup, LAMP performs a range of validation checks.

These include:

1. required columns are present;
2. numeric fields can be interpreted as numeric;
3. occupation shares sum to approximately one within province × IOIC cells;
4. multiplier values are internally consistent within province × industry cells;
5. uploaded project-plan rows correspond to valid province × IOIC combinations;
6. COPS provincial allocation shares sum to approximately one;
7. LAMP occupational groups match available COPS groups;
8. Canada multiplier industries match available occupational structure;
9. LAMP occupations match available mobility destinations;
10. mobility origin × destination pairs are unique; and
11. normalized conditional mobility shares sum to approximately one for each origin occupation.

Validation warnings are intentionally distinguished from fatal errors. Missing COPS or mobility information does not invalidate the underlying input-output scenario.

---

# Repository structure

A typical repository structure is:

```text
major-project-labour/
│
├── labour_market_mvp.py
├── io_noc_coefficients.xlsx
├── unemployment.xlsx
├── demographics.xlsx
├── wages.xlsx
├── noc_titles.xlsx
├── vacancies.xlsx
├── cops flows.xlsx
├── canada_multipliers.xlsx
├── switching_benchmarks_lamp_normalized.xlsx
├── requirements.txt
└── README.md
```

`labour_market_mvp.py` contains both the Streamlit interface and the current calculation engine.

---

# Local installation

Create and activate a Python environment, then install the required packages.

```bash
pip install -r requirements.txt
```

A minimal `requirements.txt` is:

```text
streamlit
pandas
numpy
openpyxl
altair
```

Run LAMP locally with:

```bash
streamlit run labour_market_mvp.py
```

---

# Streamlit Community Cloud

To deploy LAMP on Streamlit Community Cloud:

1. create or update the GitHub repository;
2. add the Python application and required data files;
3. add `requirements.txt`;
4. add this `README.md`;
5. sign in to Streamlit Community Cloud using GitHub;
6. create an app from the repository;
7. select `labour_market_mvp.py` as the application entry point; and
8. deploy.

Input datasets are loaded directly from the repository and do not need to be uploaded by users when running scenarios.

---

# Updating source data

When updating source datasets:

1. preserve required variable names;
2. confirm classification mappings;
3. verify all multiplier units;
4. verify occupation shares;
5. verify COPS year coverage;
6. rerun startup validation;
7. document changes to reference years or classification vintages; and
8. restart or redeploy the application.

In particular, always verify:

```text
job multiplier
    = jobs per $1 million of final demand

wage multiplier
    = dollars of labour income per $1 of final demand
```

A multiplier-unit error can produce internally consistent but economically implausible results.

---

# Recommended source documentation

The repository should document:

- Statistics Canada tables or source files used;
- input-output multiplier reference year;
- IOIC aggregation;
- NOC vintage;
- occupation aggregation methodology;
- employment reference period;
- vacancy reference period;
- wage reference period;
- COPS projection vintage;
- treatment of COPS "other inflows";
- source and construction of empirical U.S. occupational transitions;
- source and construction of Canadian skill distances;
- treatment of five-digit transitions within three-digit NOC groups;
- weighting used to construct Canada benchmark variables;
- treatment of suppressed data;
- treatment of zero-employment cells; and
- dates on which input files were last updated.

---

# Current limitations

LAMP remains an analytical prototype.

Important limitations include:

1. Occupational allocations cover **direct employment only**.
2. Industry occupational shares are held fixed.
3. Provincial COPS flows are estimated by allocating national flows using current provincial occupational employment shares.
4. The Canada labour-market benchmark excludes territorial observations.
5. National worker availability does not imply availability at a remote project site.
6. Occupational mobility relationships are based on empirical U.S. transition patterns rather than Canadian worker transitions.
7. Canadian skill distance describes occupational similarity but does not establish worker eligibility, licensing, certification, or willingness to switch.
8. Historical mobility benchmarks are not measures of workers currently available.
9. Mobility response parameters are scenario assumptions, not estimated Canadian behavioural elasticities.
10. COPS balance measures are accounting indicators rather than equilibrium shortage forecasts.
11. The model does not currently endogenize wage changes.
12. The model does not currently estimate recruitment between industries within the same occupation.
13. Interprovincial worker mobility is not yet explicitly modelled.
14. Project-specific training and apprenticeship responses are not yet endogenous.
15. Labour constraints do not yet feed back into project schedules or project costs.
16. Source-industry displacement and replacement are not yet modelled.
17. Household, price, capital, and other economy-wide general-equilibrium responses are outside the current model.

---

# Planned extensions

Potential future extensions include:

## Same-occupation industry mobility

Estimate the degree to which project workers are recruited from existing employers in other industries.

## Interprovincial mobility

Model where workers could be recruited geographically, particularly for remote and territorial projects.

## Wage responses

Allow labour-market pressure to affect occupation-specific wages and use wages as an adjustment mechanism for labour supply and mobility.

## Source-industry displacement

Estimate whether workers recruited by projects are replaced by source employers or whether activity is displaced elsewhere in the economy.

## Training and apprenticeship responses

Model additional worker supply generated through education, apprenticeship, and employer-supported training, including realistic lags.

## Project cost effects

Translate occupation-specific wage pressure into additional project labour costs.

## Project scheduling

Allow labour constraints to delay expenditure and move project activity between fiscal years.

## Competing-project scenarios

Examine how different project sequencing assumptions affect peak workforce requirements and labour-market pressure.

## Broader general-equilibrium effects

Potential longer-term extensions could incorporate:

- capital-labour substitution;
- import substitution;
- output displacement;
- household-income responses;
- consumption effects; and
- fiscal impacts.

The intent is not necessarily to reproduce a full computable general-equilibrium model. LAMP's comparative advantage is retaining detailed:

```text
project × year × industry × occupation × geography
```

information while adding transparent labour-market adjustment mechanisms.

---

# Interpretation principles

LAMP distinguishes several different concepts that should not be conflated.

## Labour requirement

Workers associated with project expenditure under the applicable input-output multiplier.

## Workforce pressure

Project demand relative to the existing occupational workforce.

## COPS balance

Projected occupational inflows minus baseline openings, with project demand subsequently added as an incremental requirement.

## Historical mobility benchmark

The scale of an origin-destination transition implied by applying an empirical historical transition rate to the Canadian or provincial source workforce.

## Potential induced reallocation

The portion of the historical mobility benchmark assumed to respond under a user-selected mobility scenario.

## Remaining requirement

Project occupational demand not met through the simulated mobility channel.

None of these quantities should automatically be interpreted as realized employment, vacancies, shortages, or worker movements.

---

# Citation and analytical use

When reporting LAMP results, analysis should identify:

- project(s) included;
- project location or model geography;
- IOIC industry assumptions;
- annual expenditure profile;
- multiplier scope;
- whether the Canada benchmark was used;
- direct versus total employment;
- COPS projection assumptions;
- mobility-pathway restrictions;
- source-capacity rule;
- assumed mobility-response rate; and
- the fact that occupational requirements refer to direct project employment.

Mobility-scenario results should always identify the user-selected behavioural assumptions.

---

# Disclaimer

LAMP is an analytical prototype for scenario assessment.

Results depend on:

- source data;
- multiplier definitions;
- classification mappings;
- occupational employment shares;
- project timing;
- COPS projections;
- occupational-transition evidence;
- skill-distance measures; and
- user-selected scenario assumptions.

Outputs should be interpreted alongside other evidence on:

- worker availability;
- vacancies;
- wages;
- collective agreements;
- licensing and certification;
- apprenticeship and training capacity;
- immigration;
- interprovincial mobility;
- remote-work arrangements;
- turnover;
- project sequencing; and
- employer recruitment practices.

LAMP should therefore be used to identify the **scale, timing, occupational composition, and potential adjustment channels associated with major-project labour demand**, rather than as a deterministic forecast of labour shortages or project feasibility.
