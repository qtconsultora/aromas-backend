from django.urls import path

from . import views

app_name = "catalogo"

urlpatterns = [
    path("menu-semanal/activo/", views.MenuSemanalActivoView.as_view(), name="menu-semanal-activo"),
    path("modalidades-venta/", views.ModalidadesVentaView.as_view(), name="modalidades-venta"),
    path("articulos/", views.ArticuloListView.as_view(), name="articulos"),
]

# No lleva el prefijo /api/catalogo/ -- se registra aparte en config/urls.py
# como /cron/alerta-costos/ para que sea una URL corta y fácil de pegar en
# el cron externo.
cron_urlpatterns = [
    path("cron/alerta-costos/", views.cron_alerta_costos, name="cron-alerta-costos"),
]
