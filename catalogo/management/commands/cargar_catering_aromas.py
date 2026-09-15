"""
Crea los Articulo (tipo ELABORADO) del catálogo de catering/finger food
propio de Aromas, a partir de `Catalogo_Productos_BORRADOR.docx`, bajo una
categoría nueva y separada llamada "Cat. Aromas" (no se tocan ni se
mezclan con los artículos ya copiados de GestQuand, ni con los que ya
existían en "Opciones a la carta"/"Packs" desde el sitio viejo).

El código de cada artículo NO es el N° del documento (ese N°, "01".."38",
podía chocar con códigos ya usados en otras líneas) -- se generan códigos
nuevos y propios arrancando en 4000 (4000, 4001, ..., 4037, en el mismo
orden en que están en el documento). Ese mismo código es el que después se
usa para nombrar la foto de cada plato (4000.jfif, 4001.jfif, ...) y el que
se vuelca de nuevo en el documento, para que catálogo, fotos y documento
queden siempre alineados por código.

La descripción y los ingredientes principales son los que ya estaban
redactados en el documento. La columna Precio del documento está en blanco
(a propósito, según su propia nota: "Columna Precio queda en blanco para
completar"), así que estos artículos quedan con precio_venta = 0 hasta
cargarlo a mano.

Las recetas (composición con insumos reales y cantidades) quedan
explícitamente para un paso aparte.

Uso:
    python manage.py cargar_catering_aromas
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from catalogo.models import Articulo, Categoria, LineaNegocio, TipoArticulo, Unidad

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "fixtures_source"
DEFAULT_PATH = FIXTURES_DIR / "catering_aromas_borrador.json"

CATEGORIA_NOMBRE = "Cat. Aromas"
CODIGO_BASE = 4000


class Command(BaseCommand):
    help = "Carga el catálogo de catering/finger food propio de Aromas (Catalogo_Productos_BORRADOR.docx) bajo la categoría 'Cat. Aromas', con códigos propios desde 4000"

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
        categoria, created = Categoria.objects.get_or_create(
            linea_negocio=LineaNegocio.CATERING, nombre=CATEGORIA_NOMBRE
        )
        if created:
            self.stdout.write(f"Categoría creada: {categoria}")

        # Si ya habías corrido una versión anterior de este comando (con el
        # código = N° del documento, "01".."38"), se migran esos artículos al
        # código nuevo en vez de dejarlos duplicados.
        self.migrar_codigos_viejos(data, categoria)

        creados = 0
        actualizados = 0
        for item in data:
            codigo = str(CODIGO_BASE + int(item["n"]) - 1)
            defaults = dict(
                nombre=item["nombre"],
                descripcion=item.get("descripcion") or "",
                ingredientes_texto=item.get("ingredientes") or "",
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
                f"Cat. Aromas: {creados} artículos creados, {actualizados} actualizados "
                f"(sin precio ni receta todavía -- son los próximos pasos)."
            )
        )

    def migrar_codigos_viejos(self, data, categoria):
        for item in data:
            codigo_viejo = item["n"]
            codigo_nuevo = str(CODIGO_BASE + int(item["n"]) - 1)
            art = Articulo.objects.filter(codigo=codigo_viejo, categoria=categoria).first()
            if art and not Articulo.objects.filter(codigo=codigo_nuevo).exists():
                self.stdout.write(f"  Código '{codigo_viejo}' -> '{codigo_nuevo}' («{art.nombre}»)")
                art.codigo = codigo_nuevo
                art.save(update_fields=["codigo"])
