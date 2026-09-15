"""
Carga las fotos reales de los platos en `Articulo.imagen`, para los rangos
de código que ya tienen fotos sacadas y nombradas por código:

    7000-7046  Viandas a la Carta (47 platos)
    8000-8014  Menú de la Semana ya publicado (15 platos)

Las fotos ya vienen redimensionadas/comprimidas (máx. 1000px de ancho,
JPEG calidad 82) en `catalogo/fixtures_source/fotos_articulos/<codigo>.jpg`
-- se procesaron una sola vez a partir de los .jfif originales de la
cámara/celular (que pesaban ~50MB en total) para que el sitio cargue
rápido y no infle el repo (quedaron en ~6MB).

Es IDEMPOTENTE: si un Articulo ya tiene `imagen` cargada, lo salta (no la
pisa), salvo que se pase `--forzar`. Nunca toca ni borra nada fuera de
estos dos rangos (los 129 platos nuevos 8015-8143 y el catering 4000-4037
todavía no tienen fotos reales).

Uso:
    python manage.py cargar_fotos_articulos
    python manage.py cargar_fotos_articulos --forzar
"""

from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand

from catalogo.models import Articulo

FOTOS_DIR = Path(__file__).resolve().parent.parent.parent / "fixtures_source" / "fotos_articulos"

CODIGOS = [str(c) for c in range(7000, 7047)] + [str(c) for c in range(8000, 8015)]


class Command(BaseCommand):
    help = "Carga las fotos reales de Viandas (7000-7046, 8000-8014) en Articulo.imagen"

    def add_arguments(self, parser):
        parser.add_argument(
            "--forzar",
            action="store_true",
            help="Reemplaza la imagen aunque el artículo ya tenga una cargada.",
        )

    def handle(self, *args, **options):
        forzar = options["forzar"]

        if not FOTOS_DIR.exists():
            self.stderr.write(self.style.ERROR(f"No existe la carpeta {FOTOS_DIR}"))
            return

        cargadas = 0
        salteadas_ya_tenia = 0
        no_encontrado_articulo = 0
        no_encontrada_foto = 0

        for codigo in CODIGOS:
            foto_path = FOTOS_DIR / f"{codigo}.jpg"
            if not foto_path.exists():
                self.stderr.write(self.style.WARNING(f"  [{codigo}] no hay foto en {foto_path.name}"))
                no_encontrada_foto += 1
                continue

            try:
                articulo = Articulo.objects.get(codigo=codigo)
            except Articulo.DoesNotExist:
                self.stderr.write(self.style.WARNING(f"  [{codigo}] no existe ningún Articulo con ese código"))
                no_encontrado_articulo += 1
                continue

            if articulo.imagen and not forzar:
                salteadas_ya_tenia += 1
                continue

            with open(foto_path, "rb") as f:
                articulo.imagen.save(f"{codigo}.jpg", File(f), save=True)

            cargadas += 1
            self.stdout.write(f"  [{codigo}] {articulo.nombre} -> foto cargada")

        self.stdout.write(self.style.SUCCESS(
            f"\nListo. Fotos cargadas: {cargadas} | ya tenían foto (salteadas): {salteadas_ya_tenia} | "
            f"sin foto disponible: {no_encontrada_foto} | código sin Articulo: {no_encontrado_articulo}"
        ))
