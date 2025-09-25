# core/action_resolver.py

"""
O motor de lógica do jogo Cidade Dorme.

Este módulo contém a classe ActionResolver, que é responsável por processar
todas as interações complexas do jogo, como a resolução de ações noturnas
e a contagem de votos para linchamento.

Ele é deliberadamente separado dos Cogs do Discord para isolar a "lógica de negócio"
da "lógica de interface", tornando o código mais limpo, testável e manutenível.
"""

import discord
import logging
import random
import asyncio
from typing import Dict, Any, List, Optional

from cogs.game_instance import GameInstance, PlayerState
from cogs.utils import send_dm_safe
from roles.base_role import Role
from roles.cidade_roles import GuardaCostas, Prefeito, Anjo, Medium
from roles.viloes_roles import AssassinoAlfa, AssassinoSimples
from roles.solo_roles import Palhaco

logger = logging.getLogger(__name__)


class ActionResolver:
    """
    Processa o estado de uma GameInstance para resolver as ações dos jogadores
    de acordo com as regras do jogo.
    """

    def __init__(self, bot: discord.Bot):
        """
        Inicializa o resolvedor de ações.

        Args:
            bot (discord.Bot): Uma referência ao objeto principal do bot, usada
                               para acessar Cogs e outros componentes globais.
        """
        self.bot = bot

    # -------------------------------------------------------------------------
    # --- Resolução de Ações Noturnas
    # -------------------------------------------------------------------------

    async def resolve_night_actions(self, game: GameInstance) -> Dict[str, Any]:
        """
        Orquestra a resolução de todas as ações noturnas registradas.

        Este é o método principal que chama métodos auxiliares em uma ordem
        específica para garantir que as interações de papéis sejam tratadas
        corretamente.

        Args:
            game (GameInstance): O estado atual da partida a ser processada.

        Returns:
            Dict[str, Any]: Um dicionário contendo os resultados da noite,
                            como quem morreu, quem foi revivido, mensagens a
                            serem enviadas, e se o jogo terminou.
        """
        logger.info(f"[Jogo #{game.text_channel.id}] --- Resolvendo Ações Noturnas via Resolver ---")
        results = {"killed_players": [], "revived_players": [], "sound_events": [], "plague_kill_count": 0, "dm_messages": {}, "public_messages": [], "game_over": False}
        for p_state in game.players.values():
            results["dm_messages"][p_state.member.id] = []

        sorted_actions = sorted(game.night_actions.items(), key=lambda item: item[1]["priority"])
        night_visits = {p_id: {'visited_by': set(), 'visited': set()} for p_id in game.players}
        for player_id, action_data in sorted_actions:
            if target_id := action_data.get("target_id"):
                night_visits[target_id]['visited_by'].add(player_id)
                night_visits[player_id]['visited'].add(target_id)

        await self._apply_status_effects(game, sorted_actions, results)
        await self._resolve_unique_actions(game, sorted_actions, results)
        if results.get("game_over"): return results

        kill_attempts = self._gather_kill_attempts(game, sorted_actions)
        deaths_before_revive = self._resolve_deaths(game, kill_attempts, results)
        revived_this_night = await self._resolve_revivals(game, sorted_actions, deaths_before_revive, results)

        final_deaths = [d for d in deaths_before_revive if d[0] not in [r[0] for r in revived_this_night]]

        await self._resolve_information_and_plague(game, sorted_actions, final_deaths, night_visits, results)
        if results.get("game_over"): return results

        if final_deaths: results["killed_players"] = final_deaths
        if revived_this_night: results["revived_players"] = revived_this_night

        game.clear_nightly_states()

        logger.info(f"[Jogo #{game.text_channel.id}] --- Resolução Noturna Concluída via Resolver ---")
        return results

    async def _apply_status_effects(self, game: GameInstance, sorted_actions: List[Any], results: Dict):
        """Aplica efeitos que precisam ser resolvidos primeiro, como confusão e corrupção."""
        for player_id, action_data in sorted_actions:
            action_name = action_data["action"]
            target_id = action_data.get("target_id")

            if action_name == "confuse":
                if target_state := game.get_player_state_by_id(target_id):
                    target_state.is_confused = True

        for player_id, action_data in game.night_actions.items():
            if (player_state := game.get_player_state_by_id(player_id)) and player_state.is_confused and "target_id" in action_data:
                original_target_id = action_data["target_id"]
                is_revive = action_data["action"] in ["angel_revive", "witch_revive"]
                
                possible_targets_query = [p.member.id for p in game.players.values() if not p.is_alive] if is_revive else [p.member.id for p in game.get_alive_players_states()]
                possible_targets = [pid for pid in possible_targets_query if pid not in [player_id, original_target_id]]
                
                # >>> CORREÇÃO 1: Impede o crash se a lista de alvos possíveis estiver vazia.
                if possible_targets:
                    new_target_id = random.choice(possible_targets)
                    action_data["target_id"] = new_target_id
                    logger.info(f"Ação de {player_state.member.display_name} confundida! Novo alvo: {game.get_player_by_id(new_target_id).display_name}")
                    results["dm_messages"].setdefault(player_id, []).append("😵‍💫 **Que tontura!** Sua ação saiu toda errada.")

        for player_id, action_data in sorted_actions:
            action_name = action_data["action"]
            target_id = action_data.get("target_id")
            
            if action_name == "corrupt":
                if target_state := game.get_player_state_by_id(target_id):
                    target_state.is_corrupted = True
                    results["dm_messages"].setdefault(target_id, []).append("😵‍💫 Sua mente foi invadida! Você não consegue usar sua habilidade esta noite.")
            
            elif action_name == "protect":
                protector_state = game.get_player_state_by_id(player_id)
                if protector_state and not protector_state.is_corrupted:
                    if target_state := game.get_player_state_by_id(target_id):
                        target_state.protected_by = player_id

    async def _resolve_unique_actions(self, game: GameInstance, sorted_actions: List[Any], results: Dict):
        """Resolve ações únicas como Possessão, Cupido e outras que alteram o estado do jogo."""
        for player_id, action_data in sorted_actions:
            action_name = action_data["action"]
            target_id = action_data.get("target_id")
            player_state = game.get_player_state_by_id(player_id)
            if not player_state or player_state.is_corrupted: continue

            if action_name == "possess":
                game.skip_villain_kill = True
                if target_state := game.get_player_state_by_id(target_id):
                    target_state.possession_points += 1
                    results["dm_messages"].setdefault(player_id, []).append(f"Você adicionou +1 ponto de possessão a {target_state.member.display_name}. Total: {target_state.possession_points}/3.")
                    if target_state.possession_points >= 3:
                        target_state.role = AssassinoSimples()
                        await send_dm_safe(target_state.member, f"Sua mente foi quebrada! Você agora é um **Assassino Simples**.")
                        all_villains = [p.member.display_name for p in game.players.values() if p.role.faction == "Vilões" and p.is_alive]
                        await send_dm_safe(target_state.member, f"Seus novos companheiros são: **{', '.join(all_villains)}**")
                        for p_state in game.players.values():
                            if p_state.role.faction == "Vilões" and p_state.is_alive and p_state.member.id != target_id:
                                await send_dm_safe(p_state.member, f"**{target_state.member.display_name}** foi corrompido e agora é um Assassino Simples.")
            
            elif action_name == "cupid_match":
                lover1_id, lover2_id = action_data["lover1_id"], action_data["lover2_id"]
                game.lovers = (lover1_id, lover2_id)
                if (lover1 := game.get_player_by_id(lover1_id)) and (lover2 := game.get_player_by_id(lover2_id)):
                    dm_msg1 = f"💘 O Cupido acertou você! Seu grande amor é **{lover2.display_name}**. Se um de vocês morrer, o outro morrerá junto."
                    dm_msg2 = f"💘 O Cupido acertou você! Seu grande amor é **{lover1.display_name}**. Se um de vocês morrer, o outro morrerá junto."
                    results["dm_messages"].setdefault(lover1_id, []).append(dm_msg1)
                    results["dm_messages"].setdefault(lover2_id, []).append(dm_msg2)

    def _gather_kill_attempts(self, game: GameInstance, sorted_actions: List[Any]) -> Dict[int, List[tuple]]:
        """Coleta todos os votos e tentativas de assassinato da noite."""
        kill_attempts = {}
        villain_votes = {}
        for player_id, action_data in sorted_actions:
            player_state = game.get_player_state_by_id(player_id)
            if not player_state or player_state.is_corrupted: continue
            
            action = action_data["action"]
            if action == "villain_vote":
                weight = 2 if isinstance(action_data["role"], AssassinoAlfa) else 1
                villain_votes[action_data["target_id"]] = villain_votes.get(action_data["target_id"], 0) + weight
            elif action == "witch_kill":
                kill_attempts.setdefault(action_data["target_id"], []).append(("witch", player_id))
                game.witch_potion_used = True
        
        if villain_votes and not game.skip_villain_kill:
            target_id = max(villain_votes, key=villain_votes.get)
            voters = [p_id for p_id, action in game.night_actions.items() if action.get("action") == "villain_vote" and action.get("target_id") == target_id]
            kill_attempts.setdefault(target_id, []).append(("villain", voters))
        
        return kill_attempts

    def _resolve_deaths(self, game: GameInstance, kill_attempts: Dict, results: Dict) -> List[tuple]:
        """Processa as tentativas de morte, considerando proteções, e retorna quem morreu."""
        final_deaths = []
        for target_id, killers_info in kill_attempts.items():
            target_state = game.get_player_state_by_id(target_id)
            if not target_state or not target_state.is_alive: continue
            
            attack_source, attacker_id = killers_info[0]
            
            if target_state.protected_by and attack_source == 'villain':
                protector_state = game.get_player_state_by_id(target_state.protected_by)
                if protector_state:
                    protector_state.bodyguard_hits_survived += 1
                    
                    if protector_state.bodyguard_hits_survived == 1:
                        results["sound_events"].append("PROTECTION_SUCCESS")
                        results["dm_messages"].setdefault(protector_state.member.id, []).append("🛡️ Você entrou na frente de um ataque para proteger seu alvo e sobreviveu!")
                        results["dm_messages"].setdefault(target_id, []).append("🛡️ Você foi atacado, mas uma força protetora te salvou esta noite.")
                    else:
                        final_deaths.append((protector_state.member.id, "bodyguard_sacrifice", target_id))
                        results["sound_events"].append("PLAYER_DEATH")
                continue
            
            if isinstance(target_state.role, GuardaCostas):
                target_state.bodyguard_hits_survived += 1
                
                if target_state.bodyguard_hits_survived == 1:
                    results["sound_events"].append("PROTECTION_SUCCESS")
                    results["dm_messages"].setdefault(target_id, []).append("🛡️ Você foi atacado, mas sua resistência o salvou desta vez!")
                    continue
            
            final_deaths.append((target_id, attack_source, attacker_id))
            
        return final_deaths

    async def _resolve_revivals(self, game: GameInstance, sorted_actions: List[Any], final_deaths: List[tuple], results: Dict) -> List[tuple]:
        """Processa as tentativas de reviver e retorna quem foi revivido."""
        revived_this_night = []
        for player_id, action_data in sorted_actions:
            player_state = game.get_player_state_by_id(player_id)
            if not player_state or player_state.is_corrupted: continue
            
            action = action_data["action"]
            if action in ["angel_revive", "witch_revive"]:
                target_id = action_data["target_id"]
                target_state = game.get_player_state_by_id(target_id)
                
                if target_state and not target_state.is_alive and not any(d[0] == target_id for d in final_deaths):
                    target_state.revive()
                    revived_this_night.append((target_id, player_id))
                    results["sound_events"].append("PLAYER_REVIVE")
                    
                    if action == "witch_revive": game.witch_potion_used = True
                    if action == "angel_revive": game.angel_revive_used = True
                    game.reset_flags_for_player(target_id)
                    
                    if isinstance(target_state.role, Prefeito) and target_state.ghost_master_id:
                        if medium_state := game.get_player_state_by_id(target_state.ghost_master_id):
                            game.medium_talk_used = False
                            await send_dm_safe(medium_state.member, "O Prefeito foi revivido! Seu poder foi restaurado.")
        return revived_this_night

    async def _resolve_information_and_plague(self, game: GameInstance, sorted_actions: List[Any], final_deaths: List[tuple], night_visits: Dict, results: Dict):
        """Resolve ações de informação (Detetive, Fantasma) e a lógica da Praga."""
        game_flow_cog = self.bot.get_cog("GameFlowCog")
        if not game_flow_cog:
            logger.critical(f"CRITICAL: GameFlowCog not found in ActionResolver for game {game.text_channel.id}")
            return
            
        for player_id, action_data in sorted_actions:
            p_state = game.get_player_state_by_id(player_id)
            if not p_state or p_state.is_corrupted: continue
            
            if action_data["action"] == "mark_detective":
                killed_this_night_ids = [d[0] for d in final_deaths]
                marked_ids = [action_data.get("target1_id"), action_data.get("target2_id")]
                marked_killed_ids = [tid for tid in marked_ids if tid in killed_this_night_ids and tid is not None]
                
                if not marked_killed_ids:
                    results["dm_messages"].setdefault(player_id, []).append("🕵️ Sua vigília foi tranquila. Nenhum dos seus alvos morreu.")
                else:
                    killed_id = marked_killed_ids[0]
                    death_info = next((d for d in final_deaths if d[0] == killed_id), None)
                    if (killed_member := game.get_player_by_id(killed_id)) and death_info:
                        _, _, killer_info = death_info
                        killer_ids = killer_info if isinstance(killer_info, list) else [killer_info]
                        if killer_ids and (killer_member := game.get_player_by_id(random.choice(killer_ids))):
                            innocent_pool = [p.member for p in game.get_alive_players_states() if p.member.id not in [player_id, killed_id, killer_member.id]]
                            
                            # >>> CORREÇÃO 2: Bloco if/else para dar feedback correto e evitar crash.
                            if innocent_pool:
                                clue_members = [killer_member, random.choice(innocent_pool)]
                                random.shuffle(clue_members)
                                info_msg = f"🕵️ {killed_member.display_name} foi morto. Um destes está envolvido: **{', '.join([m.display_name for m in clue_members])}**."
                            else:
                                info_msg = f"🕵️ {killed_member.display_name} foi morto. Sua única pista aponta diretamente para **{killer_member.display_name}**."
                        else:
                            info_msg = f"🕵️ {killed_member.display_name} foi morto, mas o assassino é um mistério."
                        results["dm_messages"].setdefault(player_id, []).append(info_msg)

        haunt_action = next((data for _, data in sorted_actions if data["action"] == "haunt"), None)
        if haunt_action:
            haunt_target_id, ghost_id = haunt_action["target_id"], haunt_action["player_id"]
            if (ghost_state := game.get_player_state_by_id(ghost_id)) and ghost_state.ghost_master_id:
                medium_id = ghost_state.ghost_master_id
                visits = night_visits.get(haunt_target_id, {'visited_by': set(), 'visited': set()})
                visited_by_names = [game.get_player_by_id(pid).display_name for pid in visits['visited_by'] if pid != ghost_id]
                visited_names = [game.get_player_by_id(pid).display_name for pid in visits['visited']]
                report = (f"Relatório da Assombração sobre **{game.get_player_by_id(haunt_target_id).display_name}**:\n"
                          f"- Foi visitado por: **{', '.join(visited_by_names) if visited_by_names else 'Ninguém'}**\n"
                          f"- Visitou: **{', '.join(visited_names) if visited_names else 'Ninguém'}**")
                results["dm_messages"].setdefault(ghost_id, []).append(report)
                results["dm_messages"].setdefault(medium_id, []).append(report)

        prague_exterminate_action = next((data for _, data in sorted_actions if data["action"] == "plague_exterminate"), None)
        if prague_exterminate_action and not game.plague_exterminate_used:
            game.plague_exterminate_used = True
            infected_to_die_ids = {pid for pid, pstate in game.players.items() if pstate.is_infected and pstate.is_alive}
            if len(infected_to_die_ids) >= 4 and (praga_member := game.get_player_by_id(prague_exterminate_action["player_id"])):
                end_args = {"title": "Vitória da Praga!", "winners": [praga_member], "faction": "Solo (Praga)", "reason": f"A Praga eliminou {len(infected_to_die_ids)} jogadores!", "sound_event_key": "PLAGUE_WIN"}
                await game_flow_cog.end_game(game, **end_args)
                results["game_over"] = True
                return
            if infected_to_die_ids:
                results["plague_kill_count"] = len(infected_to_die_ids)
                for infected_id in infected_to_die_ids:
                    final_deaths.append((infected_id, "killed_by_plague", prague_exterminate_action["player_id"]))

        if game.plague_patient_zero_id and (pz_state := game.get_player_state_by_id(game.plague_patient_zero_id)) and pz_state.is_alive:
            newly_infected = []
            def infect_player(player_id):
                if player_id != game.plague_player_id and (p_state := game.get_player_state_by_id(player_id)) and not p_state.is_infected:
                    p_state.is_infected = True; newly_infected.append(player_id)
            for interactor_id, act_data in game.night_actions.items():
                if act_data.get("target_id") == game.plague_patient_zero_id: infect_player(interactor_id)
            if (pz_action := game.night_actions.get(game.plague_patient_zero_id)) and (target_id := pz_action.get("target_id")): infect_player(target_id)
            if newly_infected:
                for infected_id in newly_infected:
                    results["dm_messages"].setdefault(infected_id, []).append("🤒 Você se sente febril... Você foi infectado pela Praga!")

    # -------------------------------------------------------------------------
    # --- Resolução de Votação Diurna
    # -------------------------------------------------------------------------

    async def process_lynch(self, game: GameInstance) -> Dict[str, Any]:
        """
        Processa os votos do dia, aplica modificadores (Decreto, Fraude) e
        determina se um jogador é linchado.

        Args:
            game (GameInstance): O estado atual da partida.

        Returns:
            Dict[str, Any]: Um dicionário com os resultados, incluindo mensagens
                            públicas e se o jogo terminou (vitória do Palhaço).
        """
        results = {"public_messages": [], "game_over": False, "sound_event": None}
        game_flow_cog = self.bot.get_cog("GameFlowCog")
        if not game_flow_cog:
            logger.critical(f"CRITICAL: GameFlowCog not found in ActionResolver for game {game.text_channel.id}")
            return results # Retorna um resultado vazio para evitar crash

        num_alive = len(game.get_alive_players())
        majority_needed = (num_alive // 2) + 1
        if len(game.day_skip_votes) >= majority_needed:
            results["public_messages"].append("A maioria decidiu pular a votação.")
            return results
        votes = game.day_votes
        if not votes:
            results["public_messages"].append("Ninguém foi linchado."); return results
        if game.fraud_active:
            logger.info(f"[Jogo #{game.text_channel.id}] FRAUDE ATIVADA! Embaralhando votos...")
            voter_ids, target_ids = list(votes.keys()), list(votes.values())
            random.shuffle(target_ids)
            votes = {voter: target for voter, target in zip(voter_ids, target_ids)}
            results["public_messages"].append("Os resultados da votação parecem... estranhos.")
        vote_counts = {}
        for voter_id, target_id in votes.items():
            weight = 1
            if game.decreto_active:
                voter_state = game.get_player_state_by_id(voter_id)
                if voter_state and voter_state.role:
                    if isinstance(voter_state.role, Prefeito): weight = 3
                    elif voter_state.role.faction == "Cidade": weight = 2
            vote_counts[target_id] = vote_counts.get(target_id, 0) + weight
        if game.decreto_active:
            vote_details = [f"{game.get_player_by_id(pid).display_name} ({count} votos)" for pid, count in vote_counts.items()]
            results["public_messages"].append(f"Com o Decreto, a contagem final foi: {', '.join(vote_details)}.")
        max_votes = max(vote_counts.values()) if vote_counts else 0
        if max_votes < majority_needed:
            results["public_messages"].append(f"A votação não atingiu a maioria de {majority_needed} votos.")
            return results
        lynched_candidates = [pid for pid, count in vote_counts.items() if count == max_votes]
        if len(lynched_candidates) != 1:
            results["public_messages"].append("Houve um empate na votação."); return results
        lynched_player_state = game.get_player_state_by_id(lynched_candidates[0])
        lynched_member = lynched_player_state.member
        if isinstance(lynched_player_state.role, Prefeito) and not game.prefeito_saved_once:
            game.prefeito_saved_once = True
            results["public_messages"].append(f"A votação para linchar **{lynched_member.display_name}** foi esmagadora! No entanto, a cidade reconsiderou."); return results
        results["public_messages"].append(f"Com {max_votes} votos, **{lynched_member.display_name}** foi linchado!")
        await game_flow_cog.process_death(game, lynched_member, "lynched")
        if isinstance(lynched_player_state.role, Palhaco):
            results["sound_event"] = "CLOWN_WIN"
            end_game_args = { "title": "Vitória do Palhaço!", "winners": [lynched_member], "faction": "Solo (Palhaço)", "reason": f"{lynched_member.display_name} conseguiu ser linchado!", "sound_event_key": "CLOWN_WIN" }
            await game_flow_cog.end_game(game, **end_game_args)
            results.update({"game_over": True})
        else:
            results["sound_event"] = "PLAYER_DEATH"
        return results