import requests
from typing import Dict, List, Any

# Optional translator
try:
    from deep_translator import GoogleTranslator
    TRANSLATOR_AVAILABLE = True
except Exception:
    TRANSLATOR_AVAILABLE = False

# Gemini AI setup
import google.generativeai as genai
from config import GEMINI_API_KEY

if not GEMINI_API_KEY:
    raise RuntimeError("Missing GEMINI_API_KEY in .env")
genai.configure(api_key=GEMINI_API_KEY)
MODEL = genai.GenerativeModel("models/gemini-1.5-flash")

# ------------------- In-memory profiles -------------------
PROFILES: Dict[str, Dict[str, Any]] = {}

# ------------------- Student model utils -------------------
def policy_map(proficiency: float) -> Dict[str, Any]:
    if proficiency < 0.33:
        return {
            "style": "step_by_step",
            "depth": "deep",
            "examples": 2,
            "checks": True,
            "learning_style": "story"
        }
    if proficiency < 0.7:
        return {
            "style": "balanced",
            "depth": "medium",
            "examples": 1,
            "checks": True,
            "learning_style": "step_by_step"
        }
    return {
        "style": "concise",
        "depth": "shallow",
        "examples": 1,
        "checks": False,
        "learning_style": "concise"
    }

# ------------------- Google Search -------------------
def google_search(query: str, num_results: int = 3) -> List[Dict[str, str]]:
    from config import GOOGLE_SEARCH_API_KEY, SEARCH_ENGINE_ID
    if not GOOGLE_SEARCH_API_KEY or not SEARCH_ENGINE_ID:
        return []
    url = "https://www.googleapis.com/customsearch/v1"
    params = {"q": query, "key": GOOGLE_SEARCH_API_KEY, "cx": SEARCH_ENGINE_ID, "num": num_results}
    resp = requests.get(url, params=params, timeout=8)
    items = resp.json().get("items", [])
    results = []
    for it in items:
        results.append({"title": it.get("title", ""), "link": it.get("link", ""), "snippet": it.get("snippet", "")})
    return results

# ------------------- Build prompt -------------------
def build_prompt(student_profile: Dict[str, Any], user_question: str, sources: List[Dict[str,str]] = []) -> str:
    learning_style = student_profile.get("policy", {}).get("learning_style", "step_by_step")
    proficiency = student_profile.get("proficiency", 0.5)
    lang = student_profile.get("language", "en")
    sources_block = ""
    if sources:
        sources_block = "\n\nSources:\n" + "\n".join([f"- {s['title']}: {s['link']}" for s in sources])

    if learning_style == "story":
        instructions = "- Explain the concept using a story or narrative example."
    elif learning_style == "step_by_step":
        instructions = "- Explain step-by-step with short examples and a check question."
    else:
        instructions = "- Give concise explanation in 2-3 sentences with a short takeaway."

    prompt = f"""
You are Zyvora, a friendly human-like tutor. StudentProfile: proficiency={proficiency:.2f}, learning_style={learning_style}, language={lang}.
Be warm, encouraging, and adapt explanations to the student's learning rate. Use these rules:
{instructions}

Conversation:
Student asked: {user_question}
{sources_block}

Answer in a clear, friendly human tone.
"""
    return prompt.strip()

# ------------------- Translation -------------------
def translate(text: str, target_lang: str) -> str:
    if not target_lang or target_lang == "en":
        return text
    if TRANSLATOR_AVAILABLE:
        try:
            return GoogleTranslator(source="auto", target=target_lang).translate(text)
        except Exception:
            pass
    return text + f"\n\n(Translation to {target_lang} not available.)"

# ------------------- Generate reply -------------------
def generate_reply(user_id: str, message: str, lang: str = "en") -> Dict[str, Any]:
    profile = PROFILES.get(
        user_id,
        {"user_id": user_id, "proficiency": 0.5, "policy": policy_map(0.5), "language": lang}
    )

    # Respect survey-updated policy if exists
    if "learning_style" not in profile["policy"]:
        profile["policy"]["learning_style"] = "step_by_step"

    sources = []
    if any(w in message.lower() for w in ["explain","what is","how","define","show","solve"]):
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

    reply = translate(reply_en, profile.get("language","en"))
    return {"reply": reply, "reply_en": reply_en, "sources": sources, "profile": profile}
