# cogs/utils.py

import discord
from discord.ext import commands
from discord import option, ApplicationContext
import logging
import random
from typing import Optional, Dict, Type, TYPE_CHECKING

import config
from roles.base_role import Role
from roles.cidade_roles import cidade_role_classes
from roles.viloes_roles import viloes_role_classes
from roles.solo_roles import solo_role_classes

# Evita importação circular, mas permite o type hinting
if TYPE_CHECKING:
    from .game_instance import GameInstance

logger = logging.getLogger(__name__)

# Combina todos os dicionários de classes de papéis para fácil acesso pelo nome
all_role_classes = {**cidade_role_classes, **viloes_role_classes, **solo_role_classes}

# --- Funções de Autocomplete ---

async def search_roles(ctx: discord.AutocompleteContext) -> list:
    """Retorna uma lista de papéis que correspondem ao que o usuário está digitando."""
    return [role for role in all_role_classes.keys() if role.lower().startswith(ctx.value.lower())]

# --- Funções Utilitárias ---

async def send_public_message(bot: commands.Bot, channel: discord.TextChannel, message: Optional[str] = None, embed: Optional[discord.Embed] = None, file_path: Optional[str] = None, allowed_mentions: Optional[discord.AllowedMentions] = None, game: Optional['GameInstance'] = None):
    """
    Envia uma mensagem para um canal de texto público especificado.
    """
    if not channel:
        logger.error("Tentativa de enviar mensagem pública para um canal nulo.")
        return

    discord_file = None
    if file_path:
        try:
            discord_file = discord.File(file_path)
        except FileNotFoundError:
            logger.error(f"Arquivo de imagem não encontrado em: {file_path}")
            # --- NOVA LÓGICA DE NOTIFICAÇÃO ---
            if game and not game.asset_error_notified:
                game.asset_error_notified = True
                await channel.send(f"⚠️ **Aviso para o Admin:** Não encontrei os arquivos de imagem/áudio. Verifique se a pasta `assets` foi enviada corretamente para a hospedagem do bot.")
    try:
        await channel.send(content=message, embed=embed, file=discord_file, allowed_mentions=allowed_mentions)
    except discord.Forbidden:
        logger.error(f"Sem permissão para enviar mensagens no canal {channel.name}.")
        # Se não puder enviar a mensagem de erro, apenas loga.
        if game and not game.permission_error_notified:
            game.permission_error_notified = True
            logger.critical(f"CRÍTICO: Não consigo enviar mensagens no canal do jogo {channel.name}. Verifique as permissões de 'Ver Canal' e 'Enviar Mensagens'.")
    except Exception as e:
        logger.error(f"Erro ao enviar mensagem pública para {channel.name}: {e}")

async def send_dm_safe(member: discord.Member, message: str = None, embed: discord.Embed = None, file: discord.File = None):
    """Envia uma DM para um membro, tratando exceções comuns."""
    if not member or member.bot: return
    try:
        await member.send(content=message, embed=embed, file=file)
    except discord.Forbidden:
        logger.warning(f"Não foi possível enviar DM para {member.display_name} (DMs fechadas).")
    except Exception as e:
        logger.warning(f"Não foi possível enviar DM para {member.display_name}: {e}")

# --- Mensagens Humorísticas (Centralizadas) ---
def get_random_humor(category_key: str) -> str:
    """Retorna uma frase humorística aleatória de uma categoria."""
    # Agora usa a variável importada de config.py
    return random.choice(config.HUMOR_MESSAGES.get(category_key, [""]))

class UtilsCog(commands.Cog):
    """Cog para funções utilitárias, comandos informativos e de administração."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        logger.info("Cog Utils carregado.")

    def _format_roles_for_embed(self, embed: discord.Embed, roles: Dict[str, Type[Role]]):
        """Formata a lista de papéis para um campo de embed."""
        roles_text = ""
        for role_class in roles.values():
            role_instance = role_class()
            abilities_str = "\n".join(role_instance.abilities) if isinstance(role_instance.abilities, (list, tuple)) else role_instance.abilities
            roles_text += f"**{role_instance.name}**\n{abilities_str}\n\n"
        embed.description = roles_text
        return embed

    @commands.slash_command(name="explicar", description="Explica detalhadamente como um personagem funciona.")
    @option("personagem", description="O nome do personagem que você quer entender.", autocomplete=search_roles)
    async def explicar(self, ctx: ApplicationContext, personagem: str):
        """Envia uma explicação detalhada de um papel específico."""
        role_class = all_role_classes.get(personagem)
        if not role_class:
            await ctx.respond(f"Não encontrei um personagem chamado '{personagem}'.", ephemeral=True)
            return

        role_instance = role_class()
        embed = discord.Embed(title=f"🔎 Detalhes do Papel: {role_instance.name}", description=role_instance.description, color=role_instance.get_faction_color())
        embed.add_field(name="📜 Facção", value=role_instance.faction, inline=True)
        abilities_text = "\n".join(role_instance.abilities) if isinstance(role_instance.abilities, (list, tuple)) else role_instance.abilities
        embed.add_field(name="✨ Habilidades", value=abilities_text, inline=False)
        embed.set_footer(text="Use estas informações com sabedoria...")
        await ctx.respond(embed=embed)

    @commands.slash_command(name="ajuda", description="Explica as regras e como jogar Cidade Dorme.")
    async def ajuda(self, ctx: ApplicationContext):
        """Envia uma mensagem pública explicando as regras do jogo."""
        embed = discord.Embed(title="📜 Como Jogar Cidade Dorme 📜", description="Bem-vindo à cidade! Aqui, a confiança é um luxo e cada noite pode ser a sua última.", color=discord.Color.gold())
        embed.add_field(name="🎯 O Objetivo", value="- **🏙️ Cidade:** Eliminar todos os Vilões.\n- **👺 Vilões:** Eliminar a Cidade até atingir a paridade.\n- **🎭 Solo:** Você tem um objetivo único. Leia a descrição da sua função!", inline=False)
        embed.add_field(name="🔄 Fases do Jogo", value="O jogo alterna entre Noite e Dia.", inline=False)
        embed.add_field(name="🌃 Noite", value="Todos são silenciados. Se seu personagem tem uma habilidade, use os comandos na nossa conversa privada (DM).", inline=False)
        embed.add_field(name="☀️ Dia e Votação 🔥", value="Todos podem falar para discutir e descobrir os vilões. No final, uma votação secreta via DM decidirá quem será linchado.", inline=False)
        embed.set_footer(text="Use /funcoes para ver todos os personagens.")
        await ctx.respond(embed=embed)
        
    @commands.slash_command(name="funcoes", description="Lista todos os personagens do jogo e suas habilidades.")
    async def funcoes(self, ctx: ApplicationContext):
        """Envia uma série de embeds públicos listando todos os papéis e habilidades."""
        await ctx.defer()
        embed_cidade = self._format_roles_for_embed(discord.Embed(title="🏙️ Funções da Cidade", color=discord.Color.blue()), cidade_role_classes)
        await ctx.followup.send(embed=embed_cidade)
        embed_viloes = self._format_roles_for_embed(discord.Embed(title="👺 Funções dos Vilões", color=discord.Color.red()), viloes_role_classes)
        await ctx.channel.send(embed=embed_viloes)
        embed_solo = self._format_roles_for_embed(discord.Embed(title="🎭 Funções Solo", color=discord.Color.purple()), solo_role_classes)
        await ctx.channel.send(embed=embed_solo)

    @commands.slash_command(name="ping", description="Testa se o bot está respondendo.")
    async def ping(self, ctx: ApplicationContext):
        """Um comando simples para verificar se o bot está online e sua latência."""
        latency = self.bot.latency * 1000
        await ctx.respond(f"Pong! A latência é de {latency:.2f}ms. Estou mais vivo que a maioria dos jogadores na noite 3!", ephemeral=True)

    @commands.slash_command(name="encerrar", description="[Admin] Força o fim de uma partida ou cancela uma preparação neste canal.")
    @commands.has_permissions(manage_guild=True)
    async def encerrar(self, ctx: ApplicationContext):
        """Força o encerramento de um jogo no canal atual."""
        game = self.bot.game_manager.get_game(ctx.channel.id)
        if not game:
            await ctx.respond("Nenhum jogo em andamento ou em preparação para encerrar neste canal.", ephemeral=True)
            return
            
        game_flow_cog = self.bot.get_cog("GameFlowCog")
        if not game_flow_cog:
            await ctx.respond("Erro: Não foi possível encontrar o controle de fluxo do jogo.", ephemeral=True)
            return

        await ctx.respond("Encerrando a sessão atual à força...", ephemeral=True)
        await game_flow_cog.end_game(
            game,
            "Fim de Jogo Forçado", 
            [], # Sem vencedores
            "Ninguém", 
            "A partida foi encerrada por um administrador.", 
            error=True # Impede a atualização de estatísticas
        )

    @commands.slash_command(name="desmutar_todos", description="[Admin] Força o unmute de todos no canal de voz da partida atual.")
    @commands.has_permissions(manage_guild=True)
    async def desmutar_todos(self, ctx: ApplicationContext):
        """Força o unmute de todos os membros no canal de voz da partida do canal atual."""
        await ctx.defer(ephemeral=True)
        game = self.bot.game_manager.get_game(ctx.channel.id)
        if not game or not game.voice_channel:
            await ctx.followup.send("Nenhuma partida com um canal de voz associado está ativa neste canal.")
            return

        unmuted_count, failed_count = 0, 0
        for member in game.voice_channel.members:
            if member.voice and member.voice.mute:
                try:
                    await member.edit(mute=False, reason=f"Comando /desmutar_todos usado por {ctx.author}")
                    unmuted_count += 1
                except Exception as e:
                    logger.error(f"Falha ao desmutar {member.display_name} via comando: {e}")
                    failed_count += 1
        
        await ctx.followup.send(f"Comando executado! ✅\n- **{unmuted_count}** membro(s) desmutados.\n- **{failed_count}** falha(s).")

def setup(bot: commands.Bot):
    bot.add_cog(UtilsCog(bot))