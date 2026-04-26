# User Guide

Welcome to Wallet.py! This guide shows you how to use the platform to manage and analyze your investment portfolio.

---

## 📱 Home Screen

When you access **http://localhost:5000**, you will see:

- **Portfolio Summary** — Quick view of your assets
- **Upload Button** — Import data from your brokers
- **Navigation** — Top menu with main options

---

## 📤 1. Import Data

### How to Upload

1. Click **"Upload"** in the navigation bar
2. Drag a CSV/XLSX file or click to select
3. Choose the data source type:
   - **B3 Movimentation** (B3 Movement)
   - **B3 Negotiation** (B3 Negotiation)
   - **Avenue Extract** (Avenue Statement)
   - **Generic Extract** (Generic Format)
4. Click **"Upload"**

### Get Data from Sources

#### B3 (Brazilian Exchange)

Access [B3 Investor Area](https://www.investidor.b3.com.br/extrato/) and download:

- **Extract > Negotiation** — Stock buys and sells
- **Extract > Movement** — Dividends, debits, credits

Supported formats: XLSX or CSV

#### Avenue (US Broker)

1. Log in to your Avenue account
2. Go to **Account > Statements**
3. Export the CSV file

**Supported:**
- Old format: `Data,Hora,Liquidação,...`
- New format: `Data transação,Data liquidação,...`

#### Generic Format

Create a CSV file with the following columns (in English):

```
Date,Asset,Movimentation,Quantity,Price,Total
2024-01-15,AAPL,Buy,10,150.00,1500.00
2024-02-20,AAPL,Sell,5,160.00,800.00
2024-03-10,ITUB3,Buy,100,26.50,2650.00
2024-03-15,ITUB3,Wages,50,0.00,50.00
2024-04-01,ITUB3,Taxes,0,0.00,10.00
```

**Required fields:**
- `Date` — Date in YYYY-MM-DD format
- `Asset` — Asset code (e.g., AAPL, ITUB3, BTC)
- `Movimentation` — `Buy`, `Sell`, `Wages`, `Taxes`
- `Quantity` — Number of shares/crypto
- `Price` — Unit price
- `Total` — Total value (quantity × price)

---

## 📊 2. Consolidate Portfolio

After importing data, click **"Consolidate"** to see the complete summary:

### Information Displayed

**Summary table by asset class:**
- Class, Currency, Position value, Cost, Wages, Rent Wages, Taxes, Liquid Cost, Realized/Unrealized Gain, Capital Gain, Rentability, Relative position

**Per-asset table:**
- Name, Close Price, 1D Variation, Shares, Position value, Avg Buy Price, individual gain/loss metrics

### Sold Positions

Assets that have been fully sold appear on a separate **"Sold"** page (link available in the navigation or at `/sold`). They are excluded from the main consolidation view.

---

## 🔍 3. View Asset Details

Click on any asset in the consolidation table to access the **detailed view**:

### Information Cards

- **Current Price** — Real-time quote
- **Quantity** — Total position
- **Total Value** — Price × Quantity
- **Profitability** — P&L in R$ and %
- **Allocation** — % of portfolio

### Transaction Tables

**Buys:**
- Date, quantity, unit price, total

**Sells:**
- When you exited the position

**Dividends/Wages:**
- Credits received

**Taxes:**
- Charges deducted

### Charts

**Candlestick Chart:**
- Asset price history fetched from Yahoo Finance (yfinance)

### News

If a **Serper API key** is configured (see § API Configuration below), recent news articles related to the asset are shown below the charts.

---

## 📈 4. Asset History

On the asset detail page, a **"History"** link is available that shows the historical evolution of your position (quantity, cost, value over time) as Plotly charts.

Direct URL: `/history/<source>/<asset>` (e.g. `/history/b3/ITUB3`)

---

## ➕ 5. Manual Transaction Entry

You can add transactions manually without uploading a file:

1. In the sidebar of any asset, look for **"Add Transaction"** (if available)
2. Fill in:
   - Date
   - Asset
   - Type of movement
   - Quantity
   - Price
3. Click **"Add"**

**Deduplication system** prevents duplicates even in manual entry.

---

## � 6. API Configuration

Go to **http://localhost:5000/config/api** to configure optional services:

### Gemini API Key (Google AI Studio)

Enables AI-assisted ticker resolution: when an asset ticker cannot be identified automatically, the system queries `gemini-2.0-flash` to find the best Yahoo Finance symbol.

1. Get a free key at [Google AI Studio](https://aistudio.google.com/)
2. Paste it in the **Gemini API Key** field and save

### Serper API Key (serper.dev)

Enables a **News** section on every asset detail page, showing recent articles via Google Search.

1. Get a key at [serper.dev](https://serper.dev/)
2. Paste it in the **Serper API Key** field and save

### Cache TTLs

You can adjust how long prices and scraping results are cached:

| Setting | Default | Effect |
|---------|---------|--------|
| Default TTL | 3600 s | Global HTTP cache fallback |
| yfinance TTL | 900 s | Yahoo Finance price data |
| Exchange Rate TTL | 3600 s | USD/BRL rate |
| Scraping TTL | 3600 s | Custom XPath scraping |

Click **Clear Cache** to force an immediate refresh of all cached data.

---

## 📈 Supported Asset Types

### B3 (Brazilian Stocks)

- **Stocks:** `ITUB3`, `VALE3`, `WEGE3`, `BBAS3`, etc.
- **REITs:** `HGLG11`, `HGBS11`, `CSHG11`, etc.
- System automatically adds `.SA` for yfinance

### Crypto

- **Bitcoin:** `BTC` → `BTC-USD` on yfinance → multiplies by BRL/USD rate
- **Ethereum:** `ETH` → `ETH-USD`
- Any yfinance-supported ticker

### USA (Avenue)

- **USA Stocks:** `AAPL`, `GOOGL`, `MSFT`, etc.
- Prices in USD

### Custom

For assets not found on yfinance, the system:
1. Checks `scrape_dict` in `processing.py` for XPath-based price scraping
2. If a Gemini API key is configured, queries `gemini-2.0-flash` for the best Yahoo Finance ticker
3. Falls back to a direct yfinance lookup with the raw ticker string

---

You can upload from:
- Different brokers (B3 + Avenue)
- Different months of the same report
- System will automatically deduplicate

---

## ❓ Frequently Asked Questions

**Q: How is profitability calculated?**  
A: Profitability = (Current Value - Total Cost) / Total Cost × 100%

**Q: Can I edit an already imported transaction?**  
A: Currently no edit interface. Delete the asset and re-import.

**Q: Is my data synchronized to the cloud?**  
A: No. Everything is stored locally in SQLite on your computer.

**Q: Can I backup my data?**  
A: Yes! Copy the `instance/wallet.db` file to a safe location.

**Q: How do I restore a backup?**  
A: Paste the `wallet.db` file in the `instance/` folder and restart the application.

---

## 💾 Backup and Security

### Create Backup

```bash
cp instance/wallet.db instance/wallet.db.backup.$(date +%Y%m%d)
```

### Restore Backup

```bash
cp instance/wallet.db.backup.20240415 instance/wallet.db
./wallet.py
```

### Use Google Drive / Dropbox (optional)

You can sync the `instance/` folder with cloud services:

```bash
ln -s ~/Google\ Drive/wallet-backup instance/wallet.db
```

---

## 📞 Support

For questions or bugs, open an issue on the [GitHub repository](https://github.com/andrenepomuceno/wallet.py).

---

**Tip:** Start with a small upload to familiarize yourself with the platform before importing all your data!
