import re

import requests

from src.config import (
    ABBREVIATIONS,
    INFOHUB_HEADERS,
    INFOHUB_SEARCH_URL,
    RERANK_TOP_K,
    SEARCH_TOP_K,
)


# Common filler words to strip from queries
_STOP_WORDS = {
    "რა", "არის", "როგორ", "რატომ", "რას", "გულისხმობს", "ვის", "სად",
    "რომელი", "რამდენი", "როდის", "the", "is", "what", "how", "why",
    "მინდა", "ვიცოდე", "მითხარი", "ახსენი", "განმარტე",
}


def _strip_html(html: str) -> str:
    """Remove HTML tags and clean up whitespace."""
    text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def _clean_query(question: str) -> str:
    """Remove filler words from the question to get better search terms."""
    words = question.strip().rstrip("?!.").split()
    keywords = [w for w in words if w.lower() not in _STOP_WORDS]
    return " ".join(keywords) if keywords else question.strip()


def _expand_query(query: str) -> list[str]:
    """Expand query using abbreviation map. Returns list of query variants."""
    words = query.split()
    queries = [query]

    for word in words:
        word_lower = word.lower()
        # Check if word is an abbreviation
        if word_lower in ABBREVIATIONS:
            expanded = query.replace(word, ABBREVIATIONS[word_lower])
            queries.append(expanded)
        # Check if word matches an expansion (reverse lookup)
        for abbr, full in ABBREVIATIONS.items():
            if word_lower == abbr and full not in query:
                queries.append(f"{query} {full}")
                break

    return list(dict.fromkeys(queries))  # deduplicate preserving order


def _score_relevance(query: str, doc: dict) -> float:
    """Score document relevance using keyword overlap (0.0 to 1.0)."""
    query_words = set(query.lower().split())
    # Also add expanded terms to matching
    expanded_words = set()
    for w in query_words:
        if w in ABBREVIATIONS:
            expanded_words.update(ABBREVIATIONS[w].lower().split())
    query_words |= expanded_words

    if not query_words:
        return 0.0

    # Combine name and description for matching
    doc_text = f"{doc.get('name', '')} {doc.get('description', '')}".lower()
    doc_words = set(doc_text.split())

    # Keyword overlap ratio
    overlap = query_words & doc_words
    score = len(overlap) / len(query_words)

    # Bonus for name match (title relevance is stronger signal)
    name_words = set(doc.get("name", "").lower().split())
    name_overlap = query_words & name_words
    if name_overlap:
        score += 0.2 * (len(name_overlap) / len(query_words))

    return min(score, 1.0)


def _search_api(query: str, top_k: int) -> tuple[list[dict], int]:
    """Call InfoHub API and return (docs, total_count)."""
    params = {
        "q": query,
        "AISearch": "false",
        "searchInName": "true",
        "searchInText": "true",
        "searchType": "3",
        "searchForm": "false",
        "skip": "0",
        "take": str(top_k),
        "searchInAllSubTypes": "false",
    }

    try:
        response = requests.get(
            INFOHUB_SEARCH_URL,
            params=params,
            headers=INFOHUB_HEADERS,
            timeout=15,
        )
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Search API error: {e}")
        return [], 0

    data = response.json()
    total_count = data.get("totalCount", 0)
    results = []

    for doc in data.get("data", []):
        description = doc.get("additionalDescription", "") or ""
        clean_desc = _strip_html(description) if description else ""

        doc_uuid = doc.get("uniqueKey", "")
        doc_url = f"https://infohub.rs.ge/ka/workspace/document/{doc_uuid}" if doc_uuid else ""

        results.append({
            "name": doc.get("name", ""),
            "description": clean_desc,
            "type": doc.get("type", {}).get("name", ""),
            "base_type": doc.get("baseType", {}).get("name", ""),
            "url": doc_url,
            "uuid": doc_uuid,
            "date": doc.get("receiptDate", ""),
        })

    return results, total_count


def retrieve(query: str, top_k: int = SEARCH_TOP_K, rerank_k: int = RERANK_TOP_K) -> dict:
    """Search InfoHub API, score & rerank results."""
    clean_q = _clean_query(query)

    # First search
    docs, total_count = _search_api(clean_q, top_k)

    # If no results, try query expansion
    if not docs:
        for expanded_q in _expand_query(clean_q)[1:]:  # skip original
            docs, total_count = _search_api(expanded_q, top_k)
            if docs:
                clean_q = expanded_q
                break

    # If query is a single word, also search expanded forms and merge
    if len(clean_q.split()) == 1 and clean_q.lower() in ABBREVIATIONS:
        expanded = ABBREVIATIONS[clean_q.lower()]
        extra_docs, extra_total = _search_api(expanded, top_k)
        total_count = max(total_count, extra_total)
        # Merge, avoiding duplicates by uuid
        seen_uuids = {d["uuid"] for d in docs}
        for d in extra_docs:
            if d["uuid"] not in seen_uuids:
                docs.append(d)
                seen_uuids.add(d["uuid"])

    # Score and rerank
    for doc in docs:
        doc["relevance_score"] = _score_relevance(clean_q, doc)

    docs.sort(key=lambda d: d["relevance_score"], reverse=True)
    top_docs = docs[:rerank_k]

    return {
        "docs": top_docs,
        "total_api_results": total_count,
        "query_used": clean_q,
    }
