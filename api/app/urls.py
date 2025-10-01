from django.urls import path
from . import views

urlpatterns = [
    path('upload/', views.terraform_logs_view, name='upload_log_file'),  # исправлено
    path('logs/', views.terraform_logs_view, name='get_logs'),           # исправлено
    path('logs/json-bodies/', views.terraform_logs_view, name='get_json_bodies'),  # исправлено
]