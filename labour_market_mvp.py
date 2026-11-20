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
