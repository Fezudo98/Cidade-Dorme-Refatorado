# roles/solo_roles.py

from .base_role import Role
import discord

# --- Papéis da Facção Solo ---

class Palhaco(Role):
    def __init__(self):
        super().__init__(
            name="Palhaço",
            faction="Solo",
            description="Seu objetivo é ser incompreendido. Você quer que a cidade te linche!",
            abilities=(
                "- **Vitória por Linchamento:** Se você for o jogador escolhido para ser linchado durante o dia, você vence o jogo sozinho!"
            ),
            image_file="palhaco.png"
        )

class Fofoqueiro(Role):
    def __init__(self):
        super().__init__(
            name="Fofoqueiro",
            faction="Solo",
            description="Você adora uma boa fofoca e vive pelo caos. Seu objetivo é sobreviver e espalhar a discórdia.",
            abilities=(
                "- **Escolher Alvo:** Na primeira noite, use `/escolher_alvo [nome_jogador]` para marcar um alvo.\n"
                "- **Fofoca Póstuma:** Se você morrer, o papel do seu alvo será revelado para todos!\n"
                "- **Comparar Times:** Duas vezes por jogo, à noite, use `/comparar [jogador1] [jogador2]` para saber se dois jogadores são da mesma facção.\n"
                "- **Vitória por Sobrevivência:** Se você estiver vivo quando a Cidade ou os Vilões vencerem, você vence junto com eles."
            ),
            image_file="fofoqueiro.png"
        )

class Bruxo(Role):
    def __init__(self):
        super().__init__(
            name="Bruxo",
            faction="Solo",
            description="Você é um agente do caos com poder sobre a vida e a morte. Suas alianças são fluidas e sua vitória depende do impacto de suas ações.",
            abilities=(
                "- **Poções:** Você tem UMA Poção da Vida (`/reviver`) e UMA Poção da Morte (`/eliminar`). Você só pode usar UMA delas durante todo o jogo.\n"
                "- **Condição de Vitória:** Você vence junto com uma facção se sua única ação com poção for decisiva para a vitória dela (ex: matar o Prefeito e os Vilões vencerem, ou matar o Assassino Alfa e a Cidade vencer)."
            ),
            image_file="bruxo.png"
        )

class Cupido(Role):
    def __init__(self):
        super().__init__(
            name="Cupido",
            faction="Solo",
            description="Você une duas almas em um destino compartilhado. O amor (e você) pode conquistar tudo.",
            abilities=(
                "- **Flechar Amantes:** Na primeira noite, use `/apaixonar [jogador1] [jogador2]` para formar um casal.\n"
                "- **Destino Ligado:** Se um Amante morrer, o outro morre junto.\n"
                "- **Vitória por Amor:** Se o casal sobreviver e a facção de um deles vencer, o outro vence junto. Se o casal for o último sobrevivente, eles (e você) vencem sozinhos."
            ),
            image_file="cupido.png"
        )

class Praga(Role):
    def __init__(self):
        super().__init__(
            name="A Praga",
            faction="Solo",
            description="Você é uma doença ambulante. Seu objetivo é causar uma epidemia devastadora.",
            abilities=(
                "- **Paciente Zero:** Na primeira noite, use `/escolher_alvo [nome_jogador]` para infectar seu primeiro alvo. Apenas ele pode espalhar a doença.\n"
                "- **Exterminar:** Uma vez por jogo, à noite, use `/exterminar` para eliminar todos os jogadores infectados.\n"
                "- **Condição de Vitória:** Você vence o jogo sozinho se usar `/exterminar` e eliminar, no mínimo, 4 jogadores de uma só vez."
            ),
            image_file="praga.png"
        )

class Corruptor(Role):
    def __init__(self):
        super().__init__(
            name="Corruptor",
            faction="Solo",
            description="Sua diversão é impedir que os outros usem suas habilidades.",
            abilities=(
                "- **Corromper:** Toda noite, use `/corromper [nome_jogador]` para bloquear a habilidade de um alvo.\n"
                "- **Condição de Vitória:** Você vence sozinho se estiver vivo no final do jogo e nenhuma outra facção tiver cumprido a sua condição de vitória."
            ),
            image_file="corruptor.png"
        )

class CacadorDeCabecas(Role):
    def __init__(self):
        super().__init__(
            name="Caçador de Cabeças",
            faction="Solo",
            description="Você é um mercenário implacável. Não importa quem ganha a guerra, desde que você cumpra o seu contrato. Encontre a sua presa, manipule os outros para fazerem o trabalho sujo e colete a sua recompensa.",
            abilities=(
                "- **O Contrato:** No início do jogo, você recebe o nome de um alvo. Sua única missão é garantir que ele seja **linchado** pela cidade.\n"
                "- **Vitória por Contrato:** Se você conseguir que a cidade linche o seu alvo e você estiver vivo, você vence o jogo sozinho e imediatamente.\n"
                "- **Plano B:** Se o seu alvo morrer por qualquer outro meio, você perde suas habilidades e se torna um **Cidadão Comum**. Seu novo objetivo é ajudar a Cidade a vencer."
            ),
            image_file="cacador_de_cabecas.png"
        )

# Dicionário para fácil acesso aos construtores dos papéis Solo
solo_role_classes = {
    "Palhaço": Palhaco,
    "Fofoqueiro": Fofoqueiro,
    "Bruxo": Bruxo,
    "Cupido": Cupido,
    "Praga": Praga,
    "Corruptor": Corruptor,
    "Caçador de Cabeças": CacadorDeCabecas,
}
