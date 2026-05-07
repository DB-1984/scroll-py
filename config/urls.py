from django.contrib import admin
from django.urls import path, include # Make sure include is imported

urlpatterns = [
    path('x-admin-x/', admin.site.urls),
    path('accounts/', include('allauth.urls')),
    path('', include('scroll.urls')), 
]