# roles/viloes_roles.py

from .base_role import Role
import discord

# --- Papéis da Facção Vilões ---

class AssassinoAlfa(Role):
    def __init__(self):
        super().__init__(
            name="Assassino Alfa",
            faction="Vilões",
            description="Você é o cérebro por trás do caos. Além de liderar os ataques, você tem o poder de manipular o tempo e até mesmo corromper os corações da cidade.",
            abilities=(
                "- **Voto de Liderança:** Seu voto na eliminação noturna dos Vilões tem peso 2.\n"
                "- **Sabotar:** Uma vez por jogo, durante o dia, use `/sabotar` para interromper tudo e forçar a chegada da noite, cancelando qualquer votação.\n"
                "- **Possuir:** Durante a noite, use `/possuir [nome]` para tentar converter um jogador. Esta ação substitui a eliminação da noite. Após 3 pontos de possessão, o alvo se torna um Assassino Simples. (Disponível apenas em jogos com 11+ jogadores)."
            ),
            image_file="assassino_alfa.png"
        )

class AssassinoJunior(Role):
    def __init__(self):
        super().__init__(
            name="Assassino Júnior",
            faction="Vilões",
            description="Você é o aprendiz do caos, um mestre da confusão.",
            abilities=(
                # >>> CORREÇÃO: Habilidades atualizadas
                "- **Marca da Vingança:** Na primeira noite, use `/escolher_alvo [nome]`. Se você morrer, seu alvo morre junto com você.\n"
                "- **Confundir:** Toda noite, use `/confundir [nome]` para fazer com que o alvo erre a sua próxima ação, redirecionando-a para um alvo aleatório. O efeito dura até a noite seguinte."
            ),
            image_file="assassino_junior.png"
        )
        
class Cumplice(Role):
    def __init__(self):
        super().__init__(
            name="Cúmplice",
            faction="Vilões",
            description="Você é o mestre da informação e do caos, o espião que age nas sombras.",
            abilities=(
                "- **Espionagem:** Na primeira noite, use `/escolher_alvo [nome]` para descobrir o papel exato de um jogador. A informação será partilhada com todos os seus companheiros Vilões.\n"
                "- **Fraudar Votação:** Uma vez por jogo, durante a votação, use `/fraudar` para embaralhar aleatoriamente o alvo de todos os votos. É um tiro no escuro que pode salvar sua equipe ou destruí-la."
            ),
            image_file="cumplice.png"
        )

class AssassinoSimples(Role):
    def __init__(self):
        super().__init__(
            name="Assassino Simples",
            faction="Vilões",
            description="Sua mente foi corrompida. Você perdeu suas habilidades antigas e agora serve à facção dos Vilões. Seu único objetivo é eliminar a cidade.",
            abilities=(
                "- **Votar:** Você participa da votação noturna dos Vilões para escolher quem será eliminado.\n"
                "- **Conexão Criminosa:** Ao ser convertido, você descobre quem são seus novos companheiros Vilões."
            ),
            image_file="assassino_simples.png"
        )

# Dicionário para fácil acesso
viloes_role_classes = {
    "Assassino Alfa": AssassinoAlfa,
    "Assassino Júnior": AssassinoJunior,
    "Cúmplice": Cumplice,
    "Assassino Simples": AssassinoSimples,
}
