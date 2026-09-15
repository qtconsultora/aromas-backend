"""
Repara una colisión de códigos entre Viandas y el catálogo importado de
GestQuand, descubierta el 15/09/2026 al auditar el esquema de códigos
4000+/7000+/8000+ contra los 229 platos esperados (38 Catering + 47 a la
carta + 15 menú semanal + 129 nuevos).

Qué pasó: `reordenar_codigos_viandas` decide que un plato "ya está en su
código final" con sólo mirar si YA EXISTE algún Articulo con ese código —
sin chequear que sea el plato correcto. En dos casos, un artículo
importado de GestQuand (que trae su propio código de origen tal cual)
coincidía por pura casualidad con el código destino de un plato de
Viandas, así que el comando se salteó la renumeración pensando que ya
estaba hecha:

- código "7041" (a la carta N° 42, "1/2 Carlito de Pollo") lo tiene en
  realidad "BANDEJA DORADAS MASA SECA 23*28" (insumo de GestQuand,
  id=1807) — el plato real quedó sin renumerar, todavía como "V-42".
- código "8005" (menú semanal N° 1005, "Milanesas de Berenjenas Horno
  Gratinada") lo tiene en realidad "TABLA PREMIUM P/2" (catering de
  GestQuand, id=1228) — el plato real quedó sin renumerar, todavía como
  "V-1005".

Se confirmó por auditoría completa que estos son los ÚNICOS 2 casos en
todo el rango 4000-8143 (los otros 227 códigos esperados están bien).

Reparación (en dos pasos, para no pisar nada):
1. A los artículos de GestQuand que ocupan el código en disputa se les
   antepone el prefijo "GQ-" (mismo criterio que ya se usó para "V-42"/
   "V-1005": libera el código sin borrar ni tocar ningún otro dato del
   artículo).
2. Se renombra el plato de Viandas de su código "V-..." al código final
   que le correspondía siempre.

No crea ni borra ningún Articulo — sólo cambia el campo `codigo` de los
4 artículos involucrados. Las FK que ya apuntaban al plato de Viandas
(por ejemplo OpcionMenuDia) siguen apuntando al mismo objeto (se
relacionan por id, no por código), así que no hace falta tocar nada más:
en cuanto cambia el `codigo`, el menú semanal ya publicado queda
mostrando el código correcto solo.

Uso:
    python manage.py reparar_colision_gestquand_viandas
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from catalogo.models import Articulo

# (código en disputa, código temporal para el artículo de GestQuand, código
#  viejo "V-..." del plato de Viandas que hay que liberar hacia el código
#  en disputa)
COLISIONES = [
    ("7041", "GQ-7041", "V-42"),
    ("8005", "GQ-8005", "V-1005"),
]


class Command(BaseCommand):
    help = (
        "Repara la colisión de códigos entre 2 platos de Viandas (V-42, V-1005) y "
        "2 artículos de GestQuand que casualmente ya tenían esos mismos códigos "
        "(7041, 8005), descubierta al auditar el esquema completo 4000+/7000+/8000+."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        for codigo_final, codigo_temp_gq, codigo_viejo_vianda in COLISIONES:
            ocupante = Articulo.objects.filter(codigo=codigo_final).first()
            plato_vianda = Articulo.objects.filter(codigo=codigo_viejo_vianda).first()

            if not plato_vianda:
                # Ya se corrió este comando antes (o ya estaba bien) — nada que hacer.
                if Articulo.objects.filter(codigo=codigo_final).exclude(
                    codigo=codigo_temp_gq
                ).exists():
                    self.stdout.write(
                        f"  [{codigo_final}] ya está bien (no encontré '{codigo_viejo_vianda}' para mover)."
                    )
                continue

            if ocupante and ocupante.pk != plato_vianda.pk:
                if ocupante.codigo == codigo_temp_gq:
                    self.stdout.write(
                        f"  Ocupante de '{codigo_final}' ya estaba renombrado a '{codigo_temp_gq}'."
                    )
                else:
                    self.stdout.write(
                        f"  Libero '{codigo_final}': «{ocupante.nombre}» (GestQuand, id={ocupante.pk}) "
                        f"-> código '{codigo_temp_gq}'"
                    )
                    ocupante.codigo = codigo_temp_gq
                    ocupante.save(update_fields=["codigo"])

            self.stdout.write(
                f"  «{plato_vianda.nombre}» (id={plato_vianda.pk}): "
                f"'{codigo_viejo_vianda}' -> '{codigo_final}'"
            )
            plato_vianda.codigo = codigo_final
            plato_vianda.save(update_fields=["codigo"])

        self.stdout.write(self.style.SUCCESS("Colisión reparada."))
