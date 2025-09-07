from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from models.ai_model import PROFILES, policy_map, generate_reply
import random

app = Flask(__name__)
app.secret_key = "supersecretkey"

# ------------------- In-memory users -------------------
USERS = {}  # { username: {password: "..."} }

# ------------------- Loading page -------------------
@app.route('/')
def loading():
    return render_template('loading.html')

# ------------------- Intro page -------------------
@app.route('/intro', methods=['GET', 'POST'])
def intro():
    if request.method == 'POST':
        action = request.form.get("action")
        if action == "login":
            return redirect(url_for("login"))
        elif action == "signup":
            return redirect(url_for("signup"))
        else:
            # Continue without login
            user_id = f"guest_{random.randint(1000,9999)}"
            session['user_id'] = user_id
            PROFILES[user_id] = {
                "user_id": user_id,
                "proficiency": 0.5,
                "policy": policy_map(0.5)
            }
            return redirect(url_for("survey"))
    return render_template('intro.html')

# ------------------- Signup page -------------------
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")

        if username in USERS:
            flash("Username already exists. Please choose another.", "error")
            return render_template('signup.html')

        # Save user
        USERS[username] = {"email": email, "password": password}
        session['user_id'] = username
        PROFILES[username] = {
            "user_id": username,
            "proficiency": 0.5,
            "policy": policy_map(0.5)
        }
        flash("Signup successful! Please login.", "success")
        return redirect(url_for("login"))
    return render_template('signup.html')

# ------------------- Login page -------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get("username")
        password = request.form.get("password")

        if username in USERS and USERS[username]["password"] == password:
            session['user_id'] = username
            if username not in PROFILES:
                PROFILES[username] = {
                    "user_id": username,
                    "proficiency": 0.5,
                    "policy": policy_map(0.5)
                }
            return redirect(url_for("survey"))
        else:
            flash("No details found. Please sign up first.", "error")
            return render_template('login.html')

    return render_template('login.html')

# ------------------- Survey page -------------------
@app.route("/survey", methods=["GET", "POST"])
def survey():
    if request.method == "POST":
        q1 = request.form.get("q1")
        q2 = request.form.get("q2")
        q3 = request.form.get("q3")

        # Basic rule to determine learning rate
        if q2 == "yes":  
            session["learning_rate"] = "low"
        elif q1 == "yes" and q3 == "yes":
            session["learning_rate"] = "high"
        else:
            session["learning_rate"] = "average"

        return redirect(url_for("index"))
    return render_template("survey.html")

# ------------------- AI main pages -------------------
@app.route('/index')
def index():
    return render_template('index.html')

@app.route("/text")
def text_mode():
    return render_template("text.html")

@app.route("/voice")
def voice_mode():
    return render_template("voice.html")

# ------------------- Chat API -------------------
@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_id = session.get("user_id", "guest")
    message = data.get("message", "")
    reply = generate_reply(user_id, message)
    return jsonify(reply)


if __name__ == "__main__":
    app.run(debug=True)
