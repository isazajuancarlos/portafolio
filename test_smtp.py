#!/usr/bin/env python3
"""
Script de prueba para verificar credenciales SMTP de Zoho
"""
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

EMAIL_PWD = os.getenv("PASSWORD")

print("=== Test de Conexión SMTP Zoho ===")
print(f"Usuario: contacto@xiliux.com")
print(f"Password cargada: {'✓ SÍ' if EMAIL_PWD else '✗ NO'}")
if EMAIL_PWD:
    print(f"Longitud password: {len(EMAIL_PWD)} caracteres")
    print(f"Primeros 3 caracteres: {EMAIL_PWD[:3]}...")
print()

if not EMAIL_PWD:
    print("ERROR: La variable PASSWORD no está definida en .env")
    exit(1)

try:
    print("Intentando conectar a smtp.zoho.com:465...")
    server = smtplib.SMTP_SSL('smtp.zoho.com', 465, timeout=10)
    print("✓ Conexión SSL establecida")

    print("Intentando autenticación...")
    server.login('contacto@xiliux.com', EMAIL_PWD)
    print("✓ Autenticación exitosa")

    # Enviar email de prueba
    print("Enviando email de prueba...")
    msg = MIMEMultipart()
    msg['From'] = 'contacto@xiliux.com'
    msg['To'] = 'contacto@xiliux.com'
    msg['Subject'] = "Test SMTP - Portafolio"

    body = "Este es un email de prueba desde el script de diagnóstico.\nSi recibes esto, el SMTP funciona correctamente."
    msg.attach(MIMEText(body, 'plain'))

    server.send_message(msg)
    print("✓ Email enviado correctamente")

    server.quit()
    print("\n✅ TODAS LAS PRUEBAS PASARON - SMTP funciona correctamente")

except smtplib.SMTPAuthenticationError as e:
    print(f"\n❌ ERROR DE AUTENTICACIÓN")
    print(f"Código: {e.smtp_code}")
    print(f"Mensaje: {e.smtp_error.decode('utf-8') if hasattr(e.smtp_error, 'decode') else e.smtp_error}")
    print("\nPosibles causas:")
    print("1. La contraseña en .env es incorrecta")
    print("2. La cuenta requiere contraseña de aplicación específica")
    print("3. SMTP no está habilitado en la configuración de Zoho")

except smtplib.SMTPException as e:
    print(f"\n❌ ERROR SMTP: {type(e).__name__}")
    print(f"Detalles: {str(e)}")

except ConnectionRefusedError:
    print("\n❌ ERROR: Conexión rechazada")
    print("El servidor SMTP no acepta conexiones en el puerto 465")

except TimeoutError:
    print("\n❌ ERROR: Timeout de conexión")
    print("No se pudo conectar al servidor SMTP (problema de red)")

except Exception as e:
    print(f"\n❌ ERROR INESPERADO: {type(e).__name__}")
    print(f"Detalles: {str(e)}")
    import traceback
    traceback.print_exc()
