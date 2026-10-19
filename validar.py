"""
Verifica el PDF de salida contra el original, sin abrirlos a mano.

No importa nada de actualizar_precios.py: todo sale de comparar los dos PDF
palabra por palabra. Asi, un error en la deteccion del script no se contagia
al validador.

Cada numero con formato X,XX del original se busca en la misma posicion del
PDF nuevo y se clasifica: sigue IGUAL, quedo multiplicado (X_MULT), cambio a
OTRO valor, o esta AUSENTE. Sobre esa clasificacion se hacen cinco
comprobaciones:

1. PRECIOS. En las paginas de tabla, el precio es el ultimo numero de cada
   linea y tiene que ser exactamente el viejo por el multiplicador. Si sigue
   igual, es un precio salteado. En las paginas multicolumna todos los
   numeros son precios.

2. MEDIDAS. En las paginas de tabla, el resto de los numeros de la linea
   tienen que seguir iguales. Si cambio alguno, se toco una medida.

3. MULTICOLUMNA SIN MARCAR. Si en una pagina de tabla una linea alterna
   codigo y precio (entre dos numeros hay una palabra con digitos, como
   "JT-201"), probablemente es una pagina multicolumna que no se paso por
   --multicolumna, y solo se actualizo el ultimo precio de cada linea.
   Es una heuristica.

4. CANTIDAD DE NUMEROS POR PAGINA. Tiene que ser la misma antes y despues.
   Si sube, se escribio un precio encima de otro texto; si baja, se perdio
   algo.

5. FUGA DE DATOS. Las cadenas de marca que habia que eliminar no pueden
   aparecer en la capa de texto del PDF nuevo.

Supuesto compartido con el script: en una pagina de tabla el precio es el
ultimo numero con formato X,XX de la linea. El validador lo implementa por su
cuenta y lo contrasta con el resultado, pero si el supuesto no vale para un
catalogo (por ejemplo, precios "1.234,56" que el patron no reconoce), los dos
se equivocan igual.

Uso
---
    python validar.py ORIGINAL.pdf NUEVO.pdf -p 20
    python validar.py o.pdf n.pdf -p 20 --multicolumna 3 --marcas NORVAL EDICION
"""
import argparse
import re
from decimal import ROUND_HALF_UP, Decimal

import pymupdf as fitz

RX_NUMERO = re.compile(r"^\d+,\d{2}$")
RX_DIGITO = re.compile(r"\d")

TOLERANCIA_LINEA = 3  # puntos: palabras con el centro a esta distancia, misma linea
TOLERANCIA_Y = 8      # puntos: cuanto puede moverse el texto en vertical
TOLERANCIA_X = 12     # puntos: idem horizontal

IGUAL, X_MULT, OTRO, AUSENTE = "igual", "x_mult", "otro", "ausente"


def a_texto(valor):
    return str(valor.quantize(Decimal("0.01"), ROUND_HALF_UP)).replace(".", ",")


def esperado(viejo, mult):
    return a_texto(Decimal(viejo.replace(",", ".")) * mult)


def es_numero(palabra):
    return bool(RX_NUMERO.match(palabra[4]))


def agrupar_lineas(palabras):
    """Agrupa palabras en lineas por su centro vertical; cada linea, de izquierda a derecha."""
    lineas = []  # [(centro de la primera palabra, [palabras])]
    for p in sorted(palabras, key=lambda w: (w[1] + w[3]) / 2):
        centro = (p[1] + p[3]) / 2
        if lineas and abs(lineas[-1][0] - centro) <= TOLERANCIA_LINEA:
            lineas[-1][1].append(p)
        else:
            lineas.append((centro, [p]))
    return [sorted(ps, key=lambda w: w[0]) for _, ps in lineas]


def emparejar(nums_o, nums_n):
    """{palabra del original: texto en su posicion del nuevo}, uno a uno, el mas cercano primero."""
    pares = []
    for o in nums_o:
        for j, n in enumerate(nums_n):
            dx, dy = abs(n[0] - o[0]), abs(n[3] - o[3])
            if dx < TOLERANCIA_X and dy < TOLERANCIA_Y:
                pares.append((dx + dy, o, j))
    hallados, usados = {}, set()
    for _, o, j in sorted(pares, key=lambda par: par[0]):
        if o not in hallados and j not in usados:
            hallados[o] = nums_n[j][4]
            usados.add(j)
    return hallados


def clasificar(viejo, hallado, mult):
    if hallado is None:
        return AUSENTE
    if hallado == viejo:
        return IGUAL
    if hallado == esperado(viejo, mult):
        return X_MULT
    return OTRO


def validar(ruta_orig, ruta_nuevo, porcentaje, multicolumna, conservar, marcas,
            alto_encabezado=91.0):
    orig = fitz.open(ruta_orig)
    nuevo = fitz.open(ruta_nuevo)
    mult = 1 + porcentaje / 100

    mismas_paginas = orig.page_count == nuevo.page_count
    if not mismas_paginas:
        print(f"ATENCION: {orig.page_count} paginas vs {nuevo.page_count}")

    precios = correctos = salteados = distintos = sin_texto = 0
    medidas = medidas_modificadas = 0
    sospechosas = 0
    casos = []
    por_pagina = []

    def caso(pag, motivo):
        if len(casos) < 10:
            casos.append(f"pag {pag:>3}  {motivo}")

    for n in range(min(orig.page_count, nuevo.page_count)):
        quita_encabezado = n not in conservar

        def en_encabezado(w):
            return quita_encabezado and w[3] < alto_encabezado

        palabras_o = orig[n].get_text("words")
        eliminados = sum(1 for w in palabras_o if es_numero(w) and en_encabezado(w))
        palabras_o = [w for w in palabras_o if not en_encabezado(w)]
        nums_o = [w for w in palabras_o if es_numero(w)]
        nums_n = [w for w in nuevo[n].get_text("words") if es_numero(w)]

        hallados = emparejar(nums_o, nums_n)
        estado = {w: clasificar(w[4], hallados.get(w), mult) for w in nums_o}

        def revisar_precio(w):
            nonlocal precios, correctos, salteados, distintos, sin_texto
            precios += 1
            viejo, esp = w[4], esperado(w[4], mult)
            if estado[w] == X_MULT:
                correctos += 1
            elif estado[w] == IGUAL:
                salteados += 1
                caso(n + 1, f"precio salteado: {viejo} sigue igual, esperaba {esp}")
            elif estado[w] == OTRO:
                distintos += 1
                caso(n + 1, f"precio {viejo} -> {hallados[w]}, esperaba {esp}")
            else:
                sin_texto += 1
                caso(n + 1, f"precio {viejo}: no hay texto en su posicion")

        def revisar_medida(w):
            nonlocal medidas, medidas_modificadas
            medidas += 1
            if estado[w] == IGUAL:
                return
            medidas_modificadas += 1
            if estado[w] == X_MULT:
                caso(n + 1, f"medida {w[4]} tratada como precio -> {hallados[w]}")
            elif estado[w] == OTRO:
                caso(n + 1, f"medida {w[4]} cambio a {hallados[w]}")
            else:
                caso(n + 1, f"medida {w[4]}: no hay texto en su posicion")

        precios_antes = precios
        if n in multicolumna:
            for w in nums_o:
                revisar_precio(w)
        else:
            for linea in agrupar_lineas(palabras_o):
                indices = [k for k, w in enumerate(linea) if es_numero(w)]
                if not indices:
                    continue
                *otros, ultimo = indices
                revisar_precio(linea[ultimo])
                for k in otros:
                    revisar_medida(linea[k])
                # una palabra con digitos entre dos numeros: codigo-precio-codigo-precio
                entre = [w for a, b in zip(indices, indices[1:])
                         for w in linea[a + 1:b] if RX_DIGITO.search(w[4])]
                if entre:
                    sospechosas += 1
                    caso(n + 1, f"linea con codigos entre precios ({entre[0][4]}...):"
                                f" pagina multicolumna sin --multicolumna?")

        por_pagina.append((n + 1, precios - precios_antes, len(nums_o),
                           len(nums_n), eliminados))

    print(f"\nPaginas: {orig.page_count}")

    print("\n--- PRECIOS ---")
    print(f"  esperados                   : {precios}")
    if precios:
        print(f"  {f'correctos (+{porcentaje:g}% exacto)':<28}: {correctos}"
              f"  ({correctos / precios * 100:.2f}%)")
    print(f"  salteados (siguen iguales)  : {salteados}")
    print(f"  con otro valor              : {distintos}")
    print(f"  sin texto en su posicion    : {sin_texto}")

    print("\n--- MEDIDAS Y OTROS NUMEROS (paginas de tabla) ---")
    print(f"  numeros que no son precio   : {medidas}")
    print(f"  modificados                 : {medidas_modificadas}")

    print("\n--- LINEAS DE TABLA QUE PARECEN MULTICOLUMNA ---")
    print(f"  lineas sospechosas          : {sospechosas}")

    print("\n--- FUGA DE DATOS EN LA CAPA DE TEXTO ---")
    # solo en las paginas donde SI se quito el encabezado: en las conservadas
    # (portada, por ejemplo) la marca tiene que seguir ahi
    revisadas = [i for i in range(nuevo.page_count) if i not in conservar]
    todo = "\n".join(nuevo[i].get_text("text") for i in revisadas).upper()
    print(f"  (revisadas {len(revisadas)} paginas; "
          f"{nuevo.page_count - len(revisadas)} conservan el encabezado a proposito)")
    fugas = 0
    for marca in marcas:
        presente = marca.upper() in todo
        fugas += presente
        print(f"  '{marca}': {'PRESENTE (mal)' if presente else 'ausente (ok)'}")

    print("\n--- CANTIDAD DE NUMEROS POR PAGINA (antes -> despues) ---")
    descuadres = 0
    for pag, cuantos, cuenta_o, cuenta_n, eliminados in por_pagina:
        avisos = []
        if eliminados:
            avisos.append(f"{eliminados} eliminados con el encabezado")
        if cuenta_o != cuenta_n:
            descuadres += 1
            avisos.append(f"DESCUADRE {cuenta_o} -> {cuenta_n}")
        extra = ("   <- " + "; ".join(avisos)) if avisos else ""
        print(f"  pag {pag:>3}: {cuenta_o:>4} -> {cuenta_n:>4}"
              f"   ({cuantos} precios){extra}")
    if descuadres:
        print(f"\n  {descuadres} pagina(s) con descuadre: se escribio un precio"
              f" encima de otro texto, o se perdio un numero.")

    if casos:
        print("\n--- PRIMEROS CASOS A REVISAR ---")
        for c in casos:
            print(f"  {c}")

    ok = (mismas_paginas and salteados == 0 and distintos == 0 and sin_texto == 0
          and medidas_modificadas == 0 and sospechosas == 0 and fugas == 0
          and descuadres == 0)
    print(f"\nRESULTADO: {'TODO OK' if ok else 'HAY QUE REVISAR'}")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("original")
    ap.add_argument("nuevo")
    ap.add_argument("-p", "--porcentaje", type=Decimal, default=Decimal(20))
    ap.add_argument("--multicolumna", type=int, nargs="*", default=[],
                    help="indices (base 0) de paginas con varios precios por linea")
    ap.add_argument("--conservar-encabezado", type=int, nargs="*", default=[0],
                    help="indices (base 0) de paginas donde NO se borro el encabezado")
    ap.add_argument("--alto-encabezado", type=float, default=91.0,
                    help="alto en puntos de la banda de encabezado que se borro")
    ap.add_argument("--marcas", nargs="*", default=[],
                    help="cadenas que NO deben aparecer en el PDF nuevo")
    a = ap.parse_args()
    raise SystemExit(validar(a.original, a.nuevo, a.porcentaje,
                             set(a.multicolumna), set(a.conservar_encabezado),
                             a.marcas, a.alto_encabezado))


if __name__ == "__main__":
    main()
