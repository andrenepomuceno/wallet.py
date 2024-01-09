# Wallet App

O Wallet App é uma aplicação web desenvolvida em Flask para gerenciar e analisar uma carteira de investimentos. Permite o upload de dados de investimento e fornece funcionalidades para visualização e filtragem destes dados.

## Recursos

- Upload de arquivos CSV/XLSX com dados de investimentos.
- Armazenamento de dados em banco de dados SQLite.
- Visualização e filtragem de dados de investimentos.
- Interface web para interação com o usuário.

## Dependências

- Flask
- SQLAlchemy
- Pandas
- Yahoo Finance

## Configuração do Ambiente

```shell
cd wallet.js

python3 -m venv venv
source venv/bin/activate

pip3 install -r requirements.txt

./wallet.js
```

Então acesse a página inicial em `http://localhost:5000`