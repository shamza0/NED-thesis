# VizQuery

Ask a question about a food-delivery database in plain English — get a chart.

Built for an MS thesis at NED University. Runs 100% locally using Ollama.

---

## Requirements

- Python 3.11+
- [Ollama](https://ollama.com/download) installed and running

---

## Getting started

```bash
# 1. Clone and enter the project
git clone <repo-url>
cd ned-thesis

# 2. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Pull the LLM
ollama pull qwen2.5-coder:7b

# 5. Generate the database
python data/generate_data.py

# 6. Run
ollama serve          # keep this running in a separate terminal
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501) in your browser.

---

## Run tests

```bash
pytest
```

## Run evaluation harness

```bash
python eval/run_eval.py
```

---

## Stack

Python · SQLite · Ollama · Streamlit · Plotly
