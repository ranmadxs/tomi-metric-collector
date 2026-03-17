#!/usr/bin/env python3
"""Genera GIF animado: sensor ultrasónico, estanque, alertas - estilo moderno."""

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import os
import math

# Render a 2x y escalar para anti-aliasing suave
SCALE = 2
W, H = 600 * SCALE, 340 * SCALE
DURATION = 350
LOOP = 0

# Paleta moderna
BG = (15, 23, 42)
TANK_BG = (30, 41, 59)
TANK_BORDER = (56, 189, 248)
WATER_HI = (56, 189, 248)
WATER_LO = (248, 113, 113)
SENSOR = (71, 85, 105)
SENSOR_EYE = (56, 189, 248)
PHONE = (30, 41, 59)
PHONE_BORDER = (148, 163, 184)
ALERT = (239, 68, 68)
OK = (74, 222, 128)
TEXT_MUTED = (148, 163, 184)


def rounded_rect(draw, xy, radius, fill=None, outline=None, width=1):
    """Dibuja rectángulo con esquinas redondeadas."""
    x1, y1, x2, y2 = xy
    draw.rounded_rectangle([x1, y1, x2, y2], radius=radius, fill=fill, outline=outline, width=width)


def draw_frame(draw, frame_num, total_frames):
    t = frame_num / total_frames
    
    # Fondo con gradiente sutil (simulado con overlay)
    draw.rectangle([0, 0, W, H], fill=BG)
    
    tank_x, tank_y = 100 * SCALE, 100 * SCALE
    tank_w, tank_h = 160 * SCALE, 180 * SCALE
    radius = 16 * SCALE
    
    # Nivel de agua
    if t < 0.18:
        level = 0.65
    elif t < 0.38:
        level = 0.65 - (t - 0.18) * 2.2
        level = max(0.12, level)
    elif t < 0.58:
        level = 0.12
    else:
        level = 0.12 + (t - 0.58) * 2.0
        level = min(0.65, level)
    
    # Estanque - rounded
    rounded_rect(draw, [tank_x, tank_y, tank_x + tank_w, tank_y + tank_h], 
                radius, fill=TANK_BG, outline=TANK_BORDER, width=2 * SCALE)
    
    # Agua - superficie redondeada arriba
    water_top = tank_y + tank_h - int(tank_h * level)
    water_color = WATER_HI if level > 0.22 else WATER_LO
    water_r = min(12 * SCALE, radius - 4 * SCALE)
    rounded_rect(draw, [tank_x + 6 * SCALE, water_top, tank_x + tank_w - 6 * SCALE, tank_y + tank_h - 6 * SCALE],
                water_r, fill=water_color)
    
    # Reflejo en el agua (línea sutil)
    if level > 0.2:
        refl_y = water_top + 8 * SCALE
        draw.line([tank_x + 20 * SCALE, refl_y, tank_x + tank_w - 20 * SCALE, refl_y], 
                  fill=(100, 149, 237), width=1)
    
    # Sensor - cilindro suave
    sensor_x = tank_x + tank_w // 2 - 35 * SCALE
    sensor_y = tank_y - 85 * SCALE
    sensor_w, sensor_h = 70 * SCALE, 55 * SCALE
    rounded_rect(draw, [sensor_x, sensor_y, sensor_x + sensor_w, sensor_y + sensor_h],
                 radius // 2, fill=SENSOR, outline=TANK_BORDER, width=1)
    # Ojo del sensor
    eye_margin = 15 * SCALE
    pulse = 0.7 + 0.3 * math.sin(frame_num * 0.3)
    draw.ellipse([sensor_x + eye_margin, sensor_y + 12 * SCALE, 
                  sensor_x + sensor_w - eye_margin, sensor_y + 35 * SCALE],
                 fill=SENSOR_EYE)
    
    # H2O label
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 22 * SCALE)
        font_sm = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 14 * SCALE)
    except:
        font = font_sm = ImageFont.load_default()
    
    draw.text((tank_x + tank_w // 2 - 25 * SCALE, tank_y + tank_h // 2 - 25 * SCALE), 
              "H₂O", fill=(255, 255, 255), font=font)
    
    # Señales y celular (escena 2)
    if t > 0.12 and t < 0.52:
        # Ondas de señal (puntos animados)
        for i in range(5):
            phase = (frame_num + i * 3) % 12
            px = tank_x + tank_w + 30 * SCALE + phase * 8
            py = tank_y + 50 * SCALE + i * 18
            draw.ellipse([px - 3, py - 3, px + 3, py + 3], fill=TANK_BORDER)
        # Línea hacia celular
        draw.line([tank_x + tank_w + 50 * SCALE, tank_y + 70 * SCALE, 400 * SCALE, 120 * SCALE], 
                  fill=TANK_BORDER, width=2)
        
        # Celular
        px, py = 420 * SCALE, 60 * SCALE
        rounded_rect(draw, [px, py, px + 140 * SCALE, py + 200 * SCALE], 12 * SCALE,
                    fill=PHONE, outline=PHONE_BORDER, width=1)
        rounded_rect(draw, [px + 15 * SCALE, py + 20 * SCALE, px + 125 * SCALE, py + 100 * SCALE],
                    8 * SCALE, fill=(56, 189, 248, 60))
        draw.text((px + 50 * SCALE, py + 130 * SCALE), "Gráficos", fill=TEXT_MUTED, font=font_sm)
    
    # Alerta
    if 0.22 < t < 0.68:
        alert_x, alert_y = W - 100 * SCALE, 30 * SCALE
        draw.ellipse([alert_x, alert_y, alert_x + 70 * SCALE, alert_y + 70 * SCALE], fill=ALERT)
        draw.text((alert_x + 22 * SCALE, alert_y + 18 * SCALE), "!", fill=(255, 255, 255), font=font)
    
    # Email/WhatsApp
    if 0.32 < t < 0.72:
        draw.text((tank_x, tank_y - 35 * SCALE), "Email  WhatsApp", fill=TEXT_MUTED, font=font_sm)
    
    # Camión
    if t > 0.52:
        progress = (t - 0.52) / 0.28
        truck_x = 80 * SCALE + int(progress * 220 * SCALE)
        truck_x = min(truck_x, 220 * SCALE)
        rounded_rect(draw, [truck_x, 240 * SCALE, truck_x + 90 * SCALE, 310 * SCALE], 8 * SCALE, fill=SENSOR)
        rounded_rect(draw, [truck_x + 55 * SCALE, 225 * SCALE, truck_x + 130 * SCALE, 255 * SCALE], 6 * SCALE, fill=PHONE)
    
    # Normalidad
    if t > 0.78:
        draw.text((tank_x + tank_w // 2 - 55 * SCALE, tank_y - 60 * SCALE), 
                  "Normalidad", fill=OK, font=font)


def main():
    out_path = os.path.join(os.path.dirname(__file__), "..", "tomi_metrics", "static", "images", "sensor-animation.gif")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    
    total_frames = 60
    frames = []
    
    for i in range(total_frames):
        img = Image.new("RGB", (W, H), BG)
        draw = ImageDraw.Draw(img)
        draw_frame(draw, i, total_frames)
        # Escalar para anti-aliasing suave
        img_small = img.resize((600, 340), Image.Resampling.LANCZOS)
        frames.append(img_small)
    
    frames[0].save(
        out_path,
        save_all=True,
        append_images=frames[1:],
        duration=DURATION,
        loop=LOOP,
        optimize=True
    )
    print(f"GIF creado: {out_path}")


if __name__ == "__main__":
    main()
