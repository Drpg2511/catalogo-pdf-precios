"""
Genera demo/antes_despues.png, la imagen del README: la misma tabla antes y
despues de actualizar los precios, una debajo de la otra.

La imagen se arma como pagina vectorial (show_pdf_page) y se rasteriza al
final, asi el texto queda nitido. Ancho maximo 900 px: GitHub muestra las
imagenes a ~870 px y a ese tamano el texto de la tabla queda en ~13 px.

Uso:  python generar_imagen_demo.py
      (despues de generar_catalogo_demo.py y actualizar_precios.py)
"""
import os

import pymupdf as fitz

ORIGINAL = os.path.join("demo", "catalogo_ORIGINAL.pdf")
ACTUALIZADO = os.path.join("demo", "catalogo_ACTUALIZADO.pdf")
SALIDA = os.path.join("demo", "antes_despues.png")

ANCHO_MAX_PX = 900
PAGINA = 1                                  # pagina de tabla (base 0)
RECORTE = fitz.Rect(36, 146, 559, 264)      # encabezado de la tabla + 5 filas
COLUMNA_PRECIO = fitz.Rect(458, 148, 557, 262)
MARGEN = 14
ALTO_TITULO = 34

AZUL = (0.09, 0.22, 0.39)
GRIS = (0.4, 0.45, 0.5)
NARANJA = (0.9, 0.45, 0.1)


def bloque(pag, y, fuente, titulo, subtitulo):
    """Titulo + recorte de la tabla a partir de la altura y. Devuelve la y final."""
    pag.insert_text((MARGEN, y + 15), titulo, fontsize=13, fontname="hebo",
                    color=AZUL)
    pag.insert_text((MARGEN, y + 28), subtitulo, fontsize=9, fontname="helv",
                    color=GRIS)
    y += ALTO_TITULO
    destino = fitz.Rect(MARGEN, y, MARGEN + RECORTE.width, y + RECORTE.height)
    with fitz.open(fuente) as doc:
        pag.show_pdf_page(destino, doc, PAGINA, clip=RECORTE)
    # resaltar la columna de precio, en coordenadas de la imagen
    resaltado = fitz.Rect(COLUMNA_PRECIO.x0 - RECORTE.x0 + MARGEN,
                          COLUMNA_PRECIO.y0 - RECORTE.y0 + y,
                          COLUMNA_PRECIO.x1 - RECORTE.x0 + MARGEN,
                          COLUMNA_PRECIO.y1 - RECORTE.y0 + y)
    pag.draw_rect(resaltado, color=NARANJA, width=1.5)
    return y + RECORTE.height


def main():
    ancho = RECORTE.width + 2 * MARGEN
    alto = 2 * (ALTO_TITULO + RECORTE.height) + 3 * MARGEN
    doc = fitz.open()
    pag = doc.new_page(width=ancho, height=alto)

    y = bloque(pag, MARGEN, ORIGINAL, "ANTES",
               "precio original  ·  LARGO y ANCHO tienen el mismo formato")
    bloque(pag, y + MARGEN, ACTUALIZADO, "DESPUÉS (+20 %)",
           "solo cambia PRECIO  ·  LARGO y ANCHO intactos")

    zoom = ANCHO_MAX_PX / ancho
    pix = pag.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
    while pix.width > ANCHO_MAX_PX:  # el redondeo puede sumar un pixel
        zoom *= (ANCHO_MAX_PX - 0.5) / pix.width
        pix = pag.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
    pix.save(SALIDA)
    print(f"{SALIDA} -> {pix.width} x {pix.height} px")


if __name__ == "__main__":
    main()
