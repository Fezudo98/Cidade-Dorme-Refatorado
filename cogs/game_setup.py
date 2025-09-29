# cogs/game_setup.py

import discord
from discord.ext import commands
from discord import option, ApplicationContext
import logging
import random
import os
import asyncio

# --- NOVAS IMPORTAÇÕES PARA VERIFICAÇÃO DE SERVIDOR ---
from sqlalchemy import select, insert
from database import engine, guilds_table

import config
from .game_instance import GameInstance
from .utils import send_dm_safe
from roles.base_role import Role
from roles.cidade_roles import cidade_role_classes
from roles.viloes_roles import viloes_role_classes
from roles.solo_roles import solo_role_classes, CacadorDeCabecas

logger = logging.getLogger(__name__)

# Combina todos os dicionários de classes de papéis para fácil acesso pelo nome
all_role_classes = {**cidade_role_classes, **viloes_role_classes, **solo_role_classes}

class GameSetupCog(commands.Cog):
    """Cog contendo os comandos para iniciar e preparar o jogo."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        logger.info("Cog GameSetup carregado.")

    async def _check_first_time_setup(self, ctx: ApplicationContext) -> bool:
        """
        Verifica se a mensagem de setup já foi enviada para este servidor.
        Se não foi, envia a mensagem e registra no banco de dados.
        Retorna True se for a primeira vez (e a mensagem foi enviada), False caso contrário.
        """
        # Verifica se o banco de dados está disponível para evitar erros
        if guilds_table is None or engine is None:
            logger.warning("Tabela de Guilds não está disponível. Pulando verificação de primeiro uso.")
            return False

        guild_id = ctx.guild.id
        try:
            with engine.connect() as conn:
                # Verifica se o guild_id já existe na tabela
                stmt_select = select(guilds_table).where(guilds_table.c.guild_id == guild_id)
                result = conn.execute(stmt_select).first()

                # Se não houver resultado, é a primeira vez.
                if not result:
                    logger.info(f"Primeira utilização do bot no servidor {guild_id}. Enviando mensagem de setup.")
                    # A mensagem pública não deve ser efêmera, então enviamos diretamente pelo canal.
                    await ctx.channel.send(config.MSG_FIRST_TIME_SETUP)
                    
                    # Insere o registro no banco de dados para não enviar novamente.
                    stmt_insert = insert(guilds_table).values(guild_id=guild_id, setup_message_sent=True)
                    conn.execute(stmt_insert)
                    conn.commit() # Salva a alteração
                    return True # Indica que a mensagem de setup foi enviada.
        except Exception as e:
            logger.error(f"Falha ao verificar/salvar o estado de setup para o servidor {guild_id}: {e}")
            # Se houver erro de DB, permite que o bot continue, mas avisa o admin.
            await ctx.followup.send("⚠️ Não consegui verificar as configurações iniciais do servidor. Se encontrar problemas, verifique minhas permissões.", ephemeral=True)

        return False # Indica que a mensagem já foi enviada ou houve um erro.

    async def _distribute_roles(self, game: GameInstance, players: list[discord.Member]):
        """
        Seleciona, embaralha e distribui os papéis para uma instância de jogo específica.
        """
        num_players = len(players)
        logger.info(f"[Jogo #{game.text_channel.id}] Iniciando distribuição de papéis para {num_players} jogadores.")

        composition = config.GAME_COMPOSITIONS.get(str(num_players))
        if not composition:
            logger.error(f"[Jogo #{game.text_channel.id}] Erro: Nenhuma composição definida para {num_players} jogadores.")
            return False

        roles_to_distribute = []
        
        city_count = composition.get("Cidade", 0)
        city_pool = config.ROLE_POOL.get("Cidade", {})
        if city_count > 0:
            essenciais = city_pool.get("essenciais", [])
            investigadores = city_pool.get("investigadores", [])
            city_roles = essenciais[:city_count]
            needed = city_count - len(city_roles)
            if needed > 0:
                if len(investigadores) < needed: return False
                city_roles.extend(random.sample(investigadores, needed))
            roles_to_distribute.extend(city_roles)

        villain_count = composition.get("Vilões", 0)
        villain_pool = config.ROLE_POOL.get("Vilões", {})
        if villain_count > 0:
            essenciais = villain_pool.get("essenciais", [])
            outros = villain_pool.get("outros", [])
            villain_roles = essenciais[:villain_count]
            needed = villain_count - len(villain_roles)
            if needed > 0:
                if len(outros) < needed: return False
                villain_roles.extend(random.sample(outros, needed))
            roles_to_distribute.extend(villain_roles)

        solo_count = composition.get("Solo", 0)
        if solo_count > 0:
            solo_pool = config.ROLE_POOL.get("Solo", {})
            exclusivos = solo_pool.get("exclusivos", [])
            outros = solo_pool.get("outros", [])
            final_solos = []
            if solo_count > 0 and exclusivos:
                chosen_exclusive = random.choice(exclusivos)
                final_solos.append(chosen_exclusive)
                outros_pool = [role for role in outros if role != chosen_exclusive]
                needed = solo_count - 1
                if needed > 0:
                    if len(outros_pool) < needed: return False
                    final_solos.extend(random.sample(outros_pool, needed))
            else:
                if len(outros) < solo_count: return False
                final_solos.extend(random.sample(outros, solo_count))
            roles_to_distribute.extend(final_solos)

        if len(roles_to_distribute) != num_players:
            logger.error(f"[Jogo #{game.text_channel.id}] Erro de distribuição. Esperado: {num_players}, Gerado: {len(roles_to_distribute)}.")
            return False

        role_instances = [all_role_classes[name]() for name in roles_to_distribute]
        
        random.shuffle(role_instances)
        random.shuffle(players)

        logger.info(f"[Jogo #{game.text_channel.id}] Papéis selecionados: {[role.name for role in role_instances]}")
        game.roles_in_game = role_instances
        
        tasks = []
        for i, player_member in enumerate(players):
            role_instance = role_instances[i]
            player_state = game.get_player_state_by_id(player_member.id)
            if not player_state:
                logger.error(f"[Jogo #{game.text_channel.id}] Erro crítico: Estado não encontrado para {player_member.display_name}.")
                continue
            player_state.assign_role(role_instance)
            tasks.append(self._send_role_dm(player_member, role_instance))
        
        await asyncio.gather(*tasks)
        
        if headhunter_state := next((p for p in game.players.values() if isinstance(p.role, CacadorDeCabecas)), None):
            possible_targets = [p for p in game.players.values() if p.member.id != headhunter_state.member.id]
            if possible_targets:
                target_state = random.choice(possible_targets)
                game.headhunter_info = {'hunter_id': headhunter_state.member.id, 'target_id': target_state.member.id}
                logger.info(f"[Jogo #{game.text_channel.id}] Caçador {headhunter_state.member.display_name} recebeu alvo {target_state.member.display_name}.")
                await send_dm_safe(headhunter_state.member, f"💰 **Seu Contrato:** Sua missão é garantir que **{target_state.member.display_name}** seja **linchado**.")

        return True

    async def _send_role_dm(self, member: discord.Member, role: Role):
        """Envia a DM com o papel e a imagem para um jogador."""
        try:
            embed = role.get_embed(member)
            image_path = os.path.join(config.IMAGES_PATH, role.image_file)

            if not os.path.exists(image_path):
                logger.warning(f"Imagem '{role.image_file}' não encontrada para o papel {role.name}.")
                await send_dm_safe(member, embed=embed)
            else:
                discord_file = discord.File(image_path, filename=role.image_file)
                embed.set_thumbnail(url=f"attachment://{role.image_file}")
                await send_dm_safe(member, embed=embed, file=discord_file)
            
            logger.info(f"Papel {role.name} e imagem enviados para {member.display_name}.")

        except Exception as e:
            logger.critical(f"FALHA CRÍTICA ao enviar a DM do papel para {member.display_name}. Erro: {e}", exc_info=True)
            await send_dm_safe(member, f"⚠️ Ocorreu um erro ao te enviar os detalhes do seu papel. Seu papel é: **{role.name}**.")

    @commands.slash_command(
        name="preparar",
        description="Inicia a preparação de um jogo, puxando jogadores do seu canal de voz."
    )
    async def preparar_jogo(self, ctx: ApplicationContext):
        await ctx.defer(ephemeral=True)
        
        # --- LÓGICA DE VERIFICAÇÃO DE PRIMEIRO USO ---
        # Se a função retornar True, significa que a mensagem de setup foi enviada.
        if await self._check_first_time_setup(ctx):
            # Avisa o usuário que usou o comando para checar o canal.
            await ctx.followup.send("Guia de configuração inicial enviado no canal! Verifique as permissões e tente novamente.", ephemeral=True)
            return # Interrompe a execução do comando.
        # ----------------------------------------------

        logger.info(f"Comando /preparar recebido de {ctx.author.display_name} no canal #{ctx.channel.name}")

        if self.bot.game_manager.get_game(ctx.channel.id):
            await ctx.followup.send("Já existe uma partida sendo preparada ou em andamento neste canal.", ephemeral=True)
            return

        if not ctx.author.voice or not ctx.author.voice.channel:
            logger.warning(f"Usuário {ctx.author.display_name} usou /preparar mas não está em um canal de voz.")
            await ctx.followup.send("Você precisa estar em um canal de voz para iniciar um jogo!", ephemeral=True)
            return

        voice_channel = ctx.author.voice.channel
        connected_members = [member for member in voice_channel.members if not member.bot]
        num_players = len(connected_members)
        
        logger.info(f"Membros encontrados no canal de voz '{voice_channel.name}': {[m.display_name for m in connected_members]}. Total: {num_players}")

        if not (config.MIN_PLAYERS <= num_players <= config.MAX_PLAYERS):
            await ctx.followup.send(f"Opa! Precisamos de {config.MIN_PLAYERS} a {config.MAX_PLAYERS} jogadores, e vocês são {num_players}.", ephemeral=True)
            return

        game = None
        try:
            await ctx.followup.send(f"Iniciando preparação para {num_players} jogadores. Verifiquem suas DMs!", ephemeral=True)
            
            game = self.bot.game_manager.create_game(ctx.channel, voice_channel, ctx.author)
            if not game:
                await ctx.followup.send("Erro inesperado ao criar a partida. Tente novamente.", ephemeral=True)
                return
            
            for member in connected_members:
                game.add_player(member)

            success = await self._distribute_roles(game, connected_members)
            if not success:
                await ctx.channel.send(f"⚠️ **Erro na Preparação:** Não foi possível distribuir os papéis. Verifique as configurações e os logs do bot. A preparação foi cancelada.")
                self.bot.game_manager.end_game(ctx.channel.id)
                return

            player_list_text = "\n".join([f"- {member.display_name}" for member in connected_members])
            announcement = (
                f"🎉 **Atenção, cidadãos!** 🎉\n\n"
                f"{ctx.author.mention} deu o pontapé inicial para uma nova partida!\n\n"
                f"Os **{num_players} jogadores** no canal '{voice_channel.name}' são:\n"
                f"{player_list_text}\n\n"
                f"🤫 Papéis distribuídos por **DM**. Quando estiverem prontos, o Mestre do Jogo (`{ctx.author.display_name}`) deve usar `/iniciar`."
            )
            await ctx.channel.send(announcement)

        except Exception as e:
            await ctx.followup.send("Opa! Algo deu muito errado aqui dentro. A preparação foi cancelada.", ephemeral=True)
            logger.exception("Erro inesperado durante o comando /preparar:", exc_info=e)
            if game and self.bot.game_manager.get_game(game.text_channel.id):
                self.bot.game_manager.end_game(game.text_channel.id)

def setup(bot: commands.Bot):
    bot.add_cog(GameSetupCog(bot))