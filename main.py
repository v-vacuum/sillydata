import sqlite3
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from zoneinfo import ZoneInfo

def text_frequency(df):
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
    df = df.dropna(subset=['timestamp'])

    #time zone swtichy
    df['timestamp'] = (
        df['timestamp']
        .dt.tz_localize('UTC')
        .dt.tz_convert(ZoneInfo("America/Edmonton"))  # convert to MDT/MST
    )
    #df = df[df['timestamp'].dt.year > 2005]

    # seconds since midnight for x
    df['sec'] = (
        df['timestamp'].dt.hour * 3600 +
        df['timestamp'].dt.minute * 60 +
        df['timestamp'].dt.second
    )
    # calendar date for y
    df['date'] = df['timestamp'].dt.date
    df['time_str'] = df['timestamp'].dt.strftime('%H:%M')  # for hover
    df = df.sort_values('date')

    # monthly ticks on y
    months = pd.date_range(
        df['timestamp'].min().normalize(),
        df['timestamp'].max().normalize(),
        freq='MS'
    )
    yticks = months.date

    # for the axis, show only the 3‑letter month for non‑Jan, and blank for Jan
    ytext = [
        "" if m.month == 1 else m.strftime('%b')
        for m in months
    ]

    fig = go.Figure(go.Scattergl(
        x    = df['sec'],
        y    = df['date'],
        mode = 'markers',
        marker=dict(size=2.5, opacity=0.3),
        customdata=df['time_str'],
        hovertemplate="Time: %{customdata}<br>Date: %{y}<extra></extra>"
    ))

    fig.update_layout(
        title="message: time vs. date",
        height=1800,
        margin=dict(l=80, r=20, t=60, b=10),
        xaxis=dict(
            title="Time of Day",
            tickmode='array',
            tickvals=[0, 6*3600, 12*3600, 18*3600, 24*3600],
            ticktext=["00:00", "06:00", "12:00", "18:00", "00:00"],
            range=[0,86400],
            position=0
        ),
        yaxis=dict(
            title="Date",
            autorange="reversed",
            tickmode='array',
            tickvals=yticks,
            ticktext=ytext,
            ticks="outside",
            tickfont=dict(size=10)
        )
    )

    # set graph to date range
    min_day = df['date'].min()
    max_day = df['date'].max()
    fig.update_yaxes(range=[max_day, min_day], autorange=False)

    #big year annotations
    for m in months:
        if m.month == 1:
            fig.add_annotation(
                xref="paper", x=-0.02,                # just to the left of the y‐axis
                y=m.date(),                            # at the first‐of‐Jan y‐position
                text=f"<b>{m.year}</b>",             # big year label
                showarrow=False,
                font=dict(size=16),
                xanchor="right",
                yanchor="middle"
            )

    st.plotly_chart(fig, use_container_width=True)

def process_null_data(df):
    df['text'] = df['text'].fillna('')


if __name__ == "__main__":

    #set up easy swtich between vivi and sudo
    options = ["vivi_chat.db", "sudo_chat.db"]
    selection = st.segmented_control("Database", options, selection_mode="single")
    if selection == "vivi_chat.db":
        conn = sqlite3.connect("vivi_chat.db")
    else:
        conn = sqlite3.connect("sudo_chat.db")

    query = """
    SELECT
        datetime(date/1000000000 + strftime('%s','2001-01-01'),'unixepoch') AS timestamp
    FROM message
    WHERE is_from_me = 1;
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    text_frequency(df)
