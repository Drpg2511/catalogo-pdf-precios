# Actualizar precios en un catálogo PDF, sin rehacer el catálogo

Un distribuidor recibe la lista de precios de su proveedor en PDF y necesita
revenderla con su propio margen: los mismos productos, el mismo diseño, todos
los precios un porcentaje más arriba y sin la marca del proveedor.

Este repositorio resuelve eso y, sobre todo, **verifica que el resultado sea
correcto** sin tener que revisar el PDF página por página.

![Antes y después](demo/antes_despues.png)

---

## Por qué no es un buscar-y-reemplazar

Las dos cosas que hacen fallar la solución obvia no se ven hasta que el
archivo ya está entregado.

### 1. No todo número con formato `X,XX` es un precio

En una tabla de suministro industrial las columnas de medida usan exactamente
el mismo formato que el precio:

| CÓDIGO | DESCRIPCIÓN | LARGO | ANCHO | PRECIO |
|---|---|---|---|---|
| TN-1000 | TORNILLO HEXAGONAL DIN 933 M6 | 20,11 | 9,90 | **15,90** |

Un `re.sub(r'\d+,\d{2}', ...)` sobre el texto de la página sube el precio
**y también el largo y el ancho**. El PDF sigue pareciendo perfecto. El error
aparece cuando un cliente pide un tornillo de 24 mm y recibe uno de 20.

**Solución:** agrupar las palabras de la página en líneas por su coordenada Y
y, en cada línea, recorrer **de derecha a izquierda** quedándose con el primer
número que coincida. En una tabla de precios la columna de precio es la última
de la fila, así que el primero por la derecha es el precio y las medidas
quedan intactas.

En la demo, las páginas de tabla tienen 30 números con formato de precio y
solo 10 son precios. El script cambia 10 y deja 20 sin tocar.

### 2. Tapar un texto con un rectángulo no lo elimina

La forma natural de reemplazar un precio es dibujar un rectángulo del color
del fondo encima y escribir el valor nuevo. Visualmente queda perfecto.

Pero el texto original **sigue en la capa de texto del PDF**:

```bash
pdftotext catalogo_ACTUALIZADO.pdf -   # devuelve los precios viejos
```

Cualquiera que seleccione y copie, o que pase el archivo por un extractor,
recupera la lista de precios del proveedor y el margen aplicado. Para un
catálogo que se manda a clientes, eso es una fuga de datos.

**Solución:** `add_redact_annot()` + `apply_redactions()`, que eliminan el
texto del archivo, y recién después escribir el valor nuevo. Lo mismo para la
banda de marca del encabezado: no se tapa, se borra.

### 3. `search_for()` busca subcadenas

En las páginas con varios precios por línea no sirve la regla de
derecha-a-izquierda, así que hay que localizar cada precio por su texto. El
camino evidente es `page.search_for("9,87")` — pero eso **también encuentra el
`9,87` que está dentro de `19,87`**, redacta ese trozo y escribe encima. La
celda queda corrompida y el resultado sigue pareciendo un precio válido.

En la demo son 5 colisiones de 88 precios. Se resuelve comparando palabras
completas (`get_text("words")` + regex anclado) en vez de buscar subcadenas.

Este lo encontró la verificación automática, no la revisión visual.

---

## Verificación

`validar.py` compara el PDF de salida contra el original y comprueba cuatro
cosas:

| Comprobación | Qué detecta |
|---|---|
| Cada precio detectado, en su posición | que el valor nuevo sea exactamente el viejo × multiplicador |
| Los números que **no** eran precios | que las medidas no se hayan tocado |
| Cantidad de números por página, antes y después | que no se haya escrito un precio encima de otro texto |
| Cadenas de marca en la capa de texto | que la marca del proveedor esté eliminada, no tapada |

La tercera es la más barata y la que más errores atrapa: si una página tenía
88 números con formato de precio y la salida tiene 93, algo se escribió donde
no debía, aunque el PDF se vea bien.

```
--- PRECIOS ---
  detectados y reemplazados : 108
  correctos (+20% exacto)   : 108  (100.00%)

--- MEDIDAS Y OTROS NUMEROS ---
  numeros no-precio que desaparecieron: 0

--- FUGA DE DATOS EN LA CAPA DE TEXTO ---
  'NORVAL': ausente (ok)

--- CANTIDAD DE NUMEROS POR PAGINA (antes -> despues) ---
  pag   2:   30 ->   30   (10 reemplazados)
  pag   4:   88 ->   88   (88 reemplazados)

RESULTADO: TODO OK
```

**Limitación, dicha de frente:** el validador usa la misma función de
detección que el script que genera la salida, así que verifica el
*reemplazo*, no la *detección*. Que no se haya salteado ningún precio se
comprueba contando precios por página contra el original y revisando a ojo
una muestra.

---

## Correrlo

```bash
pip install pymupdf

python generar_catalogo_demo.py          # crea el catálogo sintético

python actualizar_precios.py \
    demo/catalogo_ORIGINAL.pdf demo/catalogo_ACTUALIZADO.pdf \
    -p 20 --multicolumna 3 --conservar-encabezado 0

python validar.py \
    demo/catalogo_ORIGINAL.pdf demo/catalogo_ACTUALIZADO.pdf \
    -p 20 --multicolumna 3 --conservar-encabezado 0 \
    --marcas NORVAL SUMINISTROS "LISTA DE PRECIOS"
```

| Opción | Para qué |
|---|---|
| `-p 20` | porcentaje de aumento |
| `--multicolumna 3` | páginas (base 0) con varios precios por línea |
| `--conservar-encabezado 0` | páginas donde **no** borrar la banda de marca |
| `--dejar-encabezado` | no borrar la marca en ninguna página |

---

## Escala real

El caso que originó esto fue un catálogo de **77 páginas y ~1.275 precios**.
El script lo procesa en segundos; hacerlo a mano en un editor de PDF son
varias horas de trabajo repetitivo, y cada corrección manual es una
oportunidad más de equivocarse en un número que después nadie revisa.

Más importante que el tiempo: la verificación automática encontró dos errores
—la fuga en la capa de texto y la colisión de subcadenas— que una revisión
visual no detecta, porque en los dos casos **el PDF se ve bien**.

---

## Archivos

| Archivo | Qué hace |
|---|---|
| `generar_catalogo_demo.py` | genera el catálogo sintético de prueba |
| `actualizar_precios.py` | detecta y reemplaza los precios, borra la marca |
| `validar.py` | verifica la salida contra el original |
| `demo/` | catálogo sintético, antes y después |

Stack: Python 3 y [PyMuPDF](https://pymupdf.readthedocs.io/). Sin
dependencias externas más allá de eso.

---

## Confidencialidad

El catálogo de este repositorio es **sintético**: la empresa, los códigos y
los precios son inventados y se generan con `generar_catalogo_demo.py`. Está
construido con la misma estructura que un catálogo comercial real —incluidas
las columnas de medida en formato de precio, que son la trampa— para poder
demostrar y verificar el funcionamiento sin publicar material de ningún
cliente.
