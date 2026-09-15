"""
Movimientos de stock, igual que stock_movimientos en GestQuand: cada
cambio de stock queda auditado (cuánto había antes, cuánto quedó
después), en vez de sólo pisar articulo.stock_actual.
"""

from django.conf import settings
from django.db import models

from catalogo.models import Articulo


class TipoMovimientoStock(models.TextChoices):
    INGRESO = "INGRESO", "Ingreso (compra)"
    EGRESO = "EGRESO", "Egreso"
    AJUSTE = "AJUSTE", "Ajuste de inventario"
    VENTA = "VENTA", "Venta"
    DEVOLUCION = "DEVOLUCION", "Devolución"


class MovimientoStock(models.Model):
    articulo = models.ForeignKey(Articulo, on_delete=models.PROTECT, related_name="movimientos_stock")
    tipo = models.CharField(max_length=12, choices=TipoMovimientoStock.choices)
    cantidad = models.DecimalField(max_digits=12, decimal_places=3)
    stock_anterior = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    stock_posterior = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    referencia = models.CharField(
        max_length=100, blank=True, help_text="Nro de comprobante, motivo del ajuste, etc."
    )
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Movimiento de stock"
        verbose_name_plural = "Movimientos de stock"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_tipo_display()} {self.cantidad} — {self.articulo.nombre}"

    def save(self, *args, **kwargs):
        """Al crear el movimiento, actualiza articulo.stock_actual y deja
        registrado el antes/después — igual que hace GestQuand en código
        (no con un trigger de base de datos, para poder mostrar mensajes
        claros de stock insuficiente desde la app)."""
        es_nuevo = self._state.adding
        if es_nuevo:
            self.stock_anterior = self.articulo.stock_actual
            if self.tipo == TipoMovimientoStock.AJUSTE:
                # En un ajuste, "cantidad" es el delta con signo (puede ser negativo)
                delta = self.cantidad
            elif self.tipo in (TipoMovimientoStock.EGRESO, TipoMovimientoStock.VENTA):
                delta = -abs(self.cantidad)
            else:  # INGRESO, DEVOLUCION
                delta = abs(self.cantidad)
            self.stock_posterior = self.stock_anterior + delta
        super().save(*args, **kwargs)
        if es_nuevo:
            self.articulo.stock_actual = self.stock_posterior
            self.articulo.save(update_fields=["stock_actual"])
