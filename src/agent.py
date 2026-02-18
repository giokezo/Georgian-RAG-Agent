import time

from groq import Groq

from src.config import CITATION, GROQ_API_KEY, GROQ_MODEL, MAX_CONTEXT_CHARS
from src.retriever import retrieve

_client = None


def _get_client():
    global _client
    if _client is None:
        if not GROQ_API_KEY:
            raise ValueError(
                "GROQ_API_KEY not set. Create a .env file with your key.\n"
                "Get one free at: https://console.groq.com/keys"
            )
        _client = Groq(api_key=GROQ_API_KEY)
    return _client


SYSTEM_PROMPT = """შენ ხარ მეგობრული ასისტენტი, რომელიც სპეციალიზდება საგადასახადო და საბაჟო საკითხებზე.
შენ შეგიძლია უპასუხო ნებისმიერ შეკითხვას, მაგრამ შენი ძირითადი ექსპერტიზაა საქართველოს
საგადასახადო და საბაჟო ადმინისტრირება, infohub.rs.ge-ს დოკუმენტების საფუძველზე.

წესები:
1. უპასუხე მხოლოდ ქართულ ენაზე.
2. თუ მომხმარებელი სვამს საგადასახადო/საბაჟო შეკითხვას და მოწოდებულია კონტექსტი:
   - გააანალიზე დოკუმენტები და შეადგინე ინფორმაციული პასუხი
   - დავების გადაწყვეტილებებიდან ამოიღე სამართლებრივი პრინციპები
   - მიუთითე წყარო დოკუმენტები (სახელი და ბმული)
3. თუ მომხმარებელი სვამს ზოგად შეკითხვას (მისალმება, საუბარი, სხვა თემა):
   - უპასუხე თავაზიანად და დამხმარედ
   - პასუხის ბოლოს მოკლედ შეახსენე, რომ შენი ძირითადი დანიშნულებაა საგადასახადო
     და საბაჟო საკითხებში დახმარება, და მოიწვიე ამ თემაზე შეკითხვების დასასმელად
4. თუ კონტექსტში საკმარისი ინფორმაცია არ არის, მაინც შეეცადე პასუხის გაცემას
   და აღნიშნე რომ სრული ინფორმაციისთვის რეკომენდებულია infohub.rs.ge-ზე ძიება.
5. იყავი ზუსტი, ინფორმაციული და მეგობრული.
6. იმ შემთხვევაში, თუ მომხმარებელი დასვამს შეკითხვას სხვა ენაზე შეახსენე რომ ხარ ქართული ენის აგენტი."""


def _chat(messages: list[dict]) -> str:
    """Send messages to Groq and return the response text."""
    response = _get_client().chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
    )
    return response.choices[0].message.content


def _chat_with_retry(messages: list[dict], context_docs: list[dict]) -> str:
    """Send to Groq with retry logic for 413 and 429 errors."""
    max_retries = 2

    for attempt in range(max_retries + 1):
        try:
            return _chat(messages)
        except Exception as e:
            error_str = str(e)
            status = getattr(e, "status_code", None)

            # 413: payload too large — reduce context and retry
            if status == 413 or "413" in error_str:
                if attempt < max_retries and context_docs:
                    # Remove last doc and rebuild
                    context_docs.pop()
                    if not context_docs:
                        raise
                    new_context = build_context(context_docs)
                    messages[-1]["content"] = _build_user_prompt(
                        new_context, messages[-1]["content"].split("შეკითხვა: ")[-1].split("\n")[0]
                    )
                    continue
                raise

            # 429: rate limited — wait and retry with exponential backoff
            if status == 429 or "429" in error_str:
                if attempt < max_retries:
                    wait = 2 ** (attempt + 1)
                    time.sleep(wait)
                    continue
                raise

            raise


def build_context(docs: list[dict], max_chars: int = MAX_CONTEXT_CHARS) -> str:
    """Format retrieved documents into context string, respecting token budget."""
    context_parts = []
    chars_used = 0

    for i, doc in enumerate(docs, 1):
        parts = [f"[დოკუმენტი {i}: {doc['name']}]"]
        if doc.get("type"):
            parts.append(f"ტიპი: {doc['type']}")
        if doc.get("url"):
            parts.append(f"ბმული: {doc['url']}")
        if doc.get("description"):
            desc = doc["description"][:800]
            parts.append(desc)

        block = "\n".join(parts)

        # Check budget before adding
        if chars_used + len(block) > max_chars and context_parts:
            break

        context_parts.append(block)
        chars_used += len(block)

    return "\n\n---\n\n".join(context_parts)


def _build_user_prompt(context: str, question: str) -> str:
    return f"""კონტექსტი (infohub.rs.ge დოკუმენტები):
{context}

შეკითხვა: {question}

გააანალიზე მოწოდებული დოკუმენტები და უპასუხე შეკითხვას. მიუთითე წყარო დოკუმენტები."""


def ask(question: str) -> dict:
    """
    Full RAG pipeline: search InfoHub API, send to LLM, return structured result.

    Returns dict with:
        - answer: the LLM response text
        - docs: list of docs used (with relevance_score)
        - total_api_results: total results from API
        - query_used: cleaned query
        - search_time: seconds spent searching
        - llm_time: seconds spent on LLM call
        - total_time: total pipeline time
    """
    t_start = time.time()

    t_search_start = time.time()
    search_result = retrieve(question)
    search_time = time.time() - t_search_start

    docs = search_result["docs"]

    if not docs:
        # No docs found — let LLM answer from general knowledge
        user_prompt = f"შეკითხვა: {question}"
    else:
        context = build_context(docs)
        user_prompt = _build_user_prompt(context, question)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    t_llm_start = time.time()
    try:
        answer = _chat_with_retry(messages, docs)
    except Exception as e:
        answer = f"შეცდომა LLM API-სთან დაკავშირებისას: {e}"
    llm_time = time.time() - t_llm_start

    total_time = time.time() - t_start

    return {
        "answer": f"{answer}\n\n{CITATION}",
        "docs": docs,
        "total_api_results": search_result["total_api_results"],
        "query_used": search_result["query_used"],
        "search_time": round(search_time, 2),
        "llm_time": round(llm_time, 2),
        "total_time": round(total_time, 2),
    }


