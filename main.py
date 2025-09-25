# main.py

import discord
from discord.ext import commands
import os
import asyncio
import logging
from typing import Dict, Optional, TYPE_CHECKING

# Importa a classe GameInstance apenas para checagem de tipos
# Evita importação circular em tempo de execução
if TYPE_CHECKING:
    from cogs.game_instance import GameInstance

# Carrega as variáveis de ambiente (necessário para o BOT_TOKEN)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("Aviso: python-dotenv não está instalado. O bot tentará carregar o token do config.py.")

# Importa as configurações globais
try:
    import config
except ImportError:
    print("Erro: Arquivo config.py não encontrado.")
    exit()

# Configuração básica de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s:%(levelname)s:%(name)s: %(message)s')
logger = logging.getLogger('discord')

# --- O Game Manager ---
class GameManager:
    """Gerencia todas as instâncias de jogos ativas no bot."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.games: Dict[int, 'GameInstance'] = {}
        self.player_game_map: Dict[int, int] = {}
        logger.info("GameManager inicializado com sucesso.")

    def create_game(self, text_channel: discord.TextChannel, voice_channel: discord.VoiceChannel, game_master: discord.Member) -> Optional['GameInstance']:
        from cogs.game_instance import GameInstance # Importação local para uso em tempo de execução
        if text_channel.id in self.games:
            logger.warning(f"Tentativa de criar um jogo no canal {text_channel.id} onde um já existe.")
            return None
        new_game = GameInstance(self.bot, text_channel, voice_channel, game_master)
        self.games[text_channel.id] = new_game
        return new_game

    def get_game(self, channel_id: int) -> Optional['GameInstance']:
        return self.games.get(channel_id)

    def get_game_by_player(self, player_id: int) -> Optional['GameInstance']:
        channel_id = self.player_game_map.get(player_id)
        if channel_id:
            return self.get_game(channel_id)
        return None

    def map_player_to_game(self, player_id: int, channel_id: int):
        self.player_game_map[player_id] = channel_id
        logger.debug(f"Jogador {player_id} mapeado para o jogo no canal {channel_id}")

    def end_game(self, channel_id: int):
        if channel_id in self.games:
            game_to_end = self.games[channel_id]
            player_ids_in_game = list(game_to_end.players.keys())
            for player_id in player_ids_in_game:
                if player_id in self.player_game_map:
                    del self.player_game_map[player_id]
            del self.games[channel_id]
            logger.info(f"Jogo no canal {channel_id} finalizado e removido do manager.")
        else:
            logger.warning(f"Tentativa de finalizar um jogo inexistente no canal {channel_id}.")

# Define as intenções (Intents) - mantendo as que precisamos
intents = discord.Intents.default()
intents.voice_states = True
intents.messages = True
intents.message_content = True
# A intent de members é necessária para buscar membros, mesmo sem cache
intents.members = True 

# Cria um objeto de flags de cache e habilita o cache APENAS para membros em voz.
# Isso nos dá o melhor de dois mundos: baixo consumo de RAM e detecção de jogadores.
cache_flags = discord.MemberCacheFlags.none()
cache_flags.voice = True

# Inicializa o bot com o cache inteligente
bot = discord.Bot(
    intents=intents,
    member_cache_flags=cache_flags
)
bot.game_manager = GameManager(bot)


# --- Carregamento dos Cogs ---
cogs_dir = os.path.join(os.path.dirname(__file__), "cogs")
logger.info(f'Carregando extensões do diretório: {cogs_dir}')
if not os.path.isdir(cogs_dir):
    logger.error(f"Diretório de Cogs não encontrado: {cogs_dir}")
else:
    for filename in os.listdir(cogs_dir):
        # NOVA CONDIÇÃO: Ignora 'game_instance.py'
        if filename.endswith('.py') and not filename.startswith('__') and filename != 'game_instance.py': 
            cog_name = f'cogs.{filename[:-3]}'
            try:
                bot.load_extension(cog_name)
                logger.info(f'Cog {cog_name} carregado com sucesso.')
            except Exception as e:
                logger.error(f'Falha ao carregar cog {cog_name}: {e}', exc_info=True)

# --- Eventos do Bot ---
@bot.event
async def on_ready():
    logger.info(f'Bot conectado como {bot.user.name} (ID: {bot.user.id})')
    logger.info(f'Usando discord.py versão {discord.__version__}')
    logger.info(config.MSG_BOT_STARTING)
    try:
        await bot.sync_commands()
        logger.info('Comandos sincronizados globalmente com sucesso.')
    except Exception as e:
        logger.error(f'Falha ao sincronizar comandos globalmente: {e}')
    await bot.change_presence(activity=discord.Game(name="Cidade Dorme | /preparar"))

@bot.event
async def on_application_command_error(ctx: discord.ApplicationContext, error: discord.DiscordException):
    if isinstance(error, commands.errors.CheckFailure):
        await ctx.respond("Você não tem permissão ou não está na fase correta do jogo.", ephemeral=True)
    elif isinstance(error, commands.errors.CommandNotFound):
        await ctx.respond("Comando não encontrado. 🤔", ephemeral=True)
    elif isinstance(error, commands.errors.MissingRequiredArgument):
         await ctx.respond(f"Está faltando um argumento obrigatório: `{error.param.name}`.", ephemeral=True)
    else:
        logger.error(f'Erro inesperado no comando {getattr(ctx.command, "qualified_name", "desconhecido")}: {error}', exc_info=True)
        try:
            response_text = "Opa! Algo deu errado aqui dentro. Avise o Mestre dos Bots!"
            if ctx.interaction.response.is_done():
                await ctx.followup.send(response_text, ephemeral=True)
            else:
                await ctx.respond(response_text, ephemeral=True)
        except Exception as e:
             logger.error(f"Falha ao enviar mensagem de erro para o usuário: {e}")

# --- Execução do Bot ---
if __name__ == "__main__":
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        bot_token = getattr(config, 'BOT_TOKEN', None)

    if not bot_token or bot_token == "SEU_TOKEN_AQUI_COMO_FALLBACK":
        logger.error("Erro Crítico: Token do bot não configurado!")
        logger.error("Crie um arquivo .env na raiz e adicione a linha: BOT_TOKEN=\"seu_token_aqui\"")
    else:
        try:
            bot.run(bot_token)
        except discord.LoginFailure:
            logger.error("Falha no login: Token do bot inválido. Verifique o token.")
        except Exception as e:
            logger.error(f"Erro inesperado ao iniciar o bot: {e}", exc_info=True)