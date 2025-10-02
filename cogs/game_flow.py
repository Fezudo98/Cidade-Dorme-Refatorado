# cogs/game_flow.py (VERSÃO FINAL E CORRIGIDA)

import discord
from discord.ext import commands
import logging
import asyncio
import os
import random
from typing import List, Optional

import config
from .game_instance import GameInstance
from .utils import send_public_message, get_random_humor, send_dm_safe
from core.action_resolver import ActionResolver
from core.image_generator import ImageGenerator
from roles.solo_roles import Cupido, Corruptor, CacadorDeCabecas, Bruxo, Fofoqueiro
from roles.viloes_roles import AssassinoAlfa, AssassinoJunior
from roles.cidade_roles import Prefeito, Xerife, Anjo, CidadaoComum, GuardaCostas

logger = logging.getLogger(__name__)

class ShowdownSelect(discord.ui.Select):
    def __init__(self, user_to_act: discord.Member, targets: List[discord.Member]):
        self.user_to_act = user_to_act
        options = [discord.SelectOption(label=member.display_name, value=str(member.id)) for member in targets]
        super().__init__(placeholder=f"Escolha seu alvo, {user_to_act.display_name}...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_to_act.id:
            await interaction.response.send_message("Você não é a pessoa que deve agir agora!", ephemeral=True)
            return
        self.view.result = int(self.values[0])
        self.disabled = True
        self.placeholder = "Você escolheu seu alvo."
        await interaction.message.edit(view=self.view)
        self.view.stop()
        await interaction.response.defer()

class ShowdownView(discord.ui.View):
    def __init__(self, user_to_act: discord.Member, targets: List[discord.Member], timeout=120.0):
        super().__init__(timeout=timeout)
        self.result: Optional[int] = None
        self.add_item(ShowdownSelect(user_to_act, targets))
    async def on_timeout(self):
        self.stop()

class GameFlowCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.action_resolver = ActionResolver(bot)
        self.image_generator = ImageGenerator(assets_path=config.ASSETS_PATH)
        logger.info("Cog GameFlow (Orquestrador) carregado com ImageGenerator.")

    def cog_unload(self):
        for game in self.bot.game_manager.games.values():
            if game.current_timer_task and not game.current_timer_task.done():
                game.current_timer_task.cancel()

    async def _update_voice_permissions(self, game: GameInstance, mute: bool, force_unmute_all: bool = False):
        if not game.voice_channel: return
        logger.info(f"[Jogo #{game.text_channel.id}] Atualizando permissões de voz. Mute Geral = {mute}")
        tasks = []
        for member in game.voice_channel.members:
            if member.bot: continue
            should_be_muted = mute
            if not force_unmute_all:
                if player_state := game.get_player_state_by_id(member.id):
                    should_be_muted = mute or not player_state.is_alive
            tasks.append(self._set_member_mute(game, member, should_be_muted, "Controle de fase do jogo"))
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _set_member_mute(self, game: GameInstance, member: discord.Member, mute: bool, reason: str):
        try:
            if member.voice and member.voice.mute != mute:
                await member.edit(mute=mute, reason=reason)
        except discord.Forbidden:
            if not game.permission_error_notified:
                game.permission_error_notified = True
                embed = discord.Embed(
                    title="🚨 Erro de Permissão Crítico 🚨",
                    description="Não consigo silenciar e dessilenciar os jogadores! A jogabilidade será comprometida.",
                    color=discord.Color.red()
                )
                embed.add_field(name="Como Corrigir (para Admins):", value="1. **Hierarquia de Cargos:** Arraste o cargo do bot para **acima** dos cargos dos jogadores.\n2. **Permissões de Cargo/Canal:** Verifique se o bot tem a permissão **'Silenciar Membros'**.", inline=False)
                embed.set_footer(text="Esta mensagem só aparecerá uma vez por partida.")
                await send_public_message(self.bot, game.text_channel, embed=embed)
        except Exception as e:
            logger.error(f"Falha ao mutar/desmutar {member.display_name}: {e}")

    def _start_timer(self, game: GameInstance, duration: int, next_phase_func):
        if game.current_timer_task and not game.current_timer_task.done():
            game.current_timer_task.cancel()
        async def timer_task():
            try:
                await asyncio.sleep(duration)
                if self.bot.game_manager.get_game(game.text_channel.id):
                    await next_phase_func(game)
            except asyncio.CancelledError:
                logger.info(f"[Jogo #{game.text_channel.id}] Timer cancelado.")
        game.current_timer_task = asyncio.create_task(timer_task())

    # --- FUNÇÃO DE ÁUDIO CORRIGIDA COM RETORNO DE STATUS ---
    async def play_sound_effect(self, game: GameInstance, event_key: str, wait_for_finish: bool = False) -> bool:
        if not config.AUDIO_ENABLED or not game.voice_channel:
            return True # Considera sucesso se o áudio está desativado

        sound_list = config.AUDIO_FILES.get(event_key)
        if not sound_list:
            logger.warning(f"Nenhum arquivo de áudio definido para o evento: {event_key}")
            return True # Não é um erro crítico, apenas um som ausente na config

        chosen_file = random.choice(sound_list)
        audio_path = os.path.join(config.AUDIO_PATH, chosen_file)

        if not os.path.exists(audio_path):
            logger.error(f"Arquivo de áudio não encontrado: {audio_path}")
            game_instance = self.bot.game_manager.get_game(game.text_channel.id)
            if game_instance and not game_instance.asset_error_notified:
                game_instance.asset_error_notified = True
                await send_public_message(self.bot, game.text_channel, message=f"⚠️ **Aviso para o Admin:** Não encontrei os arquivos de áudio/imagem.")
            return False # Isso é uma falha de configuração

        voice_client = discord.utils.get(self.bot.voice_clients, guild=game.guild)

        try:
            # Lógica de conexão robusta para evitar clientes "zumbis"
            if voice_client and voice_client.is_connected():
                if voice_client.channel != game.voice_channel:
                    await voice_client.move_to(game.voice_channel)
            else:
                if voice_client:
                    await voice_client.disconnect(force=True)
                voice_client = await game.voice_channel.connect(timeout=20.0, reconnect=True)

            if not voice_client: # Verificação extra de segurança
                 raise Exception("O cliente de voz não foi conectado com sucesso.")

            if voice_client.is_playing():
                voice_client.stop()

            source = discord.FFmpegPCMAudio(audio_path)
            
            if wait_for_finish:
                finished = asyncio.Event()
                def after_playing(error):
                    if error: logger.error(f"Erro no callback do áudio: {error}")
                    finished.set()
                
                voice_client.play(source, after=after_playing)
                await asyncio.wait_for(finished.wait(), timeout=30.0)
            else:
                voice_client.play(source)

            return True # Retorna True no final do bloco try bem-sucedido

        except asyncio.TimeoutError:
            logger.error(f"[Jogo #{game.text_channel.id}] Timeout ao tentar conectar/reproduzir no canal de voz.")
            if vc := discord.utils.get(self.bot.voice_clients, guild=game.guild):
                await vc.disconnect(force=True)
            return False
        except Exception as e:
            logger.error(f"[Jogo #{game.text_channel.id}] Erro inesperado na operação de áudio: {e}")
            if vc := discord.utils.get(self.bot.voice_clients, guild=game.guild):
                await vc.disconnect(force=True)
            return False

    @commands.slash_command(name="iniciar", description="Inicia a primeira noite do jogo neste canal.")
    async def iniciar_jogo(self, ctx: discord.ApplicationContext):
        game = self.bot.game_manager.get_game(ctx.channel.id)
        if not game: await ctx.respond("Não há jogo sendo preparado neste canal.", ephemeral=True); return
        if game.current_phase != "preparing": await ctx.respond("O jogo não está em fase de preparação.", ephemeral=True); return
        if ctx.author != game.game_master: await ctx.respond("Apenas quem usou `/preparar` pode iniciar o jogo!", ephemeral=True); return
        await ctx.respond("Que comecem as tretas! A primeira noite está caindo... 🤫")
        await self.start_night(game)

    async def start_night(self, game: GameInstance):
        game.current_phase = "night"
        game.current_night += 1
        game.sheriff_shot_this_day = False
        logger.info(f"[Jogo #{game.text_channel.id}] --- Iniciando Noite {game.current_night} ---")
        if game.current_night == 1 and (actions_cog := self.bot.get_cog("ActionsCog")):
            await actions_cog.distribute_initial_info(game)
        await self._update_voice_permissions(game, mute=True)
        await self.play_sound_effect(game, "NIGHT_START")
        image_path = os.path.join(config.IMAGES_PATH, config.EVENT_IMAGES["NIGHT_START"])
        await send_public_message(self.bot, game.text_channel, message=f"🌃 **NOITE {game.current_night}** 🌃\n{get_random_humor('NIGHT_START')}", file_path=image_path, game=game)
        self._start_timer(game, config.NIGHT_DURATION_SECONDS, self.end_night)

    async def force_night(self, game: GameInstance):
        if game.current_timer_task and not game.current_timer_task.done():
            game.current_timer_task.cancel()
        await self.start_night(game)

    async def end_night(self, game: GameInstance):
        if not game.is_night(): return
        logger.info(f"[Jogo #{game.text_channel.id}] --- Fim da Noite {game.current_night} ---")
        await send_public_message(self.bot, game.text_channel, "A noite acabou! Processando os eventos...", game=game)
        night_results = await self.action_resolver.resolve_night_actions(game)
        if night_results.get("game_over"): return
        if game.pending_resolution: await self._resolve_pending_endgame(game); return
        alive_before_ids = {p.member.id for p in game.get_alive_players_states()}
        for victim_id, reason, killer_id in night_results.get("killed_players", []):
            if member := game.get_player_by_id(victim_id):
                game.killers[victim_id] = killer_id
                if reason == 'witch': game.successful_major_actions.append({'actor': killer_id, 'action': 'kill', 'target': victim_id})
                await self.process_death(game, member, reason)
                if not self.bot.game_manager.get_game(game.text_channel.id): return
        for player_id, messages in night_results.get("dm_messages", {}).items():
            if messages and (player := game.get_player_by_id(player_id)):
                await send_dm_safe(player, "\n".join(messages))
        for revived_id, reviver_id in night_results.get("revived_players", []):
            game.successful_major_actions.append({'actor': reviver_id, 'action': 'revive', 'target': revived_id})
        if await self.check_game_end(game, "após os eventos da noite"): return
        alive_after_ids = {p.member.id for p in game.get_alive_players_states()}
        killed_today = [game.get_player_by_id(pid) for pid in (alive_before_ids - alive_after_ids) if pid]
        revived_today = [game.get_player_by_id(pid) for pid in (alive_after_ids - alive_before_ids) if pid]
        day_messages, image_key = night_results.get("public_messages", []), None
        if night_results.get("plague_kill_count", 0) > 0:
            image_key = "PLAGUE_KILL"
            day_messages.append(f"☣️ A praga deixou um rastro de destruição! Encontramos os corpos de: **{', '.join(sorted([m.display_name for m in killed_today]))}**.")
        elif killed_today:
            image_key = "DAY_DEATH"
            day_messages.append(f"Manhã trágica! Encontramos os corpos de: **{', '.join(sorted([m.display_name for m in killed_today]))}**.")
        if revived_today:
            image_key = image_key or "DAY_REVIVAL"
            day_messages.append(f"Milagre! **{', '.join([m.display_name for m in revived_today])}** retornaram dos mortos!")
        if not killed_today and not revived_today and not day_messages:
            image_key, day_messages = "DAY_SAFE", ["Uma noite calma... Ninguém morreu."]
        image_key = image_key or "DAY_DEATH"
        image_path = os.path.join(config.IMAGES_PATH, config.EVENT_IMAGES[image_key])
        await send_public_message(self.bot, game.text_channel, message="\n".join(day_messages), file_path=image_path, game=game)
        await self.start_day_discussion(game)

    async def start_day_discussion(self, game: GameInstance):
        game.current_phase = "day_discussion"
        game.current_day += 1
        logger.info(f"[Jogo #{game.text_channel.id}] --- Iniciando Dia {game.current_day} ---")
        await self._update_voice_permissions(game, mute=False)
        await self.play_sound_effect(game, "DAY_START")
        await send_public_message(self.bot, game.text_channel, f"☀️ **DIA {game.current_day}** ☀️\n{get_random_humor('DAY_START')}", game=game)
        self._start_timer(game, config.DAY_DISCUSSION_DURATION_SECONDS, self.start_day_voting)

    async def start_day_voting(self, game: GameInstance):
        game.current_phase = "day_voting"
        game.clear_daily_states()
        await self.play_sound_effect(game, "VOTE_START")
        await send_public_message(self.bot, game.text_channel, f"⏳ **VOTAÇÃO ABERTA!** ⏳\n{get_random_humor('VOTE_START')}", game=game)
        for player_state in game.get_alive_players_states():
            await send_dm_safe(player_state.member, "Use `/votar [nome]` na nossa DM para me dizer quem deve ser linchado.")
        self._start_timer(game, config.VOTE_DURATION_SECONDS, self.end_day_voting)

    async def end_day_voting(self, game: GameInstance):
        if not game.is_day_voting(): return
        logger.info(f"[Jogo #{game.text_channel.id}] --- Fim da Votação ---")
        await send_public_message(self.bot, game.text_channel, "Votação encerrada! Calculando os resultados... 🔥", game=game)
        lynch_result = await self.action_resolver.process_lynch(game)
        if lynch_result.get("sound_event"): await self.play_sound_effect(game, lynch_result["sound_event"])
        for msg in lynch_result.get("public_messages", []):
            await send_public_message(self.bot, game.text_channel, msg, game=game); await asyncio.sleep(1)
        if lynch_result.get("game_over"): return
        if await self.check_game_end(game, "após o linchamento"): return
        if game.current_night >= config.MAX_GAME_NIGHTS:
            await self.check_seventh_day_win(game)
        else:
            await self.start_night(game)

    async def handle_sheriff_shot(self, game: GameInstance, sheriff: discord.Member, target: discord.Member):
        await self.play_sound_effect(game, "SHERIFF_SHOT")
        await send_public_message(self.bot, game.text_channel, f"**BANG!** 💥 {sheriff.mention}, o Xerife, atira em {target.mention}!", allowed_mentions=discord.AllowedMentions(users=True))
        game.sheriff_shots_fired += 1
        game.sheriff_shot_this_day = True
        if not game.sheriff_revealed:
            game.sheriff_revealed = True
            await send_public_message(self.bot, game.text_channel, f"🚨 {sheriff.mention} se revelou como o **Xerife**! ⭐")
        target_role = game.get_player_state_by_id(target.id).role
        if isinstance(target_role, AssassinoAlfa):
            winners = [p.member for p in game.players.values() if p.role.faction == "Cidade"]
            await self.end_game(game, "Vitória da Cidade!", winners, "Cidade", "O Xerife eliminou o Assassino Alfa!", sound_event_key="SHERIFF_WIN")
            return
        if isinstance(target_role, Prefeito):
            winners = [p.member for p in game.players.values() if p.role.faction == "Vilões"]
            await self.end_game(game, "Vitória dos Vilões!", winners, "Vilões", "O Xerife eliminou o Prefeito!", sound_event_key="VILLAINS_WIN")
            return
        game.killers[target.id] = sheriff.id
        await self.process_death(game, target, "shot_by_sheriff")
        await self.check_game_end(game, f" após o disparo do Xerife em {target.display_name}")

    async def process_death(self, game: GameInstance, target_member: discord.Member, reason: str):
        target_state = game.get_player_state_by_id(target_member.id)
        if not target_state or not target_state.is_alive: return
        logger.info(f"[Jogo #{game.text_channel.id}] Processando morte de {target_member.display_name} por: {reason}.")
        game.death_reasons[target_member.id] = reason
        target_state.kill()
        await self._set_member_mute(game, target_member, True, "Jogador eliminado")
        if game.first_death_id is None: game.first_death_id = target_member.id
        if isinstance(target_state.role, Fofoqueiro) and game.fofoqueiro_marked_target_id:
            if marked := game.get_player_state_by_id(game.fofoqueiro_marked_target_id):
                await send_public_message(self.bot, game.text_channel, f"💬 Em seu último suspiro, o Fofoqueiro revela: **{marked.member.display_name}** era **{marked.role.name}**!", game=game)
        if isinstance(target_state.role, AssassinoJunior) and game.junior_marked_target_id:
            if marked := game.get_player_state_by_id(game.junior_marked_target_id):
                await send_public_message(self.bot, game.text_channel, f"💥 O espírito vingativo de {target_member.display_name} leva **{marked.member.display_name}** junto!", game=game)
                await self.process_death(game, marked.member, "killed_by_junior_curse")
                return
        if game.lovers and target_member.id in game.lovers:
            other_lover_id = game.lovers[0] if target_member.id == game.lovers[1] else game.lovers[1]
            if other := game.get_player_state_by_id(other_lover_id):
                await send_public_message(self.bot, game.text_channel, f"💔 Ao ver seu amor morrer, **{other.member.display_name}** morreu de coração partido!", game=game)
                await self.process_death(game, other.member, "heartbreak")
                return
        if game.headhunter_info and game.headhunter_info['target_id'] == target_member.id:
            if hunter := game.get_player_state_by_id(game.headhunter_info['hunter_id']):
                if reason != "lynched":
                    hunter.role = CidadaoComum()
                    await send_dm_safe(hunter.member, "Seu alvo foi eliminado. Você se tornou um **Cidadão Comum**.")
                    game.headhunter_info = None
        await self.check_game_end(game, f"após a morte de {target_member.display_name}", victim=target_member)
            
    async def check_game_end(self, game: GameInstance, context: str, victim: Optional[discord.Member] = None) -> bool:
        if not self.bot.game_manager.get_game(game.text_channel.id): return True
        if victim and game.headhunter_info and victim.id == game.headhunter_info['target_id'] and game.death_reasons.get(victim.id) == "lynched":
            if hunter := game.get_player_state_by_id(game.headhunter_info['hunter_id']):
                await self.end_game(game, "Vitória do Caçador de Cabeças!", [hunter.member], "Solo (Caçador de Cabeças)", "O contrato foi cumprido!", sound_event_key="HEADHUNTER_WIN"); return True
        alive_players = game.get_alive_players_states()
        if not alive_players:
            await self.end_game(game, "Empate catastrófico!", [], "Ninguém", f"Todos morreram {context}."); return True
        villains_alive = [p for p in alive_players if p.role.faction == "Vilões"]
        prefeito_state = next((p for p in game.players.values() if isinstance(p.role, Prefeito)), None)
        if not villains_alive:
            if prefeito_state and prefeito_state.is_alive:
                city_winners = [p.member for p in game.players.values() if p.role.faction == "Cidade"]
                await self.end_game(game, "Vitória da Cidade!", city_winners, "Cidade", "A Cidade eliminou todos os vilões e seu líder permaneceu de pé!")
                return True
            elif prefeito_state and not prefeito_state.is_alive:
                anjo_pode_reviver = any(isinstance(p.role, Anjo) and not game.angel_revive_used for p in alive_players)
                bruxo_pode_reviver = any(isinstance(p.role, Bruxo) and not game.witch_potion_used for p in alive_players)
                if anjo_pode_reviver or bruxo_pode_reviver:
                    game.pending_resolution = True
                    await self._announce_revival_chance(game); await self.start_night(game); return True
                else:
                    await self.check_seventh_day_win(game, is_resolution=True); return True
            else:
                await self.check_seventh_day_win(game, is_resolution=True); return True
        num_villains, num_non_villains = len(villains_alive), len(alive_players) - len(villains_alive)
        if num_villains >= num_non_villains:
            await self.end_game(game, "Vitória dos Vilões!", [p.member for p in villains_alive], "Vilões", "Os Vilões atingiram a paridade!")
            return True
        return False

    async def _announce_revival_chance(self, game: GameInstance):
        can_revive_roles = []
        if any(isinstance(p.role, Anjo) for p in game.get_alive_players_states()) and not game.angel_revive_used: can_revive_roles.append("um Anjo")
        if any(isinstance(p.role, Bruxo) for p in game.get_alive_players_states()) and not game.witch_potion_used: can_revive_roles.append("um Bruxo")
        if not can_revive_roles: return
        message = f"🚨 **ALERTA** 🚨\nOs Vilões foram eliminados, mas o Prefeito caiu!\nO destino da cidade está nas mãos de **{' e '.join(can_revive_roles)}**."
        await send_public_message(self.bot, game.text_channel, message=message, game=game)

    async def _resolve_pending_endgame(self, game: GameInstance):
        game.pending_resolution = False
        prefeito_state = next((p for p in game.players.values() if isinstance(p.role, Prefeito)), None)
        if prefeito_state and prefeito_state.is_alive:
            winners = [p.member for p in game.players.values() if p.role.faction == "Cidade"]
            await self.end_game(game, "Vitória da Cidade!", winners, "Cidade", "O milagre aconteceu! O Prefeito foi revivido!")
        else:
            await self.check_seventh_day_win(game, is_resolution=True)
            
    async def check_seventh_day_win(self, game: GameInstance, is_resolution: bool = False):
        logger.info(f"[Jogo #{game.text_channel.id}] Verificando vitória do Sétimo Dia.")
        alive_players = game.get_alive_players_states()
        prefeito_state = next((p for p in alive_players if isinstance(p.role, Prefeito)), None)
        living_villains = [p for p in alive_players if p.role.faction == "Vilões"]
        if prefeito_state and living_villains and not is_resolution: await self._seventh_day_confrontation(game); return
        if game.lovers and all(p.is_alive for p in (game.get_player_state_by_id(game.lovers[0]), game.get_player_state_by_id(game.lovers[1]))):
                winners = [game.get_player_by_id(pid) for pid in game.lovers]
                if cupido := next((p for p in game.players.values() if isinstance(p.role, Cupido)), None): winners.append(cupido.member)
                await self.end_game(game, "Vitória dos Amantes!", list(set(winners)), "Solo (Amantes)", "O amor sobreviveu.", sound_event_key="LOVERS_WIN"); return
        if corruptor := next((p for p in alive_players if isinstance(p.role, Corruptor)), None):
            await self.end_game(game, "Vitória do Corruptor!", [corruptor.member], "Solo (Corruptor)", "Com a cidade em desordem, o Corruptor sobreviveu!", sound_event_key="CORRUPTOR_WIN"); return
        winners = [p.member for p in game.players.values() if p.role.faction == "Cidade" and p.is_alive]
        if winners: await self.end_game(game, "Vitória da Cidade!", winners, "Cidade", "A Cidade resistiu bravamente!"); return
        await self.end_game(game, "Empate por Impasse!", [], "Ninguém", "O tempo acabou e a situação ficou indefinida.")

    async def _seventh_day_confrontation(self, game: GameInstance):
        await send_public_message(self.bot, game.text_channel, "O Sétimo Dia chegou! O destino da cidade será decidido em um **Confronto Final!**")
        if await self._sheriff_showdown_loop(game): return
        if not self.bot.game_manager.get_game(game.text_channel.id): return
        await self._villain_final_attack(game)

    async def _sheriff_showdown_loop(self, game: GameInstance) -> bool:
        xerife_state = next((p for p in game.get_alive_players_states() if isinstance(p.role, Xerife)), None)
        max_shots = 1 if len(game.players) <= 6 else 2
        if not xerife_state or game.sheriff_shots_fired >= max_shots: return False
        while game.sheriff_shots_fired < max_shots and self.bot.game_manager.get_game(game.text_channel.id):
            targets = [p.member for p in game.get_alive_players_states() if p.member.id != xerife_state.member.id]
            if not targets: break
            view = ShowdownView(xerife_state.member, targets, timeout=120.0)
            await game.text_channel.send(f"**{xerife_state.member.mention}**, escolha seu alvo para o disparo {game.sheriff_shots_fired + 1}:", view=view)
            await view.wait()
            game.sheriff_shots_fired += 1
            if not view.result: await send_public_message(self.bot, game.text_channel, f"O Xerife {xerife_state.member.mention} não agiu e perdeu uma bala!"); continue
            target_member = game.guild.get_member(view.result)
            await send_public_message(self.bot, game.text_channel, f"{xerife_state.member.mention} atira em **{target_member.mention}**!")
            await self.handle_sheriff_shot(game, xerife_state.member, target_member)
            if not self.bot.game_manager.get_game(game.text_channel.id): return True
            await asyncio.sleep(2)
        return not self.bot.game_manager.get_game(game.text_channel.id)

    async def _villain_final_attack(self, game: GameInstance):
        vilões_vivos = [p for p in game.get_alive_players_states() if p.role.faction == "Vilões"]
        attacker_state = next((p for p in vilões_vivos if isinstance(p.role, AssassinoAlfa)), vilões_vivos[0] if vilões_vivos else None)
        if not attacker_state: await self.check_seventh_day_win(game, is_resolution=True); return
        targets = [p.member for p in game.get_alive_players_states() if p.role.faction == "Cidade"]
        if not targets: await self.end_game(game, "Vitória dos Vilões!", [p.member for p in vilões_vivos], "Vilões", "Não restaram alvos para o ataque final!"); return
        view = ShowdownView(attacker_state.member, targets, timeout=120.0)
        await game.text_channel.send(f"**{attacker_state.member.mention}**, escolha seu alvo para o ataque final:", view=view)
        await view.wait()
        if not view.result: await self.end_game(game, "Vitória da Cidade!", [p.member for p in game.players.values() if p.role.faction == "Cidade"], "Cidade", "Os Vilões hesitaram e a Cidade venceu!"); return
        target_member = game.guild.get_member(view.result)
        await send_public_message(self.bot, game.text_channel, f"O {attacker_state.role.name} ataca **{target_member.mention}**!")
        if isinstance(game.get_player_state_by_id(target_member.id).role, Prefeito):
            await self.end_game(game, "Vitória dos Vilões!", [p.member for p in vilões_vivos], "Vilões", f"O {attacker_state.role.name} eliminou o Prefeito!")
        else:
            await self.end_game(game, "Vitória da Cidade!", [p.member for p in game.players.values() if p.role.faction == "Cidade"], "Cidade", "O Prefeito sobreviveu ao ataque final!")

    async def _check_and_award_secondary_winners(self, game: GameInstance, winners: List[discord.Member], winning_faction: str) -> List[discord.Member]:
        final_winners = list(winners)
        winner_ids = {w.id for w in final_winners}
        if bruxo_state := next((p for p in game.players.values() if isinstance(p.role, Bruxo)), None):
            bruxo_wins = False
            for action in game.successful_major_actions:
                if action['actor'] == bruxo_state.member.id and (target_state := game.get_player_state_by_id(action['target'])):
                    if (action['action'] == 'kill' and ((isinstance(target_state.role, Prefeito) and winning_faction == "Vilões") or (isinstance(target_state.role, AssassinoAlfa) and winning_faction == "Cidade"))) or \
                       (action['action'] == 'revive' and target_state.role.faction == winning_faction):
                        bruxo_wins = True; break
            if bruxo_wins and bruxo_state.member.id not in winner_ids: final_winners.append(bruxo_state.member)
        if game.lovers and (game.lovers[0] in winner_ids or game.lovers[1] in winner_ids):
            for lover_id in game.lovers:
                if lover_id not in winner_ids and (l_state := game.get_player_state_by_id(lover_id)) and l_state.is_alive: final_winners.append(l_state.member)
            if (cupido := next((p for p in game.players.values() if isinstance(p.role, Cupido)), None)) and cupido.member.id not in winner_ids: final_winners.append(cupido.member)
        if winning_faction in ["Cidade", "Vilões"]:
            if (fofoqueiro := next((p for p in game.get_alive_players_states() if isinstance(p.role, Fofoqueiro)), None)) and fofoqueiro.member.id not in winner_ids:
                final_winners.append(fofoqueiro.member)
        return list(set(final_winners))

    async def _send_public_end_game_messages(self, game: GameInstance, title: str, final_winners: List[discord.Member], faction: str, reason: str, sound_event_key: Optional[str] = None):
        """Função auxiliar para enviar as mensagens públicas de fim de jogo."""
        embed = discord.Embed(title=f"🏁 FIM DE JOGO: {title} 🏁", description=f"**Motivo:** {reason}", color=discord.Color.gold())
        embed.add_field(name=f"🏆 Vencedores", value=("\n".join([w.mention for w in final_winners]) if final_winners else "Ninguém"), inline=False)
        roles_text = "\n".join([f"- {p.member.mention}: **{p.role.name}** ({p.role.faction})" for p in game.players.values() if p.role])
        embed.add_field(name="🕵️ Papéis Revelados 🕵️", value=roles_text or "N/A", inline=False)
        
        image_key = sound_event_key or ("CITY_WIN" if "Cidade" in faction else "VILLAINS_WIN" if "Vilões" in faction else None)
        image_path = os.path.join(config.IMAGES_PATH, config.EVENT_IMAGES.get(image_key, "")) if image_key else None
        
        await send_public_message(self.bot, game.text_channel, embed=embed, file_path=image_path if image_path and os.path.exists(image_path) else None)
        await asyncio.sleep(2)
        await send_public_message(self.bot, game.text_channel, message=config.MSG_CREDITS)

    async def end_game(self, game: GameInstance, title: str, winners: List[discord.Member], faction: str, reason: str, error: bool = False, sound_event_key: Optional[str] = None):
        if not self.bot.game_manager.get_game(game.text_channel.id) and not error: return
        
        try:
            final_winners = await self._check_and_award_secondary_winners(game, winners, faction)
            winner_ids = {w.id for w in final_winners}
            
            public_announcement_task = asyncio.create_task(self._send_public_end_game_messages(game, title, final_winners, faction, reason, sound_event_key))
            
            hosting_channel = self.bot.get_channel(config.CARD_HOSTING_CHANNEL_ID)
            if not hosting_channel:
                logger.error(f"CRÍTICO: Canal de hospedagem de cards com ID {config.CARD_HOSTING_CHANNEL_ID} não encontrado. Pulando geração de cards.")
            else:
                for p_state in game.players.values():
                    if not p_state.role: continue
                    outcome = "VICTORY" if p_state.member.id in winner_ids else "DEFEAT"
                    try:
                        card_path = await self.bot.loop.run_in_executor(None, self.image_generator.generate_summary_card, p_state.member.display_name, p_state.member.display_avatar.url, p_state.role.name, p_state.role.image_file, outcome, str(p_state.member.id))
                        msg = await hosting_channel.send(file=discord.File(card_path))
                        cdn_url = msg.attachments[0].url
                        site_url = f"https://fezudo98.github.io/cidadedorme-site/compartilhar.html?img={cdn_url}"
                        dm_message = (f"Aqui está o resumo da sua última partida!\n\nClique no link abaixo para ver e salvar sua imagem. Perfeito para compartilhar nos Stories!\n\n➡️ **[Ver Meu Resumo]({site_url})** ⬅️")
                        await send_dm_safe(p_state.member, message=dm_message)
                    except Exception as e:
                        logger.error(f"Falha total no processo de gerar/enviar card para {p_state.member.display_name}: {e}", exc_info=True)

            await public_announcement_task

            game.current_phase = "finished"
            if game.current_timer_task: game.current_timer_task.cancel()
            
            await self._update_voice_permissions(game, mute=False, force_unmute_all=True)
            if (vc := discord.utils.get(self.bot.voice_clients, guild=game.guild)) and vc.is_connected():
                if sound_event_key: await self.play_sound_effect(game, sound_event_key, wait_for_finish=True)
                await vc.disconnect(force=True)

            if not error and (ranking_cog := self.bot.get_cog("RankingCog")):
                await ranking_cog.update_stats_after_game(game, final_winners)
        
        finally:
            self.bot.game_manager.end_game(game.text_channel.id)

def setup(bot: commands.Bot):
    bot.add_cog(GameFlowCog(bot))