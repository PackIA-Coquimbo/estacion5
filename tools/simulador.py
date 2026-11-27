"""Simula E1-E4 y E6 para los contratos v3 de la API de E5."""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from datetime import datetime, timezone

import httpx

ESTADOS_CAPTURA = ["aceptada", "repetir", "revision"]
CALIDADES = ["alta", "media", "baja", "defectos_visibles", "revision"]
TAMANOS = ["pequeno", "mediano", "grande"]
CATEGORIAS = [
    "exportacion",
    "mercado_nacional",
    "proceso",
    "rechazo",
    "revision_manual",
]
ESTADOS_CINTA = ["normal", "detenida", "falla_mecanica"]
DEFECTOS = ["mancha_leve", "mancha_grave", "golpe", "deformacion", "herida_piel"]

CATEGORIA_POR_CALIDAD = {
    "alta": "exportacion",
    "media": "mercado_nacional",
    "baja": "proceso",
    "defectos_visibles": "rechazo",
    "revision": "revision_manual",
}

RETARDO_ENTRE_ESTACIONES = 2.0
RETARDO_ENTRE_FRUTAS = 3.0
HEARTBEAT_E6 = 10.0
RUTAS = {"E1": "e1", "E2": "e2", "E3": "e3", "E4": "e4", "E6": "e6"}


def ahora_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def tamano_para(diametro_mm: float, corte_mediano: float, corte_grande: float) -> str:
    if diametro_mm > corte_grande:
        return "grande"
    if diametro_mm >= corte_mediano:
        return "mediano"
    return "pequeno"


def generar_e1(rng: random.Random, id_lote: str, id_fruta: str) -> dict:
    validez = rng.random() > 0.03
    estado = rng.choices(ESTADOS_CAPTURA, weights=[92, 5, 3])[0] if validez else "repetir"
    return {
        "id_lote": id_lote,
        "id_fruta": id_fruta,
        "estacion": "E1",
        "timestamp": ahora_iso(),
        "datos": {
            "validez_imagen": validez,
            "estado_captura": estado,
            "posicion_correcta": rng.random() > 0.05,
        },
    }


def generar_e2(
    rng: random.Random, id_lote: str, id_fruta: str, baja_confianza: bool = False
) -> dict:
    calidad = rng.choices(CALIDADES, weights=[45, 30, 12, 8, 5])[0]
    confianza = (
        rng.uniform(0.40, 0.69)
        if baja_confianza and rng.random() < 0.4
        else rng.uniform(0.72, 0.99)
    )
    if calidad == "alta":
        defectos = []
    elif calidad == "defectos_visibles":
        defectos = rng.sample(DEFECTOS, k=rng.randint(1, 2))
    else:
        defectos = rng.sample(DEFECTOS[:1], k=rng.randint(0, 1))
    return {
        "id_lote": id_lote,
        "id_fruta": id_fruta,
        "estacion": "E2",
        "timestamp": ahora_iso(),
        "datos": {
            "calidad_visual": calidad,
            "confianza_visual": round(confianza, 2),
            "defectos_detectados": defectos,
        },
    }


def generar_e3(
    rng: random.Random,
    id_lote: str,
    id_fruta: str,
    corte_mediano: float,
    corte_grande: float,
) -> dict:
    centro = (corte_mediano + corte_grande) / 2
    dispersion = (corte_grande - corte_mediano) * 0.6
    diametro = round(min(80, max(50, rng.gauss(centro, dispersion))), 1)
    return {
        "id_lote": id_lote,
        "id_fruta": id_fruta,
        "estacion": "E3",
        "timestamp": ahora_iso(),
        "datos": {
            "diametro_mm": diametro,
            "tamano": tamano_para(diametro, corte_mediano, corte_grande),
        },
    }


def generar_e4(rng: random.Random, id_lote: str, e2: dict) -> dict:
    calidad = e2["datos"]["calidad_visual"]
    categoria = CATEGORIA_POR_CALIDAD[calidad]
    probabilidad = round(rng.uniform(0.60, 0.98), 2)
    return {
        "id_lote": id_lote,
        "id_fruta": e2["id_fruta"],
        "estacion": "E4",
        "timestamp": ahora_iso(),
        "datos": {
            "categoria_final": categoria,
            "probabilidad": probabilidad,
            "requiere_revision_manual": (
                categoria == "revision_manual" or probabilidad < 0.70
            ),
        },
    }


def generar_e6(
    id_lote: str, estado_cinta: str, id_fruta_en_cinta: str | None
) -> dict:
    datos = {
        "estado_cinta": estado_cinta,
        "falla_mecanica_detectada": estado_cinta == "falla_mecanica",
    }
    if id_fruta_en_cinta:
        datos["id_fruta_en_cinta"] = id_fruta_en_cinta
    return {
        "id_lote": id_lote,
        "estacion": "E6",
        "timestamp": ahora_iso(),
        "datos": datos,
    }


class Simulador:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.rng = random.Random(args.semilla)
        self.cliente = (
            None if args.dry_run else httpx.Client(base_url=args.url, timeout=5.0)
        )
        self.estado_cinta = "normal"
        self.fruta_en_cinta: str | None = None
        self.ultimo_e6 = 0.0
        self.enviados = 0
        self.errores = 0

    def enviar(self, mensaje: dict) -> None:
        for _ in range(2 if self.args.duplicados else 1):
            self._enviar_una_vez(mensaje)

    def _enviar_una_vez(self, mensaje: dict) -> None:
        estacion = mensaje["estacion"]
        etiqueta = f"{estacion} {mensaje.get('id_fruta', self.estado_cinta)}"
        if self.cliente is None:
            print(json.dumps(mensaje, ensure_ascii=False))
            self.enviados += 1
            return
        try:
            respuesta = self.cliente.post(
                f"/api/v1/ingest/{RUTAS[estacion]}", json=mensaje
            )
        except httpx.HTTPError as error:
            self.errores += 1
            print(f"[ERROR] {etiqueta}: no se pudo conectar ({error})", file=sys.stderr)
            return
        if respuesta.status_code in (200, 201):
            self.enviados += 1
            print(f"[{respuesta.status_code}] {etiqueta}")
        else:
            self.errores += 1
            print(
                f"[{respuesta.status_code}] {etiqueta}: {respuesta.text[:300]}",
                file=sys.stderr,
            )

    def enviar_e6(self) -> None:
        self.enviar(
            generar_e6(self.args.lote, self.estado_cinta, self.fruta_en_cinta)
        )
        self.ultimo_e6 = time.monotonic()

    def cambiar_cinta(self, estado: str) -> None:
        if estado != self.estado_cinta:
            self.estado_cinta = estado
            self.enviar_e6()

    def esperar(self, segundos: float) -> None:
        if self.args.dry_run:
            return
        fin = time.monotonic() + segundos / self.args.velocidad
        while True:
            restante = fin - time.monotonic()
            if time.monotonic() - self.ultimo_e6 >= HEARTBEAT_E6 / self.args.velocidad:
                self.enviar_e6()
            if restante <= 0:
                return
            time.sleep(min(restante, 0.5))

    def procesar_fruta(self, numero: int) -> None:
        id_fruta = f"M-{numero:04d}"
        self.fruta_en_cinta = id_fruta
        self.enviar(generar_e1(self.rng, self.args.lote, id_fruta))
        self.esperar(RETARDO_ENTRE_ESTACIONES)
        e2 = generar_e2(
            self.rng, self.args.lote, id_fruta, self.args.baja_confianza
        )
        self.enviar(e2)
        self.esperar(RETARDO_ENTRE_ESTACIONES)
        if not self.args.sin_e3:
            self.enviar(
                generar_e3(
                    self.rng,
                    self.args.lote,
                    id_fruta,
                    self.args.rangos[0],
                    self.args.rangos[1],
                )
            )
            self.esperar(RETARDO_ENTRE_ESTACIONES)
        self.enviar(generar_e4(self.rng, self.args.lote, e2))

    def correr(self) -> None:
        grupo_con_falla = max(2, self.args.frutas // 2) if self.args.frutas else 5
        self.enviar_e6()
        numero = self.args.inicio
        procesadas = 0
        while self.args.frutas == 0 or procesadas < self.args.frutas:
            if self.args.falla_cinta and procesadas + 1 == grupo_con_falla:
                print("--- simulando falla mecánica de la cinta ---", file=sys.stderr)
                self.cambiar_cinta("falla_mecanica")
                self.esperar(RETARDO_ENTRE_FRUTAS * 2)
                self.cambiar_cinta("detenida")
                self.esperar(RETARDO_ENTRE_FRUTAS)
                self.cambiar_cinta("normal")
            self.procesar_fruta(numero)
            numero += 1
            procesadas += 1
            if self.args.frutas == 0 or procesadas < self.args.frutas:
                self.esperar(RETARDO_ENTRE_FRUTAS)
        self.fruta_en_cinta = None
        self.enviar_e6()

    def cerrar(self) -> None:
        if self.cliente is not None:
            self.cliente.close()


def leer_rangos(texto: str) -> tuple[float, float]:
    try:
        mediano, grande = (float(valor) for valor in texto.split(","))
    except ValueError:
        raise argparse.ArgumentTypeError(
            "usa el formato MEDIANO,GRANDE, por ejemplo 60,70"
        )
    if not 0 < mediano < grande:
        raise argparse.ArgumentTypeError("debe cumplirse 0 < MEDIANO < GRANDE")
    return mediano, grande


def leer_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Simulador E1-E4 y E6 para los contratos v3 de E5."
    )
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--lote", default="LOTE-2026-11-A")
    parser.add_argument("--frutas", type=int, default=10, help="0 = sin fin")
    parser.add_argument("--inicio", type=int, default=1)
    parser.add_argument("--velocidad", type=float, default=1.0)
    parser.add_argument("--semilla", type=int, default=None)
    parser.add_argument(
        "--rangos",
        type=leer_rangos,
        default=(60.0, 70.0),
        metavar="MEDIANO,GRANDE",
        help="cortes de diámetro en mm (por defecto 60,70)",
    )
    parser.add_argument("--falla-cinta", action="store_true")
    parser.add_argument("--sin-e3", action="store_true")
    parser.add_argument("--baja-confianza", action="store_true")
    parser.add_argument("--duplicados", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.velocidad <= 0:
        parser.error("--velocidad debe ser mayor que 0")
    if args.frutas < 0:
        parser.error("--frutas no puede ser negativo")
    if args.inicio < 1:
        parser.error("--inicio debe ser mayor que 0")
    if args.frutas == 0 and args.dry_run:
        parser.error("--dry-run necesita una cantidad de frutas mayor que 0")
    return args


def main(argv: list[str] | None = None) -> int:
    for flujo in (sys.stdout, sys.stderr):
        if hasattr(flujo, "reconfigure"):
            flujo.reconfigure(encoding="utf-8")
    args = leer_args(argv)
    simulador = Simulador(args)
    try:
        simulador.correr()
    except KeyboardInterrupt:
        print("\nSimulación detenida por el usuario.", file=sys.stderr)
    finally:
        simulador.cerrar()
    print(
        f"Mensajes aceptados: {simulador.enviados} · con error: {simulador.errores}",
        file=sys.stderr,
    )
    return 1 if simulador.errores else 0


if __name__ == "__main__":
    sys.exit(main())
