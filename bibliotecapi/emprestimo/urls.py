from django.urls import path
from . import views

urlpatterns = [
    path("emprestar/", views.emprestar, name="emprestar")
]