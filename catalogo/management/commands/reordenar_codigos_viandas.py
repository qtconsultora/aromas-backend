"""
Reacomoda los códigos de los platos de Viandas que ya estaban cargados
(del catálogo viejo, `cargar_catalogo_real`), para que todo el catálogo
quede separado por rango de código:

    4000+  Catering               (ya hecho, cargar_catering_aromas)
    7000+  Viandas a la Carta     (los 47 platos "a la carta" de siempre)
    8000+  Viandas semanales y diarias
           (8000-8014: los 15 platos del Menú de la Semana ya publicado;
            8015+: los platos nuevos que se van sumando -- ver
            cargar_viandas_nuevas)

No crea artículos nuevos: sólo les cambia el `codigo` a los que ya existen
(los que cargó `cargar_catalogo_real`). Busca cada plato por su código
ACTUAL (el "01"..."47"/"1000"..."1014" con el que los cargó
`cargar_catalogo_real`), no por nombre: el nombre no sirve como referencia
confiable porque `cargar_catalogo_real` los carga desde `data.js` (el sitio
viejo) y puede tener redacciones levemente distintas a las de
`viandas.json` (usado sólo como fixture de referencia acá) -- matchear por
nombre se probó en la práctica y se salteó 29 de los 62 platos por
diferencias de texto. Para cada id de `viandas.json` se busca primero el
artículo con `codigo=str(id)`, y si no está, con `codigo=f"V-{id}"` (dos
de estos 47+15 quedaron con ese prefijo por la colisión de códigos al
importar GestQuand: "V-42"/"V-1005").

Antes de reacomodar, borra los 15 artículos DUPLICADOS que había dejado
una corrida anterior de `cargar_viandas_nuevas`: esa carga (144 platos,
8000-8143) traía sin querer, en sus primeras 15 filas, los mismos 15
platos del Menú de la Semana que ya existían -- pero con categoría
genérica (Carnes/Vegetarianos/Pastas (Viandas) en vez de POLLO/CERDO/etc)
y código 8000-8014. Sólo se borra un artículo si su nombre coincide
EXACTO con uno de `menu_semanal_platos` Y su código actual está en el
rango 8000-8014 Y además existe *otro* artículo con ese mismo nombre en
otro código (o sea: se confirma que es un duplicado real, nunca el único
ejemplar) -- así el rango 8000-8014 queda libre para los platos
verdaderos en la Fase 2, y los 129 platos genuinos (8015-8143) no se
tocan.

El cambio de código se hace en dos pasos (todo -> códigos temporales ->
códigos finales) para que nunca se pise un artículo con otro mientras se
reacomoda, aunque el rango viejo y el nuevo se superpongan.

Uso:
    python manage.py reordenar_codigos_viandas
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from catalogo.models import Articulo

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "fixtures_source"
VIANDAS_JSON = FIXTURES_DIR / "viandas.json"

CODIGO_BASE_CARTA = 7000
CODIGO_BASE_SEMANAL = 8000
RANGO_DUPLICADOS = range(8000, 8015)  # donde quedaron los 15 duplicados


class Command(BaseCommand):
    help = "Renumera Viandas a la Carta (7000+) y Menú de la Semana ya publicado (8000-8014) por código actual"

    @transaction.atomic
    def handle(self, *args, **options):
        if not VIANDAS_JSON.exists():
            self.stderr.write(self.style.ERROR(f"No encontré {VIANDAS_JSON}"))
            return

        data = json.loads(VIANDAS_JSON.read_text(encoding="utf-8"))

        mapeo = []  # (codigo_actual_candidatos, codigo_nuevo, nombre para el log)
        for item in data["catalogo_a_la_carta"]:
            codigo_nuevo = str(CODIGO_BASE_CARTA + item["id"] - 1)
            candidatos = [str(item["id"]), f"V-{item['id']}"]
            mapeo.append((candidatos, codigo_nuevo, item["nombre"]))
        for item in data["menu_semanal_platos"]:
            codigo_nuevo = str(CODIGO_BASE_SEMANAL + item["id"] - 1000)
            candidatos = [str(item["id"]), f"V-{item['id']}"]
            mapeo.append((candidatos, codigo_nuevo, item["nombre"]))

        # --- Fase 0: borrar los 15 duplicados que dejó la carga vieja de
        # `cargar_viandas_nuevas`, para liberar el rango 8000-8014.
        borrados = []
        for item in data["menu_semanal_platos"]:
            nombre = item["nombre"]
            candidatos = list(Articulo.objects.filter(nombre=nombre))
            if len(candidatos) < 2:
                continue  # no hay duplicado, no se toca nada
            duplicados = [
                a for a in candidatos
                if a.codigo and a.codigo.isdigit() and int(a.codigo) in RANGO_DUPLICADOS
            ]
            # Sólo borramos si, sacando los duplicados, sigue quedando al
            # menos un ejemplar real del plato (nunca nos quedamos sin ninguno).
            if duplicados and len(candidatos) - len(duplicados) >= 1:
                for dup in duplicados:
                    self.stdout.write(
                        f"  Borro duplicado: «{dup.nombre}» (código {dup.codigo}, "
                        f"categoría {dup.categoria})"
                    )
                    borrados.append((dup.nombre, dup.codigo))
                    dup.delete()

        if borrados:
            self.stdout.write(self.style.SUCCESS(f"Duplicados borrados: {len(borrados)}"))
        else:
            self.stdout.write("No había duplicados para borrar (¿ya se había corrido este paso?).")

        # --- Fase 1: mover todo lo que se va a tocar a un código temporal,
        # para que ningún código final quede ocupado por otro artículo del
        # mismo lote mientras se reacomoda.
        encontrados = []
        no_encontrados = []
        ya_estaban = 0
        for candidatos, codigo_nuevo, nombre in mapeo:
            if Articulo.objects.filter(codigo=codigo_nuevo).exists():
                # Ya está en su código final (por ejemplo, de una corrida
                # anterior de este mismo comando) -- no hay nada que hacer.
                ya_estaban += 1
                continue
            art = Articulo.objects.filter(codigo__in=candidatos).first()
            if not art:
                no_encontrados.append(nombre)
                continue
            temporal = f"TMP-REORD-{art.pk}"
            art.codigo = temporal
            art.save(update_fields=["codigo"])
            encontrados.append((art, codigo_nuevo, nombre))

        # --- Fase 2: de código temporal a código final.
        cambios = []
        for art, codigo_nuevo, nombre in encontrados:
            anterior = art.codigo
            art.refresh_from_db(fields=["codigo"])
            art.codigo = codigo_nuevo
            art.save(update_fields=["codigo"])
            cambios.append((nombre, codigo_nuevo))

        for nombre, codigo_nuevo in cambios:
            self.stdout.write(f"  «{nombre}» -> {codigo_nuevo}")

        self.stdout.write(
            self.style.SUCCESS(f"Renumerados {len(cambios)} platos.")
        )
        if ya_estaban:
            self.stdout.write(f"Ya estaban en su código final (sin cambios): {ya_estaban}")
        if no_encontrados:
            self.stdout.write(
                self.style.WARNING(
                    f"No encontré con su código viejo (revisar a mano): {len(no_encontrados)} -> "
                    + ", ".join(no_encontrados)
                )
            )
