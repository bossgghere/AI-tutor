import requests
from typing import Dict, List, Any

# ------------------- Optional Translation -------------------
try:
    from deep_translator import GoogleTranslator
    TRANSLATOR_AVAILABLE = True
except Exception:
    TRANSLATOR_AVAILABLE = False

# ------------------- Gemini AI Setup -------------------
import google.generativeai as genai
from config import GEMINI_API_KEY

if not GEMINI_API_KEY:
    raise RuntimeError("Missing GEMINI_API_KEY in .env")

genai.configure(api_key=GEMINI_API_KEY)
MODEL = genai.GenerativeModel("models/gemini-1.5-flash")

# ------------------- In-memory User Profiles -------------------
PROFILES: Dict[str, Dict[str, Any]] = {}

# ------------------- Student Model Utils -------------------
def score_diagnostic(answers: Dict[str, str]) -> float:
    """Evaluate student answers and return a diagnostic score [0,1]."""
    score = 0.0

    # Q1
    a1 = answers.get("q1", "").lower()
    if any(w in a1 for w in ["energy", "sun", "food", "glucose", "convert"]):
        score += 0.35
    elif len(a1.split()) >= 3:
        score += 0.15

    # Q2
    a2 = answers.get("q2", "").lower()
    if any(w in a2 for w in ["acceleration", "increases", "increase", "more"]):
        score += 0.35
    elif len(a2.split()) >= 2:
        score += 0.1

    # Q3 (confidence level)
    try:
        conf = int(answers.get("q3", "3"))
        conf_score = max(0, min(5, conf)) / 5.0
    except Exception:
        conf_score = 0.6
    score += 0.3 * conf_score

    return min(1.0, round(score, 2))


def policy_map(proficiency: float) -> Dict[str, Any]:
    """Map proficiency to teaching policy (style, depth, examples, checks)."""
    if proficiency < 0.33:
        return {"style": "step_by_step", "depth": "deep", "examples": 2, "checks": True}
    if proficiency < 0.7:
        return {"style": "balanced", "depth": "medium", "examples": 1, "checks": True}
    return {"style": "concise", "depth": "shallow", "examples": 1, "checks": False}

# ------------------- Google Search -------------------
def google_search(query: str, num_results: int = 3) -> List[Dict[str, str]]:
    """Perform Google Custom Search and return results (title, link, snippet)."""
    from config import GOOGLE_SEARCH_API_KEY, SEARCH_ENGINE_ID
    if not GOOGLE_SEARCH_API_KEY or not SEARCH_ENGINE_ID:
        return []

    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "q": query,
        "key": GOOGLE_SEARCH_API_KEY,
        "cx": SEARCH_ENGINE_ID,
        "num": num_results,
    }
    resp = requests.get(url, params=params, timeout=8)
    items = resp.json().get("items", [])
    return [
        {"title": it.get("title", ""), "link": it.get("link", ""), "snippet": it.get("snippet", "")}
        for it in items
    ]

# ------------------- Prompt Builder -------------------
def build_prompt(student_profile: Dict[str, Any], user_question: str, sources: List[Dict[str, str]] = []) -> str:
    """Build the tutoring prompt for Gemini AI based on profile and question."""
    style = student_profile.get("policy", {}).get("style", "balanced")
    proficiency = student_profile.get("proficiency", 0.5)
    lang = student_profile.get("language", "en")

    sources_block = ""
    if sources:
        sources_block = "\n\nSources:\n" + "\n".join(
            [f"- {s['title']}: {s['link']}" for s in sources]
        )

    prompt = f"""
You are Zyvora, a friendly human-like tutor.

StudentProfile:
  proficiency = {proficiency:.2f}
  style       = {style}
  language    = {lang}

Guidelines:
- If style == step_by_step: give numbered steps, short examples after each, and end with a check question.
- If style == balanced: clear explanation, one worked example, and a one-sentence recap.
- If style == concise: 2-3 sentences with a short takeaway.

Student asked:
{user_question}

{sources_block}

Answer warmly in a clear, human tone.
If user language is not English, answer in English first (client will handle translation).
"""
    return prompt.strip()

# ------------------- Translation -------------------
def translate(text: str, target_lang: str) -> str:
    """Translate text if a non-English target language is specified."""
    if not target_lang or target_lang == "en":
        return text

    if TRANSLATOR_AVAILABLE:
        try:
            return GoogleTranslator(source="auto", target=target_lang).translate(text)
        except Exception:
            pass

    return text + f"\n\n(Translation to {target_lang} not available.)"

# ------------------- Chat Reply -------------------
def generate_reply(user_id: str, message: str, lang: str = "en") -> Dict[str, Any]:
    """Generate a tutor reply based on user profile, message, and optional search."""
    profile = PROFILES.get(
        user_id,
        {
            "user_id": user_id,
            "proficiency": 0.5,
            "policy": policy_map(0.5),
            "language": lang,
        },
    )

    # Only run search for explanatory queries
    sources: List[Dict[str, str]] = []
    if any(w in message.lower() for w in ["explain", "what is", "how", "define", "show", "solve"]):
        try:
            sources = google_search(message, num_results=3)
        except Exception:
            sources = []

    prompt = build_prompt(profile, message, sources)

    try:
        resp = MODEL.generate_content(prompt)
        reply_en = resp.text.strip()
    except Exception as e:
        return {"error": str(e)}

    reply = translate(reply_en, profile.get("language", "en"))

    return {
        "reply": reply,
        "reply_en": reply_en,
        "sources": sources,
        "profile": profile,
    }
