import sqlite3
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from typedstream import unarchive_from_data

def text_frequency(df, single_contact):
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
    df = df.dropna(subset=['timestamp'])

    #if selects to filter by a top 5 contact
    if single_contact != "All":
        df = df[df['contact_id'] == single_contact]

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

def get_decoded_hex(blob):
    data = bytes.fromhex(blob)
    arch = unarchive_from_data(data)
    from typedstream.archiving import TypedValue

    plain = None
    for item in arch.contents:
        if isinstance(item, TypedValue) and hasattr(item, "value") and isinstance(item.value, str):
            plain = item.value
    return plain

if __name__ == "__main__":

    #set up easy swtich between vivi and sudo
    options = ["vivi_chat.db", "sudo_chat.db"]
    selection = st.segmented_control("Database", options, selection_mode="single")
    if selection == "vivi_chat.db":
        conn = sqlite3.connect("vivi_chat.db")
    else:
        conn = sqlite3.connect("sudo_chat.db")

    #incoming/outgoing
    options = ["incoming", "outgoing"]
    selection = st.segmented_control("(Both by default)", options)

    query = """
    SELECT
        datetime(m.date/1000000000 + strftime('%s','2001-01-01'),'unixepoch', 'localtime') AS timestamp,
        m.is_from_me AS is_from_me,
        m.text AS text,
        m.attributedBody AS attributed_body,
        h.id AS contact_id
    FROM message AS m
    LEFT JOIN handle AS h
        ON m.handle_id = h.ROWID
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    #get top 5 contacts
    cid_series: pd.Series = pd.Series(df["contact_id"])
    top5 = cid_series.value_counts().head(5).index.tolist()
    #selecting between different contacts
    options = ["All"] + top5
    contact_filter = st.selectbox("Top 5 Contacts", options, index=0)

    if selection == "incoming":
        df = df[df['is_from_me'] == 0]
    elif selection == "outgoing":
        df = df[df['is_from_me'] == 1]

    text_frequency(df, contact_filter)
