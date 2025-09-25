# tests/test_action_resolver.py

import pytest
from core.action_resolver import ActionResolver
from cogs.game_instance import GameInstance, PlayerState
from roles.cidade_roles import Prefeito, GuardaCostas, Detetive
from roles.viloes_roles import AssassinoAlfa
from roles.solo_roles import Bruxo

pytestmark = pytest.mark.asyncio

# --- Mocks (sem alterações) ---
class MockGuild:
    def __init__(self, id: int):
        self.id = id

class MockTextChannel:
    def __init__(self, id: int, name: str, guild: MockGuild):
        self.id = id
        self.name = name
        self.guild = guild

class MockMember:
    def __init__(self, id: int, name: str):
        self.id = id
        self.display_name = name
        async def send(*args, **kwargs):
            pass
        self.send = send

class MockGameFlowCog:
    async def end_game(self, *args, **kwargs):
        pass

class MockBot:
    def __init__(self):
        class MockGameManager:
            def map_player_to_game(self, player_id, channel_id):
                pass
        self.game_manager = MockGameManager()
        self._cogs = {"GameFlowCog": MockGameFlowCog()}

    def get_cog(self, name: str):
        return self._cogs.get(name)

# --- O TESTE FINAL ---

async def test_action_resolver_calculates_correct_outcome_for_bodyguard_sacrifice():
    # 1. ARRANGE (Preparar)
    resolver = ActionResolver(MockBot())
    prefeito_member = MockMember(1, "Prefeito Zé")
    guarda_costas_member = MockMember(2, "Guarda-Costas Guto")
    assassino_member = MockMember(3, "Assassino-Alfa Ana")
    bruxo_member = MockMember(4, "Bruxo Beto")
    detetive_member = MockMember(5, "Detetive Dani")
    fake_guild = MockGuild(202)
    fake_channel = MockTextChannel(101, "canal-de-teste", guild=fake_guild)
    game_master_member = MockMember(99, "Mestre")
    fake_game = GameInstance(bot=MockBot(), text_channel=fake_channel, voice_channel=None, game_master=game_master_member)
    all_members = [prefeito_member, guarda_costas_member, assassino_member, bruxo_member, detetive_member]
    for member in all_members:
        fake_game.add_player(member)
    fake_game.players[1].assign_role(Prefeito())
    fake_game.players[2].assign_role(GuardaCostas())
    fake_game.players[3].assign_role(AssassinoAlfa())
    fake_game.players[4].assign_role(Bruxo())
    fake_game.players[5].assign_role(Detetive())
    fake_game.night_actions = {
        guarda_costas_member.id: {"action": "protect", "target_id": prefeito_member.id, "role": fake_game.players[2].role, "priority": 20},
        assassino_member.id: {"action": "villain_vote", "target_id": prefeito_member.id, "role": fake_game.players[3].role, "priority": 30},
        bruxo_member.id: {"action": "witch_kill", "target_id": guarda_costas_member.id, "role": fake_game.players[4].role, "priority": 25},
        detetive_member.id: {"action": "mark_detective", "target1_id": assassino_member.id, "target2_id": bruxo_member.id, "role": fake_game.players[5].role, "priority": 60},
    }

    # 2. ACT (Agir)
    results = await resolver.resolve_night_actions(fake_game)
    
    # 3. ASSERT (Verificar)
    # A única responsabilidade do ActionResolver é retornar um relatório correto.
    # É isso que vamos verificar.
    
    # O relatório deve conter exatamente um jogador morto.
    assert len(results["killed_players"]) == 1
    
    # Vamos verificar os detalhes desse jogador morto no relatório.
    killed_player_id, reason, context_id = results["killed_players"][0]
    
    assert killed_player_id == guarda_costas_member.id
    assert reason == "bodyguard_sacrifice"
    assert context_id == prefeito_member.id