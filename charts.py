
import pandas as pd
import plotly.express as px


def monthly_trend_chart(df: pd.DataFrame, value_column: str = "form_count"):
    """
    Line chart of a monthly metric (form count or low-score count).
    """
    if df.empty:
        return px.line(title="No data")

    fig = px.line(
        df,
        x="year_month",
        y=value_column,
        markers=True,
    )
    fig.update_layout(
        xaxis_title="Month",
        yaxis_title=value_column.replace("_", " ").title(),
        hovermode="x unified",
    )
    return fig


def instructor_avg_score_bar_chart(df: pd.DataFrame):
    """
    Bar chart showing average score per instructor_grouped.
    """
    if df.empty:
        return px.bar(title="No data")

    agg = (
        df.groupby("instructor_grouped")["score"]
        .mean()
        .reset_index()
        .sort_values("score", ascending=False)
    )
    fig = px.bar(
        agg,
        x="instructor_grouped",
        y="score",
    )
    fig.update_layout(
        xaxis_title="Instructor",
        yaxis_title="Average score",
    )
    return fig


def low_score_percentage_pie_chart(df: pd.DataFrame):
    """
    Pie chart of low-score vs other forms.
    """
    if df.empty:
        return px.pie(title="No data")

    low_count = df["low_score_flag"].sum()
    total = len(df)
    high_count = total - low_count
    plot_df = pd.DataFrame(
        {
            "category": ["Score ≤ 3", "Score > 3"],
            "count": [low_count, high_count],
        }
    )
    fig = px.pie(
        plot_df,
        names="category",
        values="count",
        hole=0.4,
    )
    return fig


def monthly_heatmap_chart(df: pd.DataFrame):
    """
    Heatmap of monthly average scores.
    """
    if df.empty:
        return px.imshow([[0]], labels=dict(color="Avg score"), title="No data")

    heat_df = df.copy()
    heat_df["year"] = heat_df["year_month"].dt.year
    heat_df["month"] = heat_df["year_month"].dt.month

    pivot = heat_df.pivot_table(
        index="year",
        columns="month",
        values="avg_score",
        aggfunc="mean",
    )

    fig = px.imshow(
        pivot,
        aspect="auto",
        labels=dict(x="Month", y="Year", color="Avg score"),
    )
    return fig


def instructor_trend_chart(df: pd.DataFrame, instructor_name: str):
    """
    Trend of average monthly scores for one instructor.
    """
    if df.empty:
        return px.line(title=f"No data for {instructor_name}")

    fig = px.line(
        df,
        x="year_month",
        y="avg_score",
        markers=True,
    )
    fig.update_layout(
        title=f"Monthly average scores for {instructor_name}",
        xaxis_title="Month",
        yaxis_title="Average score",
    )
    return fig
