# roles/base_role.py

import discord

class Role:
    """Classe base para todos os papéis do jogo."""
    def __init__(self, name: str, faction: str, description: str, abilities: str, image_file: str):
        self.name = name
        self.faction = faction # "Cidade", "Vilões", "Solo"
        self.description = description
        self.abilities = abilities # Descrição das habilidades e comandos
        self.image_file = image_file # Nome do arquivo de imagem (ex: "prefeito.png")

    def get_embed(self, member: discord.Member) -> discord.Embed:
        """Cria um Embed do Discord para enviar ao jogador via DM."""
        embed = discord.Embed(
            title=f"🎭 Seu Papel: {self.name} 🎭",
            description=f"**Facção:** {self.faction}\n\n{self.description}",
            color=self.get_faction_color()
        )
        embed.add_field(name="Habilidades e Comandos", value=self.abilities, inline=False)
        embed.set_footer(text="Leia com atenção e não revele seu papel... a menos que queira ser o primeiro a visitar o cemitério! 😉")
        # A imagem será adicionada como anexo, mas podemos colocar uma miniatura se quisermos
        # embed.set_thumbnail(url=f"attachment://{self.image_file}") # Requer que a imagem seja enviada junto
        return embed

    def get_faction_color(self) -> discord.Color:
        """Retorna uma cor baseada na facção para o Embed."""
        if self.faction == "Cidade":
            return discord.Color.blue()
        elif self.faction == "Vilões":
            return discord.Color.red()
        elif self.faction == "Solo":
            return discord.Color.purple()
        else:
            return discord.Color.default()

    async def perform_night_action(self, game_state, player_state, target_member: discord.Member):
        """Método para ser sobrescrito por papéis com ações noturnas."""
        # Lógica específica da ação noturna do papel
        pass

    async def perform_day_action(self, game_state, player_state, target_member: discord.Member):
        """Método para ser sobrescrito por papéis com ações diurnas (ex: Xerife)."""
        # Lógica específica da ação diurna do papel
        pass

    # Outros métodos específicos podem ser adicionados conforme necessário

