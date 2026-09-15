from django.contrib import admin

from .models import (
    Carrito,
    CarritoItem,
    CarritoItemDiaSemana,
    ItemPedidoDiaSemana,
    Pedido,
    PedidoItem,
)


class CarritoItemDiaSemanaInline(admin.TabularInline):
    model = CarritoItemDiaSemana
    extra = 0
    autocomplete_fields = ["plato"]


class CarritoItemInline(admin.TabularInline):
    model = CarritoItem
    extra = 0
    autocomplete_fields = ["articulo"]
    show_change_link = True


@admin.register(Carrito)
class CarritoAdmin(admin.ModelAdmin):
    list_display = ("id", "token", "cliente", "estado", "total_estimado", "updated_at")
    list_filter = ("estado",)
    inlines = [CarritoItemInline]


@admin.register(CarritoItem)
class CarritoItemAdmin(admin.ModelAdmin):
    list_display = ("carrito", "articulo", "modalidad_venta", "cantidad", "precio_unit", "subtotal", "requiere_consulta")
    list_filter = ("modalidad_venta", "requiere_consulta")
    inlines = [CarritoItemDiaSemanaInline]


class ItemPedidoDiaSemanaInline(admin.TabularInline):
    model = ItemPedidoDiaSemana
    extra = 0
    autocomplete_fields = ["plato"]


class PedidoItemInline(admin.TabularInline):
    model = PedidoItem
    extra = 0
    autocomplete_fields = ["articulo"]
    show_change_link = True


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = (
        "id", "cliente", "estado", "origen", "tipo_entrega", "pago_estado",
        "fecha_retiro", "subtotal_items", "created_at",
    )
    list_filter = ("estado", "origen", "tipo_entrega", "pago_estado")
    search_fields = ("cliente__nombre", "cliente__apellido", "cliente__razon_social", "id")
    inlines = [PedidoItemInline]


@admin.register(PedidoItem)
class PedidoItemAdmin(admin.ModelAdmin):
    list_display = ("pedido", "articulo", "modalidad_venta", "cantidad", "precio_unit", "subtotal")
    list_filter = ("modalidad_venta",)
    inlines = [ItemPedidoDiaSemanaInline]
