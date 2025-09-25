# cogs/ranking.py

import discord
from discord.ext import commands
from discord import option, ApplicationContext
import logging
import json
import os
import asyncio
from typing import Dict, List, Any

import config
from .utils import send_public_message
from .game_instance import GameInstance # Importa GameInstance para type hinting

logger = logging.getLogger(__name__)

# Lock para evitar condições de corrida ao ler/escrever o arquivo JSON
ranking_lock = asyncio.Lock()

# Estrutura padrão para um novo jogador no ranking
def get_default_player_stats(player_name: str) -> Dict[str, Any]:
    """Retorna a estrutura de dados padrão para um novo jogador."""
    return {
        "nome_jogador": player_name,
        "partidas_jogadas": 0,
        "vitorias_totais": 0,
        "vitorias_por_papel": {},
        "medalhas": []
    }

async def load_ranking() -> dict:
    """Carrega os dados do ranking do arquivo JSON de forma segura."""
    async with ranking_lock:
        try:
            # Garante que a pasta 'data' exista
            os.makedirs(config.DATA_PATH, exist_ok=True)

            # Se o arquivo não existe, cria ele com um JSON válido e retorna um dict vazio
            if not os.path.exists(config.RANKING_FILE):
                with open(config.RANKING_FILE, 'w', encoding='utf-8') as f:
                    json.dump({}, f)
                return {}
            
            # Se o arquivo existe, tenta carregar
            with open(config.RANKING_FILE, 'r', encoding='utf-8') as f:
                # Checa se o arquivo está vazio antes de tentar carregar
                if os.path.getsize(config.RANKING_FILE) == 0:
                    # Se estiver vazio, reescreve com um JSON válido
                    f.close() # Fecha o arquivo de leitura
                    with open(config.RANKING_FILE, 'w', encoding='utf-8') as wf:
                        json.dump({}, wf)
                    return {}
                
                # Se não estiver vazio, volta ao início do arquivo e carrega o JSON
                f.seek(0)
                return json.load(f)

        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Não foi possível carregar {config.RANKING_FILE}, o arquivo pode estar corrompido ou vazio. Criando um novo. Erro: {e}")
            # Se qualquer erro ocorrer, cria um novo arquivo limpo
            with open(config.RANKING_FILE, 'w', encoding='utf-8') as f:
                json.dump({}, f)
            return {}

async def save_ranking(ranking_data: dict):
    """Salva os dados do ranking no arquivo JSON de forma segura."""
    async with ranking_lock:
        try:
            with open(config.RANKING_FILE, 'w', encoding='utf-8') as f:
                json.dump(ranking_data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.exception(f"Erro inesperado ao salvar ranking: {e}")


class RankingCog(commands.Cog):
    """Cog para gerenciar o sistema de ranking global com estatísticas e medalhas."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.medal_definitions = self.load_medal_definitions()
        logger.info("Cog Ranking carregado.")

    def load_medal_definitions(self) -> Dict[str, Dict[str, str]]:
        """Carrega as definições de títulos e medalhas para fácil acesso."""
        # Esta estrutura pode ser expandida conforme necessário
        return {
            "Assassino Alfa": {"título": "O Pesadelo da Vizinhança", "medalha": "Líder do Mal"},
            "Anjo": {"título": "O Despachado do Além", "medalha": "O Anjo da Guarda"},
            "Xerife": {"título": "O Bang-Bang da Cidade", "medalha": "A Lei Sou Eu"},
            "Palhaço": {"título": "O Rei da Palhaçada", "medalha": "O Rei da Palhaçada"},
            "Bruxo": {"título": "Harry Potter do Paraguai", "medalha": "Agente do Caos"},
            # Adicione outras medalhas de maestria aqui
        }

    async def update_stats_after_game(self, game: GameInstance, winners: List[discord.Member]):
        """
        Atualiza as estatísticas de todos os jogadores de uma partida concluída.
        Esta função é chamada pelo GameFlowCog no final de um jogo.
        """
        ranking_data = await load_ranking()
        all_player_states = list(game.players.values())
        winner_ids = {w.id for w in winners}

        for p_state in all_player_states:
            player = p_state.member
            player_id_str = str(player.id)
            
            # Garante que o jogador exista no ranking
            if player_id_str not in ranking_data:
                ranking_data[player_id_str] = get_default_player_stats(player.display_name)
            
            stats = ranking_data[player_id_str]
            stats["partidas_jogadas"] += 1
            stats["nome_jogador"] = player.display_name # Atualiza o nome caso tenha mudado

            # Verifica medalhas baseadas em partidas jogadas
            if stats["partidas_jogadas"] == 50:
                await self.award_medal(player, "Maratonista", game.text_channel)
            if stats["partidas_jogadas"] == 150:
                await self.award_medal(player, "Lenda da Cidade", game.text_channel)
            
            # Se o jogador for um vencedor, atualiza vitórias
            if player.id in winner_ids:
                stats["vitorias_totais"] += 1
                if p_state.role:
                    role_name = p_state.role.name
                    current_wins = stats["vitorias_por_papel"].get(role_name, 0)
                    stats["vitorias_por_papel"][role_name] = current_wins + 1

                    # Verifica medalhas baseadas em maestria de papel
                    if stats["vitorias_por_papel"][role_name] == 10:
                        if medal_info := self.medal_definitions.get(role_name):
                            if medalha := medal_info.get("medalha"):
                                await self.award_medal(player, medalha, game.text_channel)

        await save_ranking(ranking_data)
        logger.info(f"[Jogo #{game.text_channel.id}] Estatísticas atualizadas para {len(all_player_states)} jogadores.")

    async def award_medal(self, player: discord.Member, medal_key: str, announcement_channel: discord.TextChannel):
        """Concede uma medalha a um jogador se ele ainda não a tiver."""
        ranking_data = await load_ranking()
        player_id_str = str(player.id)

        if player_id_str not in ranking_data:
            ranking_data[player_id_str] = get_default_player_stats(player.display_name)
        
        if medal_key not in ranking_data[player_id_str]["medalhas"]:
            ranking_data[player_id_str]["medalhas"].append(medal_key)
            await save_ranking(ranking_data)
            logger.info(f"Medalha '{medal_key}' concedida a {player.display_name}.")
            # Envia o anúncio no canal onde o jogo que concedeu a medalha terminou
            await send_public_message(
                self.bot, 
                announcement_channel,
                message=f"🎉 **CONQUISTA DESBLOQUEADA!** {player.mention} ganhou a medalha: **{medal_key}**!"
            )

    @commands.slash_command(name="ranking", description="Mostra o ranking dos melhores jogadores.")
    async def show_ranking(self, ctx: ApplicationContext):
        """Exibe um placar com os 10 melhores jogadores, classificados por vitórias."""
        await ctx.defer()
        ranking_data = await load_ranking()
        if not ranking_data:
            await ctx.followup.send("O placar ainda está vazio! Nenhuma partida foi jogada.")
            return

        sorted_players = sorted(ranking_data.values(), key=lambda p: p.get('vitorias_totais', 0), reverse=True)

        embed = discord.Embed(
            title="🏆 Ranking dos Melhores Jogadores",
            description="Os jogadores mais vitoriosos da Cidade Dorme!",
            color=discord.Color.gold()
        )
        
        lines = []
        for i, stats in enumerate(sorted_players[:10]):
            player_name = stats.get('nome_jogador', 'Jogador Desconhecido')
            wins = stats.get('vitorias_totais', 0)
            games = stats.get('partidas_jogadas', 0)
            win_rate = (wins / games * 100) if games > 0 else 0
            emoji = ["🥇", "🥈", "🥉"][i] if i < 3 else f"**{i+1}.**"
            lines.append(f"{emoji} **{player_name}** - {wins} vitórias ({win_rate:.1f}%)")
        
        embed.description = "\n".join(lines) if lines else "Ainda não há jogadores no ranking."
        embed.set_footer(text="Continue jogando para subir no ranking!")

        await ctx.followup.send(embed=embed)

    @commands.slash_command(name="perfil", description="Mostra suas estatísticas, títulos e medalhas.")
    @option("usuario", description="Veja o perfil de outro jogador (opcional).", required=False)
    async def show_profile(self, ctx: ApplicationContext, usuario: discord.Member = None):
        """Exibe o perfil detalhado de um jogador."""
        # >>> CORREÇÃO: Adicionado ctx.defer() para evitar timeout da interação <<<
        await ctx.defer()

        target_user = usuario or ctx.author
        ranking_data = await load_ranking()
        player_id_str = str(target_user.id)

        if player_id_str not in ranking_data:
            # >>> CORREÇÃO: Usar followup.send pois a interação foi adiada <<<
            await ctx.followup.send(f"**{target_user.display_name}** ainda não tem um perfil. É hora de jogar!")
            return

        stats = ranking_data[player_id_str]
        
        main_title = "Novato na Cidade"
        if stats["vitorias_por_papel"]:
            # Encontra o papel com mais vitórias que tem um título definido
            for role_name, wins in sorted(stats["vitorias_por_papel"].items(), key=lambda item: item[1], reverse=True):
                if wins >= 5 and (title_info := self.medal_definitions.get(role_name)) and (title := title_info.get("título")):
                    main_title = title
                    break

        win_rate = (stats["vitorias_totais"] / stats["partidas_jogadas"] * 100) if stats["partidas_jogadas"] > 0 else 0

        embed = discord.Embed(
            title=f"Perfil de {stats['nome_jogador']}",
            description=f"**Título:** {main_title}",
            color=target_user.accent_color or discord.Color.purple()
        )
        embed.set_thumbnail(url=target_user.display_avatar.url)

        embed.add_field(
            name="Estatísticas Gerais",
            value=f"🏆 **Vitórias:** {stats['vitorias_totais']}\n"
                  f"🎲 **Partidas:** {stats['partidas_jogadas']}\n"
                  f"📊 **Taxa de Vitória:** {win_rate:.1f}%",
            inline=True
        )

        if roles_wins := stats["vitorias_por_papel"]:
            sorted_roles = sorted(roles_wins.items(), key=lambda item: item[1], reverse=True)[:3]
            roles_text = "\n".join([f"**{role}**: {wins} vitórias" for role, wins in sorted_roles])
            embed.add_field(name="Melhores Papéis", value=roles_text, inline=True)
        else:
            embed.add_field(name="Melhores Papéis", value="Nenhuma vitória ainda.", inline=True)

        if medals := stats["medalhas"]:
            medals_text = "🎖️ " + "\n🎖️ ".join(medals)
            embed.add_field(name=f"Conquistas ({len(medals)})", value=medals_text, inline=False)
        
        # >>> CORREÇÃO: Usar followup.send pois a interação foi adiada <<<
        await ctx.followup.send(embed=embed)

def setup(bot: commands.Bot):
    bot.add_cog(RankingCog(bot))