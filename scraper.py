#!/usr/bin/env python3
"""
AutoRadar Bot - Web Scraper de coches españoles
Raspa Wallapop, Milanuncios, Coches.net, Motor.es
Guarda en Supabase y envía email
"""

import requests
from bs4 import BeautifulSoup
import re
import json
from datetime import datetime
import os
from supabase import create_client, Client
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import sys

# ============================================================
# CONFIGURACIÓN
# ============================================================

SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')
GMAIL_USER = os.environ.get('GMAIL_USER', '')
GMAIL_PASS = os.environ.get('GMAIL_PASS', '')
GMAIL_TO = os.environ.get('GMAIL_TO', '')

# User agents para evitar bloqueos
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
]

# Portales a raspar (rotar según día del mes)
PORTALES = {
    0: [  # Conjunto 0
        {'id': 'wallapop', 'nombre': 'Wallapop', 'url': 'https://es.wallapop.com/search?category_ids=100&keywords=coche&longitude=-3.7038&latitude=40.4168'},
        {'id': 'milanuncios', 'nombre': 'Milanuncios', 'url': 'https://www.milanuncios.com/coches-de-segunda-mano/'},
        {'id': 'coches_net', 'nombre': 'Coches.net', 'url': 'https://www.coches.net/segunda-mano/?pg=1'},
    ],
    1: [  # Conjunto 1
        {'id': 'wallapop', 'nombre': 'Wallapop', 'url': 'https://es.wallapop.com/search?category_ids=100&keywords=coche&longitude=-3.7038&latitude=40.4168'},
        {'id': 'milanuncios', 'nombre': 'Milanuncios', 'url': 'https://www.milanuncios.com/coches-de-segunda-mano/'},
        {'id': 'motor_es', 'nombre': 'Motor.es', 'url': 'https://www.motor.es/coches-segunda-mano/'},
    ],
    2: [  # Conjunto 2
        {'id': 'wallapop', 'nombre': 'Wallapop', 'url': 'https://es.wallapop.com/search?category_ids=100&keywords=coche&longitude=-3.7038&latitude=40.4168'},
        {'id': 'milanuncios', 'nombre': 'Milanuncios', 'url': 'https://www.milanuncios.com/coches-de-segunda-mano/'},
        {'id': 'autocasion', 'nombre': 'Autocasión', 'url': 'https://www.autocasion.com/coches-ocasion'},
    ]
}

# ============================================================
# FUNCIONES DE SCRAPING
# ============================================================

def get_headers():
    import random
    return {'User-Agent': random.choice(USER_AGENTS)}

def raspar_portal(url, portal_id, portal_nombre):
    """Raspa un portal y extrae coches"""
    try:
        print(f"[{portal_id}] Raspando {portal_nombre}...")
        response = requests.get(url, headers=get_headers(), timeout=15)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        html = response.text
        
        coches = []
        
        # Extraer precios con regex
        precios = []
        for match in re.finditer(r'(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)\s*(?:€|EUR)', html):
            try:
                precio = float(match.group(1).replace('.', '').replace(',', '.'))
                if 500 <= precio <= 300000:
                    precios.append(precio)
            except:
                pass
        
        # Extraer km
        kms = []
        for match in re.finditer(r'(\d{1,3}(?:\.\d{3})*)\s*(?:km|Km|KM)', html):
            try:
                km = int(match.group(1).replace('.', ''))
                if 0 <= km <= 999999:
                    kms.append(km)
            except:
                pass
        
        # Extraer años
        years = []
        for match in re.finditer(r'\b(20(?:0[0-9]|1[0-9]|2[0-5]))\b', html):
            years.append(match.group(1))
        
        if not precios:
            print(f"[{portal_id}] Sin precios encontrados")
            return coches
        
        # Crear coches con los datos extraídos
        fecha_sync = datetime.utcnow().isoformat()
        for i, precio in enumerate(precios[:50]):  # Max 50 coches por portal
            coche = {
                'portal_id': portal_id,
                'portal': portal_nombre,
                'titulo': f'{portal_nombre} - Anuncio #{i+1}',
                'precio': precio,
                'km': kms[i] if i < len(kms) else 0,
                'year': years[i] if i < len(years) else '',
                'lugar': '',
                'link': url,
                'id_unico': f'{portal_id}_{precio}_{i}_{fecha_sync.split("T")[0]}',
                'fecha_sync': fecha_sync,
                'es_nuevo': True
            }
            coches.append(coche)
        
        print(f"[{portal_id}] ✅ {len(coches)} coches extraídos")
        return coches
        
    except Exception as e:
        print(f"[{portal_id}] ❌ Error: {str(e)}")
        return []

# ============================================================
# SUPABASE
# ============================================================

def guardar_en_supabase(coches):
    """Guarda coches en Supabase"""
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("⚠️ Supabase no configurado")
        return False
    
    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        for coche in coches:
            try:
                # Intentar insert, si existe actualizar
                supabase.table('coches_anuncios').upsert(coche).execute()
            except Exception as e:
                print(f"Error guardando {coche['id_unico']}: {e}")
        
        print(f"✅ {len(coches)} coches guardados en Supabase")
        return True
    except Exception as e:
        print(f"❌ Error Supabase: {e}")
        return False

# ============================================================
# EMAIL
# ============================================================

def enviar_email_resumen(total_coches, portales_count):
    """Envía email con resumen"""
    if not GMAIL_USER or not GMAIL_PASS or not GMAIL_TO:
        print("⚠️ Email no configurado")
        return False
    
    try:
        hoy = datetime.now().strftime('%d/%m/%Y')
        asunto = f'🚗 AutoRadar - {total_coches} coches nuevos ({hoy})'
        
        cuerpo = f"""
        <html>
        <body style="font-family: Arial; background: #f5f5f5; padding: 20px;">
        <div style="background: white; border-radius: 10px; padding: 20px; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #333;">🚗 AutoRadar - Resumen Diario</h2>
            <p><strong>Fecha:</strong> {hoy}</p>
            <p><strong>Total coches nuevos:</strong> <span style="color: #4CAF50; font-size: 18px; font-weight: bold;">{total_coches}</span></p>
            <p><strong>Portales rastreados:</strong> {portales_count}</p>
            <p style="color: #666; font-size: 12px;">
                <a href="https://autoradar-dashboard.vercel.app">Ver dashboard completo</a>
            </p>
            <hr style="border: none; border-top: 1px solid #eee;">
            <p style="color: #999; font-size: 12px;">AutoRadar Bot - Rastreador automático de coches</p>
        </div>
        </body>
        </html>
        """
        
        mensaje = MIMEMultipart()
        mensaje['From'] = GMAIL_USER
        mensaje['To'] = GMAIL_TO
        mensaje['Subject'] = asunto
        mensaje.attach(MIMEText(cuerpo, 'html'))
        
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as servidor:
            servidor.login(GMAIL_USER, GMAIL_PASS)
            servidor.send_message(mensaje)
        
        print(f"✅ Email enviado a {GMAIL_TO}")
        return True
    except Exception as e:
        print(f"❌ Error email: {e}")
        return False

# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 60)
    print("🚗 AutoRadar Bot - Web Scraper")
    print("=" * 60)
    
    # Determinar qué portales raspar hoy
    dia = datetime.now().day
    rotacion = (dia - 1) % 3
    portales_hoy = PORTALES.get(rotacion, PORTALES[0])
    
    print(f"\n📅 Día del mes: {dia} (Conjunto {rotacion})")
    print(f"📋 Portales a raspar hoy: {', '.join([p['nombre'] for p in portales_hoy])}\n")
    
    # Raspar todos los portales
    todos_los_coches = []
    for portal in portales_hoy:
        coches = raspar_portal(portal['url'], portal['id'], portal['nombre'])
        todos_los_coches.extend(coches)
    
    print(f"\n📊 Total coches extraídos: {len(todos_los_coches)}")
    
    # Guardar en Supabase
    if todos_los_coches:
        guardar_en_supabase(todos_los_coches)
    
    # Enviar email
    enviar_email_resumen(len(todos_los_coches), len(portales_hoy))
    
    print("\n✅ Proceso completado")
    return 0

if __name__ == '__main__':
    sys.exit(main())
