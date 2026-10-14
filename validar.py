"""
Verifica el PDF de salida contra el original, sin abrirlos a mano.

Tres comprobaciones:

1. PRECIOS. Vuelve a detectar los precios del original y, por cada uno,
   busca en el PDF nuevo la palabra que quedo en esa misma posicion.
   Tiene que ser exactamente el valor viejo por el multiplicador.

2. MEDIDAS Y OTROS NUMEROS. Todo numero del original que NO fue
   identificado como precio tiene que seguir en el texto del PDF nuevo,
   sin cambios. Esto es lo que detecta el error silencioso de actualizar
   una columna de medida por error.

3. FUGA DE DATOS. Las cadenas de marca que habia que eliminar no pueden
   aparecer en la capa de texto del PDF nuevo. Un rectangulo encima no
   borra el texto, y esta comprobacion lo delata.

Limitacion honesta: usa la misma funcion de deteccion que el script que
genera la salida, asi que verifica el REEMPLAZO, no la DETECCION. Que no
se haya salteado ningun precio se comprueba aparte, contando precios por
pagina contra el original.

Uso
---
    python validar.py ORIGINAL.pdf NUEVO.pdf -p 20
    python validar.py o.pdf n.pdf -p 20 --multicolumna 3 --marcas NORVAL EDICION
"""
import argparse
import re

import pymupdf as fitz

from actualizar_precios import (RX_BLOQUE, Y_LIMITE_ENCABEZADO,
                                detectar_precios)

TOLERANCIA_Y = 8   # puntos: cuanto puede moverse el texto en vertical
TOLERANCIA_X = 12  # puntos: idem horizontal

a_float = lambda s: float(s.replace(",", "."))
a_texto = lambda v: f"{v:.2f}".replace(".", ",")


def validar(ruta_orig, ruta_nuevo, porcentaje, multicolumna, conservar, marcas):
    orig = fitz.open(ruta_orig)
    nuevo = fitz.open(ruta_nuevo)
    mult = 1 + porcentaje / 100

    if orig.page_count != nuevo.page_count:
        print(f"ATENCION: {orig.page_count} paginas vs {nuevo.page_count}")

    total = correctos = distintos = sin_texto = 0
    medidas_alteradas = 0
    errores = []
    por_pagina = []

    for n in range(min(orig.page_count, nuevo.page_count)):
        pag_o, pag_n = orig[n], nuevo[n]
        detectados = detectar_precios(pag_o, n, multicolumna)

        # palabras numericas del PDF nuevo, con su posicion
        rx = re.compile(r"^(\d+,\d{2})$")
        nums_nuevo = [(fitz.Rect(w[:4]), w[4]) for w in pag_n.get_text("words")
                      if rx.match(w[4])]

        esperados = []
        for viejo, areas in detectados.items():
            valor_nuevo = a_texto(a_float(viejo) * mult)
            for area in areas:
                if area.y1 < Y_LIMITE_ENCABEZADO and n not in conservar:
                    continue  # se fue con el encabezado
                esperados.append((area, viejo, valor_nuevo))

        for area, viejo, valor_nuevo in esperados:
            total += 1
            candidatos = [(abs(r.x0 - area.x0) + abs(r.y1 - area.y1), t)
                          for r, t in nums_nuevo
                          if abs(r.y1 - area.y1) < TOLERANCIA_Y
                          and abs(r.x0 - area.x0) < TOLERANCIA_X]
            if not candidatos:
                sin_texto += 1
                if len(errores) < 10:
                    errores.append((n + 1, viejo, valor_nuevo,
                                    "no hay texto en esa posicion"))
                continue
            candidatos.sort()
            hallado = candidatos[0][1]
            if hallado == valor_nuevo:
                correctos += 1
            else:
                distintos += 1
                if len(errores) < 10:
                    errores.append((n + 1, viejo, valor_nuevo,
                                    f"encontrado {hallado}"))

        # medidas: los numeros que NO eran precios deben seguir intactos
        texto_nuevo = pag_n.get_text("text")
        no_precios = set(RX_BLOQUE.findall(pag_o.get_text("text"))) - set(detectados)
        faltantes = [m for m in no_precios if m not in texto_nuevo]
        medidas_alteradas += len(faltantes)

        # invariante barata y muy efectiva: la cantidad de numeros con formato
        # X,XX tiene que ser la MISMA antes y despues. Si sube, se escribio un
        # precio encima de otro texto; si baja, se perdio algo.
        cuenta_o = len([w for w in pag_o.get_text("words") if rx.match(w[4])])
        cuenta_n = len(nums_nuevo)
        por_pagina.append((n + 1, len(esperados), len(faltantes),
                           cuenta_o, cuenta_n))

    print(f"\nPaginas: {orig.page_count}")
    print("\n--- PRECIOS ---")
    print(f"  detectados y reemplazados : {total}")
    if total:
        print(f"  correctos (+{porcentaje:g}% exacto) : {correctos}"
              f"  ({correctos / total * 100:.2f}%)")
    print(f"  con otro valor            : {distintos}")
    print(f"  sin texto en su posicion  : {sin_texto}")
    if errores:
        print("\n  primeros casos a revisar:")
        for pag, viejo, esp, msg in errores:
            print(f"    pag {pag:>3}  {viejo} -> esperaba {esp}  ({msg})")

    print("\n--- MEDIDAS Y OTROS NUMEROS ---")
    print(f"  numeros no-precio que desaparecieron: {medidas_alteradas}")

    print("\n--- FUGA DE DATOS EN LA CAPA DE TEXTO ---")
    # solo en las paginas donde SI se quito el encabezado: en las conservadas
    # (portada, por ejemplo) la marca tiene que seguir ahi
    todo = "\n".join(nuevo[i].get_text("text")
                     for i in range(nuevo.page_count)
                     if i not in conservar).upper()
    print(f"  (revisadas {nuevo.page_count - len(conservar)} paginas; "
          f"{len(conservar)} conservan el encabezado a proposito)")
    fugas = 0
    for marca in marcas:
        presente = marca.upper() in todo
        fugas += presente
        print(f"  '{marca}': {'PRESENTE (mal)' if presente else 'ausente (ok)'}")

    print("\n--- CANTIDAD DE NUMEROS POR PAGINA (antes -> despues) ---")
    descuadres = 0
    for pag, cuantos, faltan, cuenta_o, cuenta_n in por_pagina:
        avisos = []
        if faltan:
            avisos.append(f"{faltan} numeros desaparecidos")
        if cuenta_o != cuenta_n:
            descuadres += 1
            avisos.append(f"DESCUADRE {cuenta_o} -> {cuenta_n}")
        extra = ("   <- " + "; ".join(avisos)) if avisos else ""
        print(f"  pag {pag:>3}: {cuenta_o:>4} -> {cuenta_n:>4}"
              f"   ({cuantos} reemplazados){extra}")
    if descuadres:
        print(f"\n  {descuadres} pagina(s) con descuadre: se escribio un precio"
              f" encima de otro texto, o se perdio un numero.")

    ok = (distintos == 0 and sin_texto == 0 and medidas_alteradas == 0
          and fugas == 0 and descuadres == 0)
    print(f"\nRESULTADO: {'TODO OK' if ok else 'HAY QUE REVISAR'}")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("original")
    ap.add_argument("nuevo")
    ap.add_argument("-p", "--porcentaje", type=float, default=20.0)
    ap.add_argument("--multicolumna", type=int, nargs="*", default=[])
    ap.add_argument("--conservar-encabezado", type=int, nargs="*", default=[0])
    ap.add_argument("--marcas", nargs="*", default=[],
                    help="cadenas que NO deben aparecer en el PDF nuevo")
    a = ap.parse_args()
    raise SystemExit(validar(a.original, a.nuevo, a.porcentaje,
                             set(a.multicolumna), set(a.conservar_encabezado),
                             a.marcas))


if __name__ == "__main__":
    main()
