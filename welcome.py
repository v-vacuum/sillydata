import streamlit as st

st.set_page_config(
    page_title="sillydata",
    page_icon="📊",
)

st.write("# sillydata")

st.sidebar.success("pick something from the sidebar")

st.markdown(
    """
    analytics for your texting habits

    **what's here:**
    - **imessage** - when you text, who you text, what words you overuse, top emojis
    - **discord** - same thing but for discord dms and servers

    ---

    ### getting started

    **imessage:**
    1. go to the imessage page in the sidebar
    2. click "Add New Data Source" and either:
       - click "Use Default iMessage Path" if you're on macOS
       - or enter a custom path to your `chat.db` file

    note: on macOS, the iMessage database is at `~/Library/Messages/chat.db`.
    you may need to grant Terminal/your IDE full disk access in System Preferences > Privacy & Security.

    **discord:**
    1. request your data from Discord: Settings > Privacy & Safety > Request All of My Data
    2. wait for the email with your download link (can take up to 30 days)
    3. extract the zip file
    4. go to the discord page and add the extracted folder path

    ---

    **some fun things to look at:**
    - the time vs date scatter plot shows your sleep schedule pretty clearly
    - zipf analysis shows which words you use way more than normal people
    - non-dictionary words = your typos, slang, and internet speak
"""
)
