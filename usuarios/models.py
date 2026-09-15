"""
Usuarios del sistema (staff que opera el negocio: admin, cajero, vendedor),
NO los clientes que compran. Se apoya en el login/password de Django
(auth.User) y sólo agrega el rol y datos propios del negocio, tal como
"usuarios" en GestQuand pero reusando la autenticación que ya trae Django
en vez de reimplementarla.
"""

from django.conf import settings
from django.db import models


class Rol(models.TextChoices):
    ADMIN = "ADMIN", "Administrador"
    CAJERO = "CAJERO", "Cajero"
    VENDEDOR = "VENDEDOR", "Vendedor"


class PerfilUsuario(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="perfil"
    )
    rol = models.CharField(max_length=10, choices=Rol.choices, default=Rol.VENDEDOR)
    telefono = models.CharField(max_length=30, blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Usuario del sistema"
        verbose_name_plural = "Usuarios del sistema"

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.get_rol_display()})"
