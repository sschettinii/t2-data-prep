import os
import requests
import urllib.request
from ftplib import FTP
import pandas as pd
import pyreaddbc
from dbfread import DBF
import zipfile
import json
import time
from functools import wraps
from tqdm import tqdm
import pyarrow as pa
import pyarrow.parquet as pq

BASE_DIR = os.path.dirname(os.path.abspath(__file__)) 
PASTA_AUXILIARES = os.path.join(BASE_DIR, 'arq auxiliares')
PASTA_BRUTOS = os.path.join(BASE_DIR, 'dados brutos')

os.makedirs(PASTA_AUXILIARES, exist_ok=True)
os.makedirs(PASTA_BRUTOS, exist_ok=True)

def medir_tempo(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        inicio = time.time()
        resultado = func(*args, **kwargs)
        fim = time.time()
        tempo_total = fim - inicio
        print(f"  -> ⏱️ Tempo de execução: {tempo_total:.2f} segundos.")
        return resultado
    return wrapper

@medir_tempo
def ingerir_ibge():
    print("\n[1/4] Ingerindo dados brutos do IBGE...")
    caminho_saida = os.path.join(PASTA_BRUTOS, 'municipios_ibge.json')
    
    if os.path.exists(caminho_saida):
        print(f"  -> [IGNORADO] O arquivo final 'municipios_ibge.json' já existe. Pulando etapa.")
        return

    url = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        if response.status_code == 200:
            dados_json = response.json()
            with open(caminho_saida, 'w', encoding='utf-8') as f:
                json.dump(dados_json, f, ensure_ascii=False, indent=4)
            print(f"  -> Sucesso! JSON bruto do IBGE salvo.")
        else:
            print(f"  -> [X] Erro na API do IBGE: {response.status_code}")
    except Exception as e:
        print(f"  -> [X] Erro na ingestão do IBGE: {e}")

@medir_tempo
def ingerir_snis():
    print("\n[2/4] Processando dados brutos do SNIS (Saneamento)...")
    arquivo_gz = os.path.join(PASTA_AUXILIARES, "br_mdr_snis_municipio_agua_esgoto.csv.gz")
    caminho_saida = os.path.join(PASTA_BRUTOS, 'snis_saneamento_bruto.csv')

    if os.path.exists(caminho_saida):
        print(f"  -> [IGNORADO] O arquivo final 'snis_saneamento_bruto.csv' já existe. Pulando etapa.")
        return

    try:
        if not os.path.exists(arquivo_gz):
            print(f"  -> [X] Erro: O arquivo local '{arquivo_gz}' não foi encontrado!")
            print("         Por favor, faça o download manual e coloque-o na pasta 'arq auxiliares'.")
            return
        
        print("  -> Arquivo compactado encontrado localmente no repositório.")
        print("  -> Extraindo e convertendo para o diretório de dados brutos...")
        
        df_saneamento = pd.read_csv(arquivo_gz, compression='gzip', sep=',', encoding='utf-8')
        df_saneamento.to_csv(caminho_saida, index=False)
        print(f"  -> Sucesso! CSV bruto do SNIS extraído e salvo.")
        
    except Exception as e:
        print(f"  -> [X] Erro no processamento do SNIS: {e}")

@medir_tempo
def ingerir_inmet():
    print("\n[3/4] Ingerindo dados brutos do INMET (Clima)...")
    arquivo_zip = os.path.join(PASTA_AUXILIARES, "inmet_2024.zip")
    pasta_destino = os.path.join(PASTA_BRUTOS, "clima_2024_bruto")
    
    if os.path.exists(pasta_destino) and len(os.listdir(pasta_destino)) > 0:
        print(f"  -> [IGNORADO] A pasta de clima 'clima_2024_bruto' já contém os dados extraídos. Pulando etapa.")
        return

    url_inmet = "https://portal.inmet.gov.br/uploads/dadoshistoricos/2024.zip"
    os.makedirs(pasta_destino, exist_ok=True)
    try:
        if not os.path.exists(arquivo_zip):
            print("  -> Baixando ZIP histórico do INMET (Pode demorar alguns minutos)...")
            req = urllib.request.Request(url_inmet, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response, open(arquivo_zip, 'wb') as out_file:
                out_file.write(response.read())
        else:
            print("  -> Arquivo ZIP auxiliar já existente.")

        print("  -> Extraindo arquivos CSV brutos das estações meteorológicas...")
        with zipfile.ZipFile(arquivo_zip, 'r') as zip_ref:
            zip_ref.extractall(pasta_destino)
        print(f"  -> Sucesso! Arquivos climáticos extraídos.")
    except Exception as e:
        print(f"  -> [X] Erro no INMET: {e}")

@medir_tempo
def ingerir_datasus():
    print("\n[4/4] Ingerindo dados brutos do DataSUS (Dengue Brasil)...")
    caminho_saida = os.path.join(PASTA_BRUTOS, 'dengue_brasil_2024_bruto.parquet')

    if os.path.exists(caminho_saida):
        print(f"  -> [IGNORADO] O arquivo final 'dengue_brasil_2024_bruto.parquet' já existe. Pulando etapa.")
        return

    nome_arquivo = "DENGBR24" 
    arquivo_dbc = os.path.join(PASTA_AUXILIARES, f"{nome_arquivo}.dbc")
    arquivo_dbf = os.path.join(PASTA_AUXILIARES, f"{nome_arquivo}.dbf")
    
    try:
        if not os.path.exists(arquivo_dbc):
            print(f"  -> Baixando {nome_arquivo}.dbc via FTP (Arquivo nacional completo)...")
            ftp = FTP("ftp.datasus.gov.br")
            ftp.login()
            
            try:
                ftp.cwd("/dissemin/publicos/SINAN/DADOS/FINAIS/")
            except:
                ftp.cwd("/dissemin/publicos/SINAN/DADOS/PRELIM/")
                
            with open(arquivo_dbc, 'wb') as f:
                ftp.retrbinary(f"RETR {nome_arquivo}.dbc", f.write)
            ftp.quit()
            print("  -> Download do .dbc concluído.")

        if not os.path.exists(arquivo_dbf):
            print("  -> Convertendo arquivo proprietário .dbc para .dbf...")
            pyreaddbc.dbc2dbf(arquivo_dbc, arquivo_dbf)

        print("  -> Lendo DBF e convertendo para Parquet (100% String para evitar quebra de Schema)...")
        tabela_dbf = DBF(arquivo_dbf, encoding='iso-8859-1', load=False)
        
        tamanho_lote = 250000
        lote_atual = []
        escritor_parquet = None
        esquema_base = None
        total_registros = 0

        for registro in tqdm(tabela_dbf, desc="  -> Progresso", unit=" registros"):
            lote_atual.append(registro)
            total_registros += 1

            if len(lote_atual) >= tamanho_lote:
                df_lote = pd.DataFrame(lote_atual)
                
                # ==========================================================
                # O TRUQUE DA CAMADA BRONZE: Tudo vira texto puro.
                # 1. Preenche valores vazios do DBF com string vazia
                # 2. Força todas as colunas a serem tratadas como texto
                # 3. Limpa literais "None" ou "nan" que o Pandas possa criar
                # ==========================================================
                df_lote = df_lote.fillna('')
                df_lote = df_lote.astype(str)
                df_lote = df_lote.replace(to_replace=['nan', 'None', '<NA>'], value='')

                if escritor_parquet is None:
                    tabela_arrow = pa.Table.from_pandas(df_lote)
                    esquema_base = tabela_arrow.schema
                    escritor_parquet = pq.ParquetWriter(caminho_saida, esquema_base)
                else:
                    tabela_arrow = pa.Table.from_pandas(df_lote, schema=esquema_base)

                escritor_parquet.write_table(tabela_arrow)
                lote_atual = []

        if len(lote_atual) > 0:
            df_lote = pd.DataFrame(lote_atual)
            
            df_lote = df_lote.fillna('')
            df_lote = df_lote.astype(str)
            df_lote = df_lote.replace(to_replace=['nan', 'None', '<NA>'], value='')
            
            if escritor_parquet is None:
                tabela_arrow = pa.Table.from_pandas(df_lote)
                esquema_base = tabela_arrow.schema
                escritor_parquet = pq.ParquetWriter(caminho_saida, esquema_base)
            else:
                tabela_arrow = pa.Table.from_pandas(df_lote, schema=esquema_base)
                
            escritor_parquet.write_table(tabela_arrow)

        if escritor_parquet:
            escritor_parquet.close()

        print(f"  -> Sucesso! Dados brutos da dengue salvos em Parquet ({total_registros} registros no total).")
        
    except Exception as e:
        print(f"  -> [X] Erro no DataSUS: {e}")


if __name__ == "__main__":
    print("="*65)
    print(" PIPELINE DE INGESTÃO (CAMADA RAW) - DADOS BRASIL 2024")
    print("="*65)
    
    inicio_pipeline = time.time()
    
    ingerir_ibge()
    ingerir_snis()
    ingerir_inmet()
    ingerir_datasus()
    
    fim_pipeline = time.time()
    
    print("\n" + "="*65)
    print(f" INGESTÃO FINALIZADA EM {(fim_pipeline - inicio_pipeline):.2f} SEGUNDOS!")
    print(" Todos os dados brutos estão disponíveis.")
    print("="*65)