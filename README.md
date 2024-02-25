# wallet.py

wallet.py is a web application developed in Python to manage and analyze an investment portfolio. It allows the upload of investment data and provides functionalities for viewing and filtering this data.

## Features

- Upload of CSV/XLSX files with investment data.
- Data storage in SQLite database.
- Visualization and filtering of investment data.
- Web interface for user interaction.

## Dependencies

- Flask
- SQLAlchemy
- Pandas
- Yahoo Finance

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

## Uploading Data

Download XLSL/CSV data from (PDF not supported)

[Área do Investidor > Extrato > Negociação](https://www.investidor.b3.com.br/extrato/negociacao)

[Área do Investidor > Extrato > Movimentação](https://www.investidor.b3.com.br/extrato/movimentacao)