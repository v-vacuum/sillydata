# sillydata

a streamlit dashboard for visualizing personal messaging data from discord and imessage.

<img width="794" height="658" alt="messare time vs  date" src="https://github.com/user-attachments/assets/0467d7e9-5db2-46e1-95af-40f8b95fc499" />
<img width="822" height="874" alt="image" src="https://github.com/user-attachments/assets/526be4b5-027b-44cc-8b0a-fe2cc412df55" />

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

### adding your data

**imessage (macos):**
1. go to the imessage page in the sidebar
2. click "Add New Data Source"
3. either use the default path button or enter `~/Library/Messages/chat.db`
4. you may need to grant terminal/your IDE full disk access in System Preferences > Privacy & Security

**discord:**
1. request your data from discord: Settings > Privacy & Safety > Request All of My Data
2. wait for the email (can take up to 30 days)
3. extract the zip file
4. go to the discord page and add the extracted folder path

your data sources are stored in `sillydata_config.json` (gitignored). see `sillydata_config.example.json` for the format.

## tech stack

- python 3.13
- streamlit
- plotly
- pandas
- wordfreq
- pytypedstream
