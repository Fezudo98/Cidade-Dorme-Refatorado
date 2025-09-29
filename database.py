# database.py (VERSÃO FINAL - CORRIGIDA COM AJUSTE DE PERMISSÕES)

import os
import stat # Módulo para ajudar a definir permissões
import logging
from dotenv import load_dotenv
from sqlalchemy import (
    create_engine,
    Table,
    Column,
    MetaData,
    BigInteger,
    String,
    Integer,
    JSON,
    Boolean
)
from sqlalchemy.engine import Engine

load_dotenv()
logger = logging.getLogger(__name__)

# --- Conexão com o Banco de Dados PostgreSQL ---

POSTGRES_URI = os.getenv("POSTGRES_URI")

engine: Engine = None
players_table: Table = None
guilds_table: Table = None
db_metadata = MetaData()

if not POSTGRES_URI:
    logger.critical("A variável de ambiente POSTGRES_URI não foi encontrada!")
else:
    # --- NOVO BLOCO DE CÓDIGO: AJUSTE DE PERMISSÕES ---
    # Antes de tentar conectar, vamos garantir que a chave privada está segura.
    KEY_FILE_PATH = 'private-key.key'
    try:
        if os.path.exists(KEY_FILE_PATH):
            # Define as permissões para 0600 (apenas o dono pode ler e escrever)
            os.chmod(KEY_FILE_PATH, stat.S_IRUSR | stat.S_IWUSR)
            logger.info(f"Permissões do arquivo '{KEY_FILE_PATH}' ajustadas para 0600.")
    except Exception as e:
        logger.error(f"Não foi possível alterar as permissões do arquivo de chave: {e}")
    # ---------------------------------------------------

    try:
        ssl_args = {
            'sslmode': 'verify-full',
            'sslrootcert': 'ca-certificate.crt', 
            'sslcert': 'ca-certificate.crt', 
            'sslkey': KEY_FILE_PATH
        }

        engine = create_engine(
            POSTGRES_URI,
            connect_args=ssl_args
        )

        players_table = Table(
            "players",
            db_metadata,
            Column("player_id", BigInteger, primary_key=True, autoincrement=False),
            Column("nome_jogador", String(100), nullable=False),
            Column("partidas_jogadas", Integer, default=0, nullable=False),
            Column("vitorias_totais", Integer, default=0, nullable=False),
            Column("vitorias_por_papel", JSON, default={}, nullable=False),
            Column("medalhas", JSON, default=[], nullable=False),
        )

        guilds_table = Table(
            "guilds",
            db_metadata,
            Column("guild_id", BigInteger, primary_key=True, autoincrement=False),
            Column("setup_message_sent", Boolean, default=False, nullable=False),
        )

        with engine.connect() as connection:
            db_metadata.create_all(connection)
            logger.info("Conexão SEGURA com o PostgreSQL estabelecida e tabela 'players' garantida!")

    except Exception as e:
        logger.critical(f"Falha ao conectar com o PostgreSQL: {e}", exc_info=True)
        engine = None
        players_table = None