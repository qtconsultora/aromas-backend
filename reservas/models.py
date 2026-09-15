"""
Reservas — no existe equivalente en GestQuand (es un comercio sin
atención en mesas ni eventos), así que este módulo es nuevo para Aromas.
Cubre las dos cosas que pidió Pichón: reservar una fecha para un servicio
de catering/evento, y reservar mesa para consumir en el local (Dorrego
1519, línea café/venta directa).
"""

from django.db import models

from clientes.models import Cliente, Direccion


class EstadoReserva(models.TextChoices):
    CONSULTADA = "CONSULTADA", "Consultada (a confirmar)"
    CONFIRMADA = "CONFIRMADA", "Confirmada"
    SENADA = "SENADA", "Confirmada con seña"
    CANCELADA = "CANCELADA", "Cancelada"
    REALIZADA = "REALIZADA", "Realizada"


class ReservaEvento(models.Model):
    """Reserva de una fecha para un servicio de catering/evento (coffee
    break, cumpleaños, empresa, etc.) — se hace ANTES de armar el pedido
    de catering en sí; cuando se confirma el detalle, se linkea el Pedido."""

    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="reservas_evento")
    tipo_evento = models.CharField(
        max_length=100, blank=True, help_text="Ej. Coffee break, cumpleaños, evento de empresa"
    )
    fecha_evento = models.DateField()
    hora_evento = models.TimeField(null=True, blank=True)
    cantidad_personas = models.PositiveIntegerField(null=True, blank=True)

    en_el_local = models.BooleanField(
        default=False, help_text="Desmarcado = el evento es en la dirección del cliente/otro lugar"
    )
    direccion = models.ForeignKey(
        Direccion, on_delete=models.SET_NULL, null=True, blank=True, related_name="reservas_evento",
        help_text="Dirección del evento, si no es en el local",
    )
    lugar_referencia = models.CharField(
        max_length=255, blank=True, help_text="Nombre del salón/oficina, referencia, etc."
    )

    sena = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    estado = models.CharField(max_length=12, choices=EstadoReserva.choices, default=EstadoReserva.CONSULTADA)

    pedido = models.ForeignKey(
        "pedidos.Pedido", on_delete=models.SET_NULL, null=True, blank=True, related_name="reserva_evento",
        help_text="Se completa cuando la reserva se convierte en un pedido de catering concreto",
    )

    observaciones = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Reserva de evento/catering"
        verbose_name_plural = "Reservas de evento/catering"
        ordering = ["fecha_evento", "hora_evento"]

    def __str__(self):
        return f"{self.fecha_evento} — {self.cliente} ({self.get_estado_display()})"


class ReservaMesa(models.Model):
    """Reserva de mesa para consumir en el local (café / venta directa)."""

    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="reservas_mesa")
    fecha = models.DateField()
    hora = models.TimeField()
    cantidad_personas = models.PositiveSmallIntegerField(default=2)
    zona_mesa = models.CharField(max_length=50, blank=True, help_text="Ej. Salón, vereda, mesa 4")
    estado = models.CharField(
        max_length=12,
        choices=[
            (EstadoReserva.CONFIRMADA, "Confirmada"),
            (EstadoReserva.CANCELADA, "Cancelada"),
            (EstadoReserva.REALIZADA, "Realizada"),
        ],
        default=EstadoReserva.CONFIRMADA,
    )
    observaciones = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Reserva de mesa"
        verbose_name_plural = "Reservas de mesa"
        ordering = ["fecha", "hora"]

    def __str__(self):
        return f"{self.fecha} {self.hora} — {self.cliente} ({self.cantidad_personas}p)"
