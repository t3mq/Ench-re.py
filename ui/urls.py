"""
URLs pour l'interface utilisateur.
"""

from django.urls import path
from . import views

app_name = 'ui'

urlpatterns = [
    # Dashboard principal
    path('', views.dashboard, name='dashboard'),
    
    # Simulations
    path('simulation/new/', views.simulation_form, name='simulation_form'),
    path('simulation/list/', views.simulation_list, name='simulation_list'),
    path('simulation/<str:simulation_id>/', views.simulation_detail, name='simulation_detail'),
    path('simulation/<str:simulation_id>/download/', views.download_results, name='download_results'),
    
    # API pour AJAX
    path('api/simulation/<str:simulation_id>/status/', views.simulation_status_api, name='simulation_status_api'),
    
    # Marché
    path('market/', views.market_overview, name='market_overview'),
    path('item/<int:item_id>/', views.item_detail, name='item_detail'),
]