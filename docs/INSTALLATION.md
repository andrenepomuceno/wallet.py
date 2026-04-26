# Installation Guide

## Prerequisites

- **Python 3.8+** (tested with 3.10+)
- **pip** or **conda** for package management
- **Git** to clone the repository

## Step-by-Step Installation

### 1️⃣ Clone the Repository

```bash
git clone git@github.com:andrenepomuceno/wallet.py.git
cd wallet.py
```

### 2️⃣ Create Virtual Environment

**With venv (Python native):**
```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows
```

**With conda:**
```bash
conda create -n wallet python=3.10
conda activate wallet
```

### 3️⃣ Install Dependencies

```bash
pip install -r requirements.txt
```

### 4️⃣ Run the Application

```bash
./wallet.py
```

The application will start at **http://localhost:5000**

---

## Directory Structure Created

On first run, the following directories are automatically created:

```
instance/
  └── wallet.db          # SQLite database (auto-created)
uploads/
  └── (imported files)
```

No database migrations are needed — the database is initialized automatically.

---

## Main Dependencies

| Package | Version | Usage |
|---------|---------|-------|
| Flask | - | Web framework |
| SQLAlchemy | - | Database ORM |
| Flask-SQLAlchemy | - | Flask + SQLAlchemy integration |
| Flask-WTF | - | Form management |
| pandas | - | CSV/XLSX data handling |
| openpyxl | - | Excel file reading |
| yfinance | - | Asset price fetching |
| Plotly | - | Interactive charts |
| lxml | - | HTML parsing (XPath scraping) |
| requests | - | HTTP requests |
| requests_cache | - | HTTP request caching |

---

## Optional API Keys

These are not required to run the application but unlock additional features.
Configure them at **http://localhost:5000/config/api** after starting the app.

| Key | Provider | Feature |
|-----|----------|---------|
| Gemini API key | Google AI Studio | AI-assisted ticker resolution for unknown assets |
| Serper API key | serper.dev | News articles on the asset detail page |

---

## Verify Installation

To verify everything was installed correctly:

```bash
python3 -c "import flask, sqlalchemy, pandas, yfinance, plotly; print('✅ All dependencies installed!')"
```

---

## Troubleshooting

### Error: "ModuleNotFoundError: No module named 'flask'"

**Solution:** Make sure the virtual environment is activated:
```bash
source venv/bin/activate
```

### Error: "Port 5000 already in use"

**Solution:** The application will use the next available port, or you can specify manually:
```bash
./wallet.py --port 5001
```

### Error reading XLSX files

**Solution:** Reinstall openpyxl:
```bash
pip install --upgrade openpyxl
```

### Database corrupted

**Solution:** Delete `instance/wallet.db` and the application will create a new one:
```bash
rm instance/wallet.db
./wallet.py
```

---

## Next Steps

After installation:

1. Read [**User Guide**](USER_GUIDE.md) to learn how to use the platform
2. Explore [**Architecture**](ARCHITECTURE.md) if you want to understand the code
3. Check [**Development**](DEVELOPMENT.md) if you want to contribute

---

**Tip:** Create a `.env` file for configuration variables (see Development Guide).
