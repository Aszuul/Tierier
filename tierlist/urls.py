from django.urls import path

from . import views

app_name = "tierlist"
urlpatterns = [
    path('', views.index, name="index"),
    path('update_order/', views.update_order, name='update_order'),
]