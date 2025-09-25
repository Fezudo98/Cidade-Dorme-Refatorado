# cogs/game_instance.py

import discord
import logging
from typing import Optional, List, Dict, Tuple, Any
import asyncio

from roles.base_role import Role
from roles.cidade_roles import Xerife, Prefeito, Medium
from roles.viloes_roles import AssassinoAlfa, Cumplice, AssassinoJunior
from roles.solo_roles import Bruxo, Praga

logger = logging.getLogger(__name__)

class PlayerState:
    """Classe para armazenar o estado individual de um jogador dentro de uma partida."""
    __slots__ = (
        'member', 'role', 'is_alive', 'protected_by', 'is_corrupted', 
        'is_infected', 'possession_points', 
        # --- MUDANÇA AQUI ---
        'bodyguard_hits_survived', 
        'is_ghost', 'ghost_master_id', 'is_confused'
    )

    def __init__(self, member: discord.Member):
        self.member = member
        self.role: Optional[Role] = None
        self.is_alive = True
        self.protected_by: Optional[int] = None
        self.is_corrupted = False
        self.is_infected = False
        self.possession_points: int = 0
        # --- MUDANÇA AQUI ---
        self.bodyguard_hits_survived: int = 0
        self.is_ghost: bool = False
        self.ghost_master_id: Optional[int] = None
        self.is_confused: bool = False

    def assign_role(self, role_obj: Role):
        """Atribui um papel a este jogador."""
        self.role = role_obj
        logger.info(f"Papel {role_obj.name} atribuído a {self.member.display_name}")

    def kill(self):
        """Marca o jogador como morto."""
        self.is_alive = False
        logger.info(f"Jogador {self.member.display_name} foi marcado como morto.")

    def revive(self):
        """Marca o jogador como vivo e reseta suas flags de estado individuais."""
        self.is_alive = True
        # --- MUDANÇA AQUI ---
        self.bodyguard_hits_survived = 0
        self.is_ghost = False
        self.ghost_master_id = None
        self.is_confused = False
        logger.info(f"Jogador {self.member.display_name} foi revivido.")

class GameInstance:
    # ... (o resto da classe GameInstance permanece exatamente o mesmo, sem necessidade de colar aqui)
    # Apenas certifique-se de que a classe PlayerState foi atualizada como acima.
    # O restante do arquivo (a classe GameInstance inteira) não precisa ser modificado.
    """
    Classe para gerenciar o estado completo de UMA partida de Cidade Dorme.
    """
    # Aplicando __slots__ também na GameInstance para consistência e pequena economia.
    __slots__ = (
        'bot', 'text_channel', 'voice_channel', 'guild', 'game_master',
        'current_phase', 'current_night', 'current_day', 'pending_resolution',
        'current_timer_task', 'players', 'roles_in_game', 'night_actions',
        'day_votes', 'day_skip_votes', 'killers', 'death_reasons',
        'successful_major_actions', 'lovers', 'headhunter_info', 'sabotage_used',
        'decreto_used', 'fraud_used', 'witch_potion_used', 'angel_revive_used',
        'medium_talk_used', 'plague_exterminate_used', 'last_protected_target',
        'last_corrupted_target', 'last_confused_target', 'fofoqueiro_comparisons',
        'accomplice_target_info', 'decreto_active', 'sabotage_blocked',
        'fraud_active', 'sheriff_shot_this_day', 'night_revive_targets',
        'bruxo_major_action', 'plague_patient_zero_id', 'plague_player_id',
        'sheriff_shots_fired', 'sheriff_revealed', 'prefeito_saved_once',
        'junior_marked_target_id', 'fofoqueiro_marked_target_id',
        'winning_faction', 'first_death_id', 'skip_villain_kill',
        # --- NOVAS FLAGS DE NOTIFICAÇÃO DE ERRO ---
        'permission_error_notified', 'audio_error_notified', 'asset_error_notified'
    )

    def __init__(self, bot: discord.Bot, text_channel: discord.TextChannel, voice_channel: discord.VoiceChannel, game_master: discord.Member):
        # --- Contexto da Partida ---
        self.bot = bot
        self.text_channel = text_channel
        self.voice_channel = voice_channel
        self.guild = text_channel.guild
        self.game_master = game_master

        # --- Estado do Fluxo do Jogo ---
        self.current_phase = "preparing"
        self.current_night = 0
        self.current_day = 0
        self.pending_resolution: bool = False
        self.current_timer_task: Optional[asyncio.Task] = None
        
        # --- Dicionários de Estado ---
        self.players: Dict[int, PlayerState] = {}
        self.roles_in_game: List[Role] = []
        self.night_actions: Dict[int, dict] = {}
        self.day_votes: Dict[int, int] = {}
        self.day_skip_votes = set()
        self.killers: Dict[int, int] = {}
        self.death_reasons: Dict[int, str] = {}
        self.successful_major_actions: List[Dict[str, Any]] = []

        # --- Flags de Estado de Papéis e Habilidades ---
        self.lovers: Optional[Tuple[int, int]] = None
        self.headhunter_info: Optional[Dict[str, int]] = None
        self.sabotage_used: bool = False
        self.decreto_used: bool = False
        self.fraud_used: bool = False
        self.witch_potion_used: bool = False
        self.angel_revive_used: bool = False
        self.medium_talk_used: bool = False
        self.plague_exterminate_used: bool = False
        self.skip_villain_kill: bool = False
        self.last_protected_target: Dict[int, int] = {}
        self.last_corrupted_target: Dict[int, int] = {}
        self.last_confused_target: Dict[int, int] = {}
        self.fofoqueiro_comparisons: Dict[int, int] = {}
        self.accomplice_target_info: Dict[str, Any] = {}
        self.decreto_active: bool = False
        self.sabotage_blocked: bool = False
        self.fraud_active: bool = False
        self.sheriff_shot_this_day: bool = False
        self.night_revive_targets: List[int] = []
        self.bruxo_major_action: Optional[Dict[str, Any]] = None
        self.plague_patient_zero_id: Optional[int] = None
        self.plague_player_id: Optional[int] = None
        self.sheriff_shots_fired: int = 0
        self.sheriff_revealed: bool = False
        self.prefeito_saved_once: bool = False
        self.junior_marked_target_id: Optional[int] = None
        self.fofoqueiro_marked_target_id: Optional[int] = None
        
        # --- Estado Pós-Jogo ---
        self.winning_faction: Optional[str] = None
        self.first_death_id: Optional[int] = None

        # --- Flags de Notificação de Erro ---
        self.permission_error_notified: bool = False
        self.audio_error_notified: bool = False
        self.asset_error_notified: bool = False
        
        logger.info(f"Nova GameInstance criada para o canal #{text_channel.name} (ID: {text_channel.id})")

    def add_player(self, member: discord.Member):
        """Adiciona um jogador a esta instância do jogo e mapeia-o no GameManager."""
        if member.id not in self.players:
            self.players[member.id] = PlayerState(member)
            logger.debug(f"Jogador {member.display_name} adicionado à partida no canal #{self.text_channel.name}.")
            self.bot.game_manager.map_player_to_game(member.id, self.text_channel.id)

    def get_player_state_by_id(self, member_id: int) -> Optional[PlayerState]:
        return self.players.get(member_id)

    def get_alive_players(self) -> List[discord.Member]:
        return [state.member for state in self.players.values() if state.is_alive]
        
    def get_alive_players_states(self) -> List[PlayerState]:
        return [state for state in self.players.values() if state.is_alive]

    def get_player_by_id(self, user_id: int) -> Optional[discord.Member]:
        player_state = self.players.get(user_id)
        # Se não temos cache de membros, o objeto 'member' pode ficar desatualizado.
        # É mais seguro buscar na guild se a referência existir.
        if player_state:
            # Tenta retornar a referência que já temos
            if player_state.member:
                return player_state.member
            # Se a referência sumiu (improvável mas possível), busca na guild
            return self.guild.get_member(user_id)
        return None
    
    def clear_nightly_states(self):
        logger.info(f"[Jogo #{self.text_channel.id}] Resetando estados noturnos.")
        self.night_actions.clear()
        self.night_revive_targets.clear()
        self.skip_villain_kill = False # Resetar aqui
        for player_state in self.players.values():
            player_state.protected_by = None
            player_state.is_corrupted = False
            player_state.is_confused = False

    def clear_daily_states(self):
        logger.info(f"[Jogo #{self.text_channel.id}] Resetando estados diários.")
        self.day_votes.clear()
        self.day_skip_votes.clear()
        self.decreto_active = False
        self.sabotage_blocked = False
        self.fraud_active = False
        self.sheriff_shot_this_day = False

    def reset_flags_for_player(self, player_id: int):
        player_state = self.get_player_state_by_id(player_id)
        if not player_state or not player_state.role: return
        
        role = player_state.role
        logger.info(f"[Jogo #{self.text_channel.id}] Resetando flags para revivido: {player_state.member.display_name} ({role.name})")

        # --- NOVA LINHA ADICIONADA AQUI ---
        if isinstance(role, AssassinoJunior): self.junior_marked_target_id = None
        
        if isinstance(role, Xerife): self.sheriff_shots_fired = 0; self.sheriff_revealed = False
        if isinstance(role, Bruxo): self.witch_potion_used = False; self.bruxo_major_action = None
        if isinstance(role, Medium): self.medium_talk_used = False
        if isinstance(role, Prefeito): self.prefeito_saved_once = False
        if isinstance(role, AssassinoAlfa): self.sabotage_used = False
        if isinstance(role, Praga): self.plague_exterminate_used = False
        if isinstance(role, Cumplice): self.fraud_used = False

        if player_id in self.last_protected_target: del self.last_protected_target[player_id]
        if player_id in self.fofoqueiro_comparisons: del self.fofoqueiro_comparisons[player_id]
        if player_id in self.last_corrupted_target: del self.last_corrupted_target[player_id]
        if player_id in self.last_confused_target: del self.last_confused_target[player_id]

    def is_idle(self) -> bool: return self.current_phase == "idle"
    def is_preparing(self) -> bool: return self.current_phase == "preparing"
    def is_night(self) -> bool: return self.current_phase == "night"
    def is_day_discussion(self) -> bool: return self.current_phase == "day_discussion"
    def is_day_voting(self) -> bool: return self.current_phase == "day_voting"
    def is_game_running(self) -> bool: return self.current_phase not in ["idle", "finished", "preparing"]