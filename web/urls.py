from django.urls import path

from . import views

app_name = "web"

urlpatterns = [
    path("", views.ViandasView.as_view(), name="viandas"),
]
