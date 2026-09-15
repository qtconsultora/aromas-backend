"""
Deja Viandas a la Carta (7000-7046) y Cat. Aromas / Catering (4000-4037)
listos para venderse por el carrito de compras (15/09/2026):

1. Carga los precios reales de Catering desde `productos_catering.xlsx`
   (fuente: `precios_catering_aromas.json`, ya con los códigos definitivos
   4000-4037) -- estos 38 artículos habían quedado todos en precio_venta=0
   porque `Catalogo_Productos_BORRADOR.docx` (la fuente que usó
   `cargar_catering_aromas`) tenía la columna Precio en blanco a propósito;
   los precios reales sólo estaban en la otra planilla.
   Sólo pisa el precio de un artículo si sigue en su estado "sin tocar"
   (precio_venta=0 y requiere_consulta=False) -- si Pichón ya le cambió el
   precio a mano desde el admin, este comando no lo toca.
   A la carta (7000-7046) NO se toca acá: ya tenían precio real ($9500,
   "PRECIOS.aLaCarta" del sitio viejo) desde `cargar_catalogo_real`.

2. Marca visible_web=True en los artículos activos de ambos rangos, para
   que aparezcan en el catálogo público (GET /api/catalogo/articulos/) y
   se puedan agregar al carrito por su código sabiendo que existen.

Idempotente: se puede volver a correr sin duplicar ni pisar nada que ya
esté bien.

Uso:
    python manage.py activar_alacarta_catering_web
"""

import json
from decimal import Decimal
from pathlib import Path

from django.core.management.base import BaseCommand

from catalogo.models import Articulo

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "fixtures_source"
PRECIOS_CATERING = FIXTURES_DIR / "precios_catering_aromas.json"


class Command(BaseCommand):
    help = "Carga precios reales de Catering y publica (visible_web=True) Catering + A la Carta para el carrito"

    def handle(self, *args, **options):
        self._cargar_precios_catering()
        self._activar_visible_web()
        self.stdout.write(self.style.SUCCESS("Catering + A la Carta listos para el carrito."))

    def _cargar_precios_catering(self):
        if not PRECIOS_CATERING.exists():
            self.stderr.write(self.style.ERROR(f"No encontré {PRECIOS_CATERING}"))
            return

        data = json.loads(PRECIOS_CATERING.read_text(encoding="utf-8"))
        actualizados, saltados, no_encontrados = 0, 0, []

        for item in data:
            art = Articulo.objects.filter(codigo=item["codigo"]).first()
            if not art:
                no_encontrados.append(item["codigo"])
                continue

            ya_tocado = art.precio_venta != 0 or art.requiere_consulta
            if ya_tocado:
                saltados += 1
                continue

            if item["consultar"]:
                art.requiere_consulta = True
                art.precio_venta = Decimal("0")
            else:
                art.precio_venta = Decimal(str(item["precio"]))
            art.save(update_fields=["precio_venta", "requiere_consulta"])
            actualizados += 1
            self.stdout.write(f"  [{art.codigo}] {art.nombre}: ${art.precio_venta}" + (" (a consultar)" if item["consultar"] else ""))

        self.stdout.write(f"Precios de catering: {actualizados} actualizados, {saltados} ya tenían precio propio (no tocados)")
        if no_encontrados:
            self.stdout.write(self.style.WARNING(f"No encontré artículo para códigos: {no_encontrados}"))

    def _activar_visible_web(self):
        qs = Articulo.objects.filter(
            codigo__regex=r"^(70[0-4][0-9]|40[0-3][0-9])$", activo=True
        ).exclude(visible_web=True)
        n = qs.update(visible_web=True)
        self.stdout.write(f"visible_web activado en {n} artículos (a la carta + catering).")
