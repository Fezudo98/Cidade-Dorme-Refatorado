# test_image_gen.py (VERSÃO 3.0)
import os
from core.image_generator import ImageGenerator

def run_test():
    # --- ESCOLHA QUAL CARD VOCÊ QUER TESTAR ---
    TEST_SCENARIO = "VICTORY"
    # -----------------------------------------

    print(f"Iniciando teste para o cenário: {TEST_SCENARIO}...")
    base_dir = os.path.dirname(os.path.abspath(__file__))
    assets_path = os.path.join(base_dir, "assets")
    if not os.path.isdir(assets_path):
        print(f"ERRO: A pasta 'assets' não foi encontrada em '{assets_path}'")
        return
        
    generator = ImageGenerator(assets_path=assets_path)

    # Dados de teste
    player_name = "Fernando Sérgio"
    player_avatar_url = "https://cdn.discordapp.com/embed/avatars/1.png" # Mudei o avatar para o azul
    
    role_name = "Assassino Alfa"
    role_image_file = "assassino_alfa.png" # O arquivo da imagem do personagem
    
    outcome = TEST_SCENARIO

    print(f"Gerando card de '{outcome}' para: {player_name} como {role_name}...")
    try:
        output_file_path = generator.generate_summary_card(
            player_name=player_name,
            player_avatar_url=player_avatar_url,
            role_name=role_name,
            role_image_file=role_image_file,
            outcome=outcome
        )
        print(f"\n✅ Sucesso! Card gerado em: {output_file_path}\n")
        print("Abra o arquivo para ver o novo design Duality!")
    except Exception as e:
        print(f"\n❌ Ocorreu um erro: {e}")

if __name__ == "__main__":
    run_test()