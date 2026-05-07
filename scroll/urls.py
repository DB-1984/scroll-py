from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('entry/<int:pk>/', views.get_entry, name='get_entry'), 
    path('edit/<int:pk>/', views.edit_entry, name='edit_entry'),
    path('delete/<int:pk>/', views.delete_entry, name='delete_entry'),
    path('register/', views.register, name='register'),
    path('share/<int:pk>/', views.share_entry_email, name='share_entry'),
    path('labels/', views.labels_list, name='labels'), 
    path('weather/', views.get_weather, name='get_weather'),
    path('quote/', views.get_quote, name='get_quote'),
]