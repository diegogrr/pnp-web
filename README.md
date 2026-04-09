# pnp-web

Aplicação web para geração de tabelas da **Fase 2: Diagnóstico Quantitativo - Acesso, Permanência e Êxito** do IFSP.
Converte a lógica originalmente desenvolvida em Jupyter Notebook em uma interface acessível para usuários não técnicos, permitindo selecionar unidade e curso e obter as tabelas prontas para visualização ou exportação em Excel.

---

## Funcionalidades

- Seleção de unidade de ensino e curso a partir dos dados disponíveis
- Geração de tabelas de **Matrícula**, **Conclusão**, **Evasão**, **Retenção** e **Eficiência**
- Estratificação por Cor/Raça, Renda Familiar, Sexo e Faixa Etária
- Visualização das tabelas diretamente no navegador
- Exportação para `.xlsx` usando a planilha-modelo oficial

---

## Estrutura do projeto

```
pnp-web/
├── app/
│   ├── __init__.py        # Factory da aplicação Flask (create_app)
│   ├── routes.py          # Endpoints da API REST
│   ├── processor.py       # Pipeline de processamento dos dados (lógica do notebook)
│   └── templates/
│       └── index.html     # Interface web (HTML + CSS + JS puro)
├── data/
│   ├── pnp_ifsp_20192024.parquet   # Base de dados PNP IFSP 2019–2024
│   └── Planilha_Modelo.xlsx        # Template de saída para exportação
├── config.py              # Configuração centralizada de caminhos
├── requirements.txt       # Dependências Python
├── Dockerfile
└── docker-compose.yml
```

### Arquivos principais do backend

| Arquivo | Função |
|---|---|
| `config.py` | Único ponto de configuração de caminhos. Define `PARQUET_PATH` e `MODELO_PATH` a partir do diretório raiz. |
| `app/__init__.py` | Cria e configura a instância Flask via `create_app()`, registrando o blueprint de rotas. |
| `app/routes.py` | Define os endpoints REST: listagem de unidades e cursos, processamento e exportação. Faz a ponte entre o frontend e o `processor.py`. |
| `app/processor.py` | Contém toda a lógica de negócio extraída do notebook original. As funções `processar()` e `exportar_xlsx()` orquestram o pipeline completo de geração das tabelas. **Não deve ter sua lógica alterada.** |

### Endpoints

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/` | Página principal (frontend) |
| `GET` | `/unidades` | Lista todas as unidades disponíveis |
| `GET` | `/cursos?unidade=<nome>` | Lista os cursos de uma unidade |
| `POST` | `/processar` | Executa o pipeline; retorna as tabelas em JSON |
| `POST` | `/exportar` | Executa o pipeline e retorna o arquivo `.xlsx` |

---

## Execução com Docker

### Pré-requisitos

- [Docker](https://docs.docker.com/get-docker/) instalado
- [Docker Compose](https://docs.docker.com/compose/) (já incluso no Docker Desktop)

### Subir a aplicação

```bash
docker-compose up --build
```

A aplicação ficará disponível em `http://localhost:5005`.

### Parar a aplicação

```bash
docker-compose down
```

> O serviço está configurado com `restart: unless-stopped`, ou seja, reinicia automaticamente após reinicializações do sistema até que seja parado manualmente.

---

## Execução local (sem Docker)

```bash
pip install -r requirements.txt
flask --app app run --debug
```

Acesse em `http://localhost:5000`.

---

## Dados

Os arquivos em `data/` são de **domínio público**, provenientes do sistema [Plataforma Nilo Peçanha](https://www.plataformanilopecanha.org/):

- `pnp_ifsp_20192024.parquet` — microdados de matrículas do IFSP entre 2019 e 2024
- `Planilha_Modelo.xlsx` — template com a estrutura de abas e formatação do relatório final

---

## Créditos

A lógica de processamento e os critérios de classificação dos indicadores foram concebidos originalmente pelo **Prof. Nilson** (IFSP), no notebook Python `GeraTabelasPNP.ipynb`.
Este projeto converte essa lógica em uma aplicação web acessível, sem alterar nenhuma regra de negócio ou fórmula do trabalho original.
