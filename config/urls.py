"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView
from django.views.static import serve as static_serve

from catalogo.urls import cron_urlpatterns

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/catalogo/", include("catalogo.urls")),
    path("", include(cron_urlpatterns)),
    path("api/pedidos/", include("pedidos.urls")),
    path(
        "probar-carrito/",
        TemplateView.as_view(template_name="pedidos/carrito_test.html"),
        name="probar-carrito",
    ),
    path("", include("web.urls")),
]

# Fotos de platos (Articulo.imagen). Render Starter no tiene un bucket S3
# aparte -- Django las sirve directo acá. Ojo: el disco de Render es
# efímero (se borra en cada deploy), por eso build.sh vuelve a correr
# `cargar_fotos_articulos` en cada build (es idempotente, así que no hace
# nada si las fotos ya están).
urlpatterns += [
    path(f"{settings.MEDIA_URL.lstrip('/')}<path:path>", static_serve, {"document_root": settings.MEDIA_ROOT}),
]
