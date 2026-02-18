import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Paths
PROJECT_ROOT = Path(__file__).parent.parent

# InfoHub API
INFOHUB_API_BASE = "https://infohubapi.rs.ge/api"
INFOHUB_SEARCH_URL = f"{INFOHUB_API_BASE}/documents/search"
INFOHUB_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "languagecode": "ka",
    "Referer": "https://infohub.rs.ge/",
}

# Search
SEARCH_TOP_K = 10
RERANK_TOP_K = 5

# Token budget
MAX_CONTEXT_CHARS = 3000

# Groq
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = "llama-3.3-70b-versatile"

# Georgian tax abbreviation map
ABBREVIATIONS = {
    "დღგ": "დამატებული ღირებულების გადასახადი",
    "სსკ": "საგადასახადო კოდექსი",
    "სშკ": "საბაჟო კოდექსი",
    "მოგ": "მოგების გადასახადი",
    "საშ": "საშემოსავლო გადასახადი",
    "ექსპ": "ექსპორტი",
    "იმპ": "იმპორტი",
    "დეკლ": "დეკლარაცია",
    "ეკ": "ეკონომიკური კოდექსი",
    "ფიზპ": "ფიზიკური პირი",
    "იურპ": "იურიდიული პირი",
    "ქონ": "ქონების გადასახადი",
    "აქც": "აქციზი",
}

# Citation
CITATION = (
    'წყარო: „ინფორმაციულ-მეთოდოლოგიური ჰაბი (საგადასახადო და საბაჟო '
    'ადმინისტრირებასთან დაკავშირებული დოკუმენტები და ინფორმაცია ერთ სივრცეში)"\n'
    'https://infohub.rs.ge/ka'
)
