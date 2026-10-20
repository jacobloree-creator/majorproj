# Major Projects Labour-Market Requirements

A Streamlit scenario-assessment tool that translates major-project investment spending into estimated industry employment, labour income, and direct occupational labour requirements by province.

The application is intended to support analysis of labour-market requirements associated with major investments in electricity, infrastructure, construction, and other transition-related activities.

## What the app does

Users can:

- select a province;
- select one or more Input-Output Industry Classification (IOIC) industries;
- enter an investment or final-demand shock in millions of dollars;
- choose between within-province and all-provinces multiplier effects;
- estimate direct, indirect, induced, and total employment effects;
- estimate direct and total labour-income effects;
- allocate direct industry employment requirements across three-digit NOC occupational groups;
- compare new occupational demand with existing provincial employment in each occupation;
- rank occupations by estimated employment pressure; and
- download scenario results in Excel or CSV format.

## Methodology

For province `r`, shocked IOIC industry `i`, and occupation `o`, the application calculates direct industry employment as:

```text
direct_jobs[i,r] = investment_millions[i,r] * direct_job_multiplier[i,r]
```

Job multipliers are expressed as jobs per $1 million of final demand.

The application allocates direct industry jobs to occupations using the observed occupational composition of each province-industry cell:

```text
new_jobs[o,i,r] = direct_jobs[i,r] * occupation_share[o,i,r]
```

It then sums occupational requirements across all shocked industries:

```text
new_jobs[o,r] = sum over i of new_jobs[o,i,r]
```

Occupational employment pressure is calculated as:

```text
employment_pressure[o,r] = 100 * new_jobs[o,r] / existing_employment[o,r]
```

Labour-income effects are calculated separately. Wage multipliers are expressed as dollars of labour income per $1 of final demand:

```text
labour_income[i,r] = investment_dollars[i,r] * wage_multiplier[i,r]
```

## Important interpretation note

Occupational requirements are calculated for **direct jobs only**.

Indirect and induced jobs arise in other industries and should not automatically inherit the occupational composition of the directly shocked industry. The application therefore reports indirect and induced employment in the industry-level results, but does not allocate those effects across occupations.

The results represent scenario-based labour-demand estimates. They are not forecasts of realized employment, worker shortages, vacancies, or project feasibility. A larger occupational demand shock does not necessarily imply a shortage because workers may be available through unemployment, interprovincial mobility, occupational mobility, training, immigration, or other adjustment channels.

## Repository structure

```text
major-project-labour/
├── app.py
├── coefficients.xlsx
├── requirements.txt
└── README.md
```

- `app.py`: Streamlit interface and calculation engine.
- `coefficients.xlsx`: validated province × IOIC × NOC coefficient dataset.
- `requirements.txt`: Python dependencies.
- `README.md`: project documentation.

## Required coefficient variables

The Excel coefficient file must contain the following columns:

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

### Key fields

- `IOIC`: Input-Output Industry Classification code.
- `PROV`: two-letter province code, such as `AB` or `ON`.
- `NOC3DIG`: three-digit National Occupational Classification group.
- `emp`: employment in the province × industry × occupation cell.
- `totalemp_ind`: total employment in the province × industry cell.
- `occshare`: occupation's share of employment within the province × industry cell.
- `totalemp_occ`: total provincial employment in the occupation across industries.
- `*_job`: job multipliers expressed as jobs per $1 million of final demand.
- `*_wage`: labour-income multipliers expressed as dollars of labour income per $1 of final demand.

## Data validation

When the app starts, it checks that:

1. all required columns are present;
2. numeric variables can be read as numeric values;
3. occupation shares sum to approximately one within each province × IOIC industry;
4. industry multipliers are constant within each province × IOIC cell; and
5. scenario entries correspond to valid province × IOIC combinations.

A province × industry cell with zero observed employment is retained for diagnostic purposes, but its direct employment effect cannot be allocated across occupations because an occupational composition is unavailable.

## Local installation

Create and activate a Python environment, then install the required packages:

```bash
pip install -r requirements.txt
```

A suitable `requirements.txt` is:

```text
streamlit
pandas
numpy
openpyxl
```

Run the application locally:

```bash
streamlit run app.py
```

## Deploying on Streamlit Community Cloud

1. Create a GitHub repository.
2. Upload `app.py`, `coefficients.xlsx`, `requirements.txt`, and `README.md`.
3. Sign in to Streamlit Community Cloud using GitHub.
4. Create a new app from the repository.
5. Select `app.py` as the application entrypoint.
6. Deploy the app.

The application loads `coefficients.xlsx` directly from the repository, so users do not need to upload the coefficient dataset when running a scenario.

## Updating the coefficient data

To update the underlying data:

1. preserve the required variable names and definitions;
2. replace `coefficients.xlsx` in the repository;
3. validate that occupation shares sum to approximately one by province × IOIC;
4. verify that job and wage multiplier units have not changed; and
5. redeploy or restart the Streamlit application if required.

Changes to the classification vintage, multiplier year, employment reference period, or source methodology should be documented in this README.

## Recommended data documentation

The repository should record:

- the Statistics Canada table numbers or source files used;
- the IOIC aggregation and reference year;
- the NOC version and aggregation level;
- the employment data source and reference period;
- the treatment of construction and other activity-based IOIC industries;
- any imputation used for zero-employment or unmapped cells; and
- the date on which `coefficients.xlsx` was last updated.

## Current limitations

- Occupational allocations cover direct employment only.
- Occupational shares are assumed fixed within each province × industry cell.
- The framework does not yet model wage responses, displacement, productivity changes, or endogenous labour supply.
- Employment pressure is measured against the existing provincial occupational workforce and should not be interpreted as a shortage probability.
- Project timing and construction, operations, and maintenance phases are not yet modelled separately.
- Concurrent projects can be represented by entering multiple shocks, but the current version does not include a year-by-year project schedule.

## Potential extensions

Future versions could add:

- project profiles by year and phase;
- concurrent-project scenarios;
- vacancies and unemployment by occupation and province;
- retirement and demographic replacement pressures;
- apprenticeship and training pipelines;
- interprovincial mobility;
- occupational mobility and skill-similarity measures;
- occupation-specific wage effects; and
- properly allocated indirect occupational requirements using industry-by-industry employment effects.

## Citation and use

If results from the application are used in analysis or advice, cite the underlying Statistics Canada inputs and clearly identify:

- the scenario assumptions;
- the province and IOIC industries shocked;
- the investment amounts;
- whether within-province or all-provinces multipliers were used; and
- that occupational estimates refer to direct employment requirements.

## Disclaimer

This application is an analytical prototype for scenario assessment. Results depend on the underlying coefficient data, multiplier definitions, classification mappings, and user-entered shocks. Outputs should be interpreted alongside evidence on labour availability, vacancies, mobility, training capacity, immigration, wages, and project timing.
