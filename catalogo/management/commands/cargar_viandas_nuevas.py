"""
Crea los Articulo (tipo ELABORADO) de los platos nuevos de viandas, a
partir de `Platos_Nuevos_Viandas.xlsx` (Desktop\\aromas\\Viandas), bajo la
línea de negocio Viandas.

Dentro del esquema de códigos de Viandas (7000+ a la carta, 8000-8014
Menú de la Semana ya publicado -- ver `reordenar_codigos_viandas`), estos
son los platos genuinamente NUEVOS: 8015 en adelante, 129 platos en total
(8015-8143), sin huecos. Las primeras 15 filas de `Platos_Nuevos_Viandas.xlsx`
resultaron ser los mismos 15 platos que ya estaban cargados como Menú de
la Semana (1000-1014) -- esos 15 quedan afuera de este fixture a propósito,
para no duplicarlos; los renumera `reordenar_codigos_viandas` en vez de
este comando.

El código de cada plato es el que ya trae el propio archivo/fixture en la
columna "Código" -- no se recalcula ni se reacomoda, se usa tal cual. Ese
mismo código es el que después se va a usar para nombrar la foto de cada
plato cuando existan (por ahora ningún plato de este lote tiene foto
todavía -- no se encontró ninguna con ese rango de código en la carpeta
Fotos; se van a ir sumando después con los datos que haya en los
documentos).

La columna "Categoría" del archivo (Carnes/Vegetarianos/Minutas/Pastas) se
respeta como categoría propia dentro de la línea Viandas (no se mezcla con
las categorías en MAYÚSCULA que ya usan los platos "a la carta" originales
-- son dos conjuntos de categorías separados, aunque el validador de
reglas del menú semanal (`MenuSemanal.reglas_incumplidas`) las compara en
mayúsculas de todos modos, así que igual matchean si algún día se usan en
un menú semanal).

Las recetas (composición con insumos reales) quedan para un paso aparte.

Uso:
    python manage.py cargar_viandas_nuevas
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from catalogo.models import Articulo, Categoria, LineaNegocio, TipoArticulo, Unidad

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "fixtures_source"
DEFAULT_PATH = FIXTURES_DIR / "viandas_nuevas_aromas.json"


class Command(BaseCommand):
    help = "Carga los platos nuevos de viandas (Platos_Nuevos_Viandas.xlsx), códigos 8000+, por categoría (Carnes/Vegetarianos/Minutas/Pastas)"

    def add_arguments(self, parser):
        parser.add_argument("--archivo", default=str(DEFAULT_PATH))

    @transaction.atomic
    def handle(self, *args, **options):
        path = Path(options["archivo"])
        if not path.exists():
            self.stderr.write(self.style.ERROR(f"No encontré el archivo: {path}"))
            return

        data = json.loads(path.read_text(encoding="utf-8"))

        unidad_default, _ = Unidad.objects.get_or_create(
            nombre="Unidad", defaults={"abreviatura": "u"}
        )

        categoria_cache = {}
        creados = 0
        actualizados = 0

        for item in data:
            nombre_cat = item["categoria"]
            if nombre_cat not in categoria_cache:
                cat, created = Categoria.objects.get_or_create(
                    linea_negocio=LineaNegocio.VIANDAS, nombre=nombre_cat
                )
                categoria_cache[nombre_cat] = cat
                if created:
                    self.stdout.write(f"Categoría creada: {cat}")
            categoria = categoria_cache[nombre_cat]

            codigo = str(item["codigo"])
            defaults = dict(
                nombre=item["nombre"],
                descripcion=item.get("nota") or "",
                categoria=categoria,
                marca=None,
                unidad_compra=unidad_default,
                unidad_uso=unidad_default,
                relacion_unidades=1,
                tipo=TipoArticulo.ELABORADO,
                precio_costo=0,
                precio_venta=0,
                alicuota_iva=21,
                visible_web=False,
                requiere_consulta=False,
                activo=True,
            )
            obj, was_created = Articulo.objects.update_or_create(
                codigo=codigo, defaults=defaults
            )
            creados += int(was_created)
            actualizados += int(not was_created)

        self.stdout.write(
            self.style.SUCCESS(
                f"Viandas nuevas: {creados} artículos creados, {actualizados} actualizados "
                f"(sin foto, precio ni receta todavía)."
            )
        )
