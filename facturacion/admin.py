from django.contrib import admin

from .models import CajaMovimiento, Comprobante, ComprobanteItem, Numeracion, Pago, Turno


class ComprobanteItemInline(admin.TabularInline):
    model = ComprobanteItem
    extra = 0
    autocomplete_fields = ["articulo"]


class PagoInline(admin.TabularInline):
    model = Pago
    extra = 0


@admin.register(Comprobante)
class ComprobanteAdmin(admin.ModelAdmin):
    list_display = ("__str__", "fecha", "cliente_nombre", "total", "es_fiscal", "anulado")
    list_filter = ("tipo", "es_fiscal", "anulado")
    search_fields = ("numero", "cliente_nombre", "cliente_nro_doc", "cae")
    inlines = [ComprobanteItemInline, PagoInline]


@admin.register(Numeracion)
class NumeracionAdmin(admin.ModelAdmin):
    list_display = ("tipo", "punto_venta", "ultimo_numero")
    list_filter = ("tipo",)


class CajaMovimientoInline(admin.TabularInline):
    model = CajaMovimiento
    extra = 0


@admin.register(Turno)
class TurnoAdmin(admin.ModelAdmin):
    list_display = ("id", "usuario", "estado", "fecha_apertura", "fecha_cierre", "total_ventas")
    list_filter = ("estado",)
    inlines = [CajaMovimientoInline]
