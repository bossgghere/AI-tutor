# Zyvora

Zyvora is an AI-powered project that provides both **text** and **voice** interaction modes.  
It is built with **Python + Flask** and offers a simple web-based interface.

---

## 📂 Project Structure

```
Zyvora/
│── app.py             # Main Flask application
│── config.py          # Configuration settings
│── requirements.txt   # Python dependencies
│── .gitignore         # Ignored files/folders
│── models/            # ML/AI models
│── templates/         # HTML templates (text.html, voice.html)
│── venv/              # Virtual environment (ignored in git)
```

---

## 🚀 Getting Started

### 1️⃣ Clone the Repository

```bash
git clone https://github.com/mdparvez44/Zyvora.git
cd Zyvora
```

### 2️⃣ Create a Virtual Environment

```bash
python -m venv venv
```

Activate it:

- **Windows (PowerShell):**
  ```bash
  venv\Scripts\activate
  ```
- **Linux / MacOS:**
  ```bash
  source venv/bin/activate
  ```

### 3️⃣ Install Dependencies

```bash
pip install -r requirements.txt
```

### 4️⃣ Configure Environment

Create a `.env` file in the root directory and add your keys/settings.  
For example:

```ini
GEMINI_API_KEY=your_api_key_here
```

---

## ▶️ Running the Project

Run the Flask app with:

```bash
python app.py
```

By default, Flask runs on **HTTP**:

👉 Open your browser at:  
`http://127.0.0.1:5000/`

⚠️ Note: The app is set up for **HTTP only** (not HTTPS). This is fine for local development.

---

## 🛠️ Tech Stack
- Python (Flask)
- HTML + Tailwind CSS
- Google Generative AI API

---

## 🤝 Contributing
1. Fork this repository  
2. Create your branch:  
   ```bash
   git checkout -b feature-xyz
   ```
3. Commit changes:  
   ```bash
   git commit -m "Add feature xyz"
   ```
4. Push to your branch:  
   ```bash
   git push origin feature-xyz
   ```
5. Open a Pull Request

---

## 📜 License
MIT License © 2025 MD. Parvez
# AI-tutor
