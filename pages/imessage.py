import sqlite3
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from io import BytesIO
import typedstream
import os

def decode_attributed_body(body):
    """Decode binary attributed body using Python"""
    if not body or not isinstance(body, bytes):
        return None
    try:
        stream = BytesIO(body)
        ts_stream = typedstream.unarchive_from_stream(stream)
        decoded = ts_stream.decode()
        if isinstance(decoded, typedstream.Value):
            if isinstance(decoded.value, str):
                return decoded.value
            elif isinstance(decoded.value, dict):
                if 'NS.string' in decoded.value:
                    return decoded.value['NS.string']
            elif isinstance(decoded.value, list):
                for item in decoded.value:
                    if isinstance(item, str):
                        return item
                    elif isinstance(item, dict) and 'NS.string' in item:
                        return item['NS.string']
        return None
    except Exception as e:
        return None

@st.cache_data
def load_and_process_messages(db_path):
    """Load messages from SQLite database and decode text"""
    conn = sqlite3.connect(db_path)

    query = """
    SELECT
        datetime(m.date/1000000000 + strftime('%s','2001-01-01'),'unixepoch', 'localtime') AS timestamp,
        m.is_from_me AS is_from_me,
        m.text AS text,
        m.attributedBody AS attributedBody,
        h.id AS contact_id
    FROM message AS m
    LEFT JOIN handle AS h
        ON m.handle_id = h.ROWID
    ORDER BY m.date
    """

    df = pd.read_sql_query(query, conn)
    conn.close()

    # decode attributed bodies
    info_placeholder = st.empty()
    progress_placeholder = st.empty()
    info_placeholder.info("Decoding message text (this may take a moment)...")
    progress_bar = progress_placeholder.progress(0)

    decoded_messages = []
    total = len(df)

    for i, row in df.iterrows():
        # try attributedBody first, then fall back to text
        message_text = None

        if row['attributedBody']:
            message_text = decode_attributed_body(row['attributedBody'])

        if not message_text and row['text']:
            message_text = row['text']

        decoded_messages.append(message_text or '')

        # update progress every 100 rows
        if i % 100 == 0 or i == total - 1:
            progress_bar.progress((i + 1) / total)

    df['message'] = decoded_messages

    # clean columns
    df = df[['timestamp', 'is_from_me', 'message', 'contact_id']]
    info_placeholder.empty()
    progress_placeholder.empty()

    return df

@st.cache_data
def preprocess_messages(df):
    """Cache-heavy preprocessing: timestamp parsing, sec/date extraction."""
    df = df.copy()
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
    df = df.dropna(subset=['timestamp'])

    df['sec'] = (
        df['timestamp'].dt.hour * 3600 +
        df['timestamp'].dt.minute * 60 +
        df['timestamp'].dt.second
    )
    df['date'] = df['timestamp'].dt.date
    df['time_str'] = df['timestamp'].dt.strftime('%H:%M')
    df = df.sort_values('date')
    return df

def get_month_ticks(df):
    """Generate monthly tick positions and labels for y-axis."""
    months = pd.date_range(
        df['timestamp'].min().normalize(),
        df['timestamp'].max().normalize(),
        freq='MS'
    )
    yticks = months.date
    ytext = [
        "" if m.month == 1 else m.strftime('%b')
        for m in months
    ]
    return yticks, ytext, months

def text_frequency(df, total_count: int):
    search_query = st.text_input("Search messages", placeholder="Filter by message content...")

    if search_query:
        df = df[df['message'].str.contains(search_query, case=False, na=False)]

    if len(df) != total_count:
        st.caption(f"Showing {len(df)} of {total_count} messages")

    yticks, ytext, months = get_month_ticks(df)

    fig = go.Figure(go.Scattergl(
        x    = df['sec'],
        y    = df['date'],
        mode = 'markers',
        marker=dict(size=2.5, opacity=0.3),
        customdata=df[['time_str', 'message']].values,
        hovertemplate="Time: %{customdata[0]}<br>Date: %{y}<extra></extra><br>Message: %{customdata[1]}"
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

    # big year annotations
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

if __name__ == "__main__":
    st.title("iMessage Analysis Tool")

    # Database selection
    options = ["vivi_chat.db", "sudo_chat.db"]
    selection = st.segmented_control("Database", options, selection_mode="single")

    if selection is None:
        st.info("Please select a database to analyze.")
        st.stop()

    if not os.path.exists(selection):
        st.error(f"Database file '{selection}' not found!")
        st.stop()

    # Load and process messages (cached)
    with st.spinner("Loading and decoding messages..."):
        raw_df = load_and_process_messages(selection)

    if raw_df is None or raw_df.empty:
        st.error("Failed to process messages or no messages found.")
        st.stop()

    # Preprocess timestamps once (cached separately from filters)
    df = preprocess_messages(raw_df)

    st.success(f"Loaded {len(df)} messages!")

    # Message direction filter
    direction_options = ["Both", "Incoming", "Outgoing"]
    direction_filter = st.selectbox("Message Direction", direction_options)

    # Get top 5 contacts from full dataset
    contact_counts = df['contact_id'].value_counts()
    top5 = contact_counts.head(5).index.tolist()

    # Contact filter
    contact_options = ["All"] + top5
    contact_filter = st.selectbox("Filter by Contact (Top 5)", contact_options)

    # Apply filters (fast operations on preprocessed data)
    filtered_df = df.copy()

    if direction_filter == "Incoming":
        filtered_df = filtered_df[filtered_df['is_from_me'] == 0]
    elif direction_filter == "Outgoing":
        filtered_df = filtered_df[filtered_df['is_from_me'] == 1]

    if contact_filter != "All":
        filtered_df = filtered_df[filtered_df['contact_id'] == contact_filter]

    # Show contact stats
    st.subheader("Top Contacts")
    st.dataframe(contact_counts.head(10))

    # Generate visualization (search bar is inside this function)
    text_frequency(filtered_df, len(df))
