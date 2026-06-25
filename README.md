# Pipeline de Preparação de Dados - Surtos de Dengue PR 2024

Este repositório contém a esteira automatizada de ingestão, tratamento e integração de dados para modelagem preditiva de risco de surtos de dengue no estado do Paraná.

## Fontes Originais dos Dados (Públicos)
- **Epidemiologia (DataSUS/SINAN):** Notificações brutas de Dengue. 
- **Saneamento (SNIS/MDR):** Indicadores de infraestrutura urbana, rede de água e esgoto por município. 
- **Climatologia (INMET):** Séries históricas horárias de temperatura, umidade e precipitação das estações automáticas. [Portal de Dados do INMET](https://portal.inmet.gov.br/).
- **Geografia (IBGE):** Malha municipal e metadados via API de Localidades. 

## Estrutura do Repositório
- `data/pipeline_ingestao.py`: Script orquestrador único que gerencia o download, extração e conversão de todas as fontes.
- `data/arq auxiliares/`: Pasta local para o armazenamento de arquivos pesados temporários ou comprimidos (ignorada pelo Git).
- `data/dados brutos/`: Pasta local para o armazenamento dos DataFrames e CSVs limpos prontos para análise (ignorada pelo Git).
- `data/eda.ipynb`: Notebook com a Análise Exploratória de Dados.

## Como Executar e Reconstruir o Ambiente Local
Para manter a performance do repositório, os arquivos de dados (que ultrapassam gigabytes) não são versionados no histórico do Git. Para gerar a base de dados completa localmente na sua máquina, basta executar o pipeline automatizado.

### 1. Instale as dependências:
```bash
pip install pandas numpy pyreaddbc dbfread pyarrow requests
```

### 2. Execute a Esteira de Integração:
O script abaixo fará o download automático das fontes do governo, converterá arquivos proprietários, realizará as filtragens necessárias e salvará as tabelas prontas na pasta dados brutos.

```bash
python3 "data/pipeline_ingestao.py"
```

Nota: A etapa do DataSUS realiza o download de milhões de registros em formato comprimido via FTP. Dependendo da conexão e do servidor público, a execução total do script pode levar alguns minutos.

Após a conclusão com sucesso do script, você poderá abrir e executar o notebook data/eda.ipynb normalmente.