import streamlit as st

from src.agent import ask
from src.config import CITATION

st.set_page_config(
    page_title="InfoHub RAG Agent",
    page_icon="📚",
    layout="centered",
)


def _show_result_details(result: dict):
    """Display timing and source details for a result."""
    # Timing
    st.caption(
        f"⏱ ძიება: {result['search_time']}s | "
        f"LLM: {result['llm_time']}s | "
        f"სულ: {result['total_time']}s"
    )

    # Sources
    if result.get("docs"):
        with st.expander(f"📄 წყაროები ({len(result['docs'])} დოკუმენტი, სულ API-ში: {result['total_api_results']})"):
            for doc in result["docs"]:
                score_pct = int(doc.get("relevance_score", 0) * 100)
                header = f"**{doc['name']}**"
                meta = f"ტიპი: {doc.get('type', '—')} | რელევანტურობა: {score_pct}%"
                link = f"[🔗 ბმული]({doc['url']})" if doc.get("url") else ""
                st.markdown(f"{header}  \n{meta}  \n{link}")
                if doc.get("description"):
                    st.caption(doc["description"][:200] + "...")
                st.divider()


# Sidebar
with st.sidebar:
    st.title("📚 InfoHub RAG Agent")
    st.markdown("""
    **საგადასახადო და საბაჟო ინფორმაციის ასისტენტი**

    ეს აპლიკაცია პასუხობს თქვენს შეკითხვებს
    საგადასახადო და საბაჟო ადმინისტრირების შესახებ,
    [infohub.rs.ge](https://infohub.rs.ge/ka)-ზე
    განთავსებული დოკუმენტების საფუძველზე.

    ---
    **როგორ მუშაობს:**
    1. თქვენი შეკითხვა იძებნება დოკუმენტებში
    2. შედეგები რანჟირდება რელევანტურობით
    3. საუკეთესო დოკუმენტები ეგზავნება AI მოდელს
    4. AI აგენერირებს პასუხს წყაროს მითითებით
    """)
    st.markdown("---")
    st.caption("წყარო: infohub.rs.ge/ka")

# Main chat area
st.title("საგადასახადო/საბაჟო ასისტენტი")

# Initialize state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending_question" not in st.session_state:
    st.session_state.pending_question = None

# Example question buttons for first-time users
if not st.session_state.messages and st.session_state.pending_question is None:
    st.markdown("**სცადეთ ერთ-ერთი მაგალითი:**")
    examples = [
        "რა არის დღგ?",
        "საშემოსავლო გადასახადის განაკვეთი",
        "იმპორტის საბაჟო პროცედურები",
        "საგადასახადო დავის გასაჩივრება",
    ]
    cols = st.columns(len(examples))
    for col, example in zip(cols, examples):
        if col.button(example, use_container_width=True):
            st.session_state.pending_question = example
            st.rerun()

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message["role"] == "assistant" and "result" in message:
            _show_result_details(message["result"])

# Chat input (from text box or from example button)
prompt = st.chat_input("დასვით შეკითხვა...")
if st.session_state.pending_question:
    prompt = st.session_state.pending_question
    st.session_state.pending_question = None

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        # Pipeline status steps
        status = st.status("პასუხის მომზადება...", expanded=True)
        status.write("🔍 დოკუმენტების ძიება...")

        result = ask(prompt)

        if result["docs"]:
            status.write(f"📄 ნაპოვნია {len(result['docs'])} დოკუმენტი (სულ: {result['total_api_results']})")
            status.write("🤖 პასუხის გენერაცია...")
        status.update(label="დასრულებულია!", state="complete", expanded=False)

        st.markdown(result["answer"])
        _show_result_details(result)

    st.session_state.messages.append({
        "role": "assistant",
        "content": result["answer"],
        "result": result,
    })
