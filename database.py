# database.py (VERSÃO FINAL - CORRIGIDA COM SEUS NOMES DE ARQUIVO)

import os
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
)
from sqlalchemy.engine import Engine

load_dotenv()
logger = logging.getLogger(__name__)

# --- Conexão com o Banco de Dados PostgreSQL ---

POSTGRES_URI = os.getenv("POSTGRES_URI")

engine: Engine = None
players_table: Table = None
db_metadata = MetaData()

if not POSTGRES_URI:
    logger.critical("A variável de ambiente POSTGRES_URI não foi encontrada!")
else:
    try:
        # --- MUDANÇA CRÍTICA AQUI ---
        # O dicionário 'connect_args' foi atualizado para usar os nomes
        # EXATOS dos arquivos que você baixou.
        
        ssl_args = {
            'sslmode': 'verify-full',
            # Certificado Raiz (CA)
            'sslrootcert': 'ca-certificate.crt', 
            # Certificado do Cliente (usando o mesmo arquivo .crt)
            'sslcert': 'ca-certificate.crt', 
            # Chave Privada do Cliente
            'sslkey': 'private-key.key'    
        }

        engine = create_engine(
            POSTGRES_URI,
            connect_args=ssl_args
        )

        # O resto do arquivo permanece o mesmo...
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

        with engine.connect() as connection:
            db_metadata.create_all(connection)
            logger.info("Conexão SEGURA com o PostgreSQL estabelecida e tabela 'players' garantida!")

    except Exception as e:
        logger.critical(f"Falha ao conectar com o PostgreSQL: {e}", exc_info=True)
        engine = None
        players_table = None