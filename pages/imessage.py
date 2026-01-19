import sqlite3
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from io import BytesIO
import typedstream
import os
import re
import altair as alt
from collections import Counter
from wordfreq import zipf_frequency, word_frequency

EMOJI_PATTERN = re.compile(u"(["
    u"\U0001F600-\U0001F64F"  # emoticons
    u"\U0001F300-\U0001F5FF"  # symbols & pictographs
    u"\U0001F680-\U0001F6FF"  # transport & map symbols
    u"\U0001F1E0-\U0001F1FF"  # flags (iOS)
"])", flags=re.UNICODE)

URL_PATTERN = re.compile(r'https?://\S+')
WORD_PATTERN = re.compile(r"[a-zA-Z']+")
ZIPF_THRESHOLD = 3.0


def extract_words(text: str) -> list[str]:
    if not text or not isinstance(text, str):
        return []
    text = URL_PATTERN.sub('', text)
    text = text.lower()
    words = WORD_PATTERN.findall(text)
    return [w for w in words if len(w) >= 2 and w != "s"]


def categorize_words(words: list[str]) -> tuple[Counter, Counter]:
    dictionary_words = Counter()
    non_dictionary_words = Counter()
    for word in words:
        zipf = zipf_frequency(word, 'en')
        if zipf >= ZIPF_THRESHOLD:
            dictionary_words[word] += 1
        else:
            non_dictionary_words[word] += 1
    return dictionary_words, non_dictionary_words


@st.cache_data
def compute_word_stats_alltime(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    all_words = []
    for content in df['message']:
        all_words.extend(extract_words(content))

    dict_words, non_dict_words = categorize_words(all_words)
    total_words = len(all_words) if all_words else 1

    dict_records = []
    for word, count in dict_words.items():
        expected_freq = word_frequency(word, 'en')
        user_freq = count / total_words
        if expected_freq > 0:
            times_more = user_freq / expected_freq
        else:
            times_more = 0
        dict_records.append({
            'word': word,
            'count': count,
            'times_more': times_more
        })

    non_dict_records = []
    for word, count in non_dict_words.items():
        non_dict_records.append({
            'word': word,
            'count': count
        })

    dict_df = pd.DataFrame(dict_records)
    non_dict_df = pd.DataFrame(non_dict_records)

    return dict_df, non_dict_df


@st.fragment
def zipf_word_analysis(df: pd.DataFrame) -> None:
    dict_df, non_dict_df = compute_word_stats_alltime(df)

    st.markdown("**Zipf-Recognized Words**")
    st.caption("These are common English words. The bar shows how many times more often you use each word compared to the average English speaker. A value of 100 means you use that word 100x more than average.")
    num_zipf = st.number_input("Words Displayed", value=10, min_value=1, max_value=50, key="imsg_zipf_words")
    if not dict_df.empty:
        top_dict = dict_df.nlargest(num_zipf, 'times_more')
        fig1 = go.Figure(go.Bar(
            x=top_dict['word'],
            y=top_dict['times_more'],
            hovertemplate="<b>%{x}</b><br>%{y:.1f}x more than average<br>Count: %{customdata}<extra></extra>",
            customdata=top_dict['count']
        ))
        fig1.update_layout(
            title=f"Top {num_zipf} Zipf-Recognized Words (All Time)",
            xaxis_title="Word",
            yaxis_title="Times More Than Average",
            height=400
        )
        st.plotly_chart(fig1, use_container_width=True)
    else:
        st.info("No Zipf-recognized words found")

    st.markdown("**Non-Zipf-Recognized Words**")
    st.caption("These are words not commonly found in English - typos, slang, acronyms, or made-up words.")
    num_non_zipf = st.number_input("Words Displayed", value=10, min_value=1, max_value=50, key="imsg_non_zipf_words")
    if not non_dict_df.empty:
        top_non_dict = non_dict_df.nlargest(num_non_zipf, 'count')
        fig2 = go.Figure(go.Bar(
            x=top_non_dict['word'],
            y=top_non_dict['count'],
            hovertemplate="<b>%{x}</b><br>Count: %{y}<extra></extra>"
        ))
        fig2.update_layout(
            title=f"Top {num_non_zipf} Non-Zipf-Recognized Words (All Time)",
            xaxis_title="Word",
            yaxis_title="Count",
            height=400
        )
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("No non-Zipf-recognized words found")

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

    # Load and process messages (cached)
    with st.spinner("Loading and decoding messages..."):
        raw_df, emoji_count = load_and_process_messages(selection)

    if raw_df is None or raw_df.empty:
        st.error("Failed to process messages or no messages found.")
        st.stop()

    # Preprocess timestamps once (cached separately from filters)
    df = preprocess_messages(raw_df)

    st.success(f"Loaded {len(df)} messages!")

    direction_options = ["Both", "Incoming", "Outgoing"]
    contact_counts_all = df['contact_id'].value_counts()
    top5 = contact_counts_all.head(5).index.tolist()
    contact_options = ["All"] + top5

    st.subheader("Top Contacts")
    contacts_dir = st.selectbox("Message Direction", direction_options, key="contacts_dir")
    if contacts_dir == "Incoming":
        contacts_df = df[df['is_from_me'] == 0]
    elif contacts_dir == "Outgoing":
        contacts_df = df[df['is_from_me'] == 1]
    else:
        contacts_df = df
    st.dataframe(contacts_df['contact_id'].value_counts().head(10))

    st.subheader("Message Frequency")
    col1, col2 = st.columns(2)
    with col1:
        freq_dir = st.selectbox("Message Direction", direction_options, key="freq_dir")
    with col2:
        freq_contact = st.selectbox("Filter by Contact (Top 5)", contact_options, key="freq_contact")
    if freq_dir == "Incoming":
        freq_df = df[df['is_from_me'] == 0]
    elif freq_dir == "Outgoing":
        freq_df = df[df['is_from_me'] == 1]
    else:
        freq_df = df
    if freq_contact != "All":
        freq_df = freq_df[freq_df['contact_id'] == freq_contact]
    text_frequency(freq_df, len(df))

    st.subheader("Word Analysis")
    col1, col2 = st.columns(2)
    with col1:
        zipf_dir = st.selectbox("Message Direction", direction_options, key="zipf_dir")
    with col2:
        zipf_contact = st.selectbox("Filter by Contact (Top 5)", contact_options, key="zipf_contact")
    if zipf_dir == "Incoming":
        zipf_df = df[df['is_from_me'] == 0]
    elif zipf_dir == "Outgoing":
        zipf_df = df[df['is_from_me'] == 1]
    else:
        zipf_df = df
    if zipf_contact != "All":
        zipf_df = zipf_df[zipf_df['contact_id'] == zipf_contact]
    zipf_word_analysis(zipf_df)

    st.subheader("Emoji Analysis")
    top_emoji_graph(emoji_count)
