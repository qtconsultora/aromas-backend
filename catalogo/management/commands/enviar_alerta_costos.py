"""Manda por mail el listado de aumentos de costo todavía no revisados
(HistorialCostoArticulo con revisado=False), con el Excel adjunto.

Pensado para correr solo, disparado por un cron externo gratuito que le
pega al endpoint /cron/alerta-costos/ (ver catalogo/views.py), o a mano:

    python manage.py enviar_alerta_costos

Si no hay nada pendiente, no manda nada (para no generar spam de "todo
bien" todos los días). Si el envío de mail no está configurado
(EMAIL_HOST_USER vacío), avisa por consola y no rompe nada.
"""

from django.conf import settings
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand
from django.utils import timezone

from catalogo.admin import _exportar_historial_excel
from catalogo.models import HistorialCostoArticulo


class Command(BaseCommand):
    help = "Manda por mail el listado de aumentos de costo pendientes de revisar."

    def handle(self, *args, **options):
        pendientes = HistorialCostoArticulo.objects.filter(revisado=False).select_related("articulo")
        cantidad = pendientes.count()

        if cantidad == 0:
            self.stdout.write("No hay aumentos de costo pendientes -- no se manda nada.")
            return

        if not settings.EMAIL_HOST_USER or not settings.ALERTAS_COSTO_EMAIL:
            self.stdout.write(self.style.WARNING(
                "Hay %d aumento(s) pendiente(s) pero el envío de mail no está "
                "configurado (falta EMAIL_HOST_USER / ALERTAS_COSTO_EMAIL)." % cantidad
            ))
            return

        buffer = _exportar_historial_excel(pendientes)
        nombre = f"aumentos_costo_{timezone.localdate():%Y%m%d}.xlsx"

        asunto = f"Aromas · {cantidad} aumento(s) de costo para revisar"
        cuerpo = (
            f"Hay {cantidad} artículo(s) con aumento de costo todavía sin revisar.\n\n"
            "Adjunto va el detalle (código, descripción, ingrediente que aumentó, "
            "precio costo, precio venta y % de ganancia).\n\n"
            "Entrá al admin -> Historial de aumentos de costo para revisarlos y, "
            "si corresponde, ajustar el precio de venta a mano.\n"
        )

        email = EmailMessage(
            subject=asunto,
            body=cuerpo,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=settings.ALERTAS_COSTO_EMAIL,
        )
        email.attach(
            nombre, buffer.read(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        email.send(fail_silently=False)

        self.stdout.write(self.style.SUCCESS(
            f"Aviso mandado a {', '.join(settings.ALERTAS_COSTO_EMAIL)} ({cantidad} aumento(s))."
        ))
