# Wallet.py

Wallet.py is a Flask-based web application designed for managing and analyzing investment portfolios. It allows users to upload investment data, store it in a SQLite database, and visualize and filter the data through an intuitive web interface.

## Features

- **Upload CSV/XLSX Files**: Easily upload your investment data in CSV or XLSX format.
- **Data Consolidation**: Combine data from multiple sources to get a comprehensive overview of your portfolio.
- **Interactive Visualization**: View detailed information on individual assets and overall portfolio performance.
- **Source-specific Extracts**: Generate extracts for each data source to see detailed transactions and activities.

## Practical Use Cases

1. **Portfolio Management**: Keep track of your investments from various accounts in one place.
2. **Performance Analysis**: Analyze the performance of individual assets and the overall portfolio.
3. **Data Integration**: Seamlessly integrate data from multiple financial sources.
4. **Historical Data Tracking**: Adjust and analyze historical data based on splits and other corporate actions.

## Environment Setup

```shell
git clone git@github.com:andrenepomuceno/wallet.py.git

cd wallet.py

python3 -m venv venv
source venv/bin/activate

pip3 install -r requirements.txt

./wallet.py 
```

Then access the home page at http://localhost:5000

## Example Usage

### Step-by-Step Guide

0. **Get the Data (Example for B3)**
   - Download XLSL/CSV data from (PDF not supported)
   - [Área do Investidor > Extrato > Negociação](https://www.investidor.b3.com.br/extrato/negociacao)
   - [Área do Investidor > Extrato > Movimentação](https://www.investidor.b3.com.br/extrato/movimentacao)

1. **Upload Investment Data**
   - Navigate to the upload section and select your CSV/XLSX files containing investment data.
   - Upload the files to the application.

2. **Consolidate Data**
   - Click on the "Consolidate" button to merge data from different sources.
   - View an overview of your entire investment portfolio.

3. **View Asset Details**
   - Click on individual assets to see detailed information, including historical performance, splits, and other relevant data.

4. **Source-specific Extracts**
   - Generate and view extracts for each data source to review detailed transaction histories and other relevant information.
