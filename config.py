# config.py

import os
import json
import logging

logger = logging.getLogger(__name__)

# --- LÓGICA DE CAMINHO ROBUSTA ---
# Constrói caminhos a partir da localização deste arquivo, não do diretório de trabalho.
# Isso garante que o bot encontre os arquivos em qualquer sistema (local, Discloud, etc.).
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _load_game_configs():
    """Carrega as configurações de jogo de um arquivo JSON."""
    # Usa o caminho base para encontrar o arquivo de configuração
    config_file_path = os.path.join(_BASE_DIR, "game_configs.json")
    try:
        with open(config_file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.critical("Erro: O arquivo 'game_configs.json' não foi encontrado. O bot não pode funcionar sem ele.")
        exit()
    except json.JSONDecodeError:
        logger.critical("Erro: O arquivo 'game_configs.json' está mal formatado. Corrija o JSON.")
        exit()
    except Exception as e:
        logger.critical(f"Erro inesperado ao carregar 'game_configs.json': {e}")
        exit()

# Carrega as configurações do JSON
_game_configs = _load_game_configs()

# === Discord Bot Token ===
BOT_TOKEN = os.getenv("BOT_TOKEN", "SEU_TOKEN_AQUI_COMO_FALLBACK")

# === Caminhos para Arquivos e Pastas (AGORA ROBUSTOS) ===
ASSETS_PATH = os.path.join(_BASE_DIR, "assets")
IMAGES_PATH = os.path.join(ASSETS_PATH, "images")
AUDIO_PATH = os.path.join(ASSETS_PATH, "audio")
DATA_PATH = os.path.join(_BASE_DIR, "data")
RANKING_FILE = os.path.join(DATA_PATH, "ranking.json")


# === Configuração de Imagens de Evento ===
EVENT_IMAGES = {
    "NIGHT_START": "night.png",
    "DAY_SAFE": "day_safe.png",
    "DAY_DEATH": "day_death.png",
    "DAY_REVIVAL": "day_revival.png",
    "PLAGUE_KILL": "plague_kill.png",
    "CITY_WIN": "city_win.png",
    "VILLAINS_WIN": "villains_win.png",
    "CLOWN_WIN": "clown_win.png",
    "LOVERS_WIN": "lovers_win.png",
    "PLAGUE_WIN": "plague_win.png",
    "CORRUPTOR_WIN": "corruptor_win.png",
    "HEADHUNTER_WIN": "headhunter_win.png",
}

# === Configurações do Jogo (carregadas do JSON) ===
MIN_PLAYERS = 5
MAX_PLAYERS = 16
NIGHT_DURATION_SECONDS = 60
DAY_DISCUSSION_DURATION_SECONDS = 45
VOTE_DURATION_SECONDS = 30
MAX_GAME_NIGHTS = 7
GAME_COMPOSITIONS = _game_configs.get("GAME_COMPOSITIONS", {})
ROLE_POOL = _game_configs.get("ROLE_POOL", {})
HUMOR_MESSAGES = _game_configs.get("HUMOR_MESSAGES", {})


# === Configuração de Áudios ===
AUDIO_ENABLED = True
AUDIO_FILES = {
    "DAY_START": ["day_start.mp3"],
    "NIGHT_START": ["night_start.mp3"],
    "VOTE_START": ["vote_start.mp3"],
    "CITY_WIN": ["city_win.mp3"],
    "VILLAINS_WIN": ["villains_win.mp3"],
    "SHERIFF_WIN": ["sheriff_win.mp3"],
    "GAME_LOSE": ["game_lose.mp3"],
    "SHERIFF_SHOT": ["sheriff_shot.mp3"],
    "PLAYER_DEATH": ["player_death_1.mp3", "player_death_2.mp3", "player_death_3.mp3"],
    "PLAYER_REVIVE": ["player_revive.mp3"],
    "PROTECTION_SUCCESS": ["protection_success.mp3"],
    "CLOWN_WIN": ["clown_win.mp3"],
    "LOVERS_WIN": ["lovers_win.mp3"],
    "PLAGUE_WIN": ["plague_win.mp3"],
    "CORRUPTOR_WIN": ["corruptor_win.mp3"],
    "HEADHUNTER_WIN": ["headhunter_win.mp3"],
}

# === Mensagens ===
MSG_BOT_STARTING = "Ligando os motores... e me preparando para gerenciar múltiplas realidades de treta!"
MSG_CREDITS = (
    "Espero que tenha gostado da partida!\n"
    "Este bot foi desenvolvido com ❤️ por **Fernando Sérgio**.\n\n"
    "**Gostou do bot?**\n"
    "> Colabore com o desenvolvedor e tenha seu nome eternizado no projeto!\n"
    "> Apoie em: **https://ko-fi.com/fezudo98**\n\n"
    "Dúvidas, sugestões ou reporte de bugs, procure o desenvolvedor:\n"
    "> **GitHub:** Fezudo98\n"
    "> **Discord:** feezudo\n"
    "> **Instagram:** sergioo_1918\n"
    "> **LinkedIn:** [Clique aqui](https://www.linkedin.com/in/fernando-sergio-786560373)"
)

# === Versão do Bot ===
def get_bot_version():
    """Lê a versão do arquivo version.txt."""
    # Usa o caminho base para encontrar o arquivo de versão
    version_file_path = os.path.join(_BASE_DIR, 'version.txt')
    try:
        with open(version_file_path, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        logger.warning("Arquivo 'version.txt' não encontrado. Usando 'dev' como versão.")
        return "dev" # Retorna um placeholder se o arquivo não for encontrado
    
    # === ID do Canal para Hospedagem de Cards ===
CARD_HOSTING_CHANNEL_ID = 1420614970999046154

BOT_VERSION = get_bot_version()