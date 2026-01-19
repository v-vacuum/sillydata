import sqlite3
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from io import BytesIO
import typedstream
import os
import re
import altair as alt

EMOJI_PATTERN = re.compile(u"(["
    u"\U0001F600-\U0001F64F"  # emoticons
    u"\U0001F300-\U0001F5FF"  # symbols & pictographs
    u"\U0001F680-\U0001F6FF"  # transport & map symbols
    u"\U0001F1E0-\U0001F1FF"  # flags (iOS)
"])", flags=re.UNICODE)

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
    emoji_count = {}

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

        # count emojis in this message
        if message_text:
            emojis = EMOJI_PATTERN.findall(message_text)
            for emoji in emojis:
                if emoji in emoji_count:
                    emoji_count[emoji] += 1
                else:
                    emoji_count[emoji] = 1

        # update progress every 100 rows
        if i % 100 == 0 or i == total - 1:
            progress_bar.progress((i + 1) / total)

    df['message'] = decoded_messages

    # clean columns
    df = df[['timestamp', 'is_from_me', 'message', 'contact_id']]
    info_placeholder.empty()
    progress_placeholder.empty()

    return df, emoji_count

@st.cache_data
def text_frequency_processing(df, single_contact):
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
    df = df.dropna(subset=['timestamp'])

    # if selects to filter by a top 5 contact
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
    return df, yticks, ytext, months

def text_frequency(df, single_contact):
    df, yticks, ytext, months = text_frequency_processing(df, single_contact)

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

@st.fragment
def top_emoji_graph(emoji_count: dict):
    st.text("Top Emojis Used")

    if not emoji_count:
        st.info("No emojis found in messages.")
        return

    filter = st.number_input(
        "Emojis Displayed", value=10, placeholder="Type a number..."
    )

    emoji_df = pd.DataFrame.from_dict(emoji_count, orient='index')
    emoji_df.columns = ['Count']
    emoji_df.index.name = 'Emoji'
    emoji_df.reset_index(inplace=True)
    emoji_df = emoji_df.sort_values('Count', ascending=False)
    st.write(alt.Chart(emoji_df.head(filter)).mark_bar().encode(
        x=alt.X('Emoji', sort='-y', axis=alt.Axis(labelAngle=0)),
        y='Count',
    ).configure_axis(
        labelFontSize=20,
        titleFontSize=10
    ))

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

    # Load and process messages
    with st.spinner("Loading and decoding messages..."):
        df, emoji_count = load_and_process_messages(selection)

    if df is None or df.empty:
        st.error("Failed to process messages or no messages found.")
        st.stop()

    st.success(f"Loaded {len(df)} messages!")

    # Message direction filter
    direction_options = ["Both", "Incoming", "Outgoing"]
    direction_filter = st.selectbox("Message Direction", direction_options)

    if direction_filter == "Incoming":
        df = df[df['is_from_me'] == 0]
    elif direction_filter == "Outgoing":
        df = df[df['is_from_me'] == 1]

    # Get top 5 contacts
    contact_counts = df['contact_id'].value_counts()
    top5 = contact_counts.head(5).index.tolist()

    # Contact filter
    contact_options = ["All"] + top5
    contact_filter = st.selectbox("Filter by Contact (Top 5)", contact_options)

    # Show contact stats
    st.subheader("Top Contacts")
    st.dataframe(contact_counts.head(10))

    # Generate visualization
    text_frequency(df, contact_filter)

    # Show top emojis
    top_emoji_graph(emoji_count)
