from django.contrib import admin

from .models import MovimientoStock


@admin.register(MovimientoStock)
class MovimientoStockAdmin(admin.ModelAdmin):
    list_display = ("articulo", "tipo", "cantidad", "stock_anterior", "stock_posterior", "created_at")
    list_filter = ("tipo",)
    search_fields = ("articulo__nombre", "articulo__codigo", "referencia")
    autocomplete_fields = ["articulo"]
