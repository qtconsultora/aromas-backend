"""
Carga `unidades_por_presentacion` (cuántas piezas trae una bandeja) y
`es_vegetariano` para los 38 artículos de catering (códigos 4000-4037),
según los datos reales del catálogo viejo (assets/js/data.js del sitio
estático de catering) -- ese archivo no tiene equivalente en la base de
datos porque `cargar_catering_aromas` se armó a partir del .docx, que no
tenía estos dos campos.

Sólo toca `unidades_por_presentacion` y `es_vegetariano`: no pisa
`precio_venta` ni `descripcion` (que ya están cargados y podrían haberse
editado a mano desde el admin). Es idempotente -- correrlo de nuevo no
hace nada distinto si los valores ya están puestos.

Uso:
    python manage.py cargar_unidades_catering
"""

from django.core.management.base import BaseCommand

from catalogo.models import Articulo

CODIGO_BASE = 4000

# (n, unidades por bandeja, es_vegetariano) -- mismo orden y valores que
# CATALOGO en el data.js viejo. codigo = CODIGO_BASE + n - 1.
DATOS = [
    (1, 12, False),   # Miga Triple Jamón y Queso
    (2, 12, False),   # Miga Triple Salame y Queso
    (3, 12, False),   # Miga Triple Crudo y Ananá
    (4, 12, True),    # Miga Triple Primavera
    (5, 12, False),   # Empanadita de Jamón y Queso
    (6, 12, False),   # Empanadita de Carne
    (7, 12, True),    # Empanadita de Espinaca, Muzzarella y Champignon
    (8, 12, False),   # Empanadita de Osobuco Desmenuzado al Malbec
    (9, 12, True),    # Empanadita de Choclo y Calabaza
    (10, 10, False),  # Tortillita Individual a la Española
    (11, 10, True),   # Tortillita Individual de Verdura
    (12, 10, True),   # Tortillita Individual de Papas
    (13, 10, True),   # Pionono Agridulce de Roquefort y Nuez
    (14, 10, False),  # Pionono Agridulce de Crudo, Salsa Golf y Ananá
    (15, 10, False),  # Pionono de Morrones, Jamón y Salsa Tártara
    (16, 10, False),  # Brioche de Crudo, Rúcula y Oliva
    (17, 10, False),  # Pebetito de Jamón, Queso y Tomate
    (18, 10, False),  # Pebetito de Cerdo y Salsa de Puerros
    (19, 10, False),  # Pebetito de Vacío Desmenuzado
    (20, 10, True),   # Pizzetín de Muzzarella
    (21, 10, True),   # Pizzetín 4 Quesos
    (22, 10, True),   # Pizzetín Vegetariano
    (23, 10, True),   # Volován de Roquefort y Nuez
    (24, 10, True),   # Volován de Quesos y Ciboulette
    (25, 10, True),   # Volován de Guacamole
    (26, 10, False),  # Fosforito de Hojaldre de Jamón y Queso
    (27, 10, False),  # Croissant de Jamón y Queso
    (28, 5, False),   # Brochette de Pollo (consultar)
    (29, 5, False),   # Brochette de Lomo (consultar)
    (30, 5, False),   # Brochette de Cerdo (consultar)
    (31, 5, False),   # Bruschetta de Frutos de Mar (consultar)
    (32, 5, True),    # Bruschetta Caprese
    (33, 5, False),   # Ensaladita Individual César (consultar)
    (34, 5, True),    # Ensaladita Individual Waldorf (consultar)
    (35, 5, False),   # Ensaladita Individual Santa María (consultar)
    (36, 5, False),   # Pincho de Kabab (consultar)
    (37, 5, True),    # Pincho Caprese
    (38, 5, False),   # Pincho de Frutos de Mar (consultar)
]


class Command(BaseCommand):
    help = "Carga unidades_por_presentacion y es_vegetariano para los 38 artículos de catering (4000-4037)"

    def handle(self, *args, **options):
        actualizados = 0
        sin_cambios = 0
        no_encontrados = 0

        for n, unidades, veg in DATOS:
            codigo = str(CODIGO_BASE + n - 1)
            try:
                articulo = Articulo.objects.get(codigo=codigo)
            except Articulo.DoesNotExist:
                self.stderr.write(self.style.WARNING(f"  [{codigo}] no existe ningún Articulo con ese código"))
                no_encontrados += 1
                continue

            cambios = {}
            if articulo.unidades_por_presentacion != unidades:
                cambios["unidades_por_presentacion"] = unidades
            if articulo.es_vegetariano != veg:
                cambios["es_vegetariano"] = veg

            if cambios:
                for campo, valor in cambios.items():
                    setattr(articulo, campo, valor)
                articulo.save(update_fields=list(cambios.keys()))
                actualizados += 1
                self.stdout.write(f"  [{codigo}] {articulo.nombre} -> {cambios}")
            else:
                sin_cambios += 1

        self.stdout.write(self.style.SUCCESS(
            f"\nListo. Actualizados: {actualizados} | ya estaban al día: {sin_cambios} | sin Articulo: {no_encontrados}"
        ))
