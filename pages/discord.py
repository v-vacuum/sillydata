import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import os
import json
import altair as alt
import re

@st.cache_data
def text_frequency_processing(df):
    df['Timestamp'] = pd.to_datetime(df['Timestamp'], errors='coerce')
    df = df.dropna(subset=['Timestamp'])

    #change timezones!!(make sure is "timezone aware" or whatever)
    df['Timestamp'] = df['Timestamp'].dt.tz_localize('UTC')
    #now do your timezone!
    df['Timestamp'] = df['Timestamp'].dt.tz_convert('America/New_York')

    # seconds since midnight for x
    df['sec'] = (
        df['Timestamp'].dt.hour * 3600 +
        df['Timestamp'].dt.minute * 60 +
        df['Timestamp'].dt.second
    )

    # calendar date for y
    df['date'] = df['Timestamp'].dt.date
    df['time_str'] = df['Timestamp'].dt.strftime('%H:%M')  # for hover


    # monthly ticks on y
    months = pd.date_range(
        df['Timestamp'].min().normalize(),
        df['Timestamp'].max().normalize(),
        freq='MS'
    )

    yticks = months.date

    # for the axis, show only the 3‑letter month for non‑Jan, and blank for Jan
    ytext = [
        "" if m.month == 1 else m.strftime('%b')
        for m in months
    ]

    return df, yticks, ytext, months

def text_frequency_graph(df, top_five: list[str]) -> None:
    # Display the chart in Streamlit
    # if a top 5 user is chosen, filter

    options = ["All"] + top_five
    contact_filter = st.selectbox("Top Contacts", options, index=0)

    if contact_filter != "All":
        df = df[df['Channel'] == contact_filter]

    #channel type filter
    options = ['All', 'DM', 'GROUP_DM', 'GUILD_TEXT']
    contact_filter = st.selectbox("Channel Type", options, index=0)

    if contact_filter != "All":
        df = df[df['Channel Type'] == contact_filter]


    df, yticks, ytext, months = text_frequency_processing(df)


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
def read_data(database):
    #read and returns message_data with columns: Timestamp, Contents, Channel, Channel Type,
    # and channel_data with Channel and Message Count
    start_path = f"./{database}/Messages"
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

if __name__ == "__main__":

    #set up easy swtich between vivi and sudo
    options = ["vacuum", "sudolabel", "s2e3440z"]
    selection = st.segmented_control("Database", options, selection_mode="single", default=options[0])
    if selection == "vacuum":
        database = "package_vivi"
    elif selection == "sudolabel":
        database = "package_sudolabel"
    elif selection == "s2e3440z":
        database = "package_s2e3440z"
    else:
        database = "package_vivi"

    #read file, hardcoded as mine
    message_data, channel_data, emoji_count = read_data(database)
    #sort chanell data top users texted to least
    sorted_channel_data = sort_by_message_count(channel_data)

    #get top 5 users to pass to text frequency to sort
    top_five = list(sorted_channel_data.head(10)['Channel'])

    text_frequency_graph(message_data, top_five)
    top_users_graph(sorted_channel_data)
    top_emoji_graph(emoji_count)
