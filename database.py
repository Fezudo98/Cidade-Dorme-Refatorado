# database.py

import pymongo
import os
import logging
import certifi # Importa a biblioteca de certificados
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# --- Conexão com o Banco de Dados ---

MONGO_URI = os.getenv("MONGO_URI")

db_client = None
db_collection = None

if not MONGO_URI:
    logger.critical("A variável de ambiente MONGO_URI não foi encontrada! O bot não pode se conectar ao banco de dados.")
else:
    try:
        # >>> MUDANÇA CRÍTICA AQUI <<<
        # Adicionamos os parâmetros tls=True e tlsCAFile para forçar uma conexão segura
        # usando o certificado que baixamos.
        
        # O nome do arquivo deve ser exatamente o que você colocou na pasta raiz.
        ca_file = 'ca-certificate.pem'

        db_client = pymongo.MongoClient(
            MONGO_URI,
            tls=True,
            tlsCAFile=ca_file
        )
        
        db_client.admin.command('ping')
        logger.info("Conexão SEGURA com o MongoDB estabelecida com sucesso!")
        
        database = db_client["cidade_dorme_db"]
        db_collection = database["players"]

    except Exception as e:
        logger.critical(f"Falha ao conectar com o MongoDB: {e}", exc_info=True)
        db_client = None
        db_collection = None