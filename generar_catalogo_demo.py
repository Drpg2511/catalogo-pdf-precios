"""
Genera un catalogo comercial SINTETICO con la misma estructura que un
catalogo real de suministro industrial. Todos los datos son inventados.

Existe para poder demostrar y verificar `actualizar_precios.py` sin usar
el catalogo de ningun cliente.

Estructura:
  - Pagina 1: portada
  - Paginas 2-3: tablas normales. Cada fila tiene columnas de MEDIDA en el
    MISMO formato numerico que el PRECIO (X,XX). Es una trampa deliberada:
    un regex ingenuo actualizaria la medida en vez del precio.
  - Pagina 4: layout multicolumna (varios precios por linea).

Uso:  python generar_catalogo_demo.py
Sale: demo/catalogo_ORIGINAL.pdf
"""
import os
import random

import pymupdf as fitz

random.seed(7)  # catalogo reproducible

ANCHO, ALTO = 595, 842  # A4
AZUL = (0.09, 0.22, 0.39)
GRIS = (0.93, 0.93, 0.93)
GRIS2 = (0.86, 0.86, 0.86)

SALIDA = os.path.join("demo", "catalogo_ORIGINAL.pdf")

FAMILIAS = [
    ("TN", "TORNILLO HEXAGONAL DIN 933", ["M6", "M8", "M10", "M12", "M16"]),
    ("AR", "ARANDELA PLANA DIN 125", ["M6", "M8", "M10", "M12", "M16"]),
    ("JT", "JUNTA TORICA NBR 70 SH", ['1/8"', '1/4"', '3/8"', '1/2"', '3/4"']),
    ("VB", "VALVULA DE BOLA LATON", ['1/4"', '3/8"', '1/2"', '3/4"', '1"']),
]


def precio():
    return f"{random.uniform(0.8, 24.0):.2f}".replace(".", ",")


def medida():
    # MISMO formato que un precio -> la trampa
    return f"{random.uniform(1.0, 60.0):.2f}".replace(".", ",")


def encabezado(pag):
    """Banda superior con la marca. El cliente pide quitarla."""
    pag.draw_rect(fitz.Rect(0, 0, ANCHO, 91), color=AZUL, fill=AZUL)
    pag.insert_text((40, 40), "NORVAL SUMINISTROS", fontsize=22,
                    fontname="hebo", color=(1, 1, 1))
    pag.insert_text((40, 64), "CATALOGO GENERAL - LISTA DE PRECIOS",
                    fontsize=11, fontname="helv", color=(0.8, 0.85, 0.92))
    pag.insert_text((ANCHO - 150, 40), "EDICION 2026", fontsize=10,
                    fontname="helv", color=(1, 1, 1))


def pagina_tabla(doc, familias, titulo):
    pag = doc.new_page(width=ANCHO, height=ALTO)
    encabezado(pag)
    pag.insert_text((40, 125), titulo, fontsize=14, fontname="hebo", color=AZUL)

    y = 150
    cols = [40, 130, 300, 380, 460, 530]  # CODIGO DESC LARGO ANCHO PRECIO
    pag.draw_rect(fitz.Rect(40, y, 555, y + 20), color=AZUL, fill=AZUL)
    for x, t in zip(cols, ["CODIGO", "DESCRIPCION", "LARGO", "ANCHO", "PRECIO"]):
        pag.insert_text((x + 4, y + 14), t, fontsize=8, fontname="hebo",
                        color=(1, 1, 1))
    y += 20

    n = 0
    for pref, desc, medidas in familias:
        for m in medidas:
            fondo = GRIS if n % 2 == 0 else GRIS2
            pag.draw_rect(fitz.Rect(40, y, 555, y + 18), color=fondo, fill=fondo)
            pag.insert_text((cols[0] + 4, y + 12), f"{pref}-{1000 + n * 7:04d}",
                            fontsize=8, fontname="helv")
            pag.insert_text((cols[1] + 4, y + 12), f"{desc}  {m}",
                            fontsize=8, fontname="helv")
            # columnas trampa, mismo formato que el precio
            pag.insert_text((cols[2] + 4, y + 12), medida(), fontsize=8,
                            fontname="helv")
            pag.insert_text((cols[3] + 4, y + 12), medida(), fontsize=8,
                            fontname="helv")
            # PRECIO: siempre el ultimo de la linea (mas a la derecha)
            pag.insert_text((cols[4] + 4, y + 12), precio(), fontsize=8,
                            fontname="hebo")
            y += 18
            n += 1
        y += 6
    return pag


def pagina_multicolumna(doc):
    """Varios precios por linea: la deteccion derecha-a-izquierda no sirve aqui."""
    pag = doc.new_page(width=ANCHO, height=ALTO)
    encabezado(pag)
    pag.insert_text((40, 125), "JUNTAS TORICAS - SURTIDO POR CAJA",
                    fontsize=14, fontname="hebo", color=AZUL)
    y = 155
    for fila in range(22):
        x = 40
        for col in range(4):
            pag.insert_text((x, y), f"JT-{200 + fila * 4 + col:03d}",
                            fontsize=7.5, fontname="helv")
            pag.insert_text((x + 55, y), precio(), fontsize=7.5, fontname="hebo")
            x += 130
        y += 22
    return pag


def portada(doc):
    pag = doc.new_page(width=ANCHO, height=ALTO)
    pag.draw_rect(fitz.Rect(0, 0, ANCHO, ALTO), color=AZUL, fill=AZUL)
    pag.insert_text((60, 320), "NORVAL", fontsize=54, fontname="hebo",
                    color=(1, 1, 1))
    pag.insert_text((62, 360), "SUMINISTROS INDUSTRIALES", fontsize=16,
                    fontname="helv", color=(0.75, 0.82, 0.92))
    pag.insert_text((62, 430), "CATALOGO GENERAL 2026", fontsize=20,
                    fontname="hebo", color=(1, 1, 1))
    pag.insert_text((62, 460), "Lista de precios - Edicion 8", fontsize=12,
                    fontname="helv", color=(0.75, 0.82, 0.92))
    pag.insert_text((62, 780), "Documento de demostracion - datos ficticios",
                    fontsize=8, fontname="helv", color=(0.55, 0.65, 0.8))
    return pag


def main():
    os.makedirs("demo", exist_ok=True)
    doc = fitz.open()
    portada(doc)
    pagina_tabla(doc, FAMILIAS[:2], "FIJACIONES - TORNILLERIA Y ARANDELAS")
    pagina_tabla(doc, FAMILIAS[2:], "ESTANQUEIDAD Y VALVULERIA")
    pagina_multicolumna(doc)
    doc.save(SALIDA)
    print(f"{SALIDA} -> {doc.page_count} paginas")


if __name__ == "__main__":
    main()
