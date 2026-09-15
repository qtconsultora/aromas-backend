from django.urls import path

from . import views

app_name = "web"

urlpatterns = [
    path("", views.HubView.as_view(), name="hub"),
    path("viandas/", views.ViandasView.as_view(), name="viandas"),
    path("catering/", views.CateringView.as_view(), name="catering"),
]
