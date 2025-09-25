# database.py

import pymongo
import os
import logging
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env (especialmente útil para desenvolvimento local)
load_dotenv()

# Inicializa o logger para este módulo
logger = logging.getLogger(__name__)

# --- Conexão com o Banco de Dados ---

# 1. Pega a URI de conexão da variável de ambiente que configuramos na Square Cloud
MONGO_URI = os.getenv("mongodb://default:2abIFuPjHOqfkDFIZhazxZ4U@square-cloud-db-75614e75124a45ad898663cfe8e71178.squareweb.app:7037")

# Inicializa as variáveis como None. Se a conexão falhar, elas permanecerão assim.
db_client = None
db_collection = None

# 2. Verifica se a URI foi encontrada
if not MONGO_URI:
    logger.critical("A variável de ambiente MONGO_URI não foi encontrada! O bot não pode se conectar ao banco de dados.")
    # O bot continuará rodando, mas o Cog de Ranking se desativará.
else:
    try:
        # 3. Tenta criar um cliente MongoDB. Esta conexão será reutilizada em todo o bot.
        # É muito mais eficiente do que conectar e desconectar a cada comando.
        db_client = pymongo.MongoClient(MONGO_URI)
        
        # 4. Envia um comando 'ping' para o banco. Se isso não gerar uma exceção,
        # significa que a conexão foi estabelecida com sucesso.
        db_client.admin.command('ping')
        logger.info("Conexão com o MongoDB estabelecida com sucesso!")
        
        # 5. Aponta para o banco de dados e a coleção específicos que usaremos.
        # Se eles não existirem, o MongoDB os criará automaticamente na primeira vez
        # que inserirmos dados.
        database = db_client["cidade_dorme_db"]
        db_collection = database["players"]

    except Exception as e:
        # 6. Se qualquer erro ocorrer durante a conexão (URI errada, firewall, etc.),
        # captura a exceção e registra uma mensagem de erro crítica.
        logger.critical(f"Falha ao conectar com o MongoDB: {e}", exc_info=True)
        # Garante que as variáveis permaneçam como None para que o resto do bot saiba que a conexão falhou.
        db_client = None
        db_collection = None