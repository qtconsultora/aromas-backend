from django.urls import path

from . import views

app_name = "pedidos"

urlpatterns = [
    path("carrito/", views.CarritoCreateView.as_view(), name="carrito-create"),
    path("carrito/<uuid:token>/", views.CarritoDetailView.as_view(), name="carrito-detail"),
    path("carrito/<uuid:token>/items/", views.CarritoItemListView.as_view(), name="carrito-items"),
    path("carrito/<uuid:token>/items/<int:item_id>/", views.CarritoItemDetailView.as_view(), name="carrito-item-detail"),
    path("carrito/<uuid:token>/confirmar/", views.CarritoConfirmarView.as_view(), name="carrito-confirmar"),
]
