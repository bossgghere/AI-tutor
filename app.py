# app.py
from flask import Flask, request, jsonify, render_template
import google.generativeai as genai
import requests
from typing import Dict, List, Any
import os
import datetime
from newsapi import NewsApiClient
from config import GEMINI_API_KEY, GOOGLE_SEARCH_API_KEY, NEWSAPI_KEY, SEARCH_ENGINE_ID, PORT
from deep_translator import GoogleTranslator

if not GEMINI_API_KEY:
    raise RuntimeError("Missing GEMINI_API_KEY in .env")
genai.configure(api_key=GEMINI_API_KEY)
MODEL = genai.GenerativeModel("models/gemini-1.5-flash")

if NEWSAPI_KEY:  # Initialize News API client only if key exists
    newsapi = NewsApiClient(api_key=NEWSAPI_KEY)
else:
    newsapi = None

# ------------------- Global State (in-memory) -------------------
PROFILES: Dict[str, Dict[str, Any]] = {}

app = Flask(__name__, template_folder="templates")

# ------------------- Student Model Utils -------------------
def score_diagnostic(answers: Dict[str, str]) -> float:
    """Scores a student's diagnostic answers."""
    score = 0.0
    a1 = answers.get("q1", "").lower()
    if any(w in a1 for w in ["energy", "sun", "food", "glucose", "convert"]):
        score += 0.35
    elif len(a1.split()) >= 3:
        score += 0.15
    a2 = answers.get("q2", "").lower()
    if any(w in a2 for w in ["acceleration", "increases", "increase", "more"]):
        score += 0.35
    elif len(a2.split()) >= 2:
        score += 0.1
    try:
        conf = int(answers.get("q3", "3"))
        conf_score = max(0, min(5, conf)) / 5.0
    except Exception:
        conf_score = 0.6
    score += 0.3 * conf_score
    return min(1.0, round(score, 2))

def policy_map(proficiency: float) -> Dict[str, Any]:
    """Maps proficiency score to a teaching policy."""
    if proficiency < 0.33:
        return {"style": "step_by_step", "depth": "deep", "examples": 2, "checks": True}
    if proficiency < 0.7:
        return {"style": "balanced", "depth": "medium", "examples": 1, "checks": True}
    return {"style": "concise", "depth": "shallow", "examples": 1, "checks": False}

def google_search(query: str, num_results: int = 3) -> List[Dict[str, str]]:
    """Performs a Google Search."""
    if not GOOGLE_SEARCH_API_KEY or not SEARCH_ENGINE_ID:
        return []
    url = "https://www.googleapis.com/customsearch/v1"
    params = {"q": query, "key": GOOGLE_SEARCH_API_KEY, "cx": SEARCH_ENGINE_ID, "num": num_results}
    try:
        resp = requests.get(url, params=params, timeout=8)
        items = resp.json().get("items", [])
        results = []
        for it in items:
            results.append({"title": it.get("title", ""), "link": it.get("link", ""), "snippet": it.get("snippet", "")})
        return results
    except Exception as e:
        print(f"Google Search Error: {e}")
        return []

def get_current_datetime():
    """Fetches the current date and time."""
    now = datetime.datetime.now()
    return now.strftime("Current date and time is: %Y-%m-%d %H:%M:%S")

def get_real_time_news(query=None, country='in', lang='hi', category='general'):
    """Fetches real-time news headlines in the specified language."""
    if not newsapi:
        return "News API key not configured. Cannot fetch news."
    try:
        if query:
            articles = newsapi.get_everything(q=query, language=lang, sort_by='relevancy')['articles']
        else:
            articles = newsapi.get_top_headlines(country=country, category=category, language=lang)['articles']

        if not articles:
            # Fallback to English if no articles found for the requested language
            articles = newsapi.get_top_headlines(country='us', category='general', language='en')['articles']

        if not articles:
            return "No news headlines found for your request."

        headlines_list = []
        for i, article in enumerate(articles[:5], 1):
            title = article.get('title', 'No Title')
            source = article.get('source', {}).get('name', 'Unknown Source')
            headlines_list.append(f"**{i}. {title}** (Source: {source})")
            
        return "Top Headlines:\n" + "\n".join(headlines_list)

    except Exception as e:
        return f"An error occurred while fetching news: {e}"

def build_prompt(student_profile: Dict[str, Any], user_question: str, sources: List[Dict[str, str]] = []) -> str:
    """Constructs the prompt for the Gemini AI."""
    style = student_profile.get("policy", {}).get("style", "balanced")
    proficiency = student_profile.get("proficiency", 0.5)
    lang = student_profile.get("language", "en")
    sources_block = ""
    if sources:
        sources_block = "\n\nSources:\n" + "\n".join([f"- {s['title']}: {s['link']}" for s in sources])
    prompt = f"""
You are Zyvora, a friendly human-like tutor. StudentProfile: proficiency={proficiency:.2f}, style={style}, language={lang}.
Be warm, encouraging, and adapt explanations to the student's learning rate. Use these rules:
- If style == step_by_step: give numbered steps, short examples after each step, and ask a one-line check question at the end.
- If style == balanced: give a clear explanation, one worked example, and a one-sentence recap.
- If style == concise: give 2-3 concise sentences and a short takeaway.

Conversation:
Student asked: {user_question}
{sources_block}

Answer in a clear, friendly human tone. If the user language is not English, answer in English first then the client will handle translation if requested.
"""
    return prompt.strip()

def translate(text: str, target_lang: str) -> str:
    """Translates text if translator is available."""
    if not target_lang or target_lang == "en":
        return text
    try:
        return GoogleTranslator(source="auto", target=target_lang).translate(text)
    except Exception:
        pass
    return text + f"\n\n(Translation to {target_lang} not available.)"

def generate_reply(user_id: str, message: str, lang: str = "en") -> Dict[str, Any]:
    """Generates a reply from the Gemini AI model."""
    profile = PROFILES.get(user_id, {"user_id": user_id, "proficiency": 0.5, "policy": policy_map(0.5), "language": lang})
    
    message_lower = message.lower()
    
    if "time" in message_lower or "date" in message_lower:
        reply_en = get_current_datetime()
        reply = translate(reply_en, profile.get("language", "en"))
        return {"reply": reply, "reply_en": reply_en, "sources": [], "profile": profile}

    elif "news" in message_lower or "headlines" in message_lower:
        if "tech news" in message_lower or "technology news" in message_lower:
            reply = get_real_time_news(lang=lang, category='technology')
        elif "business news" in message_lower:
            reply = get_real_time_news(lang=lang, category='business')
        else:
            reply = get_real_time_news(lang=lang)
        
        return {"reply": reply, "reply_en": reply, "sources": [], "profile": profile}

    # --- This is the section for regular AI responses with sources ---
    sources = []
    if any(w in message_lower for w in ["explain", "what is", "how", "define", "show", "solve"]):
        sources = google_search(message, num_results=3)

    prompt = build_prompt(profile, message, sources)
    try:
        resp = MODEL.generate_content(prompt)
        reply_en = resp.text.strip()
        
        # Add a source list with bolding and links to the Gemini response
        if sources:
            source_links = "\n\n**Sources:**\n" + "\n".join([f"- **[{s['title']}]({s['link']})**" for s in sources])
            reply_en += source_links
    except Exception as e:
        return {"error": str(e)}

    reply = translate(reply_en, profile.get("language", "en"))
    return {"reply": reply, "reply_en": reply_en, "sources": sources, "profile": profile}

# ------------------- Routes -------------------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/text")
def text_mode():
    return render_template("text.html")

@app.route("/voice")
def voice_mode():
    return render_template("voice.html")

@app.route("/diagnostic", methods=["POST"])
def diagnostic_route():
    payload = request.json or {}
    user_id = payload.get("user_id", "anon")
    answers = payload.get("answers", {})
    lang = payload.get("lang", "en")
    prof = score_diagnostic(answers)
    policy = policy_map(prof)
    profile = {"user_id": user_id, "proficiency": prof, "policy": policy, "language": lang}
    PROFILES[user_id] = profile
    return jsonify({"profile": profile})

@app.route("/chat", methods=["POST"])
def chat_route():
    payload = request.json or {}
    user_id = payload.get("user_id", "anon")
    message = payload.get("message", "")
    lang = payload.get("lang", "en")
    return jsonify(generate_reply(user_id, message, lang))

@app.route("/profile/<user_id>", methods=["GET", "DELETE"])
def profile_route(user_id):
    if request.method == "GET":
        return jsonify(PROFILES.get(user_id, {}))
    else:
        PROFILES.pop(user_id, None)
        return jsonify({"ok": True})

# ------------------- Run server with HTTPS -------------------
if __name__ == "__main__":
    cert_path = "certs/cert.pem"
    key_path = "certs/key.pem"
    app.run(host="0.0.0.0", port=PORT, debug=True, ssl_context=(cert_path, key_path))