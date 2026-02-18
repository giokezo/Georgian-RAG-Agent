# Georgian RAG Agent

A Retrieval-Augmented Generation agent that answers questions about Georgian tax and customs law. It searches [infohub.rs.ge](https://infohub.rs.ge/ka) — the Georgian Revenue Service's document hub — retrieves relevant documents, scores and reranks them locally, and generates answers via an LLM. The agent responds in Georgian and can also handle general conversation while nudging users toward its core expertise.

## How it works

```
User question
     │
     ▼
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Query       │────▶│  InfoHub API      │────▶│  Relevance       │
│  Cleaning &  │     │  (fetch 10 docs)  │     │  Scoring &       │
│  Expansion   │     └──────────────────┘     │  Reranking       │
└─────────────┘                               │  (return top 5)  │
                                              └────────┬────────┘
                                                       │
                                                       ▼
                                              ┌─────────────────┐
                                              │  Token Budget    │
                                              │  Manager         │
                                              │  (max 3000 chars)│
                                              └────────┬────────┘
                                                       │
                                                       ▼
                                              ┌─────────────────┐
                                              │  Groq LLM       │
                                              │  (llama-3.3-70b)│
                                              │  + retry logic   │
                                              └────────┬────────┘
                                                       │
                                                       ▼
                                              Structured response
                                              with sources & timing
```

### Pipeline steps

1. **Query cleaning** — strips Georgian and English filler/stop words ("რა არის", "what is") to extract meaningful search terms
2. **Query expansion** — if the query contains a known abbreviation (e.g. "დღგ"), it expands it to the full term ("დამატებული ღირებულების გადასახადი") and searches both variants, merging results
3. **API search** — fetches up to 10 documents from the InfoHub search API
4. **Relevance scoring** — each document is scored (0.0–1.0) using keyword overlap between the query and the document's name + description, with a bonus weight for title matches
5. **Reranking** — documents are sorted by score, top 5 returned
6. **Token budget** — documents are packed into the LLM context greedily by relevance until a 3000-character budget is filled (~2000 tokens), staying safely under Groq's 12K TPM free-tier limit
7. **LLM generation** — the context + question are sent to Groq with retry logic (413 → reduce context, 429 → exponential backoff)
8. **Structured response** — returns the answer, source documents with scores, and timing breakdown

## Project structure

```
Georgian-RAG-Agent/
├── app.py                 # Streamlit UI — the single entry point
├── src/
│   ├── __init__.py
│   ├── config.py          # All constants: API URLs, model, abbreviations, budget
│   ├── retriever.py       # Search, scoring, reranking, query expansion
│   └── agent.py           # LLM orchestration, token budget, retry, timing
├── requirements.txt
├── .env                   # GROQ_API_KEY (not committed)
└── .gitignore
```

### `src/config.py`

Central configuration. All tunable parameters live here:

- **`SEARCH_TOP_K = 10`** — how many documents to fetch from the API
- **`RERANK_TOP_K = 5`** — how many to keep after local reranking
- **`MAX_CONTEXT_CHARS = 3000`** — character budget for LLM context (~2000 tokens)
- **`ABBREVIATIONS`** — map of 13 common Georgian tax abbreviations to their full forms, used for query expansion and relevance scoring
- **`GROQ_MODEL`** — `llama-3.3-70b-versatile` (Groq free tier)

### `src/retriever.py`

Handles everything between the user's question and a ranked list of documents:

- **`_clean_query()`** — removes stop words in Georgian and English
- **`_expand_query()`** — generates query variants from abbreviation mappings
- **`_score_relevance()`** — keyword overlap scoring with title bonus
- **`_search_api()`** — calls the InfoHub REST API
- **`retrieve()`** — orchestrates the full search → expand → score → rerank pipeline

### `src/agent.py`

Orchestrates the RAG pipeline:

- **`build_context()`** — packs documents into a context string within the character budget
- **`_chat_with_retry()`** — sends to Groq with automatic handling for 413 (payload too large → drops documents and retries) and 429 (rate limit → exponential backoff), max 2 retries each
- **`ask()`** — the main entry point. Returns a structured dict with the answer, source documents (with relevance scores), and timing breakdown (search_time, llm_time, total_time). If no documents are found (general question or no results), the LLM answers from its own knowledge and reminds the user of its tax/customs specialty

### `app.py`

Streamlit chat interface:

- Example question buttons for first-time users
- Real-time pipeline status indicator (searching → found N docs → generating → done)
- Expandable sources panel showing each document's name, type, relevance percentage, description preview, and clickable link to the original on infohub.rs.ge
- Response timing display
- Full chat history with source details preserved across messages

## Design choices

**Why keyword overlap instead of embeddings for reranking?**
Keeps the project dependency-free from vector databases and embedding models. Georgian is a morphologically rich language where simple keyword matching on the API's own search results works well enough for a reranking signal. The API already does the heavy lifting on search — we just need to sort what it returns.

**Why a character budget instead of token counting?**
Groq's free tier has a 12K tokens-per-minute limit. Counting exact tokens requires a tokenizer dependency. A 3000-character cap (~2000 tokens) is a simple, conservative approximation that keeps the full request (system prompt + context + question) well under the limit without any extra libraries.

**Why retry with context reduction on 413?**
When the LLM rejects a payload as too large, automatically dropping the lowest-ranked document and retrying is more graceful than failing outright. Since documents are already sorted by relevance, we always drop the least relevant one first.

**Why does the agent answer general questions?**
A hard "I can only answer tax questions" wall is a bad user experience. The agent answers anything but gently steers users back to its specialty, which feels more natural.

## Setup and running

### Prerequisites

- Python 3.11+
- A free Groq API key from [console.groq.com/keys](https://console.groq.com/keys)

### Installation

```bash
git clone https://github.com/giokezo/Georgian-RAG-Agent.git
cd Georgian-RAG-Agent
pip install -r requirements.txt
```

### Configuration

Create a `.env` file in the project root:

```
GROQ_API_KEY=your_groq_api_key_here
```

### Running

```bash
streamlit run app.py
```

The app will open at `http://localhost:8501`. Type a question in Georgian or click one of the example buttons to get started.

## Deployment (Streamlit Community Cloud)

You can deploy a live demo with a shareable URL for free:

1. Push the repo to GitHub (make sure `.env` is gitignored — it already is)
2. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub
3. Click **New app** → select the repo, branch (`main`), and main file (`app.py`)
4. Click **Advanced settings** → in the **Secrets** section, add:
   ```toml
   GROQ_API_KEY = "your_actual_key_here"
   ```
5. Click **Deploy**

You'll get a public URL like `https://your-app.streamlit.app` in about a minute. The app stays deployed indefinitely on the free tier. If it receives no traffic for ~7 days it goes to sleep, but wakes up automatically when someone visits the link again.

## Data source

All documents are retrieved in real time from [infohub.rs.ge](https://infohub.rs.ge/ka), the Georgian Revenue Service's information and methodology hub. This includes tax dispute rulings, situational guidelines, legislative acts, and other official documents. Nothing is stored locally — every query hits the live API.
