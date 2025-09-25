# roles/cidade_roles.py

from .base_role import Role
import discord

# --- Papéis da Facção Cidade ---

class Prefeito(Role):
    def __init__(self):
        super().__init__(
            name="Prefeito",
            faction="Cidade",
            description="Você é o líder da cidade. Sua palavra tem peso e sua sobrevivência é crucial.",
            abilities=(
                "- **Indulto Político:** Você sobrevive à primeira tentativa de linchamento contra você.\n"
                "- **Decreto:** Uma vez por jogo, durante a votação, use `/decreto` para fazer seu voto valer 3 pontos e o de cada cidadão valer 2, bloqueando a sabotagem dos Vilões."
            ),
            image_file="prefeito.png"
        )

class Anjo(Role):
    def __init__(self):
        super().__init__(
            name="Anjo",
            faction="Cidade",
            description="Você é um guardião celestial com o poder de reverter a morte.",
            abilities=(
                "- **Milagre:** Uma vez por jogo, à noite, use `/reviver [nome_jogador_morto]` para trazer alguém de volta à vida."
            ),
            image_file="anjo.png"
        )
        
class Xerife(Role):
    def __init__(self):
        super().__init__(
            name="Xerife",
            faction="Cidade",
            description="Você é a lei na cidade. Sua arma pode acabar com o jogo, para o bem ou para o mal.",
            abilities=(
                "- **Disparar:** Você tem 2 balas (ou apenas 1 em jogos com 6 ou menos jogadores) e só pode atirar **uma vez por dia**. Use `/disparar [nome_jogador]` para eliminar um alvo. Isso revelará sua identidade.\n"
                "- **Condições Especiais:** Se atirar no Assassino Alfa, a Cidade vence. Se atirar no Prefeito, os Vilões vencem."
            ),
            image_file="xerife.png"
        )
        
class GuardaCostas(Role):
    def __init__(self):
        super().__init__(
            name="Guarda-costas",
            faction="Cidade",
            description="Sua missão é proteger os outros, mesmo que custe sua vida.",
            abilities=(
                "- **Proteger:** Toda noite, use `/proteger [nome_jogador]` para defender alguém de um ataque dos vilões.\n"
                "- **Resistência Única:** Você sobrevive à primeira vez que sofreria dano, seja por um ataque direto ou por proteger alguém. Na segunda vez, você morre. Importante: Sua habilidade de proteger é ineficaz contra o ataque de um Bruxo."
            ),
            image_file="guarda_costas.png"
        )
        
class Detetive(Role):
    def __init__(self):
        super().__init__(
            name="Detetive",
            faction="Cidade",
            description="Você é um mestre da dedução, sempre em busca de pistas.",
            abilities=(
                "- **Marcar Alvos:** Toda noite, use `/marcar` para vigiar um ou dois jogadores. Se um deles for morto, você receberá o nome de dois suspeitos: o assassino e um inocente."
            ),
            image_file="detetive.png"
        )

class VidenteDeAura(Role):
    def __init__(self):
        super().__init__(
            name="Vidente de Aura",
            faction="Cidade",
            description="Você sente as energias. Consegue distinguir o bem do mal, mas sem muitos detalhes.",
            abilities=(
                "- **Investigar Aura:** Toda noite, use `/investigar_aura [nome_jogador]` para saber se a facção do alvo é 'Cidade' ou 'Não-Cidade'."
            ),
            image_file="vidente.png"
        )

class Medium(Role):
    def __init__(self):
        super().__init__(
            name="Médium",
            faction="Cidade",
            description="Você é um mestre dos espíritos, capaz de transformar uma alma perdida em um aliado espectral.",
            abilities=(
                "- **Converter Fantasma:** Uma vez por jogo, à noite, use `/mediunidade [nome_jogador_morto]` para transformar um jogador morto em um Fantasma sob seu controle.\n"
                "- **Visão Espectral:** O Fantasma pode `/assombrar` um jogador por noite, e no final da noite, ambos recebem um relatório de quem visitou o alvo e quem o alvo visitou.\n"
                "- **Reembolso:** Se você converter o Prefeito e ele for revivido, seu poder é reembolsado."
            ),
            image_file="medium.png"
        )

# >>> CORREÇÃO: Novo papel Cidadão Comum
class CidadaoComum(Role):
    def __init__(self):
        super().__init__(
            name="Cidadão Comum",
            faction="Cidade",
            description="Você era um mercenário, mas falhou no seu contrato. Agora, seu único objetivo é ajudar a cidade a vencer.",
            abilities=(
                "- **Dever Cívico:** Você não tem mais habilidades especiais. Use sua voz e seu voto para ajudar a cidade a encontrar os vilões."
            ),
            image_file="cidadao_comum.png" # Sugestão de nome de arquivo
        )

# Dicionário para fácil acesso
cidade_role_classes = {
    "Prefeito": Prefeito,
    "Anjo": Anjo,
    "Xerife": Xerife,
    "Guarda-costas": GuardaCostas,
    "Detetive": Detetive,
    "Vidente de Aura": VidenteDeAura,
    "Médium": Medium,
    "Cidadão Comum": CidadaoComum,
}
