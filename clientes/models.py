"""
Clientes de Aromas — separado de "usuarios" (staff) tal como en GestQuand:
un Cliente es alguien que compra, no alguien que opera el sistema, así que
NO se apoya en django.contrib.auth. Tiene su propio login (ClienteAuth,
por WhatsApp o email) pensado para cuando exista el sitio con cuentas de
cliente — igual que clientes_auth en GestQuand.
"""

from django.db import models


class CondicionIVA(models.TextChoices):
    CF = "CF", "Consumidor Final"
    RI = "RI", "Responsable Inscripto"
    MONOTRIBUTO = "MONOTRIBUTO", "Monotributo"
    EXENTO = "EXENTO", "Exento"


class Cliente(models.Model):
    # Datos fiscales (para poder facturar)
    tipo_doc = models.CharField(max_length=10, default="CF")
    nro_doc = models.CharField(max_length=20, blank=True)
    razon_social = models.CharField(max_length=200, blank=True)
    nombre = models.CharField(max_length=100, blank=True)
    apellido = models.CharField(max_length=100, blank=True)
    domicilio = models.CharField(max_length=255, blank=True)
    localidad = models.CharField(max_length=100, blank=True, default="Rosario")
    provincia = models.CharField(max_length=100, blank=True, default="Santa Fe")
    cp = models.CharField(max_length=10, blank=True)
    telefono = models.CharField(max_length=30, blank=True)
    whatsapp = models.CharField(max_length=30, blank=True)
    email = models.EmailField(max_length=150, blank=True)
    condicion_iva = models.CharField(
        max_length=15, choices=CondicionIVA.choices, default=CondicionIVA.CF
    )
    observaciones = models.TextField(blank=True)

    # Web / marketing
    fecha_nacimiento = models.DateField(null=True, blank=True)
    acepta_promo = models.BooleanField(default=False)
    avatar = models.ImageField(upload_to="clientes/", blank=True, null=True)

    activo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ["apellido", "nombre"]

    def __str__(self):
        return self.razon_social or f"{self.nombre} {self.apellido}".strip() or f"Cliente #{self.pk}"


class MetodoAuth(models.TextChoices):
    WHATSAPP = "WHATSAPP", "WhatsApp"
    EMAIL = "EMAIL", "Email"


class ClienteAuth(models.Model):
    """Login del cliente para el futuro sitio (no confundir con el Cliente
    en sí, que puede existir sin nunca haberse registrado online)."""

    cliente = models.OneToOneField(Cliente, on_delete=models.CASCADE, related_name="auth")
    metodo_auth = models.CharField(max_length=10, choices=MetodoAuth.choices)
    identificador = models.CharField(
        max_length=150, unique=True, help_text="El número de WhatsApp o el email usado para loguearse"
    )
    password_hash = models.CharField(max_length=255)
    verificado = models.BooleanField(default=False)
    codigo_verificacion = models.CharField(max_length=10, blank=True)
    codigo_verificacion_exp = models.DateTimeField(null=True, blank=True)
    reset_token = models.CharField(max_length=100, blank=True)
    reset_token_exp = models.DateTimeField(null=True, blank=True)
    intentos_fallidos = models.PositiveSmallIntegerField(default=0)
    bloqueado_hasta = models.DateTimeField(null=True, blank=True)
    ultimo_login = models.DateTimeField(null=True, blank=True)
    activo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Acceso web de cliente"
        verbose_name_plural = "Accesos web de clientes"

    def __str__(self):
        return f"{self.cliente} ({self.get_metodo_auth_display()}: {self.identificador})"


class Direccion(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="direcciones")
    alias = models.CharField(max_length=50, default="Casa")
    direccion = models.CharField(max_length=255)
    localidad = models.CharField(max_length=100, blank=True, default="Rosario")
    provincia = models.CharField(max_length=100, blank=True, default="Santa Fe")
    cp = models.CharField(max_length=10, blank=True)
    referencia = models.CharField(max_length=255, blank=True)
    es_default = models.BooleanField(default=False)
    activo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Dirección"
        verbose_name_plural = "Direcciones"
        ordering = ["-es_default", "-created_at"]

    def __str__(self):
        return f"{self.direccion} ({self.alias}) — {self.cliente}"
