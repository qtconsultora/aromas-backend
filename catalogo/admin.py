from django.contrib import admin

from .models import (
    Articulo,
    Categoria,
    Marca,
    MenuSemanal,
    OpcionMenuDia,
    Receta,
    Unidad,
)


@admin.register(Unidad)
class UnidadAdmin(admin.ModelAdmin):
    list_display = ("nombre", "abreviatura", "activo")
    search_fields = ("nombre",)


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "linea_negocio", "markup_pct", "orden", "activo")
    list_filter = ("linea_negocio",)
    search_fields = ("nombre",)


@admin.register(Marca)
class MarcaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "markup_pct", "activo")
    search_fields = ("nombre",)


class RecetaInline(admin.TabularInline):
    model = Receta
    fk_name = "articulo"
    extra = 0
    autocomplete_fields = ["insumo"]


@admin.register(Articulo)
class ArticuloAdmin(admin.ModelAdmin):
    list_display = (
        "codigo", "nombre", "categoria", "tipo", "precio_costo", "costo_uso_fmt",
        "precio_venta", "precio_sugerido_fmt", "stock_actual", "activo",
    )
    list_filter = ("tipo", "categoria", "activo", "visible_web", "es_vegetariano")
    search_fields = ("codigo", "nombre", "codigo_barras")
    inlines = [RecetaInline]
    readonly_fields = ("costo_uso_fmt", "costo_receta_fmt", "precio_sugerido_fmt")
    search_help_text = "Buscar por código o nombre"
    fieldsets = (
        (None, {"fields": ("codigo", "codigo_barras", "nombre", "descripcion", "categoria", "marca", "tipo")}),
        ("Unidades", {"fields": ("unidad_compra", "unidad_uso", "relacion_unidades")}),
        ("Precios", {"fields": (
            "precio_costo", "costo_uso_fmt", "costo_receta_fmt",
            "alicuota_iva", "markup_pct", "precio_sugerido_fmt", "precio_venta",
            "requiere_consulta",
        )}),
        ("Stock", {"fields": ("stock_actual", "stock_minimo", "controla_stock")}),
        ("Web", {"fields": ("imagen", "visible_web", "descripcion_web")}),
        ("Viandas (si aplica)", {"fields": ("es_vegetariano", "ingredientes_texto")}),
        ("Estado", {"fields": ("activo",)}),
    )

    @admin.display(description="Costo x uso")
    def costo_uso_fmt(self, obj):
        return f"$ {obj.costo_uso:,.4f}"

    @admin.display(description="Costo receta")
    def costo_receta_fmt(self, obj):
        return f"$ {obj.costo_receta:,.2f}"

    @admin.display(description="Precio sugerido")
    def precio_sugerido_fmt(self, obj):
        return f"$ {obj.precio_sugerido:,.2f}"


class OpcionMenuDiaInline(admin.TabularInline):
    model = OpcionMenuDia
    extra = 0
    autocomplete_fields = ["plato"]


@admin.register(MenuSemanal)
class MenuSemanalAdmin(admin.ModelAdmin):
    list_display = ("fecha_inicio", "activo", "notas")
    list_filter = ("activo",)
    inlines = [OpcionMenuDiaInline]
    actions = ["validar_reglas"]

    @admin.action(description="Validar reglas de negocio (reglas_eleccion_menus)")
    def validar_reglas(self, request, queryset):
        for menu in queryset:
            problemas = menu.reglas_incumplidas()
            if not problemas:
                self.message_user(request, f"{menu}: cumple todas las reglas ✅")
            else:
                self.message_user(
                    request,
                    f"{menu}: {len(problemas)} problema(s) — " + " | ".join(problemas),
                    level="WARNING",
                )
