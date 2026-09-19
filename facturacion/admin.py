from django.contrib import admin

from .models import (
    CajaMovimiento,
    ConfigImpresora,
    Comprobante,
    ComprobanteItem,
    Mesa,
    MesaItem,
    ZonaSalon,
    Numeracion,
    Pago,
    Turno,
)


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


class MesaItemInline(admin.TabularInline):
    model = MesaItem
    extra = 0
    autocomplete_fields = ["articulo"]


@admin.register(ZonaSalon)
class ZonaSalonAdmin(admin.ModelAdmin):
    list_display = ("nombre", "orden", "activo")
    list_editable = ("orden", "activo")


@admin.register(Mesa)
class MesaAdmin(admin.ModelAdmin):
    list_display = ("numero", "nombre", "zona", "capacidad", "forma", "estado", "turno", "usuario_apertura", "fecha_apertura")
    list_filter = ("estado", "zona")
    list_editable = ()
    inlines = [MesaItemInline]


@admin.register(ConfigImpresora)
class ConfigImpresoraAdmin(admin.ModelAdmin):
    list_display = ("sector", "punto_venta", "nombre_windows", "activa")
    list_filter = ("sector", "punto_venta", "activa")
