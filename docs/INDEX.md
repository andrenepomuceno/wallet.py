# Documentation - Wallet.py

Welcome to the **Wallet.py** documentation, an investment portfolio analyzer built with Flask that integrates data from multiple sources (B3, Avenue, and generic formats) with real-time prices.

## 📚 Table of Contents

### Getting Started
- [**Installation Guide**](INSTALLATION.md) — How to set up the environment and run the application
- [**User Guide**](USER_GUIDE.md) — How to use the platform, import data, and analyze your portfolio

### For Developers
- [**Architecture**](ARCHITECTURE.md) — Code structure, patterns, and data flow
- [**Development Guide**](DEVELOPMENT.md) — Set up dev environment, code patterns, how to add new features
- [**API Reference**](API.md) — Available endpoints and data models

### Infrastructure
- [**Database**](DATABASE.md) — Schema, SQLAlchemy models, and queries
- [**Price Integration**](PRICE_INTEGRATION.md) — How price lookups work (yfinance, custom scraping)

---

## 🚀 Quick Start

```bash
# 1. Clone repository
git clone git@github.com:andrenepomuceno/wallet.py.git
cd wallet.py

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip3 install -r requirements.txt

# 4. Run application
./wallet.py
```

Access at **http://localhost:5000**

---

## 📋 Key Features

✅ **Multi-source** — Integrates B3, Avenue, and generic formats  
✅ **Automatic deduplication** — Prevents re-importing the same data  
✅ **Real-time prices** — yfinance + custom scraping  
✅ **Smart consolidation** — Groups positions, calculates profitability  
✅ **Visualizations** — Interactive Plotly charts  
✅ **Detailed analysis** — Per-asset view with history and fundamentals  
✅ **Dark UI** — Bootstrap 5 dark theme, responsive design  

---

## 🔗 Folder Structure

```
wallet.py/
├── docs/                    # Documentation (you are here)
├── app/                     # Application code
│   ├── models.py           # Database models
│   ├── importing.py        # Data parsing and import
│   ├── processing.py       # Consolidation and price logic
│   ├── routes.py           # Flask routes and views
│   ├── forms.py            # Flask-WTF forms
│   ├── utils/              # Utilities (parsing, scraping)
│   ├── static/             # CSS, JS, images
│   └── templates/          # Jinja2 templates
├── instance/               # SQLite database (local)
├── uploads/                # Imported files
├── tests/                  # Test suite (in progress)
├── wallet.py               # Entrypoint
├── requirements.txt        # Python dependencies
└── README.md               # Main readme
```

---

## ❓ Frequently Asked Questions

**Q: What Python version is needed?**  
A: Python 3.8+ recommended.

**Q: Can I use this in production?**  
A: Not yet. Still in development. For production, add tests, CI/CD, and proper hosting.

**Q: How do I add a new data source?**  
A: See [Development Guide](DEVELOPMENT.md#adding-a-new-data-source).

**Q: Are my data stored securely?**  
A: Data is stored locally in SQLite. Configure backups as needed.

---

## 📞 Support

To report bugs or suggest improvements, create an issue on the GitHub repository.

---

**Last updated:** April 2026
