# cogs/ranking.py

import discord
from discord.ext import commands
from discord import option, ApplicationContext
import logging
from typing import Dict, List, Any

import config
from .utils import send_public_message
from .game_instance import GameInstance
# >>> MUDANÇA 1: Importa a coleção do nosso novo gerenciador de banco de dados (database.py)
from database import db_collection

logger = logging.getLogger(__name__)

# >>> MUDANÇA 2: As funções antigas de manipulação de JSON (load_ranking, save_ranking) e o lock foram removidos.
# O MongoDB gerencia o acesso e a persistência dos dados de forma atômica e segura.

class RankingCog(commands.Cog):
    """Cog para gerenciar o sistema de ranking global com estatísticas e medalhas."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.medal_definitions = self.load_medal_definitions()
        
        # >>> MUDANÇA 3: Adicionamos uma verificação crucial na inicialização.
        # Se a conexão com o banco de dados falhou (db_collection será None),
        # este Cog se desativará para evitar erros durante o jogo.
        if db_collection is None:
            logger.error("A coleção do MongoDB não está disponível. O Cog de Ranking será desativado.")
            # Itera sobre todos os comandos de barra neste Cog e os remove do bot
            if hasattr(self, '__cog_app_commands__'):
                for command in self.__cog_app_commands__:
                    self.bot.remove_application_command(command)
        else:
            logger.info("Cog Ranking carregado e conectado ao MongoDB.")

    def load_medal_definitions(self) -> Dict[str, Dict[str, str]]:
        """Carrega as definições de títulos e medalhas para fácil acesso."""
        # Esta estrutura permanece a mesma
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
        all_player_states = list(game.players.values())
        winner_ids = {w.id for w in winners}

        for p_state in all_player_states:
            player = p_state.member
            player_id = player.id
            
            # >>> MUDANÇA 4: Lógica de atualização usando operadores atômicos do MongoDB.
            # Esta é a maneira mais eficiente e segura de atualizar os dados.
            
            # Prepara os campos que serão atualizados
            update_fields = {
                '$inc': {'partidas_jogadas': 1},  # Incrementa o número de partidas jogadas
                '$set': {'nome_jogador': player.display_name}  # Atualiza o nome do jogador
            }

            # Se o jogador for um vencedor, adiciona os incrementos de vitória
            if player_id in winner_ids:
                update_fields['$inc']['vitorias_totais'] = 1
                if p_state.role:
                    role_name = p_state.role.name
                    # Usa a notação de ponto para incrementar um campo dentro de um sub-documento (objeto)
                    update_fields['$inc'][f'vitorias_por_papel.{role_name}'] = 1

            # Executa a operação de atualização no banco de dados.
            # update_one encontra um documento com o _id correspondente.
            # upsert=True significa: se o jogador não for encontrado, crie um novo documento para ele.
            db_collection.update_one(
                {'_id': player_id},
                update_fields,
                upsert=True
            )
            
            # Após a atualização, precisamos buscar os dados mais recentes para verificar as medalhas
            stats = db_collection.find_one({'_id': player_id})
            if not stats: continue

            # Lógica de verificação de medalhas (inalterada, mas agora usa os dados do DB)
            if stats.get("partidas_jogadas") in [50, 150]:
                 medal_map = {50: "Maratonista", 150: "Lenda da Cidade"}
                 await self.award_medal(player, medal_map[stats["partidas_jogadas"]], game.text_channel)
            
            if player_id in winner_ids and p_state.role:
                role_name = p_state.role.name
                if stats.get("vitorias_por_papel", {}).get(role_name) == 10:
                    if medal_info := self.medal_definitions.get(role_name):
                        if medalha := medal_info.get("medalha"):
                            await self.award_medal(player, medalha, game.text_channel)

        logger.info(f"[Jogo #{game.text_channel.id}] Estatísticas atualizadas no MongoDB para {len(all_player_states)} jogadores.")

    async def award_medal(self, player: discord.Member, medal_key: str, announcement_channel: discord.TextChannel):
        """Concede uma medalha a um jogador se ele ainda não a tiver."""
        player_id = player.id
        
        # >>> MUDANÇA 5: O operador '$addToSet' é perfeito para listas de itens únicos.
        # Ele só adiciona 'medal_key' ao array 'medalhas' se o item ainda não estiver lá.
        result = db_collection.update_one(
            {'_id': player_id},
            {'$addToSet': {'medalhas': medal_key}}
        )

        # 'result.modified_count' será 1 se a medalha foi realmente adicionada.
        # Se a medalha já existia, será 0.
        if result.modified_count > 0:
            logger.info(f"Medalha '{medal_key}' concedida a {player.display_name} no MongoDB.")
            await send_public_message(
                self.bot, 
                announcement_channel,
                message=f"🎉 **CONQUISTA DESBLOQUEADA!** {player.mention} ganhou a medalha: **{medal_key}**!"
            )

    @commands.slash_command(name="ranking", description="Mostra o ranking dos melhores jogadores.")
    async def show_ranking(self, ctx: ApplicationContext):
        """Exibe um placar com os 10 melhores jogadores, classificados por vitórias."""
        await ctx.defer()
        
        # >>> MUDANÇA 6: A consulta ao banco de dados substitui toda a lógica de carregar e ordenar o JSON.
        # find() busca documentos.
        # sort("vitorias_totais", -1) ordena pelo campo de vitórias em ordem decrescente.
        # limit(10) pega apenas os 10 primeiros resultados.
        top_players = list(db_collection.find().sort("vitorias_totais", -1).limit(10))

        if not top_players:
            await ctx.followup.send("O placar ainda está vazio! Nenhuma partida foi jogada.")
            return

        embed = discord.Embed(
            title="🏆 Ranking dos Melhores Jogadores",
            description="Os jogadores mais vitoriosos da Cidade Dorme!",
            color=discord.Color.gold()
        )
        
        lines = []
        for i, stats in enumerate(top_players):
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
        
        # >>> MUDANÇA 7: Busca um único jogador no banco de dados pelo seu ID.
        stats = db_collection.find_one({'_id': target_user.id})

        if not stats:
            await ctx.followup.send(f"**{target_user.display_name}** ainda não tem um perfil. É hora de jogar!")
            return
        
        # Lógica de exibição do perfil (inalterada)
        main_title = "Novato na Cidade"
        if stats.get("vitorias_por_papel"):
            for role_name, wins in sorted(stats["vitorias_por_papel"].items(), key=lambda item: item[1], reverse=True):
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