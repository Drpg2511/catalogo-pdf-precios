"""
Pruebas de que validar.py detecta los errores que dice detectar.

Cada prueba genera el catalogo demo en una carpeta temporal, produce una
salida (correcta o saboteada) y corre validar.py como lo correria un usuario.
Una salida saboteada tiene que hacer fallar la validacion.

    python pruebas/test_sabotajes.py      # sin dependencias extra
    python -m pytest pruebas/             # si hay pytest instalado
"""
import contextlib
import io
import subprocess
import sys
import tempfile
from pathlib import Path

import pymupdf as fitz

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import actualizar_precios  # noqa: E402

ARGS_VALIDAR = ["-p", "20", "--conservar-encabezado", "0",
                "--marcas", "NORVAL", "SUMINISTROS", "LISTA DE PRECIOS"]


@contextlib.contextmanager
def catalogo_demo():
    """Genera el catalogo demo en una carpeta temporal: (original, salida)."""
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run([sys.executable, str(RAIZ / "generar_catalogo_demo.py")],
                       cwd=tmp, check=True, capture_output=True)
        demo = Path(tmp) / "demo"
        yield demo / "catalogo_ORIGINAL.pdf", demo / "salida.pdf"


def actualizar(original, salida, multicolumna):
    with contextlib.redirect_stdout(io.StringIO()):
        actualizar_precios.actualizar(str(original), str(salida), 20,
                                      set(multicolumna), {0})


def validar(original, salida, *extra):
    r = subprocess.run([sys.executable, str(RAIZ / "validar.py"),
                        str(original), str(salida), *ARGS_VALIDAR, *extra],
                       capture_output=True, text=True)
    return r.returncode, r.stdout


def resumen(salida):
    """El RESULTADO y los primeros casos, para ver que detecto el validador."""
    lineas = salida.splitlines()
    titulo = "--- PRIMEROS CASOS A REVISAR ---"
    casos = []
    if titulo in lineas:
        i = lineas.index(titulo)
        casos = [l.strip() for l in lineas[i + 1:i + 4] if l.strip()]
    casos += [l for l in lineas if l.startswith("RESULTADO")]
    return "\n".join("    " + l for l in casos)


def detectar_todo(pagina, num_pagina, paginas_multicolumna):
    """Sabotaje: sin la regla derecha-a-izquierda, todo numero X,XX es precio."""
    precios = {}
    for w in pagina.get_text("words"):
        if actualizar_precios.RX_PALABRA.match(w[4]):
            precios.setdefault(w[4], []).append(fitz.Rect(w[:4]))
    return precios


def test_control():
    """Sin sabotaje, la demo tiene que pasar."""
    with catalogo_demo() as (original, salida):
        actualizar(original, salida, multicolumna={3})
        codigo, texto = validar(original, salida, "--multicolumna", "3")
    print(resumen(texto))
    assert codigo == 0, texto
    assert "RESULTADO: TODO OK" in texto, texto


def test_sabotaje_derecha_a_izquierda():
    """Las medidas actualizadas como si fueran precios tienen que detectarse."""
    original_detectar = actualizar_precios.detectar_precios
    actualizar_precios.detectar_precios = detectar_todo
    try:
        with catalogo_demo() as (original, salida):
            actualizar(original, salida, multicolumna={3})
            codigo, texto = validar(original, salida, "--multicolumna", "3")
    finally:
        actualizar_precios.detectar_precios = original_detectar
    print(resumen(texto))
    assert codigo == 1, texto
    assert "medida" in texto and "tratada como precio" in texto, texto


def test_sin_multicolumna():
    """Olvidar --multicolumna (en los dos comandos) tiene que detectarse."""
    with catalogo_demo() as (original, salida):
        actualizar(original, salida, multicolumna=set())
        codigo, texto = validar(original, salida)
    print(resumen(texto))
    assert codigo == 1, texto
    assert "multicolumna" in texto, texto


if __name__ == "__main__":
    fallos = 0
    for prueba in (test_control, test_sabotaje_derecha_a_izquierda,
                   test_sin_multicolumna):
        print(f"\n{prueba.__name__}: {prueba.__doc__}")
        try:
            prueba()
            print("  -> ok")
        except AssertionError as e:
            fallos += 1
            print(f"  -> FALLA\n{e}")
    print(f"\n{3 - fallos} de 3 pruebas pasaron")
    raise SystemExit(1 if fallos else 0)
