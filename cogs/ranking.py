# cogs/ranking.py

import discord
from discord.ext import commands
from discord import option, ApplicationContext
import logging
from typing import Dict, List, Any

# --- NOSSAS NOVAS IMPORTAÇÕES ---
# Funções do SQLAlchemy para construir queries de forma segura
from sqlalchemy import select, insert, update

import config
from .utils import send_public_message
from .game_instance import GameInstance
# Importa o 'engine' e a 'players_table' do nosso novo database.py
from database import engine, players_table

logger = logging.getLogger(__name__)


class RankingCog(commands.Cog):
    """Cog para gerenciar o sistema de ranking global com estatísticas e medalhas."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.medal_definitions = self.load_medal_definitions()
        
        # A verificação de inicialização agora checa se o 'engine' do SQLAlchemy foi criado com sucesso.
        if engine is None:
            logger.error("O engine do SQLAlchemy não está disponível. O Cog de Ranking será desativado.")
            # Remove os comandos de barra deste Cog se o banco de dados não estiver disponível
            if hasattr(self, '__cog_app_commands__'):
                for command in self.__cog_app_commands__:
                    self.bot.remove_application_command(command)
        else:
            logger.info("Cog Ranking carregado e conectado ao PostgreSQL.")

    def load_medal_definitions(self) -> Dict[str, Dict[str, str]]:
        """Carrega as definições de títulos e medalhas. Esta função não precisa mudar."""
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
        Atualiza as estatísticas de todos os jogadores de uma partida concluída no banco de dados PostgreSQL.
        """
        all_player_states = list(game.players.values())
        winner_ids = {w.id for w in winners}

        # Abre uma conexão e inicia uma transação. Todas as operações dentro deste bloco
        # serão confirmadas (commit) no final. Se um erro ocorrer, nada é salvo (rollback).
        with engine.begin() as conn:
            for p_state in all_player_states:
                player = p_state.member
                player_id = player.id

                # 1. Busca os dados atuais do jogador (se existirem)
                current_stats_result = conn.execute(
                    select(players_table).where(players_table.c.player_id == player_id)
                ).first()

                is_winner = player_id in winner_ids
                
                if current_stats_result:
                    # --- LÓGICA DE UPDATE (Jogador já existe) ---
                    stats = dict(current_stats_result._mapping)
                    
                    # Prepara os novos valores para as colunas
                    updated_values = {
                        "nome_jogador": player.display_name,
                        "partidas_jogadas": stats['partidas_jogadas'] + 1,
                    }

                    if is_winner:
                        updated_values["vitorias_totais"] = stats['vitorias_totais'] + 1
                        if p_state.role:
                            role_name = p_state.role.name
                            # Copia o dicionário para evitar modificar o original em memória
                            vitorias_por_papel = dict(stats['vitorias_por_papel'])
                            vitorias_por_papel[role_name] = vitorias_por_papel.get(role_name, 0) + 1
                            updated_values["vitorias_por_papel"] = vitorias_por_papel
                    
                    # Constrói e executa a query de UPDATE
                    stmt = update(players_table).where(players_table.c.player_id == player_id).values(**updated_values)
                    conn.execute(stmt)
                else:
                    # --- LÓGICA DE INSERT (Novo jogador) ---
                    vitorias_por_papel = {}
                    vitorias_totais = 0
                    if is_winner:
                        vitorias_totais = 1
                        if p_state.role:
                            vitorias_por_papel[p_state.role.name] = 1

                    # Constrói e executa a query de INSERT
                    stmt = insert(players_table).values(
                        player_id=player_id,
                        nome_jogador=player.display_name,
                        partidas_jogadas=1,
                        vitorias_totais=vitorias_totais,
                        vitorias_por_papel=vitorias_por_papel,
                        medalhas=[] # Começa com uma lista vazia de medalhas
                    )
                    conn.execute(stmt)

                # --- LÓGICA DE VERIFICAÇÃO DE MEDALHAS ---
                # Após a atualização, buscamos os dados mais recentes para a verificação.
                updated_stats = dict(conn.execute(
                    select(players_table).where(players_table.c.player_id == player_id)
                ).first()._mapping)
                
                if updated_stats.get("partidas_jogadas") in [50, 150]:
                    medal_map = {50: "Maratonista", 150: "Lenda da Cidade"}
                    await self.award_medal(conn, player, medal_map[updated_stats["partidas_jogadas"]], game.text_channel)
            
                if is_winner and p_state.role:
                    role_name = p_state.role.name
                    if updated_stats.get("vitorias_por_papel", {}).get(role_name) == 10:
                        if medal_info := self.medal_definitions.get(role_name):
                            if medalha := medal_info.get("medalha"):
                                await self.award_medal(conn, player, medalha, game.text_channel)
            
        logger.info(f"[Jogo #{game.text_channel.id}] Estatísticas atualizadas no PostgreSQL para {len(all_player_states)} jogadores.")

    async def award_medal(self, conn, player: discord.Member, medal_key: str, announcement_channel: discord.TextChannel):
        """Concede uma medalha a um jogador se ele ainda não a tiver."""
        player_id = player.id

        # Busca a lista de medalhas atual do jogador.
        current_medals = conn.execute(
            select(players_table.c.medalhas).where(players_table.c.player_id == player_id)
        ).scalar_one() # .scalar_one() pega o primeiro valor da primeira linha
        
        # O resultado do JSON é uma lista, então podemos checar diretamente
        if medal_key not in current_medals:
            # Cria a nova lista de medalhas
            new_medals = current_medals + [medal_key]
            
            # Atualiza a coluna de medalhas no banco de dados com a nova lista
            conn.execute(
                update(players_table).where(players_table.c.player_id == player_id).values(medalhas=new_medals)
            )
            logger.info(f"Medalha '{medal_key}' concedida a {player.display_name} no PostgreSQL.")
            await send_public_message(
                self.bot, 
                announcement_channel,
                message=f"🎉 **CONQUISTA DESBLOQUEADA!** {player.mention} ganhou a medalha: **{medal_key}**!"
            )

    @commands.slash_command(name="ranking", description="Mostra o ranking dos melhores jogadores.")
    async def show_ranking(self, ctx: ApplicationContext):
        """Exibe um placar com os 10 melhores jogadores, classificados por vitórias."""
        await ctx.defer()
        
        with engine.connect() as conn:
            # Constrói a query para selecionar os 10 melhores por vitórias totais
            stmt = select(players_table).order_by(players_table.c.vitorias_totais.desc()).limit(10)
            top_players_result = conn.execute(stmt).fetchall()

        if not top_players_result:
            await ctx.followup.send("O placar ainda está vazio! Nenhuma partida foi jogada.")
            return

        embed = discord.Embed(
            title="🏆 Ranking dos Melhores Jogadores",
            description="Os jogadores mais vitoriosos da Cidade Dorme!",
            color=discord.Color.gold()
        )
        
        lines = []
        for i, row in enumerate(top_players_result):
            stats = row._mapping
            player_name = stats.get('nome_jogador', 'Jogador Desconhecido')
            wins = stats.get('vitorias_totais', 0)
            games = stats.get('partidas_jogadas', 0)
            win_rate = (wins / games * 100) if games > 0 else 0
            emoji = ["🥇", "🥈", "🥉"][i] if i < 3 else f"**{i+1}.**"
            lines.append(f"{emoji} **{player_name}** - {wins} vitórias ({win_rate:.1f}%)")
        
        embed.description = "\n".join(lines)
        embed.set_footer(text="Continue jogando para subir no ranking!")
        await ctx.followup.send(embed=embed)

    @commands.slash_command(name="perfil", description="Mostra suas estatísticas, títulos e medalhas.")
    @option("usuario", description="Veja o perfil de outro jogador (opcional).", required=False)
    async def show_profile(self, ctx: ApplicationContext, usuario: discord.Member = None):
        """Exibe o perfil detalhado de um jogador."""
        await ctx.defer()
        target_user = usuario or ctx.author
        
        with engine.connect() as conn:
            # Busca o perfil do jogador específico pelo seu ID
            stmt = select(players_table).where(players_table.c.player_id == target_user.id)
            stats_result = conn.execute(stmt).first()

        if not stats_result:
            await ctx.followup.send(f"**{target_user.display_name}** ainda não tem um perfil. É hora de jogar!")
            return
        
        stats = stats_result._mapping
        
        # A lógica para exibir os dados permanece a mesma
        main_title = "Novato na Cidade"
        if vitorias_por_papel := stats.get("vitorias_por_papel"):
            for role_name, wins in sorted(vitorias_por_papel.items(), key=lambda item: item[1], reverse=True):
                if wins >= 5 and (title_info := self.medal_definitions.get(role_name)) and (title := title_info.get("título")):
                    main_title = title
                    break

        vitorias_totais = stats.get("vitorias_totais", 0)
        partidas_jogadas = stats.get("partidas_jogadas", 0)
        win_rate = (vitorias_totais / partidas_jogadas * 100) if partidas_jogadas > 0 else 0

        embed = discord.Embed(
            title=f"Perfil de {stats['nome_jogador']}",
            description=f"**Título:** {main_title}",
            color=target_user.accent_color or discord.Color.purple()
        )
        embed.set_thumbnail(url=target_user.display_avatar.url)

        embed.add_field(
            name="Estatísticas Gerais",
            value=f"🏆 **Vitórias:** {vitorias_totais}\n"
                  f"🎲 **Partidas:** {partidas_jogadas}\n"
                  f"📊 **Taxa de Vitória:** {win_rate:.1f}%",
            inline=True
        )

        if roles_wins := stats.get("vitorias_por_papel"):
            sorted_roles = sorted(roles_wins.items(), key=lambda item: item[1], reverse=True)[:3]
            roles_text = "\n".join([f"**{role}**: {wins} vitórias" for role, wins in sorted_roles])
            embed.add_field(name="Melhores Papéis", value=roles_text, inline=True)
        else:
            embed.add_field(name="Melhores Papéis", value="Nenhuma vitória ainda.", inline=True)

        if medals := stats.get("medalhas"):
            medals_text = "🎖️ " + "\n🎖️ ".join(medals)
            embed.add_field(name=f"Conquistas ({len(medals)})", value=medals_text, inline=False)
        
        await ctx.followup.send(embed=embed)


def setup(bot: commands.Bot):
    bot.add_cog(RankingCog(bot))