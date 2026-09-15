"""
Repara una corrupción de datos real que quedó en la base: la versión de
`cargar_catering_aromas` que estaba puesta en la compu (vieja, previa al
esquema de códigos 4000+) usaba el N° del documento tal cual ("01".."38")
como código del artículo, SIN generar códigos propios. Los platos de
catering con N° de una cifra ("01".."09") no chocaron con nada (los
platos "a la carta" de Viandas usan código "1".."9", sin cero adelante),
pero los de dos cifras ("10".."38") SÍ son el mismo string que el código
que usan los 29 platos "a la carta" de Viandas con esos mismos números
(ids 10-38) -- entonces `update_or_create(codigo=...)` no creó platos de
catering nuevos para esos 29: en cambio PISÓ los 29 artículos de Viandas
que ya estaban ahí, reemplazando su nombre/descripción/ingredientes/
categoría/precio por los del plato de catering correspondiente.

Este comando restaura esos 29 artículos a sus valores correctos de
Viandas "a la carta", tomados de `viandas.json` (la misma fuente que usa
`cargar_catalogo_real`, con exactamente la misma lógica de campos). Los
busca por su código ACTUAL -- después de correr `reordenar_codigos_viandas`
estos ya están en el rango 7000-7046 (7000 + id - 1), no por el código
viejo "10".."38" (que ya no existe, se pisó a sí mismo). Si todavía no
corriste `reordenar_codigos_viandas`, corré primero este comando con
`--codigos-viejos` para buscarlos por "10".."38" en cambio.

Sólo toca los campos que la corrupción pisó (nombre, descripción,
ingredientes, categoría, es_vegetariano, requiere_consulta, tipo, precio,
unidad de compra/uso, alícuota IVA) -- nunca el código (que ya debe estar
bien) ni ningún otro campo (foto, stock, etc.).

Uso:
    python manage.py reparar_corrupcion_cat_aromas
    python manage.py reparar_corrupcion_cat_aromas --codigos-viejos   # si todavía no corriste reordenar_codigos_viandas
"""

import json
from decimal import Decimal
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from catalogo.models import Articulo, Categoria, LineaNegocio, TipoArticulo, Unidad

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "fixtures_source"
VIANDAS_JSON = FIXTURES_DIR / "viandas.json"

IDS_AFECTADOS = range(10, 39)  # 10..38 inclusive
CODIGO_BASE_CARTA = 7000


class Command(BaseCommand):
    help = "Repara los 29 platos 'a la carta' de Viandas (ids 10-38) que la versión vieja de cargar_catering_aromas pisó con datos de catering"

    def add_arguments(self, parser):
        parser.add_argument(
            "--codigos-viejos",
            action="store_true",
            help="Buscar por código viejo ('10'..'38') en vez del nuevo (7009-7037). "
            "Usar sólo si todavía NO corriste reordenar_codigos_viandas.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if not VIANDAS_JSON.exists():
            self.stderr.write(self.style.ERROR(f"No encontré {VIANDAS_JSON}"))
            return

        data = json.loads(VIANDAS_JSON.read_text(encoding="utf-8"))
        items = {
            item["id"]: item
            for item in data["catalogo_a_la_carta"]
            if item["id"] in IDS_AFECTADOS
        }

        unidad_default, _ = Unidad.objects.get_or_create(
            nombre="Unidad", defaults={"abreviatura": "u"}
        )

        reparados = []
        no_encontrados = []
        sospechosos = []  # encontrado pero el nombre actual no es el de catering ni el de la vianda -- revisar a mano

        for id_, item in sorted(items.items()):
            if options["codigos_viejos"]:
                codigo_buscar = str(id_)
            else:
                codigo_buscar = str(CODIGO_BASE_CARTA + id_ - 1)

            art = Articulo.objects.filter(codigo=codigo_buscar).first()
            if not art:
                no_encontrados.append((id_, item["nombre"], codigo_buscar))
                continue

            nombre_antes = art.nombre
            cat, _ = Categoria.objects.get_or_create(
                linea_negocio=LineaNegocio.VIANDAS,
                nombre=item["categoria"],
                defaults={"orden": id_},
            )
            art.categoria = cat
            art.nombre = item["nombre"]
            art.descripcion = item.get("descripcion", "")
            art.ingredientes_texto = item.get("ingredientes", "")
            art.es_vegetariano = item.get("veg", False)
            art.requiere_consulta = item.get("consultar", False)
            art.tipo = TipoArticulo.ELABORADO
            art.precio_venta = Decimal("0") if item.get("consultar") else Decimal("9500")
            art.unidad_compra = unidad_default
            art.unidad_uso = unidad_default
            art.relacion_unidades = 1
            art.precio_costo = 0
            art.alicuota_iva = Decimal("21")
            art.activo = True
            art.save()

            reparados.append((codigo_buscar, nombre_antes, item["nombre"]))

        for codigo, antes, despues in reparados:
            if antes != despues:
                self.stdout.write(f"  [{codigo}] «{antes}» -> «{despues}» (restaurado)")
            else:
                self.stdout.write(f"  [{codigo}] «{despues}» (ya tenía el nombre correcto, campos restaurados igual)")

        self.stdout.write(self.style.SUCCESS(f"Reparados: {len(reparados)} de {len(items)}"))
        if no_encontrados:
            self.stdout.write(
                self.style.WARNING(
                    "No encontré (revisar a mano): "
                    + ", ".join(f"[{c}] {n} (id {i})" for i, n, c in no_encontrados)
                )
            )
