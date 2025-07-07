import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import os
import json

def text_frequency(df):
    # Display the chart in Streamlit

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
    df = df.sort_values('date')

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

def read_data():
    start_path = "./package/Messages"

    #get user id so that we can find the other user in chat with us
    user_data_path = "./package/Account/user.json"
    user_id = json.load(open(user_data_path))['id']

    message_data = pd.DataFrame()
    channel_data = pd.DataFrame()

    for root, dirs, files in os.walk(start_path):
        if files[0] == 'index.json':
            with open(os.path.join(root, files[0]), 'r') as f:
                index = json.load(f)
        if 'messages.json' in files and 'channel.json' in files:
            with open(os.path.join(root, 'messages.json'), 'r') as f:
                messages = json.load(f)
                df = pd.DataFrame(messages)
                if len(df) == 0:
                    continue
                #keep only Timestamp and content
                df = df[['Timestamp', 'Contents']]
                message_data = pd.concat([message_data, df])

                #count number of messages and create new data frame
                # that will rank top texted users
                message_count = df.shape[0]
            #TODO: add channel data
            # with open(os.path.join(root, 'channel.json'), 'r') as f:
            #     channel = json.load(f)
            #     #...?
            #     if channel['type'] == 'DM' and channel['recipients'] is not None :
            #         recipient = channel['recipients']
            #     elif channel['type'] == 'GROUP_DM' and channel['recipients'] is not None:
            #         name = channel['name'] if 'name' in channel and channel['name'] is not None else "defaultname"
            #         recipient = channel['recipients']
            #         #TODO: make it not stupid (instead of default name have groupdm with :user user user suer)
            #     elif channel['type'] == 'GUILD_TEXT' :
            #         recipient = channel['guild']['name'] + ' : ' + channel['name']

            #    df = pd.DataFrame(channel)
    return message_data

if __name__ == "__main__":
    #read file, hardcoded as mine
    df = read_data()
    text_frequency(df)
