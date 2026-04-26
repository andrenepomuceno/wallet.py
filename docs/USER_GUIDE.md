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

**For each asset:**
- Current position quantity
- Current price (real-time via yfinance)
- Total position value
- Profitability (P&L in R$ and %)
- Allocation (% of total portfolio)

**Charts:**
- Allocation by asset type (pie chart)
- Profitability evolution over time

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
- Asset price history
- Shows open, high, low, close

**Profitability Over Time:**
- Evolution of your P&L with this asset

### Fundamentals

If available via Yahoo Finance, shows:
- P/E Ratio
- Dividend Yield
- 52-week Range
- Market Cap

---

## ➕ 4. Manual Transaction Entry

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

For assets not found on yfinance, the system tries:
- XPath scraping (defined in `processing.py`)
- External configurable sources

---

## 🔧 Advanced Configuration

### Enable/Disable Price Sources

Edit `app/processing.py` and the `get_online_info()` function to customize how prices are fetched.

### Price Cache

Prices are cached for 60 minutes by default. To clear cache:

```bash
# Remove yfinance cache files
rm -rf ~/.cache/yfinance
```

### Multiple Uploads

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
