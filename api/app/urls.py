from django.urls import path
from . import views

urlpatterns = [
    path('upload/', views.terraform_logs_view, name='upload_log_file'),  
    path('logs/', views.terraform_logs_view, name='get_logs'),           
    path('logs/json-bodies/', views.terraform_logs_view, name='get_json_bodies'), 
]