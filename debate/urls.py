from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='debate_index'),
    path('debate/<int:pk>/', views.detail, name='debate_detail'),
    path('debate/<int:pk>/messages/', views.messages_api, name='debate_messages_api'),
]
