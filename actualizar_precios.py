"""
Sube todos los precios de un catalogo PDF un porcentaje fijo, conservando
el diseno original, y borra la banda de marca del encabezado.

Dos problemas que no son obvios y que resuelve este script
----------------------------------------------------------

1. No todo numero con formato X,XX es un precio.
   En una tabla de suministro industrial las columnas de medida usan el
   mismo formato que el precio. Un `re.sub(r'\\d+,\\d{2}', ...)` sobre el
   texto de la pagina actualiza las medidas tambien, y el error es
   invisible: el PDF sigue pareciendo correcto.

   Solucion: agrupar las palabras de la pagina en lineas por su coordenada
   Y y, en cada linea, recorrer de derecha a izquierda y quedarse con el
   PRIMER numero que coincida. En una tabla de precios la columna de precio
   es la ultima de la fila, asi que el primero por la derecha es el precio.

   Excepcion: las paginas con layout multicolumna tienen varios precios por
   linea y ahi esa regla no sirve. Esas paginas se pasan por `--multicolumna`
   y se procesan buscando todas las coincidencias.

2. Tapar un texto con un rectangulo no lo elimina.
   `draw_rect` dibuja encima, pero el texto original sigue en la capa de
   texto del PDF: `pdftotext archivo.pdf -` lo devuelve entero. Un catalogo
   "actualizado" asi filtra los precios viejos a cualquiera que sepa
   seleccionar y copiar.

   Solucion: `add_redact_annot` + `apply_redactions`, que borran el texto
   del archivo, y recien despues escribir el precio nuevo.

Uso
---
    python actualizar_precios.py ENTRADA.pdf SALIDA.pdf --porcentaje 20
    python actualizar_precios.py cat.pdf out.pdf -p 20 --multicolumna 3
    python actualizar_precios.py cat.pdf out.pdf -p 20 --conservar-encabezado 0
"""
import argparse
import re

import pymupdf as fitz

NOMBRE_FUENTE = "helv"
TAMANO_FUENTE = 8
AJUSTE_VERTICAL_PRECIO = -2.0
COLOR_TEXTO = (0, 0, 0)
Y_LIMITE_ENCABEZADO = 91.0

RX_PALABRA = re.compile(r"^(\d+,\d{2})$")   # la palabra entera es un precio
RX_BLOQUE = re.compile(r"\b(\d+,\d{2})\b")  # cualquier precio dentro del texto


def detectar_precios(pagina, num_pagina, paginas_multicolumna):
    """Devuelve {'texto_precio': [Rect, ...]} con los precios de la pagina.

    Paginas multicolumna: busca todas las coincidencias del texto.
    Paginas de tabla: una sola por linea, la de mas a la derecha.
    """
    precios = {}

    palabras = pagina.get_text("words")
    if not palabras:
        return {}

    if num_pagina in paginas_multicolumna:
        # Todas las palabras que SEAN un precio, con su posicion exacta.
        #
        # El camino evidente aqui es `search_for(texto)`, pero busca
        # subcadenas: `search_for("9,87")` tambien matchea el "9,87" que
        # esta dentro de "19,87", redacta ese trozo y escribe encima. La
        # celda queda corrompida y a simple vista parece un precio valido.
        # Comparar palabras completas con el regex evita el problema.
        for palabra in palabras:
            if RX_PALABRA.match(palabra[4]):
                precios.setdefault(palabra[4], []).append(fitz.Rect(palabra[:4]))
        return precios

    # agrupar palabras en lineas por coordenada Y, con tolerancia
    lineas, tolerancia_y = {}, 2
    for p in palabras:
        y0 = p[1]
        clave = next((y for y in lineas if abs(y - y0) <= tolerancia_y), None)
        if clave is None:
            clave = y0
            lineas[clave] = []
        lineas[clave].append(p)

    # en cada linea, de derecha a izquierda, el primer precio y cortar
    for clave in sorted(lineas):
        for palabra in sorted(lineas[clave], key=lambda w: w[0])[::-1]:
            if RX_PALABRA.match(palabra[4]):
                precios.setdefault(palabra[4], []).append(fitz.Rect(palabra[:4]))
                break

    return precios


def color_de_fondo(pixmap, area, es_multicolumna):
    """Muestrea el color de fondo al lado del precio para que el parche no se vea."""
    if es_multicolumna:
        x, y = int(area.x0 + 2), max(0, int(area.y0 - 3))
    else:
        x, y = max(0, int(area.x0 - 3)), int(area.y0 + 2)
    x = min(x, pixmap.width - 1)
    y = min(y, pixmap.height - 1)
    rgb = pixmap.pixel(x, y)
    return (rgb[0] / 255, rgb[1] / 255, rgb[2] / 255)


def actualizar(entrada, salida, porcentaje, paginas_multicolumna,
               paginas_conservar_encabezado, quitar_encabezado=True):
    doc = fitz.open(entrada)
    multiplicador = 1 + porcentaje / 100
    total = 0

    for n, pagina in enumerate(doc):
        pixmap = pagina.get_pixmap(dpi=72)  # antes de modificar la pagina
        pendientes = []

        if quitar_encabezado and n not in paginas_conservar_encabezado:
            pagina.add_redact_annot(
                fitz.Rect(0, 0, pagina.rect.width, Y_LIMITE_ENCABEZADO),
                fill=(1, 1, 1))

        detectados = detectar_precios(pagina, n, paginas_multicolumna)
        for viejo, areas in detectados.items():
            nuevo = f"{float(viejo.replace(',', '.')) * multiplicador:.2f}"
            nuevo = nuevo.replace(".", ",")
            for area in areas:
                en_encabezado = (area.y1 < Y_LIMITE_ENCABEZADO
                                 and n not in paginas_conservar_encabezado)
                if quitar_encabezado and en_encabezado:
                    continue  # ese texto se va con el encabezado

                fondo = color_de_fondo(pixmap, area, n in paginas_multicolumna)
                rect = fitz.Rect(area.x0, area.y0 + AJUSTE_VERTICAL_PRECIO,
                                 area.x1 + 1, area.y1 + AJUSTE_VERTICAL_PRECIO)
                pagina.add_redact_annot(rect, fill=fondo)
                pendientes.append((rect, nuevo))

        # borra de verdad el texto viejo; despues escribe el nuevo
        pagina.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)
        for rect, nuevo in pendientes:
            pagina.insert_text(rect.bottom_left, nuevo,
                               fontsize=TAMANO_FUENTE, fontname=NOMBRE_FUENTE,
                               color=COLOR_TEXTO, render_mode=2)

        total += len(pendientes)
        print(f"  pagina {n + 1}: {len(pendientes)} precios")

    doc.save(salida, garbage=4, deflate=True)
    doc.close()
    print(f"\n{salida}  ({total} precios, +{porcentaje}%)")
    return total


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("entrada")
    ap.add_argument("salida")
    ap.add_argument("-p", "--porcentaje", type=float, default=20.0)
    ap.add_argument("--multicolumna", type=int, nargs="*", default=[],
                    help="indices (base 0) de paginas con varios precios por linea")
    ap.add_argument("--conservar-encabezado", type=int, nargs="*", default=[0],
                    help="indices (base 0) de paginas donde NO borrar el encabezado")
    ap.add_argument("--dejar-encabezado", action="store_true",
                    help="no borrar el encabezado en ninguna pagina")
    a = ap.parse_args()

    actualizar(a.entrada, a.salida, a.porcentaje, set(a.multicolumna),
               set(a.conservar_encabezado), not a.dejar_encabezado)


if __name__ == "__main__":
    main()
