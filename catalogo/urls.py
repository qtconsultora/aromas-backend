from django.urls import path

from . import views

app_name = "catalogo"

urlpatterns = [
    path("menu-semanal/activo/", views.MenuSemanalActivoView.as_view(), name="menu-semanal-activo"),
    path("modalidades-venta/", views.ModalidadesVentaView.as_view(), name="modalidades-venta"),
    path("articulos/", views.ArticuloListView.as_view(), name="articulos"),
]
