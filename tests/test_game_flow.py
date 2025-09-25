# tests/test_game_flow.py

import pytest
from unittest.mock import patch, AsyncMock

from cogs.game_flow import GameFlowCog
from cogs.game_instance import GameInstance, PlayerState
from roles.cidade_roles import Prefeito, Xerife, CidadaoComum
from roles.viloes_roles import AssassinoAlfa

# Reutilizando e aprimorando os mocks
from tests.test_action_resolver import MockGuild

pytestmark = pytest.mark.asyncio

# --- MOCKS FINAIS E REATIVOS ---

class MockMember:
    def __init__(self, id: int, name: str):
        self.id = id
        self.display_name = name
        self.mention = f"<@{self.id}>"
        async def send(*args, **kwargs): pass
        self.send = send

class MockGuild:
    def __init__(self, id: int, members: list):
        self.id = id
        self._members = {member.id: member for member in members}
    def get_member(self, member_id: int):
        return self._members.get(member_id)

class MockTextChannel:
    def __init__(self, id: int, name: str, guild: MockGuild):
        self.id = id
        self.name = name
        self.guild = guild
        self.send = AsyncMock()

class MockBot:
    def __init__(self):
        self._active_game = None

        class MockGameManager:
            def __init__(self, bot_ref):
                self._bot_ref = bot_ref
            def map_player_to_game(self, player_id, channel_id): pass
            def get_game(self, channel_id):
                return self._bot_ref._active_game
            def end_game(self, channel_id):
                self._bot_ref._active_game = None

        self.game_manager = MockGameManager(self)
        self._cogs = {}

    def get_cog(self, name: str): return self._cogs.get(name)
    def add_cog(self, cog): self._cogs[cog.__class__.__name__] = cog


async def test_seventh_day_confrontation_sheriff_wins():
    """
    Testa o confronto do Sétimo Dia, onde o Xerife atira no Assassino Alfa,
    resultando em uma vitória imediata para a Cidade.
    """
    # 1. ARRANGE
    mock_bot = MockBot()
    game_flow_cog = GameFlowCog(mock_bot)
    mock_bot.add_cog(game_flow_cog)

    # CORREÇÃO FINALÍSSIMA AQUI: A lambda agora aceita *args e **kwargs
    # O objeto 'game' será o primeiro argumento posicional, ou seja, args[0].
    game_flow_cog.end_game = AsyncMock(side_effect=lambda *args, **kwargs: mock_bot.game_manager.end_game(args[0].text_channel.id))
    
    prefeito_member = MockMember(1, "Prefeito Zé")
    xerife_member = MockMember(2, "Xerife Guto")
    assassino_member = MockMember(3, "Assassino-Alfa Ana")
    cidadao_member = MockMember(4, "Cidadão Carlos")
    
    all_test_members = [prefeito_member, xerife_member, assassino_member, cidadao_member]
    
    fake_guild = MockGuild(202, members=all_test_members)
    fake_channel = MockTextChannel(101, "canal-de-teste", guild=fake_guild)
    fake_game = GameInstance(bot=mock_bot, text_channel=fake_channel, voice_channel=None, game_master=MockMember(99, "Mestre"))
    
    mock_bot._active_game = fake_game

    for member in all_test_members:
        fake_game.add_player(member)
        
    fake_game.players[1].assign_role(Prefeito())
    fake_game.players[2].assign_role(Xerife())
    fake_game.players[3].assign_role(AssassinoAlfa())
    fake_game.players[4].assign_role(CidadaoComum())

    fake_game.current_night = 7
    fake_game.sheriff_shots_fired = 0

    # 2. MOCK
    mock_view_instance = AsyncMock()
    mock_view_instance.result = assassino_member.id

    with patch('cogs.game_flow.ShowdownView', return_value=mock_view_instance) as mock_showdown_view_class:
        
        # 3. ACT
        await game_flow_cog.check_seventh_day_win(fake_game)

        # 4. ASSERT
        mock_showdown_view_class.assert_called_once()
        game_flow_cog.end_game.assert_awaited_once()

        call_args, call_kwargs = game_flow_cog.end_game.call_args
        
        # Unpack the positional arguments for easier assertion
        called_game, called_title, called_winners, called_faction, called_reason = call_args

        assert called_title == "Vitória da Cidade!"
        assert called_faction == "Cidade"
        assert called_reason == "O Xerife eliminou o Assassino Alfa!"
        assert call_kwargs['sound_event_key'] == "SHERIFF_WIN"

        winner_ids = {winner.id for winner in called_winners}
        expected_winner_ids = {prefeito_member.id, xerife_member.id, cidadao_member.id}
        assert winner_ids == expected_winner_ids