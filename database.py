# database.py

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

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()
logger = logging.getLogger(__name__)

# --- Conexão com o Banco de Dados PostgreSQL ---

# A variável de ambiente agora deve ser a URI de conexão do seu banco PostgreSQL
POSTGRES_URI = os.getenv("POSTGRES_URI")

# Estas variáveis serão exportadas e usadas por outros arquivos (como ranking.py)
engine: Engine = None
players_table: Table = None
db_metadata = MetaData()

# Verifica se a URI de conexão foi fornecida no ambiente
if not POSTGRES_URI:
    logger.critical("A variável de ambiente POSTGRES_URI não foi encontrada! O bot não pode se conectar ao banco de dados.")
else:
    try:
        # Cria o "motor" de conexão com o banco de dados.
        # O SQLAlchemy gerencia um pool de conexões para otimizar o desempenho.
        engine = create_engine(POSTGRES_URI)

        # Define a estrutura da nossa tabela de jogadores.
        # Isto é o equivalente ao schema em um banco de dados relacional.
        players_table = Table(
            "players",
            db_metadata,
            # Usamos BigInteger para o ID do Discord, que é um número grande.
            # É a chave primária da nossa tabela.
            Column("player_id", BigInteger, primary_key=True, autoincrement=False),
            
            # Colunas para estatísticas básicas.
            Column("nome_jogador", String(100), nullable=False),
            Column("partidas_jogadas", Integer, default=0, nullable=False),
            Column("vitorias_totais", Integer, default=0, nullable=False),
            
            # Usamos o tipo JSON (JSONB no PostgreSQL) para armazenar dados flexíveis.
            # É o melhor dos dois mundos: a estrutura de um banco relacional com
            # a flexibilidade de um banco NoSQL para campos específicos.
            Column("vitorias_por_papel", JSON, default={}, nullable=False),
            Column("medalhas", JSON, default=[], nullable=False),
        )

        # Tenta se conectar ao banco de dados e criar a tabela se ela ainda não existir.
        # O método create_all é "idempotente", o que significa que ele só cria a tabela
        # se ela não for encontrada, sendo seguro executá-lo a cada inicialização do bot.
        with engine.connect() as connection:
            db_metadata.create_all(connection)
            logger.info("Conexão com o PostgreSQL estabelecida e tabela 'players' garantida!")

    except Exception as e:
        # Se qualquer erro ocorrer durante a conexão ou configuração da tabela,
        # logamos o erro crítico e deixamos as variáveis 'engine' e 'players_table' como None.
        logger.critical(f"Falha ao conectar com o PostgreSQL ou configurar a tabela: {e}", exc_info=True)
        engine = None
        players_table = None