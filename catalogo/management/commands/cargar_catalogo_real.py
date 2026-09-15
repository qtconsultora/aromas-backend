"""
Carga el catálogo real de Aromas (platos a la carta + menú semanal 1000-1014
+ bebidas + opciones de catering) a partir de los archivos que ya existen en
la carpeta del proyecto (data.js del sitio de viandas y productos_catering.xlsx),
creando Articulo (el modelo unificado, tipo ELABORADO/VENTA según corresponda).

Sirve para:
1) Validar que el esquema de la base de datos funciona con datos reales.
2) Dejar el catálogo ya cargado como punto de partida del panel admin.

IMPORTANTE sobre recetas: estos artículos se cargan con tipo=ELABORADO (los
platos) o VENTA (bebidas/catering suelto), pero SIN ítems de Receta —
el catálogo viejo sólo tenía el texto libre de ingredientes (se guarda en
`ingredientes_texto` como referencia), no cantidades reales por insumo. El
costeo real (costo_receta) va a dar $0 hasta que se carguen los insumos con
cantidad desde el admin, artículo por artículo.

Uso:
    python manage.py cargar_catalogo_real
    python manage.py cargar_catalogo_real --borrar-antes   # limpia el catálogo antes de recargar
"""

import json
import re
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from catalogo.models import (
    Articulo,
    Categoria,
    LineaNegocio,
    MenuSemanal,
    OpcionMenuDia,
    TipoArticulo,
    Unidad,
)

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "fixtures_source"

DIA_JS_A_CODIGO = {
    "Lunes": "LUN",
    "Martes": "MAR",
    "Miércoles": "MIE",
    "Jueves": "JUE",
    "Viernes": "VIE",
}

# El pool exclusivo del menú semanal (códigos 1000+) no trae categoría propia
# en data.js (todos figuran como "MENÚ SEMANAL"). Para que las reglas de
# negocio (reglas_eleccion_menus.md) se puedan chequear de verdad, se
# reclasifica cada plato según a cuál de las categorías del catálogo "a la
# carta" corresponde por su contenido real.
CATEGORIA_REAL_MENU_SEMANAL = {
    1000: "POLLO",
    1001: "POLLO",
    1002: "VEGETARIANOS",
    1003: "CERDO",
    1004: "POLLO",
    1005: "VEGETARIANOS",
    1006: "POLLO",
    1007: "CERDO",
    1008: "PASTAS",  # lasaña — reglas_eleccion_menus.md la trata como pasta
    1009: "PASTAS",
    1010: "CREPPES",
    1011: "PASTAS",
    1012: "MINUTAS",
    1013: "MINUTAS",  # omelette — la categoría MINUTAS ya incluye tortillas (ver id 47)
    1014: "TARTAS Y EMPANADAS",
}


def parse_precio(raw):
    """'$ 5400' / 14000 -> Decimal; '$ ', 'consultar' o None -> None."""
    if raw is None:
        return None
    digitos = re.sub(r"[^\d]", "", str(raw))
    if not digitos:
        return None
    try:
        return Decimal(digitos)
    except InvalidOperation:
        return None


class Command(BaseCommand):
    help = "Carga el catálogo real de Aromas (viandas, menú semanal, bebidas, catering)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--borrar-antes",
            action="store_true",
            help="Borra Articulo/Categoria y MenuSemanal antes de recargar",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        self.unidad_default, _ = Unidad.objects.get_or_create(
            nombre="Unidad", defaults={"abreviatura": "u"}
        )

        if options["borrar_antes"]:
            self.stdout.write("Borrando catálogo existente...")
            OpcionMenuDia.objects.all().delete()
            MenuSemanal.objects.all().delete()
            Articulo.objects.all().delete()
            Categoria.objects.all().delete()

        viandas = json.loads((FIXTURES_DIR / "viandas.json").read_text(encoding="utf-8"))
        catering = json.loads((FIXTURES_DIR / "catering.json").read_text(encoding="utf-8"))

        self.cargar_viandas(viandas)
        self.cargar_bebidas(viandas["bebidas"])
        self.cargar_catering(catering)

        self.stdout.write(self.style.SUCCESS("Catálogo cargado correctamente."))

    def get_categoria(self, linea, nombre, orden=0):
        cat, _ = Categoria.objects.get_or_create(
            linea_negocio=linea, nombre=nombre, defaults={"orden": orden}
        )
        return cat

    def _articulo_defaults(self, **kwargs):
        base = dict(
            unidad_compra=self.unidad_default,
            unidad_uso=self.unidad_default,
            relacion_unidades=1,
            precio_costo=0,
            alicuota_iva=Decimal("21"),
            activo=True,
        )
        base.update(kwargs)
        return base

    def cargar_viandas(self, data):
        self.stdout.write("Cargando catálogo a la carta (viandas)...")
        for i, item in enumerate(data["catalogo_a_la_carta"]):
            cat = self.get_categoria(LineaNegocio.VIANDAS, item["categoria"], orden=i)
            Articulo.objects.update_or_create(
                codigo=str(item["id"]),
                defaults=self._articulo_defaults(
                    categoria=cat,
                    nombre=item["nombre"],
                    descripcion=item.get("descripcion", ""),
                    ingredientes_texto=item.get("ingredientes", ""),
                    es_vegetariano=item.get("veg", False),
                    requiere_consulta=item.get("consultar", False),
                    tipo=TipoArticulo.ELABORADO,
                    precio_venta=Decimal("0") if item.get("consultar") else Decimal("9500"),  # PRECIOS.aLaCarta
                ),
            )

        self.stdout.write("Cargando pool exclusivo del menú semanal (códigos 1000+)...")
        platos_por_codigo = {}
        for item in data["menu_semanal_platos"]:
            nombre_categoria = CATEGORIA_REAL_MENU_SEMANAL[item["id"]]
            cat_item = self.get_categoria(LineaNegocio.VIANDAS, nombre_categoria)
            plato, _ = Articulo.objects.update_or_create(
                codigo=str(item["id"]),
                defaults=self._articulo_defaults(
                    categoria=cat_item,
                    nombre=item["nombre"],
                    descripcion=item.get("descripcion", ""),
                    ingredientes_texto=item.get("ingredientes", ""),
                    es_vegetariano=item.get("veg", False),
                    requiere_consulta=False,
                    tipo=TipoArticulo.ELABORADO,
                    # Se vende como parte de PRECIOS.viandaDiaria/viandaSemanal, no suelto
                    precio_venta=Decimal("0"),
                    visible_web=False,
                ),
            )
            platos_por_codigo[item["id"]] = plato

        self.stdout.write("Armando la semana publicada actualmente como MenuSemanal...")
        # La semana "actual" del sitio no tiene fecha real asociada en data.js;
        # se usa el lunes de la semana en curso como ancla. Ajustable a mano
        # desde el admin una vez que se sepa la fecha real.
        hoy = date.today()
        lunes_actual = hoy - timedelta(days=hoy.weekday())
        menu, _ = MenuSemanal.objects.update_or_create(
            fecha_inicio=lunes_actual,
            defaults={"activo": True, "notas": "Importado desde el sitio actual (data.js)"},
        )
        for dia_info in data["menu_semanal_dias"]:
            dia_codigo = DIA_JS_A_CODIGO[dia_info["dia"]]
            for numero_opcion, codigo_plato in enumerate(dia_info["platos"], start=1):
                OpcionMenuDia.objects.update_or_create(
                    menu_semanal=menu,
                    dia_semana=dia_codigo,
                    numero_opcion=numero_opcion,
                    defaults={"plato": platos_por_codigo[codigo_plato]},
                )

        problemas = menu.reglas_incumplidas()
        if problemas:
            self.stdout.write(
                self.style.WARNING(
                    f"La semana importada tiene {len(problemas)} cosa(s) para revisar contra "
                    "reglas_eleccion_menus.md: " + " | ".join(problemas)
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS("La semana importada cumple todas las reglas de negocio."))

    def cargar_bebidas(self, bebidas):
        self.stdout.write("Cargando bebidas (línea café/venta directa)...")
        cat = self.get_categoria(LineaNegocio.CAFE, "Bebidas")
        for item in bebidas:
            Articulo.objects.update_or_create(
                nombre=item["nombre"],
                categoria=cat,
                defaults=self._articulo_defaults(
                    descripcion=item.get("descripcion", ""),
                    precio_venta=Decimal(str(item["precio"])),
                    tipo=TipoArticulo.VENTA,
                    visible_web=True,
                ),
            )

    def cargar_catering(self, data):
        self.stdout.write("Cargando opciones sueltas de catering...")
        cat_opciones = self.get_categoria(LineaNegocio.CATERING, "Opciones a la carta")
        for item in data["opciones"]:
            precio = parse_precio(item.get("precio"))
            Articulo.objects.update_or_create(
                nombre=item["plato"],
                categoria=cat_opciones,
                defaults=self._articulo_defaults(
                    descripcion=f"Rinde {item.get('porciones')} porciones" if item.get("porciones") else "",
                    precio_venta=precio or Decimal("0"),
                    requiere_consulta=precio is None,
                    tipo=TipoArticulo.ELABORADO,
                ),
            )

        self.stdout.write("Cargando packs de catering (coffee breaks, etc.)...")
        cat_packs = self.get_categoria(LineaNegocio.CATERING, "Packs", orden=1)
        for item in data["packs"]:
            precio = parse_precio(item.get("precio_raw"))
            Articulo.objects.update_or_create(
                nombre=item["nombre"],
                categoria=cat_packs,
                defaults=self._articulo_defaults(
                    descripcion=item.get("descripcion", ""),
                    precio_venta=precio or Decimal("0"),
                    requiere_consulta=precio is None,
                    tipo=TipoArticulo.ELABORADO,
                ),
            )
