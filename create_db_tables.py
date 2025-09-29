import os
import stat
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

# Carrega as variáveis de ambiente (como a POSTGRES_URI)
load_dotenv()

print("Iniciando script de criação de tabelas...")

# --- Lógica de Conexão (copiada do seu database.py) ---
POSTGRES_URI = os.getenv("POSTGRES_URI")

if not POSTGRES_URI:
    print("ERRO CRÍTICO: A variável de ambiente POSTGRES_URI não foi encontrada!")
    exit()

# Ajuste de permissões para a chave SSL
KEY_FILE_PATH = 'private-key.key'
if os.path.exists(KEY_FILE_PATH):
    try:
        os.chmod(KEY_FILE_PATH, stat.S_IRUSR | stat.S_IWUSR)
        print(f"Permissões do arquivo '{KEY_FILE_PATH}' ajustadas.")
    except Exception as e:
        print(f"Aviso: Não foi possível alterar as permissões do arquivo de chave: {e}")

# Argumentos de conexão SSL
ssl_args = {
    'sslmode': 'verify-full',
    'sslrootcert': 'ca-certificate.crt',
    'sslcert': 'ca-certificate.crt',
    'sslkey': KEY_FILE_PATH
}

try:
    # Conecta ao banco de dados
    engine = create_engine(POSTGRES_URI, connect_args=ssl_args)
    db_metadata = MetaData()

    # --- Definição de TODAS as tabelas (players e guilds) ---
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

    # --- Comando Mágico ---
    # Isso irá verificar o banco de dados. Se a tabela 'players' já existe, não fará nada.
    # Se a tabela 'guilds' não existe, ela será criada.
    print("Sincronizando metadados com o banco de dados...")
    db_metadata.create_all(engine)

    print("✅ Sucesso! Todas as tabelas foram criadas ou já existem.")
    print("Você já pode voltar o arquivo principal para 'main.py' e reiniciar a aplicação.")

except Exception as e:
    print(f"❌ Falha ao criar as tabelas: {e}")