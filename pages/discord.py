import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import os
import json
import altair as alt
import re
import zipfile
import shutil
from collections import Counter
from wordfreq import zipf_frequency, word_frequency
from config import (
    get_discord_sources,
    add_discord_source,
    remove_discord_source,
)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
DISCORD_UPLOAD_DIR = os.path.join(DATA_DIR, "discord")

URL_PATTERN = re.compile(r'https?://\S+')
MENTION_PATTERN = re.compile(r'<@!?\d+>')
CUSTOM_EMOJI_PATTERN = re.compile(r'<a?:\w+:\d+>')
WORD_PATTERN = re.compile(r"[a-zA-Z']+")


def extract_words(text: str) -> list[str]:
    if not text or not isinstance(text, str):
        return []
    text = URL_PATTERN.sub('', text)
    text = MENTION_PATTERN.sub('', text)
    text = CUSTOM_EMOJI_PATTERN.sub('', text)
    text = text.lower()
    words = WORD_PATTERN.findall(text)
    return [w for w in words if len(w) >= 2 and w != "s"]


ZIPF_THRESHOLD = 3.0

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
    for content in df['Contents']:
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
    num_zipf = st.number_input("Words Displayed", value=10, min_value=1, max_value=50, key="zipf_words")
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
    st.caption("These are words not commonly found in English - typos, slang, acronyms, usernames, or made-up words.")
    num_non_zipf = st.number_input("Words Displayed", value=10, min_value=1, max_value=50, key="non_zipf_words")
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


@st.cache_data
def preprocess_messages(df):
    """Cache-heavy preprocessing: timestamp parsing, timezone conversion, sec/date extraction."""
    df = df.copy()
    df['Timestamp'] = pd.to_datetime(df['Timestamp'], errors='coerce')
    df = df.dropna(subset=['Timestamp'])

    df['Timestamp'] = df['Timestamp'].dt.tz_localize('UTC')
    df['Timestamp'] = df['Timestamp'].dt.tz_convert('America/New_York')

    df['sec'] = (
        df['Timestamp'].dt.hour * 3600 +
        df['Timestamp'].dt.minute * 60 +
        df['Timestamp'].dt.second
    )
    df['date'] = df['Timestamp'].dt.date
    df['time_str'] = df['Timestamp'].dt.strftime('%H:%M')
    return df

def get_month_ticks(df):
    """Generate monthly tick positions and labels for y-axis."""
    months = pd.date_range(
        df['Timestamp'].min().normalize(),
        df['Timestamp'].max().normalize(),
        freq='MS'
    )
    yticks = months.date
    ytext = [
        "" if m.month == 1 else m.strftime('%b')
        for m in months
    ]
    return yticks, ytext, months

def text_frequency_graph(df, total_count: int) -> None:
    search_query = st.text_input("Search messages", placeholder="Filter by message content...")

    if search_query:
        df = df[df['Contents'].str.contains(search_query, case=False, na=False)]

    yticks, ytext, months = get_month_ticks(df)

    if len(df) != total_count:
        st.caption(f"Showing {len(df)} of {total_count} messages")


    fig = go.Figure(go.Scattergl(
        x    = df['sec'],
        y    = df['date'],
        mode = 'markers',
        marker=dict(size=2.5, opacity=0.3),
        customdata=df[['time_str', 'Contents', 'Channel']].values,
        hovertemplate="Time: %{customdata[0]}<br>Date: %{y}<extra></extra><br>Channel: %{customdata[2]}<br>Message: %{customdata[1]}"
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


@st.cache_data
def sort_by_message_count(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(by='Message Count', ascending=False)
    return df

@st.fragment
def top_users_graph(df: pd.DataFrame):
    #creates a chart of the top users texted, bar graph with # of texts
    st.text("Top Users Messaged")
    #have a filter for the number of users they want to see
    filter = st.number_input(
        "Users Displayed", value=20, placeholder="Type a number..."
    )

    top = df.head(filter)
    st.write(alt.Chart(top).mark_bar().encode(
        x=alt.X('Channel', sort=None),
        y='Message Count',
    ))

@st.fragment
def top_emoji_graph(emoji_count: dict):
    #creates a chart of the top emojis used, bar graph with # of uses
    st.text("Top Emojis Used")
    #have a filter for the number of emojis they want to see
    filter = st.number_input(
        "Emojis Displayed", value=10, placeholder="Type a number..."
    )

    #get top emojis used... sigh
    # maybe just change dict into pd.DataFrame
    emoji_df = pd.DataFrame.from_dict(emoji_count, orient = 'index')
    emoji_df.columns = ['Count']
    emoji_df.index.name = 'Emoji'
    emoji_df.reset_index(inplace=True)
    st.write(alt.Chart(emoji_df.head(filter)).mark_bar().encode(
        x=alt.X('Emoji', sort='-y', axis=alt.Axis(labelAngle = 0)),
        y='Count',
    ).configure_axis(
        labelFontSize=20,
        titleFontSize=10
    ))


@st.cache_data
def read_data(base_path: str):
    """Read Discord data export.

    Args:
        base_path: Path to the Discord data export directory (contains messages/ subdirectory)
    """
    messages_subdir = os.path.join(base_path, "messages")
    if os.path.isdir(messages_subdir):
        start_path = messages_subdir
    else:
        start_path = base_path
    message_data = pd.DataFrame()
    channel_data = pd.DataFrame()

    #for counting emojis
    emoji_count = {}
    emoji_pattern = re.compile(u"(["
    u"\U0001F600-\U0001F64F"  # emoticons
    u"\U0001F300-\U0001F5FF"  # symbols & pictographs
    u"\U0001F680-\U0001F6FF"  # transport & map symbols
    u"\U0001F1E0-\U0001F1FF"  # flags (iOS)
                    "])", flags= re.UNICODE)


    with open(os.path.join(start_path, 'index.json'), 'r') as f:
        index = json.load(f) #this is index.json how did you forget bro

    for root, dirs, files in os.walk(start_path):
        if 'messages.json' in files and 'channel.json' in files:
            with open(os.path.join(root, 'messages.json'), 'r') as f:
                messages = json.load(f)
                init_messages = pd.DataFrame(messages)

                if len(init_messages) == 0:
                    continue
                #keep only Timestamp and content
                init_messages = init_messages[['Timestamp', 'Contents']]

                #get emojis in contents if there is one, and add to dict
                for message in init_messages['Contents']:
                    emojis = emoji_pattern.findall(message)
                    for emoji in emojis:
                        if emoji in emoji_count:
                            emoji_count[emoji] += 1
                        else:
                            emoji_count[emoji] = 1
                #count number of messages and create new data frame
                # that will rank top texted users
                message_count = init_messages.shape[0]

            with open(os.path.join(root, 'channel.json'), 'r') as f:
                channel = json.load(f)
                channel_type = channel['type']
                # get name of channel
                channel_id = channel['id']
                #index the channel id to get name of channel
                channel_name = index[channel_id]

                #process channel name if is DM
                if channel_name.startswith('Direct Message with '):
                    channel_name = channel_name.split('Direct Message with ')[1]
                if channel_name.endswith('#0'):
                    channel_name = channel_name.split('#0')[0]

                #append channel data to channel_data dataframe
                if channel_name != 'Unknown channel' and channel_name != 'None':
                    df = pd.DataFrame({'Channel': [channel_name], 'Message Count': [message_count]})
                    channel_data = pd.concat([channel_data, df])

                    #add channel name to all entries of current iteration
                    init_messages['Channel'] = channel_name
                    init_messages['Channel Type'] = channel_type
                    #concat to message_data dataframe
                    message_data = pd.concat([message_data, init_messages])

    return message_data, channel_data, emoji_count

def render_add_source_form():
    """Render the form for adding a new Discord data source."""
    with st.expander("Add New Data Source", expanded=False):
        st.caption("Upload your Discord data export zip file, or enter a folder path.")

        uploaded_file = st.file_uploader(
            "Upload Discord data zip",
            type=["zip"],
            key="discord_uploader",
            help="The zip file you downloaded from Discord"
        )

        if uploaded_file is not None:
            name = st.text_input("Name for this source", value="My Discord", key="discord_upload_name")
            if st.button("Extract and Add", key="add_uploaded_discord"):
                if not name:
                    st.error("Please enter a name.")
                else:
                    os.makedirs(DISCORD_UPLOAD_DIR, exist_ok=True)
                    extract_dir = os.path.join(DISCORD_UPLOAD_DIR, name.replace(' ', '_'))

                    if os.path.exists(extract_dir):
                        shutil.rmtree(extract_dir)

                    with st.spinner("Extracting zip file..."):
                        with zipfile.ZipFile(uploaded_file, 'r') as zip_ref:
                            zip_ref.extractall(extract_dir)

                    messages_path = os.path.join(extract_dir, "messages")
                    if not os.path.isdir(messages_path):
                        subdirs = [d for d in os.listdir(extract_dir) if os.path.isdir(os.path.join(extract_dir, d))]
                        if len(subdirs) == 1:
                            inner_dir = os.path.join(extract_dir, subdirs[0])
                            if os.path.isdir(os.path.join(inner_dir, "messages")):
                                extract_dir = inner_dir

                    messages_path = os.path.join(extract_dir, "messages")
                    if os.path.isdir(messages_path):
                        add_discord_source(name, extract_dir)
                        st.success(f"Added '{name}'!")
                        st.rerun()
                    else:
                        st.error("Zip doesn't contain a valid Discord export (no 'messages' folder found).")

        st.markdown("---")
        st.caption("Or enter a folder path:")
        name_path = st.text_input("Name", value="My Discord", key="discord_name_input")
        path = st.text_input(
            "Path",
            value="~/Downloads/package",
            key="discord_path_input",
            help="Drag the folder into Terminal to get its path"
        )

        if st.button("Add Path", key="add_discord_btn"):
            if not name_path:
                st.error("Please enter a name.")
            elif not path:
                st.error("Please enter a path.")
            else:
                expanded = os.path.expanduser(path)
                messages_path = os.path.join(expanded, "messages")
                is_valid = os.path.isdir(messages_path) or (
                    os.path.isdir(expanded) and
                    os.path.exists(os.path.join(expanded, "index.json"))
                )

                if is_valid:
                    add_discord_source(name_path, path)
                    st.success(f"Added '{name_path}'!")
                    st.rerun()
                elif os.path.isdir(expanded):
                    st.error("Folder exists but doesn't look like a Discord export. Expected a 'messages' subdirectory.")
                else:
                    st.error(f"Folder not found: {expanded}")


def render_manage_sources(sources):
    """Render the source management UI."""
    with st.expander("Manage Data Sources"):
        for i, source in enumerate(sources):
            col1, col2 = st.columns([3, 1])
            with col1:
                status = "found" if source.exists() else "not found"
                st.text(f"{source.name}: {source.path} ({status})")
            with col2:
                if st.button("Remove", key=f"remove_discord_{i}_{source.name}"):
                    remove_discord_source(source.name)
                    st.rerun()


if __name__ == "__main__":
    st.title("Discord Analysis Tool")

    sources = get_discord_sources()

    if not sources:
        st.info("No data sources configured. Add one below to get started.")
        render_add_source_form()
        st.stop()

    valid_sources = [s for s in sources if s.exists()]

    if not valid_sources:
        st.warning("No valid data sources found. Please check your paths or add a new source.")
        render_add_source_form()
        render_manage_sources(sources)
        st.stop()

    source_names = [s.name for s in valid_sources]
    selection = st.segmented_control("Database", source_names, selection_mode="single")

    render_add_source_form()
    render_manage_sources(sources)

    if selection is None:
        st.info("Please select a database to analyze.")
        st.stop()

    selected_source = next((s for s in valid_sources if s.name == selection), None)
    if not selected_source:
        st.error("Selected source not found.")
        st.stop()

    data_path = selected_source.get_expanded_path()

    raw_message_data, channel_data, emoji_count = read_data(data_path)

    df = preprocess_messages(raw_message_data)
    total_count = len(df)

    sorted_channel_data = sort_by_message_count(channel_data)
    top_ten = list(sorted_channel_data.head(10)['Channel'])

    channel_options = ["All"] + top_ten
    channel_filter = st.selectbox("Top Contacts", channel_options, index=0)

    type_options = ['All', 'DM', 'GROUP_DM', 'GUILD_TEXT']
    type_filter = st.selectbox("Channel Type", type_options, index=0)

    filtered_df = df

    if channel_filter != "All":
        filtered_df = filtered_df[filtered_df['Channel'] == channel_filter]

    if type_filter != "All":
        filtered_df = filtered_df[filtered_df['Channel Type'] == type_filter]

    text_frequency_graph(filtered_df, total_count)
    top_users_graph(sorted_channel_data)
    top_emoji_graph(emoji_count)
    zipf_word_analysis(raw_message_data)
