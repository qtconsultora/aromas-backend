"""
Publica una semana del "Menú de la Semana" pisando en el lugar los 15
Articulo "slot" (8000-8014) y avanzando la fecha del MenuSemanal activo --
es el mecanismo que ya se usa siempre para cambiar de semana (ver
`catalogo/views.py::MenuSemanalActivoView`: siempre sirve el único
MenuSemanal con activo=True, y sus 15 OpcionMenuDia apuntan siempre a los
mismos 15 Articulo 8000-8014; lo que cambia cada semana es el contenido de
esos 15 Articulo, no las relaciones).

Para cada plato del fixture:
  - Busca el Articulo "slot" por `codigo_slot` (8000-8014, ya existe).
  - Busca el Articulo "fuente" por `codigo_fuente` (pool de 129 platos
    nuevos, 8015-8143) sólo para copiarle la `categoria` real (el slot
    hereda la categoría del plato que le toca esta semana, así
    `reglas_incumplidas()` puede chequear pastas/guisos/pescados/minutas
    de verdad).
  - Pisa nombre, descripcion, categoria, es_vegetariano en el slot.
  - Carga la foto ya procesada desde
    catalogo/fixtures_source/fotos_articulos/<codigo_slot>.jpg (si existe).
  - NO toca precio_venta/visible_web (los slots se venden agrupados vía
    Articulo 9000/9002 "Vianda Diaria"/"Vianda Semanal", no sueltos).

Después avanza `MenuSemanal.fecha_inicio` (y dejar `activo=True`) al valor
del fixture, y al final corre `reglas_incumplidas()` e imprime el
resultado -- si hay problemas, NO aborta (podés estar iterando), pero los
deja bien visibles.

Es IDEMPOTENTE: correrlo dos veces con el mismo fixture da el mismo
resultado.

Uso:
    python manage.py publicar_menu_semanal catalogo/fixtures_source/semana1_2026-09-21.json
    python manage.py publicar_menu_semanal catalogo/fixtures_source/semana1_2026-09-21.json --dry-run
"""

import json
from datetime import date
from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from catalogo.models import Articulo, Categoria, MenuSemanal, OpcionMenuDia

FOTOS_DIR = Path(__file__).resolve().parent.parent.parent / "fixtures_source" / "fotos_articulos"


class Command(BaseCommand):
    help = "Publica una semana del Menú de la Semana (pisa los 15 Articulo slot 8000-8014 y avanza MenuSemanal.fecha_inicio)"

    def add_arguments(self, parser):
        parser.add_argument("fixture", help="Ruta al JSON con la semana a publicar")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Muestra qué haría (incluyendo reglas_incumplidas) sin escribir nada en la base.",
        )

    def handle(self, *args, **options):
        fixture_path = Path(options["fixture"])
        if not fixture_path.exists():
            raise CommandError(f"No existe el archivo {fixture_path}")

        with open(fixture_path, encoding="utf-8") as f:
            data = json.load(f)

        platos = data["platos"]
        if len(platos) != 15:
            raise CommandError(f"El fixture tiene {len(platos)} platos, deberían ser 15 (5 días x 3 opciones)")

        dry_run = options["dry_run"]

        with transaction.atomic():
            self._publicar(data, platos, dry_run)
            if dry_run:
                self.stdout.write(self.style.WARNING("--dry-run: se revierte todo, no se guardó nada."))
                transaction.set_rollback(True)

    def _publicar(self, data, platos, dry_run):
        actualizados = []
        for item in platos:
            codigo_slot = str(item["codigo_slot"])
            codigo_fuente = str(item["codigo_fuente"])

            try:
                slot = Articulo.objects.get(codigo=codigo_slot)
            except Articulo.DoesNotExist:
                raise CommandError(f"No existe Articulo slot con codigo={codigo_slot}")

            try:
                fuente = Articulo.objects.get(codigo=codigo_fuente)
            except Articulo.DoesNotExist:
                raise CommandError(f"No existe Articulo fuente con codigo={codigo_fuente}")

            # Sanity check: el slot para este día/opción tiene que ser el
            # mismo que ya está enganchado en el OpcionMenuDia -- si no
            # coincide, el fixture tiene mal el mapeo día->slot.
            existe_opcion = OpcionMenuDia.objects.filter(
                dia_semana=item["dia"], numero_opcion=item["numero_opcion"], plato__codigo=codigo_slot
            ).exists()
            if not existe_opcion:
                raise CommandError(
                    f"{item['dia']} opción {item['numero_opcion']}: el codigo_slot {codigo_slot} "
                    "no coincide con el OpcionMenuDia ya cargado para ese día/opción -- revisar el fixture."
                )

            categoria = fuente.categoria
            override = item.get("categoria_nombre_override")
            if override:
                try:
                    categoria = Categoria.objects.get(
                        linea_negocio=fuente.categoria.linea_negocio, nombre=override
                    )
                except Categoria.DoesNotExist:
                    raise CommandError(
                        f"categoria_nombre_override={override!r} no existe para "
                        f"linea_negocio={fuente.categoria.linea_negocio!r}"
                    )

            slot.nombre = item["nombre"]
            slot.descripcion = item["descripcion"]
            slot.categoria = categoria
            slot.es_vegetariano = item["es_vegetariano"]
            slot.save()

            foto_path = FOTOS_DIR / f"{codigo_slot}.jpg"
            foto_msg = "sin foto en disco"
            if foto_path.exists():
                with open(foto_path, "rb") as fh:
                    slot.imagen.save(f"{codigo_slot}.jpg", File(fh), save=True)
                foto_msg = "foto actualizada"

            actualizados.append(f"  [{item['dia']} op{item['numero_opcion']}] {codigo_slot} -> {slot.nombre} ({foto_msg})")

        for linea in actualizados:
            self.stdout.write(linea)

        menu = MenuSemanal.objects.filter(activo=True).first()
        if menu is None:
            raise CommandError("No hay ningún MenuSemanal con activo=True -- no sé cuál avanzar.")

        fecha_anterior = menu.fecha_inicio
        menu.fecha_inicio = date.fromisoformat(data["fecha_inicio"])
        if data.get("notas"):
            menu.notas = data["notas"]
        menu.save()
        self.stdout.write(self.style.SUCCESS(
            f"\nMenuSemanal id={menu.id}: fecha_inicio {fecha_anterior} -> {menu.fecha_inicio} (activo={menu.activo})"
        ))

        problemas = menu.reglas_incumplidas()
        if problemas:
            self.stdout.write(self.style.WARNING(
                f"\n{len(problemas)} cosa(s) para revisar contra reglas_eleccion_menus.md:"
            ))
            for p in problemas:
                self.stdout.write(self.style.WARNING(f"  - {p}"))
        else:
            self.stdout.write(self.style.SUCCESS("\nLa semana cumple todas las reglas de negocio."))
