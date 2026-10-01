from django.urls import path

from . import views

app_name = "tierlist"
urlpatterns = [
    path('', views.index, name="index"),
    path('register/', views.register, name='register'),
    path('save/', views.save_draft, name='save'),
    path('palette/update/', views.update_palette, name='update_palette'),
    path('choices/<int:choice_id>/color/', views.update_choice_color, name='update_choice_color'),
    path('update_order/', views.update_order, name='update_order'),
    path('add_choice/', views.add_choice, name='add_choice'),
    path('add_category/', views.add_category, name='add_category'),
    path('update_category/<int:category_id>/', views.update_category, name='update_category'),
    path('delete_category/<int:category_id>/', views.delete_category, name='delete_category'),
    path('delete_choice/<int:choice_id>/', views.delete_choice, name='delete_choice'),
    path(
        'categories/<int:category_id>/choices/<int:choice_id>/remove/',
        views.remove_category_choice,
        name='remove_category_choice',
    ),
]