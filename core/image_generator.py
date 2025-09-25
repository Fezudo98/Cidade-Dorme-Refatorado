# core/image_generator.py (VERSÃO 4.1 - CORREÇÃO FINAL)

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import requests
import io
import os
import logging # <-- 1. IMPORTAÇÃO ADICIONADA
from typing import Dict

logger = logging.getLogger(__name__) # <-- 2. INICIALIZAÇÃO DO LOGGER ADICIONADA

class ImageGenerator:
    def __init__(self, assets_path: str):
        self.assets_path = assets_path
        self.images_path = os.path.join(assets_path, "images")
        self.fonts_path = os.path.join(assets_path, "fonts")
        self.generated_path = os.path.join(assets_path, "generated_cards")
        os.makedirs(self.generated_path, exist_ok=True)
        
        try:
            self.font_title = ImageFont.truetype(os.path.join(self.fonts_path, "titulos.ttf"), 150)
            self.font_name = ImageFont.truetype(os.path.join(self.fonts_path, "textos.ttf"), 75)
            self.font_role = ImageFont.truetype(os.path.join(self.fonts_path, "textos.ttf"), 70)
            self.font_footer = ImageFont.truetype(os.path.join(self.fonts_path, "textos.ttf"), 50)
        except IOError:
            print("AVISO: Fontes não encontradas. Usando fontes padrão.")
            self.font_title = ImageFont.load_default()
            self.font_name = ImageFont.load_default()
            self.font_role = ImageFont.load_default()
            self.font_footer = ImageFont.load_default()

    def _crop_to_circle(self, image: Image.Image) -> Image.Image:
        mask = Image.new('L', image.size, 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0) + image.size, fill=255)
        
        output = image.copy()
        output.putalpha(mask)
        return output

    def generate_summary_card(self, player_name: str, player_avatar_url: str, role_name: str, role_image_file: str, outcome: str, player_id: str) -> str:
        width, height = 1080, 1920
        output_path = os.path.join(self.generated_path, f"summary_{player_id}.png")

        try:
            bg_path = os.path.join(self.images_path, "favicon.png")
            card = Image.open(bg_path).convert("RGB")
            card = card.resize((width, height), Image.LANCZOS)
            card = card.filter(ImageFilter.GaussianBlur(radius=20))
            card = ImageEnhance.Brightness(card).enhance(0.8)
        except FileNotFoundError:
            card = Image.new('RGB', (width, height), (20, 20, 30))

        avatar_size = (400, 400)
        overlap = 50
        try:
            role_img_path = os.path.join(self.images_path, role_image_file)
            role_img = Image.open(role_img_path).convert("RGBA").resize(avatar_size, Image.LANCZOS)
            role_img_circle = self._crop_to_circle(role_img)
        except Exception as e:
            logger.error(f"Falha ao carregar imagem do papel {role_image_file}: {e}")
            role_img_circle = Image.new('RGBA', avatar_size, (0,0,0,0))
        try:
            response = requests.get(player_avatar_url)
            player_img = Image.open(io.BytesIO(response.content)).convert("RGBA").resize(avatar_size, Image.LANCZOS)
            player_img_circle = self._crop_to_circle(player_img)
        except Exception as e:
            logger.error(f"Falha ao carregar avatar do jogador {player_name}: {e}")
            player_img_circle = Image.new('RGBA', avatar_size, (0,0,0,0))
            
        center_y = 650
        role_pos_x = (width // 2) - overlap
        player_pos_x = (width // 2) - avatar_size[0] + overlap
        
        card.paste(role_img_circle, (role_pos_x, center_y), role_img_circle)
        card.paste(player_img_circle, (player_pos_x, center_y), player_img_circle)
        
        draw = ImageDraw.Draw(card)
        def draw_text_with_shadow(position, text, font, fill_color):
            x, y = position
            shadow_color = (0, 0, 0)
            draw.text((x+4, y+4), text, font=font, fill=shadow_color, anchor="ms")
            draw.text(position, text, font=font, fill=fill_color, anchor="ms")

        title_text = "VITÓRIA!" if outcome == "VICTORY" else "FIM DE JOGO"
        title_color = (255, 215, 0) if outcome == "VICTORY" else (200, 200, 200)
        draw_text_with_shadow((width/2, 300), title_text, self.font_title, title_color)

        current_y = center_y + avatar_size[1] + 100
        draw_text_with_shadow((width/2, current_y), player_name, self.font_name, (255, 255, 255))
        current_y += 90
        draw_text_with_shadow((width/2, current_y), role_name, self.font_role, (220, 220, 220))
        draw_text_with_shadow((width/2, height - 100), "Jogue Cidade Dorme no Discord", self.font_footer, (200, 200, 200))
        
        card.save(output_path)
        return output_path