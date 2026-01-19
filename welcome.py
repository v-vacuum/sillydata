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
    - **facetime** - tbd

    **getting started:**
    - for imessage, you'll need your `chat.db` file (find it in `~/Library/Messages/`)
    - for discord, request your data package from discord's privacy settings

    **some fun things to look at:**
    - the time vs date scatter plot shows your sleep schedule pretty clearly
    - zipf analysis shows which words you use way more than normal people
    - non-dictionary words = your typos, slang, and internet speak
"""
)
