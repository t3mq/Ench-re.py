"""
Vues pour l'interface utilisateur de l'application de simulation de marché.
"""

import json
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Dict, Any, List

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, Http404
from django.urls import reverse
from django.core.paginator import Paginator
from django.db.models import Sum, Count, Avg
from django.conf import settings
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
import logging

from core.models import Item
from core.utils import load_json
from market.models import Order, Transaction
from simulation.models import SimulationRun, SimulationMetric
from simulation.manager import SimulationManager
from simulation.scenarios import create_scenario
from market.engine import MarketEngine
from .forms import SimulationForm

logger = logging.getLogger(__name__)


def dashboard(request):
    """
    Vue principale du dashboard avec résumé des activités.
    """
    # Statistiques générales
    stats = {
        'total_simulations': SimulationRun.objects.count(),
        'total_transactions': Transaction.objects.aggregate(count=Count('id'))['count'] or 0,
        'total_volume': Transaction.objects.aggregate(sum=Sum('quantity'))['sum'] or 0,
        'total_value': Transaction.objects.aggregate(sum=Sum('price'))['sum'] or 0,
    }
    
    # Simulation en cours
    running_simulation = SimulationRun.objects.filter(status='running').first()
    if running_simulation:
        # Calcul du pourcentage de progression (approximatif)
        completed_steps = SimulationMetric.objects.filter(simulation=running_simulation).count()
        if running_simulation.total_steps > 0:
            running_simulation.progress_percent = (completed_steps / running_simulation.total_steps) * 100
        else:
            running_simulation.progress_percent = 0
    
    # Simulations récentes
    recent_simulations = SimulationRun.objects.all().order_by('-created_at')[:10]
    
    # Données pour le graphique (derniers 7 jours)
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=6)
    
    chart_data = {
        'labels': [],
        'transactions': []
    }
    
    for i in range(7):
        date = start_date + timedelta(days=i)
        chart_data['labels'].append(date.strftime('%d/%m'))
        
        daily_transactions = Transaction.objects.filter(
            timestamp__date=date
        ).count()
        chart_data['transactions'].append(daily_transactions)
    
    context = {
        'stats': stats,
        'running_simulation': running_simulation,
        'recent_simulations': recent_simulations,
        'chart_data': {
            'labels': json.dumps(chart_data['labels']),
            'transactions': json.dumps(chart_data['transactions'])
        }
    }
    
    return render(request, 'ui/dashboard.html', context)


def simulation_form(request):
    """
    Formulaire pour créer une nouvelle simulation.
    """
    if request.method == 'POST':
        form = SimulationForm(request.POST)
        if form.is_valid():
            try:
                # Vérification qu'aucune simulation n'est en cours
                if SimulationRun.objects.filter(status='running').exists():
                    messages.error(request, "Une simulation est déjà en cours. Attendez qu'elle se termine.")
                    return render(request, 'ui/simulation_form.html', {'form': form})
                
                # Lancement de la simulation en arrière-plan
                result = _launch_simulation(form.cleaned_data)
                
                if result['success']:
                    messages.success(request, f"Simulation lancée avec succès ! ID: {result['simulation_id']}")
                    return redirect('ui:simulation_detail', simulation_id=result['simulation_id'])
                else:
                    messages.error(request, f"Erreur lors du lancement: {result['error']}")
                    
            except Exception as e:
                logger.error(f"Erreur lors du lancement de simulation: {e}")
                messages.error(request, f"Erreur technique: {str(e)}")
        
    else:
        form = SimulationForm()
    
    return render(request, 'ui/simulation_form.html', {'form': form})


def _launch_simulation(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Lance une simulation avec la configuration donnée.
    
    Args:
        config: Configuration de la simulation
        
    Returns:
        Dict avec le résultat du lancement
    """
    try:
        # Création du SimulationRun
        sim_run = SimulationRun.objects.create(
            simulation_id=f"sim_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            scenario=config['scenario'],
            total_steps=config['n_steps'],
            total_agents=config['n_buyers'] + config['n_sellers'],
            start_time=datetime.now(),
            config=config,
            status='running'
        )
        
        # Configuration du SimulationManager
        manager = SimulationManager(
            config={
                'scenario': config['scenario'],
                'checkpoint_interval': 50,
                'output_dir': settings.SIM_OUTPUT_DIR
            }
        )
        
        # Initialisation du marché et des agents
        manager.initialize_market(n_items=config.get('n_items', 10))
        manager.create_agents(
            n_buyers=config['n_buyers'],
            n_sellers=config['n_sellers']
        )
        
        # TODO: Lancer en arrière-plan avec Celery ou threading
        # Pour l'instant, on simule un lancement réussi
        
        logger.info(f"Simulation {sim_run.simulation_id} configurée avec succès")
        
        return {
            'success': True,
            'simulation_id': sim_run.simulation_id
        }
        
    except Exception as e:
        logger.error(f"Erreur lors du lancement de simulation: {e}")
        return {
            'success': False,
            'error': str(e)
        }


def simulation_list(request):
    """
    Liste de toutes les simulations avec pagination.
    """
    simulations = SimulationRun.objects.all().order_by('-created_at')
    
    # Filtrage par statut
    status_filter = request.GET.get('status')
    if status_filter:
        simulations = simulations.filter(status=status_filter)
    
    # Pagination
    paginator = Paginator(simulations, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'status_filter': status_filter,
        'status_choices': SimulationRun._meta.get_field('status').choices
    }
    
    return render(request, 'ui/simulation_list.html', context)


def simulation_detail(request, simulation_id: str):
    """
    Détail d'une simulation avec métriques et graphiques.
    
    Args:
        simulation_id: Identifiant de la simulation
    """
    simulation = get_object_or_404(SimulationRun, simulation_id=simulation_id)
    
    # Métriques de la simulation
    metrics = SimulationMetric.objects.filter(
        simulation=simulation
    ).order_by('step_number')
    
    # Données pour les graphiques
    chart_data = {
        'steps': [m.step_number for m in metrics],
        'transactions': [m.transactions_executed for m in metrics],
        'volume': [m.total_volume for m in metrics],
        'value': [float(m.total_value) for m in metrics]
    }
    
    # Statistiques de résumé
    summary_stats = {
        'total_transactions': sum(m.transactions_executed for m in metrics),
        'total_volume': sum(m.total_volume for m in metrics),
        'total_value': sum(m.total_value for m in metrics),
        'avg_transactions_per_step': sum(m.transactions_executed for m in metrics) / len(metrics) if metrics else 0,
        'peak_volume_step': max(metrics, key=lambda x: x.total_volume).step_number if metrics else 0,
    }
    
    context = {
        'simulation': simulation,
        'metrics': metrics,
        'chart_data': {
            'steps': json.dumps(chart_data['steps']),
            'transactions': json.dumps(chart_data['transactions']),
            'volume': json.dumps(chart_data['volume']),
            'value': json.dumps(chart_data['value'])
        },
        'summary_stats': summary_stats
    }
    
    return render(request, 'ui/simulation_detail.html', context)


def market_overview(request):
    """
    Vue d'ensemble du marché avec les objets et leurs prix.
    """
    market_engine = MarketEngine()
    
    # Récupération de tous les objets
    items = Item.objects.all()
    market_data = []
    
    for item in items:
        data = market_engine.get_market_snapshot(item)
        
        # Ajout d'informations supplémentaires
        data.update({
            'category': item.get_category_display(),
            'total_supply': item.total_supply,
            'description': item.description
        })
        
        market_data.append(data)
    
    # Tri par volume décroissant
    market_data.sort(key=lambda x: x['volume_24h'], reverse=True)
    
    # Statistiques globales du marché
    market_stats = {
        'total_items': len(items),
        'total_volume_24h': sum(d['volume_24h'] for d in market_data),
        'total_value_24h': sum(d['value_24h'] for d in market_data),
        'active_items': len([d for d in market_data if d['volume_24h'] > 0]),
    }
    
    context = {
        'market_data': market_data,
        'market_stats': market_stats
    }
    
    return render(request, 'ui/market_overview.html', context)


def download_results(request, simulation_id: str):
    """
    Télécharge le fichier de résultats d'une simulation.
    
    Args:
        simulation_id: Identifiant de la simulation
    """
    simulation = get_object_or_404(SimulationRun, simulation_id=simulation_id)
    
    if not simulation.results_file_path:
        raise Http404("Fichier de résultats non trouvé")
    
    file_path = Path(simulation.results_file_path)
    
    if not file_path.exists():
        raise Http404("Fichier de résultats non trouvé sur le disque")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        response = HttpResponse(content, content_type='application/json')
        response['Content-Disposition'] = f'attachment; filename="simulation_{simulation_id}_results.json"'
        
        return response
        
    except Exception as e:
        logger.error(f"Erreur lors du téléchargement des résultats: {e}")
        messages.error(request, "Erreur lors du téléchargement du fichier")
        return redirect('ui:simulation_detail', simulation_id=simulation_id)


@require_http_methods(["GET"])
def simulation_status_api(request, simulation_id: str):
    """
    API pour récupérer le statut d'une simulation (AJAX).
    
    Args:
        simulation_id: Identifiant de la simulation
    """
    try:
        simulation = get_object_or_404(SimulationRun, simulation_id=simulation_id)
        
        # Progression
        completed_steps = SimulationMetric.objects.filter(simulation=simulation).count()
        progress_percent = (completed_steps / simulation.total_steps * 100) if simulation.total_steps > 0 else 0
        
        # Dernière métrique
        last_metric = SimulationMetric.objects.filter(
            simulation=simulation
        ).order_by('-step_number').first()
        
        data = {
            'simulation_id': simulation.simulation_id,
            'status': simulation.status,
            'progress_percent': round(progress_percent, 1),
            'completed_steps': completed_steps,
            'total_steps': simulation.total_steps,
            'is_running': simulation.status == 'running',
            'last_metric': {
                'step': last_metric.step_number if last_metric else 0,
                'transactions': last_metric.transactions_executed if last_metric else 0,
                'volume': last_metric.total_volume if last_metric else 0
            } if last_metric else None
        }
        
        return JsonResponse(data)
        
    except Exception as e:
        logger.error(f"Erreur API statut simulation: {e}")
        return JsonResponse({'error': str(e)}, status=500)


def item_detail(request, item_id: int):
    """
    Détail d'un objet de collection avec son historique de marché.
    
    Args:
        item_id: ID de l'objet
    """
    item = get_object_or_404(Item, id=item_id)
    market_engine = MarketEngine()
    
    # Données de marché
    market_data = market_engine.get_market_snapshot(item)
    
    # Carnet d'ordres
    order_book = market_engine.get_order_book(item)
    
    # Historique des transactions (dernières 50)
    transactions = Transaction.objects.filter(
        item=item
    ).order_by('-timestamp')[:50]
    
    # Données pour graphique des prix
    price_history = []
    for transaction in reversed(transactions):
        price_history.append({
            'timestamp': transaction.timestamp.isoformat(),
            'price': float(transaction.price),
            'quantity': transaction.quantity
        })
    
    context = {
        'item': item,
        'market_data': market_data,
        'order_book': order_book,
        'transactions': transactions,
        'price_history': json.dumps(price_history)
    }
    
    return render(request, 'ui/item_detail.html', context)
