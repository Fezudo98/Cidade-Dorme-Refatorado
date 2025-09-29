# cogs/utils.py

import discord
from discord.ext import commands
from discord import option, ApplicationContext, Permissions
import logging
import random
import os
from typing import Optional, Dict, Type, TYPE_CHECKING

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from database import engine

import config
from roles.base_role import Role
from roles.cidade_roles import cidade_role_classes
from roles.viloes_roles import viloes_role_classes
from roles.solo_roles import solo_role_classes

# Evita importação circular, mas permite o type hinting
if TYPE_CHECKING:
    from .game_instance import GameInstance
    from .game_flow import GameFlowCog # Import para type hint

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
            if game and not game.asset_error_notified:
                game.asset_error_notified = True
                await channel.send(f"⚠️ **Aviso para o Admin:** Não encontrei os arquivos de imagem/áudio. Verifique se a pasta `assets` foi enviada corretamente para a hospedagem do bot.")
    try:
        await channel.send(content=message, embed=embed, file=discord_file, allowed_mentions=allowed_mentions)
    except discord.Forbidden:
        logger.error(f"Sem permissão para enviar mensagens no canal {channel.name}.")
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

def get_random_humor(category_key: str) -> str:
    """Retorna uma frase humorística aleatória de uma categoria."""
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
        embed = discord.Embed(title="📜 Como Jogar Cidade Dorme 📜", description="Bem-vindo à cidade! Aqui, a confiança é um luxo e cada noite pode ser a sua última.", color=discord.Color.gold())
        embed.add_field(name="🎯 O Objetivo", value="- **🏙️ Cidade:** Eliminar todos os Vilões.\n- **👺 Vilões:** Eliminar a Cidade até atingir a paridade.\n- **🎭 Solo:** Você tem um objetivo único. Leia a descrição da sua função!", inline=False)
        embed.add_field(name="🔄 Fases do Jogo", value="O jogo alterna entre Noite e Dia.", inline=False)
        embed.add_field(name="🌃 Noite", value="Todos são silenciados. Se seu personagem tem uma habilidade, use os comandos na nossa conversa privada (DM).", inline=False)
        embed.add_field(name="☀️ Dia e Votação 🔥", value="Todos podem falar para discutir e descobrir os vilões. No final, uma votação secreta via DM decidirá quem será linchado.", inline=False)
        embed.set_footer(text="Use /funcoes para ver todos os personagens.")
        await ctx.respond(embed=embed)
        
    @commands.slash_command(name="funcoes", description="Lista todos os personagens do jogo e suas habilidades.")
    async def funcoes(self, ctx: ApplicationContext):
        await ctx.defer()
        embed_cidade = self._format_roles_for_embed(discord.Embed(title="🏙️ Funções da Cidade", color=discord.Color.blue()), cidade_role_classes)
        await ctx.followup.send(embed=embed_cidade)
        embed_viloes = self._format_roles_for_embed(discord.Embed(title="👺 Funções dos Vilões", color=discord.Color.red()), viloes_role_classes)
        await ctx.channel.send(embed=embed_viloes)
        embed_solo = self._format_roles_for_embed(discord.Embed(title="🎭 Funções Solo", color=discord.Color.purple()), solo_role_classes)
        await ctx.channel.send(embed=embed_solo)

    @commands.slash_command(name="ping", description="Testa se o bot está respondendo.")
    async def ping(self, ctx: ApplicationContext):
        latency = self.bot.latency * 1000
        await ctx.respond(f"Pong! A latência é de {latency:.2f}ms. Estou mais vivo que a maioria dos jogadores na noite 3!", ephemeral=True)

    # --- COMANDOS DE ADMINISTRAÇÃO ROBUSTOS ---

    @commands.slash_command(name="health", description="[Admin] Executa um teste funcional completo do bot.")
    @commands.has_permissions(manage_guild=True)
    async def health_check(self, ctx: ApplicationContext):
        """Executa uma verificação de saúde e testes funcionais nos sistemas do bot."""
        await ctx.defer(ephemeral=True)
        
        embed = discord.Embed(title="🩺 Teste Funcional Completo", color=discord.Color.green())
        status_color = discord.Color.green()
        test_image_file = None
        
        # --- TESTE 1: SISTEMAS BÁSICOS ---
        embed.add_field(name="--- SISTEMAS BÁSICOS ---", value="", inline=False)
        
        latency = self.bot.latency * 1000
        embed.add_field(name="🌐 Conexão com Discord", value=f"✅ Latência: {latency:.2f}ms")
        
        db_status = "❌ Falha"
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            db_status = "✅ Conectado"
        except SQLAlchemyError:
            status_color = discord.Color.orange()
        embed.add_field(name="🗄️ Banco de Dados", value=db_status)
        
        assets_path = config.ASSETS_PATH
        assets_status = "❌ Não encontrada!"
        if os.path.isdir(assets_path):
            assets_status = "✅ Acessível"
        else:
            status_color = discord.Color.red()
        embed.add_field(name="🖼️ Pasta de Assets", value=assets_status)

        # --- TESTE 2: PERMISSÕES ---
        embed.add_field(name="--- PERMISSÕES ESSENCIAIS ---", value="", inline=False)
        bot_member = ctx.guild.get_member(self.bot.user.id)
        
        text_perms = ctx.channel.permissions_for(bot_member)
        text_perms_status = []
        required_text_perms = {'send_messages': text_perms.send_messages, 'embed_links': text_perms.embed_links, 'attach_files': text_perms.attach_files}
        for perm, has_perm in required_text_perms.items():
            emoji = "✅" if has_perm else "❌"
            text_perms_status.append(f"{emoji} {perm}")
            if not has_perm: status_color = discord.Color.orange()
        embed.add_field(name=f"Canal #{ctx.channel.name}", value="\n".join(text_perms_status))

        # --- TESTE 3: FUNCIONALIDADES DE VOZ ---
        embed.add_field(name="--- TESTE DE ÁUDIO E VOZ ---", value="", inline=False)
        
        if not ctx.author.voice or not ctx.author.voice.channel:
            embed.add_field(name="🎤 Teste de Voz", value="⚠️ Pulei o teste: você não está em um canal de voz.")
        else:
            voice_channel = ctx.author.voice.channel
            voice_perms = voice_channel.permissions_for(bot_member)
            
            voice_perms_status = []
            required_voice_perms = {'connect': voice_perms.connect, 'speak': voice_perms.speak, 'mute_members': voice_perms.mute_members}
            for perm, has_perm in required_voice_perms.items():
                emoji = "✅" if has_perm else "❌"
                voice_perms_status.append(f"{emoji} {perm}")
                if not has_perm: status_color = discord.Color.red()
            embed.add_field(name=f"Canal de Voz '{voice_channel.name}'", value="\n".join(voice_perms_status))
            
            audio_status = "Não testado"
            if required_voice_perms['connect'] and required_voice_perms['speak']:
                game_flow_cog: 'GameFlowCog' = self.bot.get_cog("GameFlowCog")
                if not game_flow_cog:
                    audio_status = "❌ Falha: Cog de fluxo de jogo não encontrado."
                    status_color = discord.Color.red()
                else:
                    try:
                        from types import SimpleNamespace
                        mock_game = SimpleNamespace(guild=ctx.guild, voice_channel=voice_channel, asset_error_notified=False)
                        await game_flow_cog.play_sound_effect(mock_game, "HEALTH_CHECK", wait_for_finish=True)
                        audio_status = "✅ Sucesso: Áudio de teste executado!"
                        
                        vc = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
                        if vc: await vc.disconnect()
                    except Exception as e:
                        logger.error(f"Erro no teste de áudio do /health: {e}")
                        audio_status = f"❌ Falha: {e}"
                        status_color = discord.Color.red()
            else:
                audio_status = "⚠️ Pulei o teste: Permissões de 'conectar' ou 'falar' ausentes."
            embed.add_field(name="🎶 Teste de Reprodução", value=audio_status, inline=False)

        # --- TESTE 4: ENVIO DE IMAGEM ---
        embed.add_field(name="--- TESTE DE ENVIO DE IMAGEM ---", value="", inline=False)
        
        img_status = "Não testado"
        if text_perms.attach_files:
            try:
                image_name = config.EVENT_IMAGES.get("CITY_WIN", "city_win.png")
                test_image_path = os.path.join(config.IMAGES_PATH, image_name)
                
                if not os.path.exists(test_image_path):
                    img_status = f"❌ Falha: Imagem de teste (`{image_name}`) não encontrada."
                    status_color = discord.Color.red()
                else:
                    test_image_file = discord.File(test_image_path, filename="health_test_image.png")
                    img_status = "✅ Sucesso! Imagem de teste encontrada e pronta para envio."
            except Exception as e:
                img_status = f"❌ Falha ao carregar a imagem: {e}"
                status_color = discord.Color.red()
        else:
            img_status = "⚠️ Pulei o teste: Permissão de 'anexar arquivos' ausente."
        
        embed.add_field(name="Teste de Imagem", value=img_status, inline=False)
        
        embed.color = status_color
        embed.set_footer(text="Vermelho = Erro Crítico | Laranja = Aviso/Problema de Permissão")
        
        await ctx.followup.send(embed=embed, file=test_image_file, ephemeral=True)


    @commands.slash_command(name="encerrar", description="[Admin] Força o fim de uma partida ou cancela uma preparação neste canal.")
    @commands.has_permissions(manage_guild=True)
    async def encerrar(self, ctx: ApplicationContext):
        await ctx.defer(ephemeral=True)
        game = self.bot.game_manager.get_game(ctx.channel.id)
        if not game:
            await ctx.followup.send("Nenhum jogo em andamento ou em preparação para encerrar neste canal.")
            return
        game_flow_cog = self.bot.get_cog("GameFlowCog")
        if not game_flow_cog:
            await ctx.followup.send("Erro: Não foi possível encontrar o controle de fluxo do jogo.")
            return
        await ctx.followup.send("Encerrando a sessão atual à força...")
        await game_flow_cog.end_game(
            game, "Fim de Jogo Forçado", [], "Ninguém", 
            "A partida foi encerrada por um administrador.", error=True
        )

    @commands.slash_command(name="desmutar_todos", description="[Admin] Força o unmute de todos no canal de voz da partida atual.")
    @commands.has_permissions(manage_guild=True)
    async def desmutar_todos(self, ctx: ApplicationContext):
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