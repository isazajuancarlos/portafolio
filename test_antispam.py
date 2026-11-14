"""Pareja roja/verde para el filtro de contenido anti-spam (directiva 33).

Corre: `python test_antispam.py` — sin dependencias, no toca red ni correo.
El caso ROJO es el spam REAL medido el 2026-11-08; el VERDE son contactos
legítimos que NO se pueden perder (incluido uno terso y uno con URL).
"""
from antispam import es_spam_contenido

# --- ROJO: debe marcarse como spam (el patrón medido y variantes) ---
ROJOS = [
    ("NATREGTEGH1610646NEHTYHYHTR", "cornell54609@notlettersmail.com", "METYUTYTJ1610646MAWRERGTRH"),
    ("Juan", "alguien@mailinator.com", "Hola, me interesa"),            # correo desechable
    ("ABC12345678901234567", "real@gmail.com", "hola"),                  # token basura en nombre
    ("Pedro", "real@gmail.com", "mira esto XK19LP22ZZ8841QWmzz73aa"),   # token basura en mensaje
    ("NATREGTEGHNEHTYHYHTRQWERTYUIOP", "x@dominio.com", "hola"),         # nombre 30+ sin espacios
]

# --- VERDE: NO se puede marcar (leads legítimos) ---
VERDES = [
    ("Juan Carlos Isaza", "isazajuancarlos@gmail.com",
     "Hola, quiero cotizar un sistema de informes para mi empresa. ¿Podemos hablar?"),
    ("María", "maria@outlook.com", "Interesada, llámenme por favor."),   # terso, nombre corto
    ("Soluciones S.A.S.", "ventas@miempresa.com.co",
     "Vean nuestra web https://www.miempresa.com.co/proyectos/2024 y escríbannos."),  # URL con dígitos
    ("José Pérez", "jose.perez@gmail.com", "Buenas, necesito asesoría en Ley 1581."),
]


def main():
    fallos = 0
    for n, e, m in ROJOS:
        if not es_spam_contenido(n, e, m):
            print(f"FALLO (falso negativo): NO marcó spam → nombre={n!r} email={e!r}")
            fallos += 1
    for n, e, m in VERDES:
        if es_spam_contenido(n, e, m):
            print(f"FALLO (falso positivo): marcó spam a un lead REAL → nombre={n!r} email={e!r}")
            fallos += 1
    total = len(ROJOS) + len(VERDES)
    if fallos:
        print(f"\n{fallos}/{total} FALLARON")
        raise SystemExit(1)
    print(f"OK: {len(ROJOS)} rojos marcados, {len(VERDES)} verdes dejados pasar ({total}/{total})")


if __name__ == "__main__":
    main()
