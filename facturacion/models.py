"""
Facturación, calcada de GestQuand: comprobantes con numeración propia por
tipo y punto de venta, preparados para ARCA (antes AFIP) el día que se
implemente, turnos de caja para la venta mostrador en el local, y pagos
por comprobante (soporta pagos mixtos).

No se reimplementa acá el detalle de la integración con ARCA (WSAA/WSFEv1)
— eso, como en GestQuand, se deja para cuando Pichón tenga los
certificados. El campo `cae` queda vacío hasta entonces y `es_fiscal` en
False: el sistema puede emitir "TK" (ticket no fiscal) y facturas
manuales mientras tanto.
"""

from django.conf import settings
from django.db import models

from catalogo.models import Articulo
from clientes.models import Cliente


class TipoComprobante(models.TextChoices):
    FA_A = "FA_A", "Factura A"
    FA_B = "FA_B", "Factura B"
    FA_C = "FA_C", "Factura C"
    NC_A = "NC_A", "Nota de Crédito A"
    NC_B = "NC_B", "Nota de Crédito B"
    NC_C = "NC_C", "Nota de Crédito C"
    ND_A = "ND_A", "Nota de Débito A"
    ND_B = "ND_B", "Nota de Débito B"
    ND_C = "ND_C", "Nota de Débito C"
    NP = "NP", "Nota de Pedido (no fiscal)"
    TK = "TK", "Ticket (no fiscal)"


# Códigos ARCA por tipo (mismo mapeo que TIPO_COMPROBANTE en config.py de GestQuand)
TIPO_COD_ARCA = {
    "FA_A": 1, "FA_B": 6, "FA_C": 11,
    "NC_A": 3, "NC_B": 8, "NC_C": 13,
    "ND_A": 2, "ND_B": 7, "ND_C": 12,
}


class EstadoTurno(models.TextChoices):
    ABIERTO = "ABIERTO", "Abierto"
    CERRADO = "CERRADO", "Cerrado"


class Turno(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="turnos")
    fecha_apertura = models.DateTimeField(auto_now_add=True)
    fecha_cierre = models.DateTimeField(null=True, blank=True)
    monto_inicial = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    monto_cierre = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_efectivo = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_tarjeta = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_qr = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_ventas = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    observaciones = models.TextField(blank=True)
    estado = models.CharField(max_length=10, choices=EstadoTurno.choices, default=EstadoTurno.ABIERTO)

    class Meta:
        verbose_name = "Turno de caja"
        verbose_name_plural = "Turnos de caja"
        ordering = ["-fecha_apertura"]

    def __str__(self):
        return f"Turno #{self.pk} — {self.usuario} ({self.get_estado_display()})"


class Comprobante(models.Model):
    tipo = models.CharField(max_length=10, choices=TipoComprobante.choices)
    punto_venta = models.PositiveSmallIntegerField(default=1)
    numero = models.BigIntegerField()
    fecha = models.DateField(auto_now_add=True)

    cliente = models.ForeignKey(
        Cliente, on_delete=models.PROTECT, null=True, blank=True, related_name="comprobantes"
    )
    cliente_tipo_doc = models.CharField(max_length=10, default="CF")
    cliente_nro_doc = models.CharField(max_length=20, default="0")
    cliente_nombre = models.CharField(max_length=200, default="Consumidor Final")

    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    descuento_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    descuento_monto = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    neto_gravado = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    iva_105 = models.DecimalField("IVA 10.5%", max_digits=12, decimal_places=2, default=0)
    iva_21 = models.DecimalField("IVA 21%", max_digits=12, decimal_places=2, default=0)
    iva_27 = models.DecimalField("IVA 27%", max_digits=12, decimal_places=2, default=0)
    otros_tributos = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # ARCA (antes AFIP) — se completa cuando se implemente la integración fiscal
    cae = models.CharField(max_length=20, blank=True)
    cae_vto = models.DateField(null=True, blank=True)
    es_fiscal = models.BooleanField(default=False)

    comp_asociado = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="notas_asociadas",
        help_text="Comprobante original al que corresponde esta NC/ND",
    )

    turno = models.ForeignKey(
        Turno, on_delete=models.PROTECT, null=True, blank=True, related_name="comprobantes"
    )
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="comprobantes")
    anulado = models.BooleanField(default=False)
    observaciones = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Comprobante"
        verbose_name_plural = "Comprobantes"
        ordering = ["-fecha", "-numero"]
        unique_together = ("tipo", "punto_venta", "numero")

    def __str__(self):
        return f"{self.get_tipo_display()} {self.punto_venta:04d}-{self.numero:08d}"

    @property
    def tipo_cod_arca(self):
        return TIPO_COD_ARCA.get(self.tipo)


class ComprobanteItem(models.Model):
    comprobante = models.ForeignKey(Comprobante, on_delete=models.CASCADE, related_name="items")
    articulo = models.ForeignKey(Articulo, on_delete=models.PROTECT, null=True, blank=True)
    codigo = models.CharField(max_length=50, blank=True)
    descripcion = models.CharField(max_length=255)
    cantidad = models.DecimalField(max_digits=12, decimal_places=3, default=1)
    precio_unit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    alicuota_iva = models.DecimalField(max_digits=5, decimal_places=2, default=21)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    iva_monto = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    observaciones = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "Ítem de comprobante"
        verbose_name_plural = "Ítems de comprobante"

    def __str__(self):
        return f"{self.cantidad} × {self.descripcion}"


class MedioPago(models.TextChoices):
    EFECTIVO = "EFECTIVO", "Efectivo"
    TARJETA_DEBITO = "TARJETA_DEBITO", "Tarjeta de débito"
    TARJETA_CREDITO = "TARJETA_CREDITO", "Tarjeta de crédito"
    QR = "QR", "QR / Mercado Pago"
    CUENTA_CORRIENTE = "CUENTA_CORRIENTE", "Cuenta corriente"


class Pago(models.Model):
    comprobante = models.ForeignKey(Comprobante, on_delete=models.CASCADE, related_name="pagos")
    medio = models.CharField(max_length=20, choices=MedioPago.choices)
    monto = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    referencia = models.CharField(
        max_length=100, blank=True, help_text="Nro de tarjeta, nro de operación de MP, etc."
    )
    cuotas = models.PositiveSmallIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Pago"
        verbose_name_plural = "Pagos"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_medio_display()} — ${self.monto}"


class Numeracion(models.Model):
    tipo = models.CharField(max_length=10, choices=TipoComprobante.choices)
    punto_venta = models.PositiveSmallIntegerField(default=1)
    ultimo_numero = models.BigIntegerField(default=0)

    class Meta:
        verbose_name = "Numeración"
        verbose_name_plural = "Numeraciones"
        unique_together = ("tipo", "punto_venta")

    def __str__(self):
        return f"{self.get_tipo_display()} PV{self.punto_venta:04d} — último: {self.ultimo_numero}"

    def siguiente_numero(self):
        """Reserva y devuelve el próximo número. Usar dentro de una transacción
        con select_for_update() para evitar números duplicados en concurrencia."""
        self.ultimo_numero += 1
        self.save(update_fields=["ultimo_numero"])
        return self.ultimo_numero


class TipoMovimientoCaja(models.TextChoices):
    INGRESO = "INGRESO", "Ingreso"
    EGRESO = "EGRESO", "Egreso"


class CajaMovimiento(models.Model):
    turno = models.ForeignKey(Turno, on_delete=models.PROTECT, related_name="movimientos")
    tipo = models.CharField(max_length=10, choices=TipoMovimientoCaja.choices)
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    concepto = models.CharField(max_length=255, blank=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Movimiento de caja"
        verbose_name_plural = "Movimientos de caja"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_tipo_display()} ${self.monto} — {self.concepto}"


class ZonaSalon(models.Model):
    """Zona física del salón donde están ubicadas las mesas (ej. 'Interior',
    'Terraza') -- separado a propósito de `catalogo.Sector` (que es a dónde
    se manda a imprimir cada plato, cocina/barra, no dónde está la mesa).
    Se usa para las pestañas del mapa de mesas en el cliente local."""

    nombre = models.CharField(max_length=50, unique=True)
    orden = models.PositiveSmallIntegerField(default=0)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Zona del salón"
        verbose_name_plural = "Zonas del salón"
        ordering = ["orden", "nombre"]

    def __str__(self):
        return self.nombre


class EstadoMesa(models.TextChoices):
    LIBRE = "LIBRE", "Libre"
    OCUPADA = "OCUPADA", "Ocupada"
    CUENTA_PEDIDA = "CUENTA_PEDIDA", "Cuenta pedida"
    RESERVADA = "RESERVADA", "Reservada"


class FormaMesa(models.TextChoices):
    CUADRADA = "CUADRADA", "Cuadrada"
    REDONDA = "REDONDA", "Redonda"


class Mesa(models.Model):
    """Mesa física del local (consumo en el salón). Se abre al sentarse la
    primera persona y se va acumulando pedido (MesaItem) hasta que se cobra
    -- ahí se convierte todo en un Comprobante real (igual que una venta de
    mostrador) y la mesa vuelve a quedar LIBRE.

    `zona`, `forma`, `ancho`, `alto`, `pos_x`, `pos_y` y `capacidad` son
    para el mapa visual de mesas del cliente local (arrastrable, por
    pestaña de zona) -- `pos_x`/`pos_y` los actualiza la app cuando alguien
    mueve la mesa en "Modo edición", no hace falta tocarlos acá salvo para
    dejar una posición inicial razonable."""

    numero = models.PositiveSmallIntegerField(unique=True)
    nombre = models.CharField(max_length=50, blank=True, help_text="Ej. 'Mesa 3', 'Barra', 'Terraza 1'.")
    estado = models.CharField(max_length=20, choices=EstadoMesa.choices, default=EstadoMesa.LIBRE)
    zona = models.ForeignKey(
        ZonaSalon, on_delete=models.PROTECT, null=True, blank=True, related_name="mesas",
        help_text="Zona del salón (pestaña en el mapa de mesas). Sin asignar, la mesa no aparece en ningún mapa.",
    )
    capacidad = models.PositiveSmallIntegerField(default=4, help_text="Cantidad de comensales.")
    forma = models.CharField(max_length=10, choices=FormaMesa.choices, default=FormaMesa.CUADRADA)
    ancho = models.PositiveSmallIntegerField(default=110, help_text="Ancho en píxeles en el mapa de mesas.")
    alto = models.PositiveSmallIntegerField(default=90, help_text="Alto en píxeles en el mapa de mesas.")
    pos_x = models.PositiveSmallIntegerField(default=20, help_text="Posición X en el mapa de mesas.")
    pos_y = models.PositiveSmallIntegerField(default=20, help_text="Posición Y en el mapa de mesas.")
    turno = models.ForeignKey(
        Turno, on_delete=models.SET_NULL, null=True, blank=True, related_name="mesas",
        help_text="Turno de caja en el que se abrió (para poder auditar/cerrar todo junto).",
    )
    usuario_apertura = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="mesas_abiertas"
    )
    fecha_apertura = models.DateTimeField(null=True, blank=True)
    observaciones = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "Mesa"
        verbose_name_plural = "Mesas"
        ordering = ["numero"]

    def __str__(self):
        return self.nombre or f"Mesa {self.numero}"


class MesaItem(models.Model):
    """Línea de pedido acumulada en una mesa mientras está OCUPADA. Al
    cobrar la mesa, estas líneas se copian a ComprobanteItem y se borran de
    acá (el registro permanente queda en el Comprobante, no acá)."""

    mesa = models.ForeignKey(Mesa, on_delete=models.CASCADE, related_name="items")
    articulo = models.ForeignKey(Articulo, on_delete=models.PROTECT)
    descripcion = models.CharField(max_length=255, blank=True)
    cantidad = models.DecimalField(max_digits=12, decimal_places=3, default=1)
    precio_unit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    sectores_enviados = models.CharField(
        max_length=200, blank=True, default="",
        help_text="Sectores (separados por coma) a los que ya se mandó a imprimir esta línea -- "
                   "un artículo puede ir a más de un sector (ej. Cocina y Barra), y cada uno se "
                   "manda por separado para no reimprimir lo que ya salió.",
    )
    observaciones = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Ítem de mesa"
        verbose_name_plural = "Ítems de mesa"
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.cantidad} × {self.descripcion or self.articulo}"


class ConfigImpresora(models.Model):
    """Mapea un Sector (catalogo.Sector -- el mismo que se tilda en cada
    artículo, ej. Cocina/Barra) al nombre real de la impresora en Windows,
    por punto de venta -- el día que haya más de una terminal, cada una
    puede tener impresoras físicas distintas conectadas aunque el sector
    se llame igual."""

    sector = models.ForeignKey("catalogo.Sector", on_delete=models.CASCADE, related_name="impresoras")
    punto_venta = models.PositiveSmallIntegerField(default=1)
    nombre_windows = models.CharField(
        max_length=150, blank=True,
        help_text="Nombre exacto de la impresora tal como figura en Windows (Dispositivos e impresoras).",
    )
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Configuración de impresora"
        verbose_name_plural = "Configuración de impresoras"
        unique_together = ("sector", "punto_venta")
        ordering = ["punto_venta", "sector__nombre"]

    def __str__(self):
        return f"{self.sector} (PV{self.punto_venta}) → {self.nombre_windows or 'sin asignar'}"
