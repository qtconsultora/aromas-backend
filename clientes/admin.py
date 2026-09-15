from django.contrib import admin

from .models import Cliente, ClienteAuth, Direccion


class DireccionInline(admin.TabularInline):
    model = Direccion
    extra = 0


class ClienteAuthInline(admin.StackedInline):
    model = ClienteAuth
    extra = 0
    fields = ("metodo_auth", "identificador", "verificado", "activo")
    readonly_fields = ()


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ("__str__", "nro_doc", "telefono", "whatsapp", "condicion_iva", "activo")
    list_filter = ("condicion_iva", "activo")
    search_fields = ("nombre", "apellido", "razon_social", "nro_doc", "telefono", "whatsapp", "email")
    inlines = [DireccionInline, ClienteAuthInline]


@admin.register(Direccion)
class DireccionAdmin(admin.ModelAdmin):
    list_display = ("cliente", "alias", "direccion", "localidad", "es_default")
    list_filter = ("alias", "localidad", "es_default")
    search_fields = ("direccion", "cliente__nombre", "cliente__apellido", "cliente__razon_social")
