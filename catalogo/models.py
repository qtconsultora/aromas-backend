"""
Catálogo de Aromas, con la idea central tomada de GestQuand: un único
modelo Articulo para TODO (ingredientes, platos elaborados, productos de
venta directa), diferenciado por el campo `tipo`. Esto reemplaza el
esquema anterior (ProductoVianda/ProductoCatering/ProductoCafe separados
por herencia), que no dejaba lugar para modelar ingredientes ni costear
recetas de verdad.

Igual que en GestQuand:
- unidad_compra / unidad_uso / relacion_unidades resuelven el caso "compro
  un bidón de 5L pero uso la receta en cc": costo_uso = precio_costo /
  relacion_unidades se calcula en código, nunca se guarda en la base.
- Receta es una tabla de composición (auto-relacionada a través de
  Articulo): un articulo "elaborado" está hecho de N insumos, cada uno
  con su cantidad. El costo de un elaborado es la suma de
  cantidad * costo_uso de cada insumo.
- Precio sugerido = costo * (1 + IVA%/100) * (1 + Markup%/100). Es sólo
  una referencia: precio_venta lo edita el usuario y es lo que se usa
  siempre para vender.

Lo que sí es específico de Aromas (no existe en GestQuand, que es un
comercio genérico sin menú rotativo) es MenuSemanal/OpcionMenuDia, que se
mantiene tal cual estaba: ahora el "plato" de cada opción es un Articulo
(tipo elaborado o venta) en vez de un ProductoVianda aparte.
"""

from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.core.exceptions import ValidationError
from django.db import models


class LineaNegocio(models.TextChoices):
    VIANDAS = "VIANDAS", "Viandas"
    CATERING = "CATERING", "Catering / Finger food"
    CAFE = "CAFE", "Café / venta directa"
    INSUMOS = "INSUMOS", "Insumos (no se vende, sólo recetas)"


class Unidad(models.Model):
    nombre = models.CharField(max_length=50, unique=True)
    abreviatura = models.CharField(max_length=10, blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Unidad"
        verbose_name_plural = "Unidades"
        ordering = ["nombre"]

    def __str__(self):
        return self.abreviatura or self.nombre


class Categoria(models.Model):
    linea_negocio = models.CharField(max_length=10, choices=LineaNegocio.choices)
    nombre = models.CharField(max_length=100)
    markup_pct = models.DecimalField(
        max_digits=8, decimal_places=2, default=0,
        help_text="Markup por defecto de los artículos de esta categoría",
    )
    orden = models.PositiveSmallIntegerField(default=0)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Categoría"
        verbose_name_plural = "Categorías"
        ordering = ["linea_negocio", "orden", "nombre"]
        unique_together = ("linea_negocio", "nombre")

    def __str__(self):
        return f"{self.nombre} ({self.get_linea_negocio_display()})"


class Marca(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    markup_pct = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Marca"
        verbose_name_plural = "Marcas"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class TipoArticulo(models.TextChoices):
    VENTA = "VENTA", "Venta (se vende, también puede usarse como insumo)"
    INSUMO = "INSUMO", "Insumo (sólo para recetas, no se vende suelto)"
    ELABORADO = "ELABORADO", "Elaborado (tiene receta, se vende)"


def calcular_precio_sugerido(costo, iva_pct, markup_pct):
    """Precio final = costo * (1 + IVA%/100) * (1 + Markup%/100). Igual que en GestQuand.

    Ojo: no usar `or 0` acá -- un IVA o markup en 0 (legítimo, ej. artículos
    exentos) es un Decimal("0") "falsy", y `Decimal("0") or 0` da el int 0,
    lo que después mezcla Decimal con float en la división y rompe.
    """
    from decimal import Decimal

    costo = costo if costo is not None else Decimal("0")
    iva_pct = iva_pct if iva_pct is not None else Decimal("0")
    markup_pct = markup_pct if markup_pct is not None else Decimal("0")
    con_iva = costo * (1 + iva_pct / 100)
    return con_iva * (1 + markup_pct / 100)


class Sector(models.Model):
    """Un destino de impresión de comanda (Cocina, Barra, etc.). Es la
    fuente única de sectores: de acá salen tanto los checks de "dónde
    imprime" de cada artículo (Articulo.sectores_impresion) como el mapeo
    a impresora de Windows por terminal (facturacion.ConfigImpresora). El
    nombre reservado "TICKET" identifica la impresora de mostrador para el
    comprobante final -- no se ofrece como opción tildable en un artículo."""

    nombre = models.CharField(max_length=30, unique=True)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Sector de impresión"
        verbose_name_plural = "Sectores de impresión"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Articulo(models.Model):
    codigo = models.CharField(max_length=50, unique=True, null=True, blank=True)
    codigo_barras = models.CharField(max_length=50, blank=True)
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True)

    categoria = models.ForeignKey(
        Categoria, on_delete=models.PROTECT, related_name="articulos"
    )
    marca = models.ForeignKey(
        Marca, on_delete=models.SET_NULL, null=True, blank=True, related_name="articulos"
    )

    # Unidad de compra (ej. bidón, caja) vs. unidad de uso (ej. cc, gramo).
    # Si no se usa conversión (la mayoría de los productos vendidos por
    # unidad), unidad_compra = unidad_uso y relacion_unidades = 1.
    unidad_compra = models.ForeignKey(
        Unidad, on_delete=models.PROTECT, related_name="articulos_compra"
    )
    unidad_uso = models.ForeignKey(
        Unidad, on_delete=models.PROTECT, related_name="articulos_uso"
    )
    relacion_unidades = models.DecimalField(
        max_digits=12, decimal_places=4, default=1,
        help_text="Cuántas unidades de uso trae la unidad de compra (ej. bidón 5L = 5000 cc)",
    )

    tipo = models.CharField(max_length=10, choices=TipoArticulo.choices, default=TipoArticulo.VENTA)

    precio_costo = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text="Costo de la unidad de COMPRA (precio del proveedor). Para un "
                   "Elaborado con receta cargada, este valor se recalcula solo a "
                   "partir del costo real de los ingredientes al guardar -- no se "
                   "edita a mano.",
    )
    precio_venta = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text="Precio final editable. El sugerido es sólo una referencia.",
    )
    alicuota_iva = models.DecimalField(max_digits=5, decimal_places=2, default=21)
    markup_pct = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    stock_actual = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    stock_minimo = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    controla_stock = models.BooleanField(default=True)

    imagen = models.ImageField(upload_to="articulos/", blank=True, null=True)
    visible_web = models.BooleanField(
        "Publicado (visible en la web)",
        default=False,
        help_text="Con esto tildado y 'Activo' tildado, el artículo aparece en el catálogo "
                   "público (Catering / Viandas a la carta) apenas guardás. No aplica a la "
                   "vianda del día/semana -- eso se controla agregando el plato como opción "
                   "dentro de un Menú Semanal marcado 'Activo'.",
    )
    descripcion_web = models.TextField(blank=True)

    requiere_consulta = models.BooleanField(
        default=False,
        help_text="El precio/disponibilidad se confirma por WhatsApp (catering a medida, etc.)",
    )
    es_vegetariano = models.BooleanField(
        default=False, help_text="Sólo relevante para platos de la línea Viandas"
    )
    unidades_por_presentacion = models.PositiveIntegerField(
        default=1,
        help_text="Para catering: cuántas piezas trae la presentación mínima de venta "
                   "(ej. una bandeja de 12 empanaditas). En el resto de las líneas queda en 1.",
    )
    ingredientes_texto = models.TextField(
        blank=True,
        help_text="Referencia libre (ingredientes tal como figuraban en el catálogo viejo, "
                   "antes de tener recetas reales con cantidades). No se usa para costear.",
    )
    sectores_impresion = models.ManyToManyField(
        "Sector", blank=True, related_name="articulos", verbose_name="Sectores de impresión",
        help_text="Tildá a qué sector(es) de cocina/barra se manda la comanda de este artículo "
                   "al venderlo (se puede tildar más de uno, ej. Cocina y Barra a la vez). Sin "
                   "tildar ninguno = no imprime comanda aparte, sólo queda en el ticket (ej. una "
                   "gaseosa envasada, o una vianda para llevar).",
    )

    activo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Artículo"
        verbose_name_plural = "Artículos"
        ordering = ["categoria", "nombre"]

    def __str__(self):
        return f"{self.codigo + ' ' if self.codigo else ''}{self.nombre}"

    def clean(self):
        if self.relacion_unidades and self.relacion_unidades <= 0:
            raise ValidationError("La relación de unidades tiene que ser mayor a 0.")

    @property
    def costo_uso(self):
        """Costo por unidad de USO — lo que se usa en recetas (nunca precio_costo directo)."""
        relacion = self.relacion_unidades or 1
        return (self.precio_costo or 0) / relacion

    @property
    def costo_receta(self):
        """Sólo tiene sentido para tipo=ELABORADO: suma de cantidad * costo_uso de cada insumo."""
        total = 0
        for item in self.receta_items.select_related("insumo"):
            total += item.cantidad * item.insumo.costo_uso
        return total

    @property
    def costo_para_precio(self):
        """El costo que corresponde usar para sugerir precio: costo_receta si es
        elaborado (y tiene ingredientes cargados), costo_uso en cualquier otro caso."""
        if self.tipo == TipoArticulo.ELABORADO and self.receta_items.exists():
            return self.costo_receta
        return self.costo_uso

    @property
    def precio_sugerido(self):
        return calcular_precio_sugerido(self.costo_para_precio, self.alicuota_iva, self.markup_pct)

    @property
    def pct_ganancia(self):
        """% de ganancia entre precio_costo (o costo_para_precio si no hay
        precio_costo cargado) y precio_venta. Sólo informativo."""
        base = self.precio_costo if self.precio_costo else self.costo_para_precio
        if not self.precio_venta or not base:
            return 0
        return (self.precio_venta - base) / self.precio_venta * 100

    def sincronizar_precio_costo_desde_receta(self, guardar=True):
        """Para un ELABORADO con receta cargada: pone `precio_costo` en línea
        con el costo real de los ingredientes (`costo_receta`), multiplicado
        por `relacion_unidades` para que `costo_uso` termine dando lo mismo
        que `costo_receta`. Se llama después de guardar los ítems de receta
        (el admin lo hace solo); devuelve True si hubo que actualizar algo.
        No hace nada si el artículo no es ELABORADO o todavía no tiene
        ingredientes cargados -- en ese caso `precio_costo` se sigue
        cargando a mano, como cualquier insumo.

        De paso, detecta qué insumo(s) de la receta subieron de costo desde
        la última vez (comparando contra el snapshot guardado en cada
        Receta.costo_uso_insumo_anterior) y, si el costo total del elaborado
        terminó subiendo, deja registrado un HistorialCostoArticulo para que
        aparezca en el listado de "aumentos de costo" del admin."""
        if self.tipo != TipoArticulo.ELABORADO or not self.receta_items.exists():
            return False

        ingredientes_que_subieron = []
        for item in self.receta_items.select_related("insumo").all():
            # Cuantizo a la misma precisión que guarda el campo (4 decimales):
            # costo_uso sale de una división que puede dar decimal periódico
            # (ej. dividir por 2900), así que comparar el valor "crudo" contra
            # lo que quedó guardado la vez anterior detecta un "aumento"
            # falso por puro redondeo, incluso cuando el insumo no cambió.
            costo_actual = item.insumo.costo_uso.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
            anterior = item.costo_uso_insumo_anterior
            if anterior is not None and costo_actual > anterior:
                ingredientes_que_subieron.append(item.insumo.nombre)
            if costo_actual != anterior:
                item.costo_uso_insumo_anterior = costo_actual
                item.save(update_fields=["costo_uso_insumo_anterior"])

        nuevo_precio_costo = (self.costo_receta * (self.relacion_unidades or 1)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        if nuevo_precio_costo != self.precio_costo:
            costo_anterior = self.precio_costo
            self.precio_costo = nuevo_precio_costo
            if guardar:
                self.save(update_fields=["precio_costo"])
            if nuevo_precio_costo > costo_anterior:
                HistorialCostoArticulo.objects.create(
                    articulo=self,
                    ingrediente_detalle=", ".join(ingredientes_que_subieron) or "receta (varios insumos)",
                    costo_anterior=costo_anterior,
                    costo_nuevo=nuevo_precio_costo,
                    precio_venta_al_momento=self.precio_venta,
                )
            return True
        return False


class Receta(models.Model):
    """Composición de un artículo elaborado. `articulo` es el elaborado que
    se vende, `insumo` es OTRO artículo (tipo insumo, o venta usado como
    insumo) que forma parte de su receta."""

    articulo = models.ForeignKey(
        Articulo, on_delete=models.CASCADE, related_name="receta_items"
    )
    insumo = models.ForeignKey(
        Articulo, on_delete=models.PROTECT, related_name="usado_en_recetas"
    )
    cantidad = models.DecimalField(max_digits=12, decimal_places=4, default=1)
    unidad = models.ForeignKey(Unidad, on_delete=models.PROTECT)
    observaciones = models.CharField(max_length=255, blank=True)
    costo_uso_insumo_anterior = models.DecimalField(
        max_digits=14, decimal_places=4, null=True, blank=True, editable=False,
        help_text="Uso interno: último costo x uso conocido del insumo, para detectar "
                   "aumentos y armar el historial de costos.",
    )

    class Meta:
        verbose_name = "Ítem de receta"
        verbose_name_plural = "Ítems de receta"
        unique_together = ("articulo", "insumo")

    def __str__(self):
        return f"{self.articulo.nombre}: {self.cantidad} {self.unidad} de {self.insumo.nombre}"

    def clean(self):
        if self.articulo_id and self.insumo_id and self.articulo_id == self.insumo_id:
            raise ValidationError("Un artículo no puede ser insumo de sí mismo.")


class HistorialCostoArticulo(models.Model):
    """Registro de cada vez que sube el `precio_costo` de un Articulo (sea un
    insumo cargado a mano en el admin, o un elaborado recalculado solo desde
    su receta). No se generan registros cuando el costo baja o no cambia --
    sólo interesa el aumento, que es lo que puede ameritar revisar el precio
    de venta.

    Se arma como un historial que el admin va "revisando" (campo `revisado`)
    en vez de compararse contra un umbral en %, porque varios aumentos
    chiquitos seguidos nunca superarían un % fijo tomados de a uno -- acá
    queda cada aumento a la vista hasta que alguien lo marca como
    revisado, sin importar cuán chico haya sido."""

    articulo = models.ForeignKey(
        Articulo, on_delete=models.CASCADE, related_name="historial_costos"
    )
    ingrediente_detalle = models.CharField(
        max_length=255, blank=True,
        help_text="Para elaborados: nombre(s) del/los insumo(s) de la receta que subieron "
                   "de costo y motivaron este aumento. Vacío para insumos cargados a mano.",
    )
    costo_anterior = models.DecimalField(max_digits=14, decimal_places=4)
    costo_nuevo = models.DecimalField(max_digits=14, decimal_places=4)
    precio_venta_al_momento = models.DecimalField(max_digits=12, decimal_places=2)
    fecha = models.DateTimeField(auto_now_add=True)
    revisado = models.BooleanField(
        default=False,
        help_text="Tildar una vez que se revisó si corresponde ajustar el precio de venta.",
    )
    revisado_fecha = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Aumento de costo"
        verbose_name_plural = "Historial de aumentos de costo"
        ordering = ["-fecha"]

    def __str__(self):
        return f"{self.articulo} · $ {self.costo_anterior} → $ {self.costo_nuevo} ({self.fecha:%d/%m/%Y})"

    @property
    def pct_aumento(self):
        if not self.costo_anterior:
            return None
        return (self.costo_nuevo - self.costo_anterior) / self.costo_anterior * 100

    @property
    def pct_ganancia_al_momento(self):
        if not self.precio_venta_al_momento:
            return None
        return (self.precio_venta_al_momento - self.costo_nuevo) / self.precio_venta_al_momento * 100


DIAS_SEMANA_HABILES = [
    ("LUN", "Lunes"),
    ("MAR", "Martes"),
    ("MIE", "Miércoles"),
    ("JUE", "Jueves"),
    ("VIE", "Viernes"),
]


class MenuSemanal(models.Model):
    """Una semana del menú de viandas (5 días x 3 opciones). Específico de
    Aromas — GestQuand no tiene equivalente porque es un comercio genérico
    sin menú rotativo."""

    fecha_inicio = models.DateField(
        unique=True, help_text="Lunes de la semana que arranca este menú"
    )
    activo = models.BooleanField(
        default=False, help_text="La semana que está publicada ahora mismo en el sitio"
    )
    notas = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = "Menú semanal"
        verbose_name_plural = "Menús semanales"
        ordering = ["-fecha_inicio"]

    def __str__(self):
        return f"Semana del {self.fecha_inicio.strftime('%d/%m/%Y')}"

    def reglas_incumplidas(self):
        """Chequea las reglas de negocio de reglas_eleccion_menus.md. Ver el
        docstring largo en la versión anterior de este archivo (git/README)
        para el detalle regla por regla; se mantiene igual que antes."""
        problemas = []
        opciones = list(
            self.opciones.select_related("plato", "plato__categoria").all()
        )
        por_dia = {}
        for op in opciones:
            por_dia.setdefault(op.dia_semana, []).append(op)

        categorias_pasta_jueves = {"PASTAS", "CREPPES"}

        for dia, _ in DIAS_SEMANA_HABILES:
            ops = sorted(por_dia.get(dia, []), key=lambda o: o.numero_opcion)
            if len(ops) != 3:
                problemas.append(f"{dia}: tiene {len(ops)} opciones cargadas (deberían ser 3)")
                continue

            categorias = [o.plato.categoria.nombre.upper() for o in ops]
            veg_flags = [getattr(o.plato, "es_vegetariano", False) for o in ops]

            if not veg_flags[2]:
                problemas.append(f"{dia}: la opción 3 no es vegetariana")
            if veg_flags[0] or veg_flags[1]:
                problemas.append(f"{dia}: hay una opción vegetariana fuera de la opción 3")
            if all(veg_flags):
                problemas.append(f"{dia}: las 3 opciones son vegetarianas")

            if dia == "JUE":
                if any(c not in categorias_pasta_jueves for c in categorias):
                    problemas.append("JUE: hay una opción que no es pasta (los jueves son sólo pastas)")
            else:
                if any("PASTA" in c for c in categorias):
                    problemas.append(f"{dia}: hay pastas fuera del jueves")

            if dia != "MAR" and any("GUISO" in c for c in categorias):
                problemas.append(f"{dia}: hay un guiso fuera del martes")

            if dia not in ("VIE", "JUE") and any("PESCADO" in c for c in categorias):
                problemas.append(f"{dia}: hay pescado antes de jueves")

            if dia == "VIE":
                minutas = sum("MINUTA" in c for c in categorias)
                if minutas != 1:
                    problemas.append(f"VIE: hay {minutas} minutas (debería haber exactamente 1)")
            elif any("MINUTA" in c for c in categorias):
                problemas.append(f"{dia}: hay una minuta fuera del viernes")

        ids_vistos = {}
        for op in opciones:
            ids_vistos.setdefault(op.plato_id, []).append(op.dia_semana)
        for plato_id, dias in ids_vistos.items():
            if len(dias) > 1:
                nombre = next(o.plato.nombre for o in opciones if o.plato_id == plato_id)
                problemas.append(f'"{nombre}" se repite esta semana ({", ".join(dias)})')

        semanas_cercanas = MenuSemanal.objects.filter(
            fecha_inicio__in=[
                self.fecha_inicio - timedelta(weeks=2),
                self.fecha_inicio - timedelta(weeks=1),
                self.fecha_inicio + timedelta(weeks=1),
            ]
        )
        platos_cercanos = set(
            OpcionMenuDia.objects.filter(menu_semanal__in=semanas_cercanas).values_list(
                "plato_id", flat=True
            )
        )
        for op in opciones:
            if op.plato_id in platos_cercanos:
                problemas.append(
                    f'"{op.plato.nombre}" ya se usó en una semana adyacente (±2 semanas)'
                )

        return problemas


class OpcionMenuDia(models.Model):
    menu_semanal = models.ForeignKey(MenuSemanal, on_delete=models.CASCADE, related_name="opciones")
    dia_semana = models.CharField(max_length=3, choices=DIAS_SEMANA_HABILES)
    numero_opcion = models.PositiveSmallIntegerField(
        choices=[(1, "Opción 1"), (2, "Opción 2"), (3, "Opción 3 (vegetariana)")]
    )
    plato = models.ForeignKey(Articulo, on_delete=models.PROTECT, related_name="apariciones_en_menu")

    class Meta:
        verbose_name = "Opción de menú del día"
        verbose_name_plural = "Opciones de menú del día"
        unique_together = ("menu_semanal", "dia_semana", "numero_opcion")
        ordering = ["menu_semanal", "dia_semana", "numero_opcion"]

    def __str__(self):
        return f"{self.menu_semanal} · {self.get_dia_semana_display()} · opción {self.numero_opcion}: {self.plato.nombre}"
