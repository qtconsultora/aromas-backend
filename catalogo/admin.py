import io

from django.contrib import admin
from django.http import HttpResponse
from django.utils import timezone
from django.utils.html import format_html

from .models import (
    Articulo,
    Categoria,
    HistorialCostoArticulo,
    Marca,
    MenuSemanal,
    OpcionMenuDia,
    Receta,
    TipoArticulo,
    Unidad,
)


def _exportar_historial_excel(queryset):
    """Arma un .xlsx en memoria con las columnas que pidió Pichón: código,
    descripción, ingrediente que aumentó, precio costo, precio venta y
    % de ganancia. Se usa tanto desde la acción del admin como desde el
    management command que manda el email periódico."""
    from openpyxl import Workbook
    from openpyxl.styles import Font

    wb = Workbook()
    ws = wb.active
    ws.title = "Aumentos de costo"
    encabezados = [
        "Código", "Descripción", "Ingrediente que aumentó",
        "Costo anterior", "Precio costo nuevo", "Precio venta",
        "% ganancia", "Fecha", "Revisado",
    ]
    ws.append(encabezados)
    for cell in ws[1]:
        cell.font = Font(bold=True)

    for h in queryset.select_related("articulo"):
        pct = h.pct_ganancia_al_momento
        ws.append([
            h.articulo.codigo or "",
            h.articulo.nombre,
            h.ingrediente_detalle or "—",
            float(h.costo_anterior),
            float(h.costo_nuevo),
            float(h.precio_venta_al_momento),
            round(float(pct), 1) if pct is not None else "",
            timezone.localtime(h.fecha).strftime("%d/%m/%Y %H:%M"),
            "Sí" if h.revisado else "No",
        ])

    for col in ws.columns:
        largo = max(len(str(c.value)) for c in col if c.value is not None)
        ws.column_dimensions[col[0].column_letter].width = min(largo + 2, 40)

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


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

    def get_readonly_fields(self, request, obj=None):
        fields = list(self.readonly_fields)
        if obj and obj.tipo == TipoArticulo.ELABORADO and obj.receta_items.exists():
            # Con receta cargada, "Precio costo" deja de ser editable a mano:
            # se recalcula solo a partir del costo real de los ingredientes
            # (ver save_related) para que nunca quede desactualizado.
            fields.append("precio_costo")
        return fields

    def save_model(self, request, obj, form, change):
        costo_anterior = None
        if change and "precio_costo" in form.changed_data:
            # Traigo el valor previo de la base (form.initial puede venir
            # vacío en algunos casos) para comparar contra lo que se acaba
            # de tipear y, si subió, dejarlo en el historial.
            previo = Articulo.objects.filter(pk=obj.pk).values_list("precio_costo", flat=True).first()
            costo_anterior = previo
        super().save_model(request, obj, form, change)
        if costo_anterior is not None and obj.precio_costo > costo_anterior:
            HistorialCostoArticulo.objects.create(
                articulo=obj,
                ingrediente_detalle="",
                costo_anterior=costo_anterior,
                costo_nuevo=obj.precio_costo,
                precio_venta_al_momento=obj.precio_venta,
            )

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        form.instance.sincronizar_precio_costo_desde_receta()

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


@admin.register(HistorialCostoArticulo)
class HistorialCostoArticuloAdmin(admin.ModelAdmin):
    """El listado de "aumentos de costo" que pidió Pichón: código, desc,
    ingrediente que aumentó, precio costo, precio venta y % de ganancia.
    Por defecto muestra sólo lo no revisado (ver get_queryset/lista);
    "Marcar como revisado" es la forma de sacar algo de esa cola una vez
    que se decidió (o no) tocar el precio de venta."""

    list_display = (
        "fecha", "codigo_fmt", "articulo", "ingrediente_detalle",
        "costo_anterior", "costo_nuevo", "precio_venta_al_momento",
        "pct_ganancia_fmt", "revisado",
    )
    list_filter = ("revisado", "fecha")
    search_fields = ("articulo__codigo", "articulo__nombre", "ingrediente_detalle")
    date_hierarchy = "fecha"
    actions = ["marcar_revisado", "exportar_excel"]
    list_per_page = 100

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related("articulo")
        # Sin filtros ni búsqueda aplicados (primer ingreso a la pantalla),
        # arranco mostrando sólo lo pendiente -- así la pantalla es directamente
        # la "cola de revisión" y no hay que acordarse de filtrar.
        if not request.GET:
            return qs.filter(revisado=False)
        return qs

    @admin.display(description="Código", ordering="articulo__codigo")
    def codigo_fmt(self, obj):
        return obj.articulo.codigo or "—"

    @admin.display(description="% ganancia")
    def pct_ganancia_fmt(self, obj):
        pct = obj.pct_ganancia_al_momento
        return f"{pct:.1f}%" if pct is not None else "—"

    @admin.action(description="Marcar como revisado")
    def marcar_revisado(self, request, queryset):
        actualizados = queryset.filter(revisado=False).update(revisado=True, revisado_fecha=timezone.now())
        self.message_user(request, f"{actualizados} aumento(s) marcado(s) como revisado.")

    @admin.action(description="Exportar a Excel")
    def exportar_excel(self, request, queryset):
        buffer = _exportar_historial_excel(queryset)
        nombre = f"aumentos_costo_{timezone.localdate():%Y%m%d}.xlsx"
        response = HttpResponse(
            buffer.read(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f'attachment; filename="{nombre}"'
        return response


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
