# cogs/actions.py

"""
Cog de Interface de Ações do Jogador.

Este Cog é responsável por definir todos os comandos de barra (/slash commands)
que os jogadores usam para realizar suas ações durante a partida, como proteger,
eliminar, votar, etc.

A principal responsabilidade deste arquivo é:
1. Validar se um jogador pode usar um comando (através de decoradores).
2. Receber a entrada do jogador (ex: o alvo de uma habilidade).
3. Registrar a "intenção" da ação no objeto GameInstance.
4. Enviar uma mensagem de confirmação para o jogador.

A lógica complexa de COMO essas ações interagem e são resolvidas foi
abstraída para a classe ActionResolver em `core/action_resolver.py`.
"""

import discord
from discord.ext import commands
from discord import option, ApplicationContext
import logging
import asyncio
import random
from typing import Optional, List

from .game_instance import GameInstance, PlayerState
from .utils import send_dm_safe, send_public_message
from roles.base_role import Role
from roles.cidade_roles import GuardaCostas, Detetive, Anjo, Xerife, Prefeito, Medium, VidenteDeAura
from roles.viloes_roles import AssassinoAlfa, AssassinoJunior, Cumplice, AssassinoSimples
from roles.solo_roles import Palhaco, Fofoqueiro, Bruxo, Cupido, Praga, Corruptor

logger = logging.getLogger(__name__)

# --- Funções de Autocomplete e Ajuda (Permanecem aqui, pois são usadas pelos comandos) ---

async def search_alive_players(ctx: discord.AutocompleteContext) -> list:
    game = ctx.bot.game_manager.get_game_by_player(ctx.interaction.user.id) if isinstance(ctx.interaction.channel, discord.DMChannel) else ctx.bot.game_manager.get_game(ctx.interaction.channel_id)
    if not game: return []
    return [p.member.display_name for p in game.get_alive_players_states() if p.member.display_name.lower().startswith(ctx.value.lower())]

async def search_dead_players(ctx: discord.AutocompleteContext) -> list:
    game = ctx.bot.game_manager.get_game_by_player(ctx.interaction.user.id) if isinstance(ctx.interaction.channel, discord.DMChannel) else ctx.bot.game_manager.get_game(ctx.interaction.channel_id)
    if not game: return []
    return [p.member.display_name for p in game.players.values() if not p.is_alive and p.member.display_name.lower().startswith(ctx.value.lower())]

def find_player_by_name(game: GameInstance, name: str, alive_only: bool = True) -> Optional[discord.Member]:
    name_lower = name.lower()
    for player_state in game.players.values():
        if player_state.member.display_name.lower() == name_lower:
            if (alive_only and player_state.is_alive) or not alive_only:
                return player_state.member
    matches = [p_state.member for p_state in game.players.values() if p_state.member.display_name.lower().startswith(name_lower) and ((alive_only and p_state.is_alive) or not alive_only)]
    if len(matches) == 1: return matches[0]
    return None

def find_dead_player_by_name(game: GameInstance, name: str) -> Optional[discord.Member]:
    player_state = next((ps for ps in game.players.values() if ps.member.display_name.lower() == name.lower() and not ps.is_alive), None)
    return player_state.member if player_state else None

# --- Decorators para Checagens (Permanecem aqui para proteger os comandos) ---

def get_game_instance(ctx: ApplicationContext) -> Optional[GameInstance]:
    return ctx.bot.game_manager.get_game_by_player(ctx.author.id) if isinstance(ctx.channel, discord.DMChannel) else ctx.bot.game_manager.get_game(ctx.channel.id)

def game_check(check_function):
    async def predicate(ctx: ApplicationContext):
        game = get_game_instance(ctx)
        if not game: await ctx.respond("Não encontrei uma partida ativa para você ou neste canal.", ephemeral=True); return False
        ctx.game = game
        return await check_function(ctx, game)
    return commands.check(predicate)

def check_game_phase(allowed_phases: List[str]):
    async def check(ctx, game: GameInstance):
        if game.current_phase not in allowed_phases: await ctx.respond(f"Ação inválida para a fase atual ({game.current_phase}).", ephemeral=True); return False
        return True
    return game_check(check)

def check_player_state(requires_alive: bool = True, requires_dm: bool = True):
    async def check(ctx, game: GameInstance):
        if requires_dm and ctx.command.name not in ["disparar", "sabotar", "fraudar"] and not isinstance(ctx.channel, discord.DMChannel):
            await ctx.respond("Essa ação é secreta! Use este comando na nossa conversa privada (DM).", ephemeral=True); return False
        player_state = game.get_player_state_by_id(ctx.author.id)
        if not player_state: await ctx.respond("Você não está nesta partida.", ephemeral=True); return False
        if requires_alive and not player_state.is_alive and ctx.command.name != "assombrar": await ctx.respond("Fantasmas não podem fazer ações. 👻", ephemeral=True); return False
        return True
    return game_check(check)

def check_role(allowed_roles: List[type]):
    async def check(ctx, game: GameInstance):
        player_state = game.get_player_state_by_id(ctx.author.id)
        if not player_state or not isinstance(player_state.role, tuple(allowed_roles)): await ctx.respond("Você não tem o papel necessário para usar este comando.", ephemeral=True); return False
        if game.is_night() and player_state.is_corrupted: await ctx.respond("Sua mente está turva... Você não consegue usar suas habilidades esta noite.", ephemeral=True); return False
        return True
    return game_check(check)

def check_is_ghost():
    async def check(ctx, game: GameInstance):
        player_state = game.get_player_state_by_id(ctx.author.id)
        if not player_state or not player_state.is_ghost: await ctx.respond("Apenas Fantasmas podem assombrar...", ephemeral=True); return False
        return True
    return game_check(check)

def record_night_action(game: GameInstance, player_id: int, role: Role, action_name: str, target_id: Optional[int] = None, priority: int = 50, **kwargs):
    game.night_actions[player_id] = {"action": action_name, "target_id": target_id, "role": role, "priority": priority, **kwargs}
    logger.info(f"[Jogo #{game.text_channel.id}] Ação noturna '{action_name}' registrada para {player_id} -> {target_id}")

# =====================================================================================
# --- CLASSE DO COG DE AÇÕES ---
# =====================================================================================

class ActionsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        logger.info("Cog Actions (Interface) carregado.")

    async def distribute_initial_info(self, game: GameInstance):
        """Envia informações iniciais aos jogadores na primeira noite (ex: parceiros vilões)."""
        logger.info(f"[Jogo #{game.text_channel.id}] Distribuindo informações iniciais da Noite 1.")
        tasks = []
        villains = [p for p in game.players.values() if p.role and p.role.faction == "Vilões"]
        villain_names = [v.member.display_name for v in villains]
        for villain_state in villains:
            other_villains = [name for name in villain_names if name != villain_state.member.display_name]
            message = f"Olá, {villain_state.role.name}. 🤫 Seus parceiros no crime são: **{', '.join(other_villains)}**." if other_villains else f"Olá, {villain_state.role.name}. Você é a única ameaça da sua facção. Aja com cuidado."
            tasks.append(send_dm_safe(villain_state.member, message=message))
        await asyncio.gather(*tasks)

    # --- Comandos com Efeito Imediato (Mudança de Fase ou de Flags) ---

    @commands.slash_command(name="decreto", description="(Prefeito) Amplifica o poder de voto da Cidade (1x por jogo).")
    @check_game_phase(["day_voting"])
    @check_player_state()
    @check_role([Prefeito])
    async def decreto(self, ctx: ApplicationContext):
        game = ctx.game
        if game.decreto_used: await ctx.respond("Você já usou seu Decreto nesta partida.", ephemeral=True); return
        game.decreto_used = game.decreto_active = game.sabotage_blocked = True
        await send_public_message(self.bot, game.text_channel, "O Prefeito invocou um **DECRETO DE EMERGÊNCIA**!")
        await ctx.respond("Seu Decreto foi proclamado!", ephemeral=True)

    @commands.slash_command(name="sabotar", description="(Assassino Alfa) Pula o dia e vai direto para a noite (1x por jogo).")
    @check_game_phase(["day_discussion", "day_voting"])
    @check_player_state(requires_dm=False)
    @check_role([AssassinoAlfa])
    async def sabotar(self, ctx: ApplicationContext):
        game = ctx.game
        if game.sabotage_blocked: await ctx.respond("Você não pode sabotar durante um Decreto de Emergência!", ephemeral=True); return
        if game.sabotage_used: await ctx.respond("A sabotagem já foi usada nesta partida.", ephemeral=True); return
        game.sabotage_used = True
        game_flow_cog = self.bot.get_cog("GameFlowCog")
        if game_flow_cog:
            await ctx.respond("Sabotagem ativada!", ephemeral=True)
            await send_public_message(self.bot, game.text_channel, "🚨 **SABOTAGEM!** 🚨 O dia é interrompido bruscamente...")
            await game_flow_cog.force_night(game)

    @commands.slash_command(name="fraudar", description="(Cúmplice) Embaralha os votos da votação atual (1x por jogo).")
    @check_game_phase(["day_voting"])
    @check_player_state(requires_dm=False)
    @check_role([Cumplice])
    async def fraudar(self, ctx: ApplicationContext):
        game = ctx.game
        if game.fraud_used: await ctx.respond("Você já usou sua habilidade de fraudar nesta partida.", ephemeral=True); return
        game.fraud_used = game.fraud_active = True
        await ctx.respond("Fraude ativada! Os resultados serão... inesperados.", ephemeral=True)
        await send_public_message(self.bot, game.text_channel, "🎭 Uma onda de desinformação se espalha! A votação foi comprometida...")

    @commands.slash_command(name="disparar", description="(Xerife) Atira em um jogador durante o dia.")
    @check_game_phase(["day_discussion", "day_voting"])
    @check_player_state(requires_dm=False)
    @check_role([Xerife])
    @option("jogador", description="O jogador em quem você quer atirar.", autocomplete=search_alive_players)
    async def disparar(self, ctx: ApplicationContext, jogador: str):
        game = ctx.game
        game_flow_cog = self.bot.get_cog("GameFlowCog")
        max_shots = 1 if len(game.players) <= 6 else 2
        if game.sheriff_shot_this_day: await ctx.respond("Você só pode disparar uma vez por dia.", ephemeral=True); return
        if game.sheriff_shots_fired >= max_shots: await ctx.respond(f"Você já gastou suas {max_shots} balas.", ephemeral=True); return
        target_member = find_player_by_name(game, jogador)
        if not target_member: await ctx.respond(f"Não achei o jogador '{jogador}'.", ephemeral=True); return
        if target_member.id == ctx.author.id: await ctx.respond("Atirar em si mesmo não é boa ideia.", ephemeral=True); return
        
        # O disparo do Xerife é uma ação com consequências imediatas e complexas
        # que alteram o fluxo do jogo, por isso sua lógica permanece no GameFlow.
        if game_flow_cog:
            await ctx.respond("Disparo efetuado!", ephemeral=True)
            await game_flow_cog.handle_sheriff_shot(game, ctx.author, target_member)

    # --- Comandos que Registram Ações Noturnas ---

    @commands.slash_command(name="possuir", description="(Assassino Alfa) Tenta converter um jogador para a sua facção.")
    @check_game_phase(["night"])
    @check_player_state()
    @check_role([AssassinoAlfa])
    @option("jogador", description="O alvo da sua influência maligna.", autocomplete=search_alive_players)
    async def possuir(self, ctx: ApplicationContext, jogador: str):
        game = ctx.game
        if len(game.players) < 11: await ctx.respond("A habilidade de Possuir só está disponível com 11+ jogadores.", ephemeral=True); return
        target_member = find_player_by_name(game, jogador)
        if not target_member: await ctx.respond(f"Não achei o jogador vivo '{jogador}'.", ephemeral=True); return
        if game.get_player_state_by_id(target_member.id).role.faction == "Vilões": await ctx.respond("Você não pode possuir quem já está do seu lado.", ephemeral=True); return
        player_state = game.get_player_state_by_id(ctx.author.id)
        record_night_action(game, ctx.author.id, player_state.role, "possess", target_member.id, priority=90)
        await ctx.respond(f"Sua influência maligna se espalha em direção a **{target_member.display_name}**.", ephemeral=True)

    @commands.slash_command(name="apaixonar", description="(Cupido) Escolha dois jogadores para se apaixonarem (Noite 1).")
    @check_game_phase(["night"])
    @check_player_state()
    @check_role([Cupido])
    @option("jogador1", autocomplete=search_alive_players)
    @option("jogador2", autocomplete=search_alive_players)
    async def apaixonar(self, ctx: ApplicationContext, jogador1: str, jogador2: str):
        game = ctx.game
        if game.current_night != 1: await ctx.respond("Você só pode usar essa magia na primeira noite!", ephemeral=True); return
        target1 = find_player_by_name(game, jogador1)
        target2 = find_player_by_name(game, jogador2)
        if not target1 or not target2: await ctx.respond(f"Não encontrei um ou ambos: '{jogador1}', '{jogador2}'.", ephemeral=True); return
        if target1 == target2: await ctx.respond("Escolha dois jogadores diferentes!", ephemeral=True); return
        player_state = game.get_player_state_by_id(ctx.author.id)
        record_night_action(game, ctx.author.id, player_state.role, "cupid_match", priority=10, lover1_id=target1.id, lover2_id=target2.id)
        await ctx.respond(f"Flecha disparada! 🏹 Você escolheu {target1.display_name} e {target2.display_name}.", ephemeral=True)

    @commands.slash_command(name="proteger", description="(Guarda-costas) Escolha um jogador para proteger esta noite.")
    @check_game_phase(["night"])
    @check_player_state()
    @check_role([GuardaCostas])
    @option("jogador", autocomplete=search_alive_players)
    async def proteger(self, ctx: ApplicationContext, jogador: str):
        game = ctx.game
        target_member = find_player_by_name(game, jogador)
        if not target_member: await ctx.respond(f"Não achei o jogador vivo '{jogador}'.", ephemeral=True); return
        if target_member.id == ctx.author.id: await ctx.respond("Você não pode proteger a si mesmo.", ephemeral=True); return
        if game.last_protected_target.get(ctx.author.id) == target_member.id: await ctx.respond("Você já protegeu essa pessoa na noite passada.", ephemeral=True); return
        player_state = game.get_player_state_by_id(ctx.author.id)
        record_night_action(game, ctx.author.id, player_state.role, "protect", priority=20, target_id=target_member.id)
        game.last_protected_target[ctx.author.id] = target_member.id
        await ctx.respond(f"Entendido! Você montará guarda para {target_member.display_name} esta noite.", ephemeral=True)

    @commands.slash_command(name="corromper", description="(Corruptor) Bloqueia a habilidade de um jogador esta noite.")
    @check_game_phase(["night"])
    @check_player_state()
    @check_role([Corruptor])
    @option("jogador", autocomplete=search_alive_players)
    async def corromper(self, ctx: ApplicationContext, jogador: str):
        game = ctx.game
        target_member = find_player_by_name(game, jogador)
        if not target_member: await ctx.respond(f"Não achei o jogador vivo '{jogador}'.", ephemeral=True); return
        if game.last_corrupted_target.get(ctx.author.id) == target_member.id: await ctx.respond("Você já corrompeu essa pessoa na noite passada.", ephemeral=True); return
        player_state = game.get_player_state_by_id(ctx.author.id)
        record_night_action(game, ctx.author.id, player_state.role, "corrupt", target_member.id, priority=15)
        game.last_corrupted_target[ctx.author.id] = target_member.id
        await ctx.respond(f"Você tentará corromper a mente de {target_member.display_name} esta noite.", ephemeral=True)

    @commands.slash_command(name="confundir", description="(Assassino Júnior) Força o alvo a errar sua próxima ação.")
    @check_game_phase(["night"])
    @check_player_state()
    @check_role([AssassinoJunior])
    @option("jogador", autocomplete=search_alive_players)
    async def confundir(self, ctx: ApplicationContext, jogador: str):
        game = ctx.game
        target_member = find_player_by_name(game, jogador)
        if not target_member: await ctx.respond(f"Não achei o jogador vivo '{jogador}'.", ephemeral=True); return
        if game.last_confused_target.get(ctx.author.id) == target_member.id: await ctx.respond("Você já confundiu essa pessoa na noite passada.", ephemeral=True); return
        player_state = game.get_player_state_by_id(ctx.author.id)
        record_night_action(game, ctx.author.id, player_state.role, "confuse", target_member.id, priority=16)
        game.last_confused_target[ctx.author.id] = target_member.id
        await ctx.respond(f"Você semeia a confusão na mente de **{target_member.display_name}**.", ephemeral=True)

    @commands.slash_command(name="eliminar", description="(Vilões/Bruxo) Escolha um jogador para tentar eliminar.")
    @check_game_phase(["night"])
    @check_player_state()
    @check_role([AssassinoAlfa, AssassinoJunior, Cumplice, Bruxo, AssassinoSimples])
    @option("jogador", autocomplete=search_alive_players)
    async def eliminar(self, ctx: ApplicationContext, jogador: str):
        game = ctx.game
        player_state = game.get_player_state_by_id(ctx.author.id)
        is_witch = isinstance(player_state.role, Bruxo)
        if is_witch and game.witch_potion_used: await ctx.respond("Sua única poção já foi usada.", ephemeral=True); return
        target_member = find_player_by_name(game, jogador)
        if not target_member: await ctx.respond(f"Não achei o jogador '{jogador}'.", ephemeral=True); return
        if target_member.id == ctx.author.id: await ctx.respond("Se auto-eliminar? Má ideia...", ephemeral=True); return
        if is_witch: game.bruxo_major_action = {"action": "kill", "target_id": target_member.id}
        action_name = "villain_vote" if not is_witch else "witch_kill"
        priority = 30 if not is_witch else 25
        record_night_action(game, ctx.author.id, player_state.role, action_name, target_member.id, priority=priority)
        await ctx.respond(f"Alvo marcado! {target_member.display_name} está na sua mira.", ephemeral=True)

    @commands.slash_command(name="reviver", description="(Anjo/Bruxo) Traga um jogador morto de volta à vida.")
    @check_game_phase(["night"])
    @check_player_state()
    @check_role([Anjo, Bruxo])
    @option("jogador", autocomplete=search_dead_players)
    async def reviver(self, ctx: ApplicationContext, jogador: str):
        game = ctx.game
        player_state = game.get_player_state_by_id(ctx.author.id)
        is_angel = isinstance(player_state.role, Anjo)
        is_witch = isinstance(player_state.role, Bruxo)
        if is_angel and game.angel_revive_used: await ctx.respond("Seu milagre já foi usado.", ephemeral=True); return
        if is_witch and game.witch_potion_used: await ctx.respond("Sua única poção já foi usada.", ephemeral=True); return
        target_member = find_dead_player_by_name(game, jogador)
        if not target_member: await ctx.respond(f"Não achei o jogador morto '{jogador}'.", ephemeral=True); return
        if is_witch: game.bruxo_major_action = {"action": "revive", "target_id": target_member.id}
        action_name = "angel_revive" if is_angel else "witch_revive"
        record_night_action(game, ctx.author.id, player_state.role, action_name, target_member.id, priority=40)
        await ctx.respond(f"Você tentará trazer {target_member.display_name} de volta do além.", ephemeral=True)

    @commands.slash_command(name="marcar", description="(Detetive) Marque um ou dois jogadores para investigar.")
    @check_game_phase(["night"])
    @check_player_state()
    @check_role([Detetive])
    @option("jogador1", autocomplete=search_alive_players)
    @option("jogador2", autocomplete=search_alive_players, required=False)
    async def marcar(self, ctx: ApplicationContext, jogador1: str, jogador2: str = None):
        game = ctx.game
        num_players = len(game.players)
        player_state = game.get_player_state_by_id(ctx.author.id)
        if num_players <= 5:
            if jogador2 is not None: await ctx.respond("Em partidas pequenas, só pode investigar uma pessoa.", ephemeral=True); return
            target1 = find_player_by_name(game, jogador1)
            if not target1: await ctx.respond(f"Não encontrei o jogador '{jogador1}'.", ephemeral=True); return
            record_night_action(game, ctx.author.id, player_state.role, "mark_detective", priority=60, target1_id=target1.id, target2_id=None)
            await ctx.respond(f"Você está de olho em {target1.display_name} esta noite.", ephemeral=True)
        else:
            if jogador2 is None: await ctx.respond("Em partidas com mais de 5 jogadores, marque duas pessoas.", ephemeral=True); return
            target1 = find_player_by_name(game, jogador1)
            target2 = find_player_by_name(game, jogador2)
            if not target1 or not target2: await ctx.respond(f"Não encontrei '{jogador1}' ou '{jogador2}'.", ephemeral=True); return
            if target1 == target2: await ctx.respond("Escolha dois jogadores diferentes!", ephemeral=True); return
            record_night_action(game, ctx.author.id, player_state.role, "mark_detective", priority=60, target1_id=target1.id, target2_id=target2.id)
            await ctx.respond(f"Você está de olho em {target1.display_name} e {target2.display_name} esta noite.", ephemeral=True)

    @commands.slash_command(name="mediunidade", description="(Médium) Converte um jogador morto em um Fantasma aliado.")
    @check_game_phase(["night"])
    @check_player_state()
    @check_role([Medium])
    @option("jogador_morto", autocomplete=search_dead_players)
    async def mediunidade(self, ctx: ApplicationContext, jogador_morto: str):
        game = ctx.game
        if game.medium_talk_used: await ctx.respond("Você já usou seu poder de converter um Fantasma.", ephemeral=True); return
        target_member = find_dead_player_by_name(game, jogador_morto)
        if not target_member: await ctx.respond(f"Não encontrei o espírito '{jogador_morto}'.", ephemeral=True); return
        target_state = game.get_player_state_by_id(target_member.id)
        if target_state.is_ghost: await ctx.respond("Este espírito já está ligado a este plano.", ephemeral=True); return
        game.medium_talk_used = True
        target_state.is_ghost = True
        target_state.ghost_master_id = ctx.author.id
        await ctx.respond(f"Você estabeleceu uma conexão com o espírito de **{target_member.display_name}**!", ephemeral=True)
        ghost_embed = discord.Embed(title="👻 Você se tornou um Fantasma! 👻", description=f"O Médium **{ctx.author.display_name}** o trouxe de volta. Use `/assombrar` para vigiar alguém.", color=discord.Color.light_grey())
        await send_dm_safe(target_member, embed=ghost_embed)

    @commands.slash_command(name="assombrar", description="(Fantasma) Escolha um jogador para vigiar esta noite.")
    @check_game_phase(["night"])
    @check_player_state(requires_alive=False)
    @check_is_ghost()
    @option("jogador", autocomplete=search_alive_players)
    async def assombrar(self, ctx: ApplicationContext, jogador: str):
        game = ctx.game
        target_member = find_player_by_name(game, jogador)
        if not target_member: await ctx.respond(f"Não achei o jogador '{jogador}'.", ephemeral=True); return
        player_state = game.get_player_state_by_id(ctx.author.id)
        record_night_action(game, ctx.author.id, player_state.role, "haunt", target_member.id, priority=5)
        await ctx.respond(f"Você focará sua energia espectral em **{target_member.display_name}** esta noite.", ephemeral=True)

    @commands.slash_command(name="exterminar", description="(Praga) Libera a praga para eliminar todos os infectados.")
    @check_game_phase(["night"])
    @check_player_state()
    @check_role([Praga])
    async def exterminar(self, ctx: ApplicationContext):
        game = ctx.game
        if game.plague_exterminate_used: await ctx.respond("Você já tentou o extermínio uma vez.", ephemeral=True); return
        player_state = game.get_player_state_by_id(ctx.author.id)
        record_night_action(game, ctx.author.id, player_state.role, "plague_exterminate", priority=35)
        await ctx.respond("☣️ Você decidiu que é a hora! Você liberará o poder total da praga!", ephemeral=True)
    
    # --- Comandos com Resposta Imediata (Habilidades de Informação) ---
    
    @commands.slash_command(name="comparar", description="(Fofoqueiro) Vê se dois jogadores são do mesmo time (2x por jogo).")
    @check_game_phase(["night"])
    @check_player_state()
    @check_role([Fofoqueiro])
    @option("jogador1", autocomplete=search_alive_players)
    @option("jogador2", autocomplete=search_alive_players)
    async def comparar(self, ctx: ApplicationContext, jogador1: str, jogador2: str):
        game = ctx.game
        uses = game.fofoqueiro_comparisons.get(ctx.author.id, 0)
        if uses >= 2: await ctx.respond("Você já usou sua fofoca comparativa duas vezes.", ephemeral=True); return
        target1 = find_player_by_name(game, jogador1)
        target2 = find_player_by_name(game, jogador2)
        if not target1 or not target2: await ctx.respond(f"Não encontrei um ou ambos: '{jogador1}', '{jogador2}'.", ephemeral=True); return
        if target1.id == target2.id: await ctx.respond("Escolha dois jogadores diferentes.", ephemeral=True); return
        target1_state = game.get_player_state_by_id(target1.id)
        target2_state = game.get_player_state_by_id(target2.id)
        are_same_faction = target1_state.role.faction == target2_state.role.faction
        result_message = "são da mesma facção" if are_same_faction else "NÃO são da mesma facção"
        game.fofoqueiro_comparisons[ctx.author.id] = uses + 1
        await ctx.respond(f"Sua investigação revelou: **{target1.display_name}** e **{target2.display_name}** {result_message}. ({uses + 1}/2 usos)", ephemeral=True)

    @commands.slash_command(name="escolher_alvo", description="(Cúmplice/Júnior/Fofoqueiro/Praga) Escolha seu alvo inicial (Noite 1).")
    @check_game_phase(["night"])
    @check_player_state()
    @check_role([Cumplice, AssassinoJunior, Fofoqueiro, Praga])
    @option("jogador", autocomplete=search_alive_players)
    async def escolher_alvo(self, ctx: ApplicationContext, jogador: str):
        game = ctx.game
        if game.current_night != 1: await ctx.respond("Essa escolha só pode ser feita na primeira noite!", ephemeral=True); return
        target_member = find_player_by_name(game, jogador)
        if not target_member: await ctx.respond(f"Não achei o jogador '{jogador}'.", ephemeral=True); return
        player_state = game.get_player_state_by_id(ctx.author.id)
        
        # Cúmplice tem resultado imediato
        if isinstance(player_state.role, Cumplice):
            target_state = game.get_player_state_by_id(target_member.id)
            info_message = f"Investigação concluída! O papel de {target_member.display_name} é **{target_state.role.name}**."
            await ctx.respond(info_message, ephemeral=True)
            for villain_state in [p for p in game.players.values() if p.role and p.role.faction == "Vilões" and p.member.id != ctx.author.id]:
                await send_dm_safe(villain_state.member, f"🤫 O Cúmplice descobriu: {target_member.display_name} é **{target_state.role.name}**.")
            return

        # Outros papéis apenas registram a ação
        if isinstance(player_state.role, Praga): game.plague_patient_zero_id = target_member.id
        elif isinstance(player_state.role, AssassinoJunior): game.junior_marked_target_id = target_member.id
        elif isinstance(player_state.role, Fofoqueiro): game.fofoqueiro_marked_target_id = target_member.id
        
        action_name = f"{player_state.role.name.lower().replace(' ', '_')}_target"
        record_night_action(game, ctx.author.id, player_state.role, action_name, target_member.id, priority=70)
        await ctx.respond(f"Alvo definido! Você escolheu {target_member.display_name}.", ephemeral=True)

    @commands.slash_command(name="investigar_aura", description="(Vidente de Aura) Investiga a facção de um jogador.")
    @check_game_phase(["night"])
    @check_player_state()
    @check_role([VidenteDeAura])
    @option("jogador", autocomplete=search_alive_players)
    async def investigar_aura(self, ctx: ApplicationContext, jogador: str):
        game = ctx.game
        target_member = find_player_by_name(game, jogador)
        if not target_member: await ctx.respond(f"Não achei o jogador '{jogador}'.", ephemeral=True); return
        target_state = game.get_player_state_by_id(target_member.id)
        aura_result = "da Cidade" if target_state.role.faction == "Cidade" else "Não é da Cidade"
        await ctx.respond(f"A aura de {target_member.display_name} **{aura_result}**.", ephemeral=True)
        
    # --- Comandos de Votação Diurna ---

    @commands.slash_command(name="votar", description="Vote em quem você acha que deve ser linchado.")
    @check_game_phase(["day_voting"])
    @check_player_state(requires_dm=True)
    @check_role([]) # Permite que qualquer um vote
    @option("jogador", autocomplete=search_alive_players)
    async def votar(self, ctx: ApplicationContext, jogador: str):
        game = ctx.game
        target_member = find_player_by_name(game, jogador)
        if not target_member: await ctx.respond(f"Não achei o jogador '{jogador}'.", ephemeral=True); return
        if ctx.author.id in game.day_skip_votes: game.day_skip_votes.remove(ctx.author.id)
        game.day_votes[ctx.author.id] = target_member.id
        await ctx.respond(f"Seu voto em {target_member.display_name} foi registrado!", ephemeral=True)

    @commands.slash_command(name="pular", description="Vote para pular a votação do dia.")
    @check_game_phase(["day_voting"])
    @check_player_state()
    @check_role([]) # Permite que qualquer um pule
    async def pular(self, ctx: ApplicationContext):
        game = ctx.game
        player_id = ctx.author.id
        if player_id in game.day_votes: del game.day_votes[player_id]
        game.day_skip_votes.add(player_id)
        await ctx.respond("Seu voto para pular foi registrado!", ephemeral=True)
        num_alive = len(game.get_alive_players())
        majority_needed = (num_alive // 2) + 1
        if len(game.day_skip_votes) >= majority_needed:
            if game.current_timer_task and not game.current_timer_task.done(): game.current_timer_task.cancel()
            game_flow_cog = self.bot.get_cog("GameFlowCog")
            if game_flow_cog:
                await game_flow_cog.end_day_voting(game)


def setup(bot: commands.Bot):
    bot.add_cog(ActionsCog(bot))