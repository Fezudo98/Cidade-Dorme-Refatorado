# Cidade Dorme Online - Bot para Discord

![Imgur](https://imgur.com/zGdvBKo.png)

Bem-vindo ao repositório do **Cidade Dorme Online**, um bot para Discord que traz a experiência clássica do jogo de dedução social (também conhecido como Máfia ou Werewolf) diretamente para o seu servidor. Com uma arquitetura robusta, o bot gerencia múltiplas partidas simultaneamente, garantindo uma jogabilidade fluida e organizada.

---

## 📜 Visão Geral

O objetivo deste projeto é criar uma plataforma completa e automatizada para jogar Cidade Dorme. O bot lida com todas as complexidades do jogo:

-   **Distribuição de Papéis:** Atribui secretamente papéis com habilidades únicas para cada jogador via DM.
-   **Ciclo de Dia e Noite:** Gerencia as fases do jogo, silenciando e liberando o áudio dos jogadores automaticamente.
-   **Ações e Comandos:** Permite que os jogadores usem suas habilidades através de comandos de barra (`/`).
-   **Votação e Linchamento:** Conduz votações secretas e processa os resultados.
-   **Condições de Vitória Complexas:** Suporta múltiplos cenários de vitória, incluindo vitórias de facções (Cidade, Vilões) e vitórias de papéis Solo (Palhaço, Amantes, etc.).
-   **Sistema de Ranking:** Salva estatísticas de jogo e concede medalhas por conquistas.

---

## ✨ Funcionalidades Principais

-   **Gerenciamento Multi-Jogo:** O bot pode hospedar partidas em múltiplos canais ou servidores ao mesmo tempo sem conflitos.
-   **Interface Moderna:** Utiliza componentes interativos do Discord, como botões e menus de seleção, para uma experiência de usuário intuitiva.
-   **Áudio Imersivo:** Efeitos sonoros para eventos importantes do jogo, como o início da noite, mortes e disparos.
-   **Papéis Diversificados:** Uma vasta gama de papéis divididos em três facções:
    -   🏙️ **Cidade:** Prefeito, Xerife, Anjo, Guarda-costas, Detetive e mais.
    -   👺 **Vilões:** Assassino Alfa, Assassino Júnior, Cúmplice e outros.
    -   🎭 **Solo:** Papéis com objetivos únicos, como Palhaço, Caçador de Cabeças e Cupido.
-   **Sistema de Ranking e Conquistas:** Acompanha vitórias, partidas jogadas e concede medalhas por maestria em papéis e outros marcos.

---

## 🚀 Como Jogar

1.  **Convide o Bot:** Adicione o bot ao seu servidor do Discord.
2.  **Entre em um Canal de Voz:** Reúna seus amigos (de 5 a 16 jogadores) em um mesmo canal de voz.
3.  **Inicie a Preparação:** Em um canal de texto, digite `/preparar`. O bot irá identificar os jogadores no seu canal de voz e distribuir os papéis secretamente.
4.  **Receba seu Papel:** Verifique sua Mensagem Direta (DM) com o bot para descobrir seu papel e suas habilidades.
5.  **Comece o Jogo:** Quando todos estiverem prontos, o Mestre do Jogo (quem usou `/preparar`) digita `/iniciar`.
6.  **Sobreviva e Vença!** Use suas habilidades durante a noite e sua lábia durante o dia para alcançar o objetivo da sua facção.

### Comandos Essenciais
-   `/ajuda`: Mostra as regras básicas do jogo.
-   `/funcoes`: Lista todos os papéis e suas habilidades.
-   `/ranking`: Exibe o placar dos melhores jogadores.
-   `/perfil`: Mostra suas estatísticas e conquistas.

---

## 🛠️ Desenvolvido Com

-   **Linguagem:** Python 3.10+
-   **Biblioteca Discord:** [Py-cord](https://github.com/Pycord-Development/pycord) (um fork do `discord.py`)
-   **Dependências:** `python-dotenv` para gerenciamento de segredos, `PyNaCl` para áudio.

---

## 🏆 Créditos

Este projeto foi idealizado e desenvolvido inteiramente por:

**Fernando Sérgio**

-   **GitHub:** [@Fezudo98](https://github.com/Fezudo98)
-   **Instagram** [@sergioo_1918]
-   **LinkedIN** [www.linkedin.com/in/fernando-sérgio-786560373]

Sinta-se à vontade para contribuir, reportar bugs ou dar sugestões através das Issues deste repositório!
