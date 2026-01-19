# sillydata

a streamlit dashboard for visualizing personal messaging data from discord and imessage.

## features

- **message frequency scatter plots** - interactive plots showing message timing (time of day vs date) across years of data
- **top contacts** - ranked list of most messaged people/channels
- **emoji analysis** - most-used emojis with counts
- **zipf word analysis** - compares your word usage to average english speakers using zipf's law, showing which words you overuse and your most common slang/made-up words
- **search & filtering** - filter by content, contact, channel type, message direction

## data sources

- **discord** - gdpr data export containing `Messages/` directory with json files
- **imessage** - sqlite database (chat.db) from macos

## how it works

messages are loaded and preprocessed with pandas, then visualized using plotly for the scatter plots and altair for bar charts. the zipf analysis uses the `wordfreq` library to compare your word frequencies against expected english frequencies. imessage attributed bodies (the binary format apple uses for rich text) are decoded using `pytypedstream`.

## setup

```bash
uv sync
streamlit run welcome.py
```

## tech stack

- python 3.13
- streamlit
- plotly
- pandas
- wordfreq
- pytypedstream
