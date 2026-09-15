"""
Carrito (web) y pedidos, con la forma de GestQuand (pedidos anticipados +
tablas de carrito ya pensadas para web/app) más lo específico de Aromas:
la selección de plato por día cuando el ítem es una vianda diaria/semanal.

El carrito es de INVITADO (15/09/2026, decisión de Pichón): no hace falta
loguearse ni tener cuenta de cliente para armarlo -- se identifica por
`token` (UUID que genera el propio carrito al crearse), no por sesión de
Django ni por login. El `cliente` recién se asocia al confirmar el pedido
(pedirle nombre/teléfono/dirección en ese paso, no antes). Por eso
`cliente` es null=True acá (a diferencia de Pedido, donde sí es obligatorio).
"""

import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from catalogo.models import DIAS_SEMANA_HABILES, Articulo
from clientes.models import Cliente, Direccion


class ModalidadVenta(models.TextChoices):
    VIANDA_DIARIA = "VIANDA_DIARIA", "Vianda diaria"
    VIANDA_SEMANAL = "VIANDA_SEMANAL", "Vianda semanal (5 viandas)"
    A_LA_CARTA = "A_LA_CARTA", "A la carta / venta directa"
    CATERING = "CATERING", "Catering"


class EstadoCarrito(models.TextChoices):
    ACTIVO = "ACTIVO", "Activo"
    CONVERTIDO = "CONVERTIDO", "Convertido en pedido"
    ABANDONADO = "ABANDONADO", "Abandonado"


class Carrito(models.Model):
    token = models.UUIDField(
        default=uuid.uuid4, unique=True, editable=False,
        help_text="Lo guarda el frontend (localStorage) para identificar el carrito sin login.",
    )
    cliente = models.ForeignKey(
        Cliente, on_delete=models.CASCADE, related_name="carritos", null=True, blank=True,
        help_text="Se completa recién al confirmar el pedido -- el carrito arranca de invitado.",
    )
    estado = models.CharField(max_length=12, choices=EstadoCarrito.choices, default=EstadoCarrito.ACTIVO)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Carrito"
        verbose_name_plural = "Carritos"
        ordering = ["-updated_at"]

    def __str__(self):
        quien = self.cliente or "invitado"
        return f"Carrito #{self.pk} — {quien} ({self.get_estado_display()})"

    @property
    def total_estimado(self):
        return sum((item.subtotal for item in self.items.all()), Decimal("0"))


class CarritoItem(models.Model):
    carrito = models.ForeignKey(Carrito, on_delete=models.CASCADE, related_name="items")
    articulo = models.ForeignKey(Articulo, on_delete=models.PROTECT)
    # Igual que en PedidoItem: qué modalidad de venta es este ítem (vianda
    # diaria/semanal necesita selecciones_dias; a la carta/catering no).
    modalidad_venta = models.CharField(
        max_length=20, choices=ModalidadVenta.choices, default=ModalidadVenta.A_LA_CARTA
    )
    descripcion = models.CharField(max_length=255, blank=True)
    cantidad = models.DecimalField(max_digits=12, decimal_places=3, default=1)
    precio_unit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    requiere_consulta = models.BooleanField(
        default=False,
        help_text="Alguno de los platos elegidos es 'a consultar' -- el precio final se confirma aparte.",
    )
    observaciones = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Ítem de carrito"
        verbose_name_plural = "Ítems de carrito"

    def __str__(self):
        return f"{self.cantidad} × {self.articulo.nombre}"

    @property
    def subtotal(self):
        return self.cantidad * self.precio_unit

    def clean(self):
        necesita_dias = self.modalidad_venta in ("VIANDA_DIARIA", "VIANDA_SEMANAL")
        if necesita_dias and self.articulo_id and self.articulo.tipo not in ("VENTA", "ELABORADO"):
            raise ValidationError("Vianda diaria/semanal necesita un artículo vendible (no un insumo).")


class CarritoItemDiaSemana(models.Model):
    """Qué plato eligió el cliente para cada día, dentro de un CarritoItem de
    modalidad 'vianda diaria' (1 día) o 'vianda semanal' (5 días). Mismo
    esquema que ItemPedidoDiaSemana -- se copia tal cual a esa tabla recién
    cuando el carrito se confirma como Pedido."""

    item_carrito = models.ForeignKey(CarritoItem, on_delete=models.CASCADE, related_name="selecciones_dias")
    dia_semana = models.CharField(max_length=3, choices=DIAS_SEMANA_HABILES)
    plato = models.ForeignKey(Articulo, on_delete=models.PROTECT, related_name="+")

    class Meta:
        verbose_name = "Selección de día (carrito)"
        verbose_name_plural = "Selecciones de día (carrito)"
        unique_together = ("item_carrito", "dia_semana")

    def __str__(self):
        return f"{self.get_dia_semana_display()}: {self.plato.nombre}"


class EstadoPedido(models.TextChoices):
    PENDIENTE = "PENDIENTE", "Pendiente"
    CONFIRMADO = "CONFIRMADO", "Confirmado"
    EN_PREPARACION = "EN_PREPARACION", "En preparación"
    LISTO = "LISTO", "Listo"
    ENTREGADO = "ENTREGADO", "Entregado"
    CANCELADO = "CANCELADO", "Cancelado"


class OrigenPedido(models.TextChoices):
    LOCAL = "LOCAL", "Cargado en el local"
    WEB = "WEB", "Sitio / WhatsApp"


class TipoEntrega(models.TextChoices):
    RETIRO = "RETIRO", "Retiro en el local"
    DELIVERY = "DELIVERY", "Envío a domicilio"


class PagoEstado(models.TextChoices):
    PENDIENTE = "PENDIENTE", "Pendiente"
    PARCIAL = "PARCIAL", "Pago parcial (seña)"
    PAGADO = "PAGADO", "Pagado"


class Pedido(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="pedidos")
    fecha_pedido = models.DateField(auto_now_add=True)
    fecha_retiro = models.DateField(null=True, blank=True)
    hora_retiro = models.TimeField(null=True, blank=True)

    estado = models.CharField(max_length=20, choices=EstadoPedido.choices, default=EstadoPedido.PENDIENTE)
    total_estimado = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    sena = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    comprobante = models.ForeignKey(
        "facturacion.Comprobante", on_delete=models.SET_NULL, null=True, blank=True, related_name="pedidos"
    )

    origen = models.CharField(max_length=10, choices=OrigenPedido.choices, default=OrigenPedido.LOCAL)
    direccion = models.ForeignKey(
        Direccion, on_delete=models.PROTECT, null=True, blank=True, related_name="pedidos"
    )
    tipo_entrega = models.CharField(max_length=10, choices=TipoEntrega.choices, default=TipoEntrega.RETIRO)
    pago_estado = models.CharField(max_length=10, choices=PagoEstado.choices, default=PagoEstado.PENDIENTE)

    whatsapp_enviado = models.BooleanField(default=False)
    observaciones = models.TextField(blank=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="pedidos_cargados"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Pedido"
        verbose_name_plural = "Pedidos"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Pedido #{self.pk} — {self.cliente} ({self.get_estado_display()})"

    def clean(self):
        if self.tipo_entrega == TipoEntrega.DELIVERY and not self.direccion_id:
            raise ValidationError("Un pedido con envío necesita una dirección de entrega.")

    @property
    def subtotal_items(self):
        return sum((item.subtotal for item in self.items.all()), Decimal("0"))


class PedidoItem(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name="items")
    articulo = models.ForeignKey(Articulo, on_delete=models.PROTECT)
    modalidad_venta = models.CharField(max_length=20, choices=ModalidadVenta.choices)
    descripcion = models.CharField(max_length=255, blank=True)
    cantidad = models.DecimalField(max_digits=12, decimal_places=3, default=1)
    # Precio copiado al momento de pedir (no cambia si después cambia el del artículo)
    precio_unit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    observaciones = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "Ítem de pedido"
        verbose_name_plural = "Ítems de pedido"

    def __str__(self):
        return f"{self.cantidad} × {self.articulo.nombre}"

    @property
    def subtotal(self):
        return self.cantidad * self.precio_unit

    def clean(self):
        necesita_dias = self.modalidad_venta in (
            ModalidadVenta.VIANDA_DIARIA,
            ModalidadVenta.VIANDA_SEMANAL,
        )
        if necesita_dias and self.articulo_id and self.articulo.tipo not in ("VENTA", "ELABORADO"):
            raise ValidationError("Vianda diaria/semanal necesita un artículo vendible (no un insumo).")


class ItemPedidoDiaSemana(models.Model):
    """Qué plato eligió el cliente para cada día, dentro de un PedidoItem de
    modalidad 'vianda diaria' (1 día) o 'vianda semanal' (5 días)."""

    item_pedido = models.ForeignKey(PedidoItem, on_delete=models.CASCADE, related_name="selecciones_dias")
    dia_semana = models.CharField(max_length=3, choices=DIAS_SEMANA_HABILES)
    plato = models.ForeignKey(Articulo, on_delete=models.PROTECT)

    class Meta:
        verbose_name = "Selección de día (vianda)"
        verbose_name_plural = "Selecciones de día (vianda)"
        unique_together = ("item_pedido", "dia_semana")

    def __str__(self):
        return f"{self.get_dia_semana_display()}: {self.plato.nombre}"
