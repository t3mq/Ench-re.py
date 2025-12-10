"""
Gestionnaire de simulation pour orchestrer les agents et le marché.
"""

import random
import time
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Any, Optional
from pathlib import Path
import logging

from django.db import transaction
from django.conf import settings

from core.models import Item
from core.utils import save_json, generate_simulation_id, SimulationTimer
from market.engine import MarketEngine
from market.models import Order, Transaction
from .agents import Agent, Buyer, Seller
from .scenarios import BaseScenario, DemandDoubleScenario

logger = logging.getLogger('simulation')


class SimulationManager:
    """
    Gestionnaire principal des simulations de marché.
    
    Responsabilités:
    - Orchestration des agents
    - Gestion des étapes de simulation
    - Collecte des métriques
    - Sauvegarde des résultats
    """
    
    def __init__(self, market_engine: Optional[MarketEngine] = None, 
                 agents: Optional[List[Agent]] = None, config: Optional[Dict[str, Any]] = None):
        """
        Initialise le gestionnaire de simulation.
        
        Args:
            market_engine: Moteur de marché à utiliser
            agents: Liste d'agents participants
            config: Configuration de la simulation
        """
        self.id = generate_simulation_id()
        self.market_engine = market_engine or MarketEngine()
        self.agents = agents or []
        self.config = config or {}
        
        # Paramètres de simulation
        self.current_step = 0
        self.start_time = None
        self.end_time = None
        self.is_running = False
        
        # Collecte de données
        self.metrics_history: List[Dict[str, Any]] = []
        self.results: Dict[str, Any] = {}
        
        # Configuration
        self.checkpoint_interval = self.config.get('checkpoint_interval', 50)
        self.output_dir = Path(self.config.get('output_dir', settings.SIM_OUTPUT_DIR))
        self.scenario = self.config.get('scenario', 'baseline')
        
        logger.info(f"Simulation {self.id} initialisée avec {len(self.agents)} agents")
    
    def add_agent(self, agent: Agent) -> None:
        """Ajoute un agent à la simulation."""
        if agent not in self.agents:
            self.agents.append(agent)
            logger.debug(f"Agent {agent.id} ajouté à la simulation")
    
    def remove_agent(self, agent_id: str) -> bool:
        """Retire un agent de la simulation."""
        for agent in self.agents:
            if agent.id == agent_id:
                self.agents.remove(agent)
                logger.debug(f"Agent {agent_id} retiré de la simulation")
                return True
        return False
    
    def initialize_market(self, n_items: int = 10) -> None:
        """
        Initialise le marché avec des objets de base.
        
        Args:
            n_items: Nombre d'objets à créer
        """
        if Item.objects.count() < n_items:
            logger.info("Création d'objets de collection pour la simulation")
            
            categories = ['cards', 'figurines', 'comics', 'toys', 'art']
            
            for i in range(n_items):
                category = random.choice(categories)
                item = Item.objects.create(
                    name=f"Objet {i+1} - {category.capitalize()}",
                    category=category,
                    edition=f"Édition {random.randint(1, 5)}",
                    total_supply=random.randint(100, 1000),
                    description=f"Objet de collection de la catégorie {category}"
                )
                logger.debug(f"Objet créé: {item}")
    
    def create_agents(self, n_buyers: int = 30, n_sellers: int = 20) -> None:
        """
        Crée des agents pour la simulation.
        
        Args:
            n_buyers: Nombre d'acheteurs à créer
            n_sellers: Nombre de vendeurs à créer
        """
        # Création des acheteurs
        for i in range(n_buyers):
            buyer = Buyer(
                agent_id=f"buyer_{i+1}",
                initial_cash=Decimal(str(random.uniform(500, 2000)))
            )
            self.add_agent(buyer)
        
        # Création des vendeurs
        for i in range(n_sellers):
            seller = Seller(
                agent_id=f"seller_{i+1}",
                initial_cash=Decimal(str(random.uniform(300, 1500)))
            )
            self.add_agent(seller)
        
        logger.info(f"Agents créés: {n_buyers} acheteurs, {n_sellers} vendeurs")
    
    def step(self) -> Dict[str, Any]:
        """
        Exécute une étape de simulation.
        
        Returns:
            Métriques de l'étape
        """
        step_start = time.time()
        orders_created = []
        transactions_created = []
        
        # Application du scénario
        self._apply_scenario()
        
        # Actions des agents
        random.shuffle(self.agents)  # Ordre aléatoire pour équité
        
        for agent in self.agents:
            try:
                order = agent.act(self.market_engine, self.current_step)
                if order:
                    # Soumission de l'ordre au marché
                    executed_order = self.market_engine.submit_order(order)
                    orders_created.append(executed_order)
                    
                    # Mise à jour de l'agent
                    agent.active_orders.append(executed_order.id)
                    agent.order_history.append(executed_order)
                    
            except Exception as e:
                logger.error(f"Erreur avec agent {agent.id}: {e}")
        
        # Matching global des ordres restants
        new_transactions = self.market_engine.match_orders()
        transactions_created.extend(new_transactions)
        
        # Mise à jour des agents après les transactions
        self._update_agents_after_transactions(transactions_created)
        
        # Collecte des métriques
        step_metrics = self._collect_step_metrics(
            orders_created, transactions_created, time.time() - step_start
        )
        
        self.metrics_history.append(step_metrics)
        self.current_step += 1
        
        return step_metrics
    
    def _apply_scenario(self) -> None:
        """Applique les effets du scénario courant."""
        scenario_obj = self._get_scenario_instance()
        if scenario_obj:
            scenario_obj.apply_step_effects(self.current_step, self.agents, self.market_engine)
    
    def _get_scenario_instance(self) -> Optional[BaseScenario]:
        """Récupère l'instance du scénario courant."""
        scenarios = {
            'baseline': BaseScenario(),
            'demand_x2': DemandDoubleScenario()
        }
        return scenarios.get(self.scenario)
    
    def _update_agents_after_transactions(self, transactions: List[Transaction]) -> None:
        """
        Met à jour les agents après les transactions.
        
        Args:
            transactions: Transactions exécutées
        """
        for transaction in transactions:
            # Mise à jour de l'acheteur
            buyer = self._find_agent(transaction.buyer_id)
            if buyer:
                buyer.add_item(transaction.item.id, transaction.quantity)
                buyer.update_cash(-transaction.total_value)
            
            # Mise à jour du vendeur
            seller = self._find_agent(transaction.seller_id)
            if seller:
                seller.remove_item(transaction.item.id, transaction.quantity)
                seller.update_cash(transaction.total_value)
    
    def _find_agent(self, agent_id: str) -> Optional[Agent]:
        """Trouve un agent par son ID."""
        for agent in self.agents:
            if agent.id == agent_id:
                return agent
        return None
    
    def _collect_step_metrics(self, orders: List[Order], transactions: List[Transaction], 
                             duration: float) -> Dict[str, Any]:
        """
        Collecte les métriques d'une étape.
        
        Args:
            orders: Ordres créés
            transactions: Transactions exécutées
            duration: Durée d'exécution
            
        Returns:
            Dict avec les métriques
        """
        # Métriques de base
        metrics = {
            'step': self.current_step,
            'timestamp': datetime.now().isoformat(),
            'duration_seconds': duration,
            'orders_created': len(orders),
            'transactions_executed': len(transactions),
            'total_volume': sum(t.quantity for t in transactions),
            'total_value': float(sum(t.total_value for t in transactions)),
        }
        
        # Métriques des agents
        buyers = [a for a in self.agents if isinstance(a, Buyer)]
        sellers = [a for a in self.agents if isinstance(a, Seller)]
        
        metrics.update({
            'active_buyers': len(buyers),
            'active_sellers': len(sellers),
            'avg_buyer_cash': float(sum(b.cash for b in buyers) / len(buyers)) if buyers else 0,
            'avg_seller_cash': float(sum(s.cash for s in sellers) / len(sellers)) if sellers else 0,
        })
        
        # Métriques du marché
        total_orders = Order.objects.filter(status__in=['PENDING', 'PARTIAL']).count()
        metrics['pending_orders'] = total_orders
        
        return metrics
    
    def run(self, n_steps: int, checkpoint_every: Optional[int] = None) -> Dict[str, Any]:
        """
        Exécute la simulation complète.
        
        Args:
            n_steps: Nombre d'étapes à exécuter
            checkpoint_every: Intervalle de sauvegarde (None = utilise config)
            
        Returns:
            Résultats finaux de la simulation
        """
        checkpoint_interval = checkpoint_every or self.checkpoint_interval
        
        with SimulationTimer(f"Simulation {self.id}"):
            self.start_time = datetime.now()
            self.is_running = True
            
            logger.info(f"Démarrage simulation {self.id} - {n_steps} étapes")
            
            try:
                for step_num in range(n_steps):
                    step_metrics = self.step()
                    
                    # Log périodique
                    if step_num % 10 == 0:
                        logger.info(f"Étape {step_num}: {step_metrics['transactions_executed']} transactions")
                    
                    # Checkpoint périodique
                    if checkpoint_interval > 0 and step_num % checkpoint_interval == 0 and step_num > 0:
                        self._save_checkpoint(step_num)
                
                # Finalisation
                self.end_time = datetime.now()
                self.is_running = False
                
                # Génération des résultats finaux
                self.results = self._generate_final_results()
                
                # Sauvegarde finale
                self.export_results()
                
                logger.info(f"Simulation {self.id} terminée avec succès")
                
            except Exception as e:
                self.is_running = False
                logger.error(f"Erreur pendant la simulation: {e}")
                raise
        
        return self.results
    
    def _save_checkpoint(self, step: int) -> None:
        """Sauvegarde un checkpoint de la simulation."""
        checkpoint_data = {
            'simulation_id': self.id,
            'step': step,
            'timestamp': datetime.now().isoformat(),
            'agents': [agent.to_dict() for agent in self.agents],
            'metrics_summary': self._calculate_summary_metrics()
        }
        
        checkpoint_file = self.output_dir / f"{self.id}_checkpoint_{step}.json"
        save_json(checkpoint_data, checkpoint_file)
        logger.debug(f"Checkpoint sauvegardé: {checkpoint_file}")
    
    def _generate_final_results(self) -> Dict[str, Any]:
        """Génère le rapport final de la simulation."""
        duration = (self.end_time - self.start_time).total_seconds() if self.end_time else 0
        
        results = {
            'simulation_id': self.id,
            'config': self.config,
            'scenario': self.scenario,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration_seconds': duration,
            'total_steps': self.current_step,
            'summary_metrics': self._calculate_summary_metrics(),
            'agent_results': [agent.to_dict() for agent in self.agents],
            'step_metrics': self.metrics_history
        }
        
        return results
    
    def _calculate_summary_metrics(self) -> Dict[str, Any]:
        """Calcule les métriques de résumé."""
        if not self.metrics_history:
            return {}
        
        total_transactions = sum(m['transactions_executed'] for m in self.metrics_history)
        total_volume = sum(m['total_volume'] for m in self.metrics_history)
        total_value = sum(m['total_value'] for m in self.metrics_history)
        
        return {
            'total_transactions': total_transactions,
            'total_volume': total_volume,
            'total_value': total_value,
            'avg_transactions_per_step': total_transactions / len(self.metrics_history),
            'avg_volume_per_step': total_volume / len(self.metrics_history),
            'avg_value_per_step': total_value / len(self.metrics_history),
            'final_agent_count': len(self.agents),
            'steps_completed': len(self.metrics_history)
        }
    
    def export_results(self, filepath: Optional[Path] = None) -> Path:
        """
        Exporte les résultats de la simulation.
        
        Args:
            filepath: Chemin de destination (optionnel)
            
        Returns:
            Chemin du fichier créé
        """
        if not filepath:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"simulation_{timestamp}_{self.id}.json"
            filepath = self.output_dir / filename
        
        save_json(self.results, filepath)
        logger.info(f"Résultats exportés vers: {filepath}")
        
        return filepath
    
    def get_status(self) -> Dict[str, Any]:
        """Récupère l'état actuel de la simulation."""
        return {
            'id': self.id,
            'is_running': self.is_running,
            'current_step': self.current_step,
            'agent_count': len(self.agents),
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'scenario': self.scenario,
            'last_metrics': self.metrics_history[-1] if self.metrics_history else None
        }