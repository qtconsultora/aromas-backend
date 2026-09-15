"""
Carga las fotos reales de los productos de catering (códigos 4000-4037)
en `Articulo.imagen`. Mismo patrón que `cargar_fotos_articulos` (Viandas):
las fotos ya vienen redimensionadas/comprimidas (máx. 1000px de ancho,
JPEG calidad 82) en `catalogo/fixtures_source/fotos_articulos/<codigo>.jpg`
-- se procesaron una sola vez a partir de las fotos originales (numeradas
1.jfif..38.jfif, el N° del catálogo viejo) para que el sitio cargue rápido.

Es IDEMPOTENTE: si un Articulo ya tiene `imagen` cargada Y el archivo
todavía existe en el disco, lo salta. Si el archivo desapareció (disco
efímero de Render, que se borra en cada deploy) lo vuelve a cargar aunque
el campo ya tuviera un valor. Nunca toca códigos fuera de 4000-4037.

Uso:
    python manage.py cargar_fotos_catering
    python manage.py cargar_fotos_catering --forzar
"""

from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand

from catalogo.models import Articulo

FOTOS_DIR = Path(__file__).resolve().parent.parent.parent / "fixtures_source" / "fotos_articulos"

CODIGOS = [str(c) for c in range(4000, 4038)]


class Command(BaseCommand):
    help = "Carga las fotos reales de catering (4000-4037) en Articulo.imagen"

    def add_arguments(self, parser):
        parser.add_argument(
            "--forzar",
            action="store_true",
            help="Reemplaza la imagen aunque el artículo ya tenga una cargada y el archivo exista.",
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

            ya_tiene_archivo = bool(articulo.imagen) and articulo.imagen.storage.exists(articulo.imagen.name)
            if ya_tiene_archivo and not forzar:
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
