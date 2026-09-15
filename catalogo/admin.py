from django.contrib import admin
from django.utils.html import format_html

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
    fields = ("insumo", "costo_unitario_insumo_fmt", "cantidad", "unidad", "costo_item_fmt", "observaciones")
    readonly_fields = ("costo_unitario_insumo_fmt", "costo_item_fmt")

    @admin.display(description="$ x unidad del insumo")
    def costo_unitario_insumo_fmt(self, obj):
        if not obj.pk:
            return "—"
        return f"$ {obj.insumo.costo_uso:,.4f}"

    @admin.display(description="Costo de esta línea")
    def costo_item_fmt(self, obj):
        if not obj.pk:
            return "—"
        return f"$ {obj.cantidad * obj.insumo.costo_uso:,.2f}"


@admin.register(Articulo)
class ArticuloAdmin(admin.ModelAdmin):
    list_display = (
        "foto_mini", "codigo", "nombre", "categoria", "linea_negocio_fmt", "tipo",
        "precio_venta", "stock_actual", "visible_web", "activo",
    )
    list_display_links = ("codigo", "nombre")
    list_editable = ("visible_web", "activo")
    list_filter = ("categoria__linea_negocio", "categoria", "activo", "visible_web", "es_vegetariano", "tipo")
    search_fields = ("codigo", "nombre", "codigo_barras")
    autocomplete_fields = ("categoria", "marca")
    ordering = ("codigo",)
    list_per_page = 50
    inlines = [RecetaInline]
    readonly_fields = ("costo_uso_fmt", "costo_receta_fmt", "precio_sugerido_fmt", "foto_preview")
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
        ("Web", {"fields": ("foto_preview", "imagen", "visible_web", "descripcion_web")}),
        ("Viandas / Catering (si aplica)", {"fields": ("es_vegetariano", "unidades_por_presentacion", "ingredientes_texto")}),
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

    @admin.display(description="Línea", ordering="categoria__linea_negocio")
    def linea_negocio_fmt(self, obj):
        return obj.categoria.get_linea_negocio_display() if obj.categoria else "-"

    @admin.display(description="Foto")
    def foto_mini(self, obj):
        if not obj.imagen:
            return "—"
        return format_html(
            '<img src="{}" style="width:40px;height:40px;object-fit:cover;border-radius:4px;">',
            obj.imagen.url,
        )

    @admin.display(description="Vista previa de la foto actual")
    def foto_preview(self, obj):
        if not obj.imagen:
            return "Todavía no tiene foto cargada."
        return format_html(
            '<img src="{}" style="max-width:220px;max-height:220px;object-fit:cover;border-radius:8px;">',
            obj.imagen.url,
        )


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
