from django.urls import path

from . import views

app_name = "tierlist"
urlpatterns = [
    path('', views.index, name="index"),
    path('update_order/', views.update_order, name='update_order'),
    path('add_choice/', views.add_choice, name='add_choice'),
    path('add_category/', views.add_category, name='add_category'),
    path('delete_choice/<int:choice_id>/', views.delete_choice, name='delete_choice'),
    path(
        'categories/<int:category_id>/choices/<int:choice_id>/remove/',
        views.remove_category_choice,
        name='remove_category_choice',
    ),
]