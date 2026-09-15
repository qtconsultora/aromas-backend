from django.contrib import admin

from .models import ReservaEvento, ReservaMesa


@admin.register(ReservaEvento)
class ReservaEventoAdmin(admin.ModelAdmin):
    list_display = ("fecha_evento", "hora_evento", "cliente", "tipo_evento", "cantidad_personas", "en_el_local", "estado")
    list_filter = ("estado", "en_el_local")
    search_fields = ("cliente__nombre", "cliente__apellido", "cliente__razon_social", "tipo_evento")
    date_hierarchy = "fecha_evento"


@admin.register(ReservaMesa)
class ReservaMesaAdmin(admin.ModelAdmin):
    list_display = ("fecha", "hora", "cliente", "cantidad_personas", "zona_mesa", "estado")
    list_filter = ("estado",)
    search_fields = ("cliente__nombre", "cliente__apellido", "cliente__razon_social")
    date_hierarchy = "fecha"
