"""
Copia a Aromas, DIRECTO desde GestQuand, todos los Articulo tipo INSUMO y
ELABORADO -- con su código real, categoría, marca, unidades y recetas tal
cual están hoy en producción -- a partir de un export generado con
`exportar_para_aromas.py` (corrido a mano contra la base de GestQuand,
porque es un Postgres local en la máquina de Pichón y no se puede leer
desde acá).

No inventa ni completa nada: cada artículo se carga con los datos que ya
tenía en GestQuand. Las fotos (`imagen_path` en GestQuand) quedan afuera a
propósito -- es un paso aparte, ya acordado, para más adelante.

Categorías y marcas se preservan con el mismo nombre que tienen en
GestQuand (nunca se renombran ni se fusionan). Como GestQuand no tiene el
concepto de "línea de negocio" (vende de todo, no separa viandas/catering/
café), se asigna automáticamente:
    - INSUMO     -> línea INSUMOS (no se vende, sólo se usa en recetas)
    - ELABORADO  -> línea CATERING (son los platos reales de catering/
                    finger food -- confirmalo/ajustalo en el admin si
                    alguna categoría puntual no corresponde ahí)

Uso:
    python manage.py cargar_desde_gestquand
    python manage.py cargar_desde_gestquand --archivo ruta/al/export.json
"""

import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from catalogo.models import (
    Articulo,
    Categoria,
    LineaNegocio,
    Marca,
    Receta,
    TipoArticulo,
    Unidad,
)

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "fixtures_source"
EXPORT_PATH_DEFAULT = FIXTURES_DIR / "gestquand_export.json"

# Los dos únicos códigos de GestQuand que ya estaban ocupados por platos de
# vianda cargados antes con `cargar_catalogo_real` (esos códigos eran sólo
# el índice interno del sitio viejo -- data.js -- no un SKU real). Se
# renombran para dejarle el código verdadero al artículo de GestQuand.
CODIGOS_A_LIBERAR = {
    "42": "V-42",
    "1005": "V-1005",
}

TIPO_MAP = {"insumo": TipoArticulo.INSUMO, "elaborado": TipoArticulo.ELABORADO}


def dec(value, default="0"):
    if value is None:
        return Decimal(default)
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return Decimal(default)


class Command(BaseCommand):
    help = "Copia desde GestQuand los articulos tipo insumo y elaborado (codigos, categorias, marcas, recetas)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--archivo",
            default=str(EXPORT_PATH_DEFAULT),
            help="Ruta al JSON generado por exportar_para_aromas.py",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        path = Path(options["archivo"])
        if not path.exists():
            self.stderr.write(self.style.ERROR(f"No encontré el archivo: {path}"))
            return

        data = json.loads(path.read_text(encoding="utf-8"))

        self.unidad_default, _ = Unidad.objects.get_or_create(
            nombre="Unidad", defaults={"abreviatura": "u"}
        )

        self.liberar_codigos_en_conflicto()

        unidades = self.cargar_unidades(data.get("unidades", []))
        marcas = self.cargar_marcas(data.get("marcas", []))
        markup_por_categoria = {
            c["nombre"]: dec(c.get("markup_pct")) for c in data.get("categorias", [])
        }
        categoria_cache = {}

        creados = 0
        actualizados = 0
        for item in data["articulos"]:
            categoria = self.get_categoria(categoria_cache, item, markup_por_categoria)
            marca = marcas.get(item.get("marca_nombre")) if item.get("marca_nombre") else None

            relacion = dec(item.get("relacion_unidades"), "1")
            if relacion <= 0:
                relacion = Decimal("1")

            defaults = dict(
                nombre=item["nombre"],
                descripcion=item.get("descripcion") or "",
                categoria=categoria,
                marca=marca,
                unidad_compra=self.resolver_unidad(unidades, item, "compra"),
                unidad_uso=self.resolver_unidad(unidades, item, "uso"),
                relacion_unidades=relacion,
                tipo=TIPO_MAP[item["tipo"]],
                precio_costo=dec(item.get("precio_costo")),
                precio_venta=dec(item.get("precio_venta")),
                alicuota_iva=dec(item.get("alicuota_iva"), "21"),
                markup_pct=dec(item.get("markup_pct")),
                stock_actual=dec(item.get("stock_actual")),
                stock_minimo=dec(item.get("stock_minimo")),
                controla_stock=bool(item.get("controla_stock", True)),
                visible_web=bool(item.get("visible_web", False)),
                descripcion_web=item.get("descripcion_web") or "",
                activo=bool(item.get("activo", True)),
            )

            codigo = item.get("codigo")
            if codigo:
                obj, created = Articulo.objects.update_or_create(
                    codigo=codigo, defaults=defaults
                )
            else:
                obj, created = Articulo.objects.update_or_create(
                    nombre=item["nombre"], categoria=categoria, codigo=None, defaults=defaults
                )
            creados += int(created)
            actualizados += int(not created)

        self.stdout.write(
            self.style.SUCCESS(f"Articulos: {creados} creados, {actualizados} actualizados.")
        )

        recetas_creadas, recetas_saltadas = self.cargar_recetas(
            data.get("recetas", []), unidades
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Recetas: {recetas_creadas} creadas/actualizadas, "
                f"{recetas_saltadas} salteadas (insumo o elaborado tipo 'venta', fuera de este import)."
            )
        )

    def liberar_codigos_en_conflicto(self):
        for viejo, nuevo in CODIGOS_A_LIBERAR.items():
            art = Articulo.objects.filter(codigo=viejo).first()
            if art and not Articulo.objects.filter(codigo=nuevo).exists():
                self.stdout.write(
                    f"  Código '{viejo}' ya estaba usado por «{art.nombre}» "
                    f"-> renombrado a '{nuevo}' para dejarle el código real al artículo de GestQuand."
                )
                art.codigo = nuevo
                art.save(update_fields=["codigo"])

    def cargar_unidades(self, unidades_data):
        out = {}
        for u in unidades_data:
            obj, _ = Unidad.objects.get_or_create(
                nombre=u["nombre"], defaults={"abreviatura": u.get("abreviatura") or ""}
            )
            out[u["nombre"]] = obj
        return out

    def cargar_marcas(self, marcas_data):
        out = {}
        for m in marcas_data:
            obj, _ = Marca.objects.get_or_create(
                nombre=m["nombre"], defaults={"markup_pct": dec(m.get("markup_pct"))}
            )
            out[m["nombre"]] = obj
        return out

    def get_categoria(self, cache, item, markup_por_categoria):
        nombre = item.get("categoria_nombre") or "Sin categorizar"
        linea = LineaNegocio.INSUMOS if item["tipo"] == "insumo" else LineaNegocio.CATERING
        key = (linea, nombre)
        if key not in cache:
            cache[key], _ = Categoria.objects.get_or_create(
                linea_negocio=linea,
                nombre=nombre,
                defaults={"markup_pct": markup_por_categoria.get(nombre, Decimal("0"))},
            )
        return cache[key]

    def resolver_unidad(self, unidades, item, cual):
        nombre = item.get(f"unidad_{cual}_nombre") or item.get("unidad_legacy_nombre")
        if nombre and nombre in unidades:
            return unidades[nombre]
        return self.unidad_default

    def cargar_recetas(self, recetas_data, unidades):
        por_codigo = {a.codigo: a for a in Articulo.objects.exclude(codigo__isnull=True)}
        creadas = 0
        salteadas = 0
        for r in recetas_data:
            articulo = por_codigo.get(r["articulo_codigo"])
            insumo = por_codigo.get(r["insumo_codigo"])
            if not articulo or not insumo:
                salteadas += 1
                continue
            cantidad = dec(r.get("cantidad"), "1")
            if cantidad <= 0:
                cantidad = Decimal("1")
            unidad = unidades.get(r.get("unidad_nombre")) or articulo.unidad_uso
            Receta.objects.update_or_create(
                articulo=articulo,
                insumo=insumo,
                defaults=dict(
                    cantidad=cantidad,
                    unidad=unidad,
                    observaciones=r.get("observaciones") or "",
                ),
            )
            creadas += 1
        return creadas, salteadas
