"""
Commande Django pour lancer une simulation de marché.

Usage:
    python manage.py run_simulation --scenario=baseline --steps=100 --agents=50
    python manage.py run_simulation --scenario=demand_x2 --steps=200 --agents=100 --seed=12345
"""

import random
from decimal import Decimal
from datetime import datetime
from typing import Optional

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db import transaction

from core.models import Item
from simulation.manager import SimulationManager
from simulation.scenarios import AVAILABLE_SCENARIOS, create_scenario
from simulation.models import SimulationRun, SimulationMetric
from market.engine import MarketEngine


class Command(BaseCommand):
    """
    Commande de gestion Django pour exécuter une simulation de marché.
    """
    
    help = 'Lance une simulation de marché avec agents-based modeling'
    
    def add_arguments(self, parser):
        """Définit les arguments de la commande."""
        parser.add_argument(
            '--scenario',
            type=str,
            default='baseline',
            choices=list(AVAILABLE_SCENARIOS.keys()),
            help=f'Scénario de simulation. Disponibles: {", ".join(AVAILABLE_SCENARIOS.keys())}'
        )
        
        parser.add_argument(
            '--steps',
            type=int,
            default=100,
            help='Nombre d\'étapes de simulation (défaut: 100)'
        )
        
        parser.add_argument(
            '--agents',
            type=int,
            default=50,
            help='Nombre total d\'agents (défaut: 50)'
        )
        
        parser.add_argument(
            '--buyers',
            type=int,
            help='Nombre d\'acheteurs (défaut: 60%% des agents)'
        )
        
        parser.add_argument(
            '--sellers',
            type=int,
            help='Nombre de vendeurs (défaut: 40%% des agents)'
        )
        
        parser.add_argument(
            '--items',
            type=int,
            default=10,
            help='Nombre d\'objets de collection (défaut: 10)'
        )
        
        parser.add_argument(
            '--seed',
            type=int,
            help='Graine aléatoire pour la reproductibilité'
        )
        
        parser.add_argument(
            '--output-dir',
            type=str,
            help=f'Répertoire de sortie (défaut: {settings.SIM_OUTPUT_DIR})'
        )
        
        parser.add_argument(
            '--checkpoint',
            type=int,
            default=50,
            help='Intervalle de sauvegarde (en étapes, défaut: 50)'
        )
        
        parser.add_argument(
            '--no-save',
            action='store_true',
            help='Ne pas sauvegarder les résultats en base de données'
        )
        
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Affichage détaillé du progrès'
        )
    
    def handle(self, *args, **options):
        """Exécute la commande."""
        try:
            # Configuration de la graine aléatoire
            if options['seed']:
                random.seed(options['seed'])
                self.stdout.write(f"Graine aléatoire définie: {options['seed']}")
            
            # Calcul du nombre d'acheteurs et vendeurs
            total_agents = options['agents']
            n_buyers = options['buyers'] or int(total_agents * 0.6)
            n_sellers = options['sellers'] or (total_agents - n_buyers)
            
            # Validation
            if n_buyers + n_sellers != total_agents:
                n_sellers = total_agents - n_buyers
                self.stdout.write(
                    self.style.WARNING(
                        f'Ajustement: {n_buyers} acheteurs, {n_sellers} vendeurs (total: {total_agents})'
                    )
                )
            
            if n_buyers <= 0 or n_sellers <= 0:
                raise CommandError("Il faut au moins un acheteur et un vendeur")
            
            # Configuration de la simulation
            config = {
                'scenario': options['scenario'],
                'checkpoint_interval': options['checkpoint'],
                'output_dir': options['output_dir'] or settings.SIM_OUTPUT_DIR
            }
            
            # Affichage de la configuration
            self._display_config(options, n_buyers, n_sellers)
            
            # Création du SimulationRun si sauvegarde activée
            simulation_run = None
            if not options['no_save']:
                simulation_run = self._create_simulation_run(options, n_buyers, n_sellers)
            
            # Initialisation du gestionnaire de simulation
            manager = SimulationManager(config=config)
            
            # Initialisation du marché
            self.stdout.write("Initialisation du marché...")
            manager.initialize_market(n_items=options['items'])
            
            # Création des agents
            self.stdout.write("Création des agents...")
            manager.create_agents(n_buyers=n_buyers, n_sellers=n_sellers)
            
            # Lancement de la simulation
            self.stdout.write(
                self.style.SUCCESS(f"Démarrage de la simulation - {options['steps']} étapes")
            )
            
            results = self._run_simulation_with_progress(
                manager, 
                options['steps'], 
                options['checkpoint'],
                simulation_run,
                options['verbose'],
                options['no_save']
            )
            
            # Finalisation
            if simulation_run and not options['no_save']:
                self._finalize_simulation_run(simulation_run, results)
            
            # Affichage des résultats
            self._display_results(results, manager)
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"Simulation terminée avec succès ! ID: {results['simulation_id']}"
                )
            )
            
        except KeyboardInterrupt:
            self.stdout.write(
                self.style.ERROR("Simulation interrompue par l'utilisateur")
            )
            return
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Erreur lors de la simulation: {e}")
            )
            raise CommandError(f"Échec de la simulation: {e}")
    
    def _display_config(self, options, n_buyers: int, n_sellers: int):
        """Affiche la configuration de la simulation."""
        self.stdout.write(
            self.style.HTTP_INFO("=== Configuration de la Simulation ===")
        )
        self.stdout.write(f"Scénario: {options['scenario']}")
        self.stdout.write(f"Étapes: {options['steps']}")
        self.stdout.write(f"Agents: {n_buyers} acheteurs + {n_sellers} vendeurs = {n_buyers + n_sellers} total")
        self.stdout.write(f"Objets: {options['items']}")
        if options['seed']:
            self.stdout.write(f"Graine: {options['seed']}")
        self.stdout.write(f"Checkpoint: toutes les {options['checkpoint']} étapes")
        self.stdout.write("")
    
    def _create_simulation_run(self, options, n_buyers: int, n_sellers: int) -> SimulationRun:
        """Crée l'enregistrement SimulationRun."""
        simulation_run = SimulationRun.objects.create(
            simulation_id=f"cmd_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            scenario=options['scenario'],
            total_steps=options['steps'],
            total_agents=n_buyers + n_sellers,
            start_time=datetime.now(),
            config={
                'n_buyers': n_buyers,
                'n_sellers': n_sellers,
                'n_items': options['items'],
                'seed': options['seed'],
                'checkpoint_interval': options['checkpoint']
            },
            status='running'
        )
        
        self.stdout.write(f"Simulation enregistrée: {simulation_run.simulation_id}")
        return simulation_run
    
    def _run_simulation_with_progress(self, manager: SimulationManager, n_steps: int,
                                    checkpoint_interval: int, simulation_run: Optional[SimulationRun],
                                    verbose: bool, no_save: bool) -> dict:
        """Exécute la simulation avec affichage du progrès."""
        
        for step in range(n_steps):
            # Exécution de l'étape
            step_metrics = manager.step()
            
            # Sauvegarde des métriques si activée
            if simulation_run and not no_save:
                self._save_step_metrics(simulation_run, step_metrics)
            
            # Affichage du progrès
            if verbose or step % 10 == 0 or step == n_steps - 1:
                progress = (step + 1) / n_steps * 100
                self.stdout.write(
                    f"Étape {step + 1:4d}/{n_steps} ({progress:5.1f}%) - "
                    f"Transactions: {step_metrics['transactions_executed']:3d} - "
                    f"Volume: {step_metrics['total_volume']:4d}",
                    ending='\r' if not verbose else '\n'
                )
            
            # Checkpoint
            if checkpoint_interval > 0 and step % checkpoint_interval == 0 and step > 0:
                manager._save_checkpoint(step)
                if verbose:
                    self.stdout.write(f"  Checkpoint sauvegardé à l'étape {step}")
        
        # Nouvelle ligne finale
        if not verbose:
            self.stdout.write("")
        
        # Génération des résultats finaux
        return manager._generate_final_results()
    
    def _save_step_metrics(self, simulation_run: SimulationRun, metrics: dict):
        """Sauvegarde les métriques d'une étape."""
        try:
            SimulationMetric.objects.create(
                simulation=simulation_run,
                step_number=metrics['step'],
                orders_created=metrics['orders_created'],
                transactions_executed=metrics['transactions_executed'],
                total_volume=metrics['total_volume'],
                total_value=Decimal(str(metrics['total_value'])),
                active_agents=metrics.get('active_buyers', 0) + metrics.get('active_sellers', 0),
                pending_orders=metrics.get('pending_orders', 0),
                execution_time=metrics.get('duration_seconds', 0) * 1000,  # en ms
                additional_data=metrics
            )
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f"Erreur lors de la sauvegarde des métriques: {e}")
            )
    
    def _finalize_simulation_run(self, simulation_run: SimulationRun, results: dict):
        """Finalise l'enregistrement de simulation."""
        try:
            simulation_run.end_time = datetime.now()
            simulation_run.duration_seconds = results.get('duration_seconds')
            simulation_run.status = 'completed'
            simulation_run.results_summary = results.get('summary_metrics', {})
            
            # Chemin du fichier de résultats
            if 'export_path' in results:
                simulation_run.results_file_path = str(results['export_path'])
            
            simulation_run.save()
            
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f"Erreur lors de la finalisation: {e}")
            )
    
    def _display_results(self, results: dict, manager: SimulationManager):
        """Affiche un résumé des résultats."""
        summary = results.get('summary_metrics', {})
        
        self.stdout.write(
            self.style.HTTP_INFO("\n=== Résultats de la Simulation ===")
        )
        
        if summary:
            self.stdout.write(f"Transactions totales: {summary.get('total_transactions', 0)}")
            self.stdout.write(f"Volume total: {summary.get('total_volume', 0)}")
            self.stdout.write(f"Valeur totale: {summary.get('total_value', 0):.2f}€")
            self.stdout.write(f"Moyenne transactions/étape: {summary.get('avg_transactions_per_step', 0):.1f}")
            
            if results.get('duration_seconds'):
                duration = results['duration_seconds']
                if duration < 60:
                    self.stdout.write(f"Durée d'exécution: {duration:.1f} secondes")
                else:
                    minutes = int(duration // 60)
                    seconds = duration % 60
                    self.stdout.write(f"Durée d'exécution: {minutes}m {seconds:.1f}s")
        
        # Chemin de sortie
        export_path = manager.export_results()
        self.stdout.write(f"Résultats exportés: {export_path}")