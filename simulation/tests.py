"""
Tests pour l'app simulation.
"""

import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase

from core.models import Item, ItemCategory
from market.engine import MarketEngine
from market.models import Order, OrderType
from .agents import Agent, Buyer, Seller
from .manager import SimulationManager
from .scenarios import BaselineScenario, DemandDoubleScenario, create_scenario


class AgentTest(TestCase):
    """Tests pour la classe de base Agent."""
    
    def setUp(self):
        """Initialisation des données de test."""
        self.agent = Buyer('test_buyer', Decimal('1000.00'))
    
    def test_agent_initialization(self):
        """Test d'initialisation d'un agent."""
        agent = Buyer('buyer_001', Decimal('500.00'))
        
        assert agent.id == 'buyer_001'
        assert agent.cash == Decimal('500.00')
        assert agent.inventory == {}
        assert 0.1 <= agent.risk_tolerance <= 0.9
        assert 0.2 <= agent.patience <= 0.8
        assert 0.3 <= agent.market_knowledge <= 0.9
    
    def test_inventory_management(self):
        """Test de gestion de l'inventaire."""
        agent = self.agent
        
        # Ajout d'objets
        agent.add_item(1, 5)
        agent.add_item(2, 3)
        
        assert agent.get_item_quantity(1) == 5
        assert agent.get_item_quantity(2) == 3
        assert agent.get_item_quantity(999) == 0
        
        # Ajout supplémentaire
        agent.add_item(1, 2)
        assert agent.get_item_quantity(1) == 7
        
        # Retrait d'objets
        result = agent.remove_item(1, 3)
        assert result is True
        assert agent.get_item_quantity(1) == 4
        
        # Retrait impossible (quantité insuffisante)
        result = agent.remove_item(1, 10)
        assert result is False
        assert agent.get_item_quantity(1) == 4
        
        # Retrait complet
        result = agent.remove_item(1, 4)
        assert result is True
        assert 1 not in agent.inventory
    
    def test_cash_management(self):
        """Test de gestion de l'argent."""
        agent = self.agent
        initial_cash = agent.cash
        
        # Vérification de capacité d'achat
        assert agent.can_afford(Decimal('100.00'), 5) is True
        assert agent.can_afford(Decimal('300.00'), 5) is False
        
        # Mise à jour du cash
        agent.update_cash(Decimal('-200.00'))
        assert agent.cash == initial_cash - Decimal('200.00')
        
        agent.update_cash(Decimal('50.00'))
        assert agent.cash == initial_cash - Decimal('150.00')
    
    def test_agent_serialization(self):
        """Test de sérialisation de l'agent."""
        agent = self.agent
        agent.add_item(1, 3)
        agent.add_item(2, 5)
        
        data = agent.to_dict()
        
        assert data['id'] == agent.id
        assert data['type'] == 'Buyer'
        assert data['cash'] == float(agent.cash)
        assert data['inventory'] == {1: 3, 2: 5}
        assert 'risk_tolerance' in data
        assert 'patience' in data
        assert 'market_knowledge' in data


class BuyerTest(TestCase):
    """Tests pour la classe Buyer."""
    
    def setUp(self):
        """Initialisation des données de test."""
        self.item = Item.objects.create(
            name='Test Card',
            category=ItemCategory.TRADING_CARDS,
            total_supply=100
        )
        self.market_engine = MarketEngine()
        self.buyer = Buyer('buyer_001', Decimal('1000.00'))
    
    def test_buyer_initialization(self):
        """Test d'initialisation d'un acheteur."""
        buyer = Buyer('buyer_001', Decimal('500.00'))
        
        assert isinstance(buyer, Agent)
        assert len(buyer.preferred_categories) >= 1
        assert buyer.budget_per_item > 0
    
    def test_buyer_act_no_items(self):
        """Test d'action d'acheteur sans objets disponibles."""
        # Suppression de tous les objets
        Item.objects.all().delete()
        
        order = self.buyer.act(self.market_engine, 0)
        assert order is None
    
    @patch('random.random')
    def test_buyer_act_low_probability(self, mock_random):
        """Test d'action d'acheteur avec faible probabilité."""
        # Force une probabilité élevée pour ne pas agir
        mock_random.return_value = 0.9
        
        order = self.buyer.act(self.market_engine, 0)
        assert order is None
    
    def test_create_buy_order(self):
        """Test de création d'ordre d'achat."""
        # Mock du market snapshot
        with patch.object(self.market_engine, 'get_market_snapshot') as mock_snapshot:
            mock_snapshot.return_value = {
                'best_ask': 15.0,
                'best_bid': None,
                'last_price': None
            }
            
            order = self.buyer._create_buy_order(self.item, self.market_engine)
            
            assert order is not None
            assert order.item == self.item
            assert order.agent_id == self.buyer.id
            assert order.order_type == OrderType.BUY
            assert order.price > 0
            assert order.quantity > 0


class SellerTest(TestCase):
    """Tests pour la classe Seller."""
    
    def setUp(self):
        """Initialisation des données de test."""
        self.item = Item.objects.create(
            name='Test Card',
            category=ItemCategory.TRADING_CARDS,
            total_supply=100
        )
        self.market_engine = MarketEngine()
        self.seller = Seller('seller_001', Decimal('500.00'))
    
    def test_seller_initialization(self):
        """Test d'initialisation d'un vendeur."""
        seller = Seller('seller_001', Decimal('300.00'))
        
        assert isinstance(seller, Agent)
        assert len(seller.inventory) > 0  # Inventaire initial
        assert seller.profit_target >= Decimal('1.1')
    
    def test_seller_act_empty_inventory(self):
        """Test d'action de vendeur avec inventaire vide."""
        seller = Seller('empty_seller', Decimal('100.00'))
        seller.inventory.clear()  # Vide l'inventaire
        
        order = seller.act(self.market_engine, 0)
        assert order is None
    
    def test_create_sell_order(self):
        """Test de création d'ordre de vente."""
        # S'assurer que le vendeur a l'objet en stock
        self.seller.add_item(self.item.id, 5)
        
        with patch.object(self.market_engine, 'get_market_snapshot') as mock_snapshot:
            mock_snapshot.return_value = {
                'best_bid': 12.0,
                'best_ask': None,
                'last_price': None
            }
            
            order = self.seller._create_sell_order(self.item, self.market_engine)
            
            assert order is not None
            assert order.item == self.item
            assert order.agent_id == self.seller.id
            assert order.order_type == OrderType.SELL
            assert order.price > 0
            assert order.quantity > 0


class SimulationManagerTest(TestCase):
    """Tests pour le SimulationManager."""
    
    def setUp(self):
        """Initialisation des données de test."""
        self.config = {
            'scenario': 'baseline',
            'checkpoint_interval': 10
        }
        self.manager = SimulationManager(config=self.config)
    
    def test_manager_initialization(self):
        """Test d'initialisation du gestionnaire."""
        manager = SimulationManager()
        
        assert manager.market_engine is not None
        assert manager.agents == []
        assert manager.current_step == 0
        assert manager.is_running is False
    
    def test_add_remove_agents(self):
        """Test d'ajout et retrait d'agents."""
        buyer = Buyer('buyer_001')
        seller = Seller('seller_001')
        
        # Ajout
        self.manager.add_agent(buyer)
        self.manager.add_agent(seller)
        
        assert len(self.manager.agents) == 2
        assert buyer in self.manager.agents
        assert seller in self.manager.agents
        
        # Éviter les doublons
        self.manager.add_agent(buyer)
        assert len(self.manager.agents) == 2
        
        # Retrait
        result = self.manager.remove_agent('buyer_001')
        assert result is True
        assert len(self.manager.agents) == 1
        assert buyer not in self.manager.agents
        
        # Retrait d'agent inexistant
        result = self.manager.remove_agent('inexistant')
        assert result is False
    
    def test_initialize_market(self):
        """Test d'initialisation du marché."""
        initial_count = Item.objects.count()
        
        self.manager.initialize_market(n_items=5)
        
        new_count = Item.objects.count()
        assert new_count >= initial_count  # Au moins les objets créés
    
    def test_create_agents(self):
        """Test de création d'agents."""
        self.manager.create_agents(n_buyers=3, n_sellers=2)
        
        assert len(self.manager.agents) == 5
        
        buyers = [a for a in self.manager.agents if isinstance(a, Buyer)]
        sellers = [a for a in self.manager.agents if isinstance(a, Seller)]
        
        assert len(buyers) == 3
        assert len(sellers) == 2
    
    def test_simulation_step(self):
        """Test d'exécution d'une étape."""
        # Initialisation
        self.manager.initialize_market(n_items=2)
        self.manager.create_agents(n_buyers=2, n_sellers=2)
        
        # Exécution d'une étape
        metrics = self.manager.step()
        
        assert isinstance(metrics, dict)
        assert 'step' in metrics
        assert 'timestamp' in metrics
        assert 'orders_created' in metrics
        assert 'transactions_executed' in metrics
        assert self.manager.current_step == 1
    
    def test_get_status(self):
        """Test de récupération du statut."""
        self.manager.create_agents(n_buyers=2, n_sellers=1)
        
        status = self.manager.get_status()
        
        assert 'id' in status
        assert 'is_running' in status
        assert 'current_step' in status
        assert 'agent_count' in status
        assert status['agent_count'] == 3
        assert status['current_step'] == 0
        assert status['is_running'] is False


class ScenarioTest(TestCase):
    """Tests pour les scénarios de simulation."""
    
    def test_baseline_scenario(self):
        """Test du scénario baseline."""
        scenario = BaselineScenario()
        
        assert scenario.name == 'Baseline'
        assert 'description' in scenario.parameters
        
        # Test d'application (ne devrait rien faire)
        agents = []
        market = MagicMock()
        
        # Ne devrait pas lever d'erreur
        scenario.apply_step_effects(10, agents, market)
    
    def test_demand_double_scenario(self):
        """Test du scénario de doublement de demande."""
        scenario = DemandDoubleScenario(trigger_step=5, duration=3)
        
        assert scenario.name == 'Demand x2'
        assert scenario.trigger_step == 5
        assert scenario.duration == 3
        assert scenario.end_step == 8
        
        # Test avant déclenchement
        agents = [Buyer('buyer_1')]
        market = MagicMock()
        
        scenario.apply_step_effects(3, agents, market)
        # Pas d'effet avant le déclenchement
        
        # Test pendant l'effet
        original_budget = agents[0].budget_per_item
        scenario.apply_step_effects(6, agents, market)
        
        # Le budget devrait être modifié
        assert agents[0].budget_per_item != original_budget
    
    def test_create_scenario_factory(self):
        """Test de la factory de création de scénarios."""
        # Scénario valide
        scenario = create_scenario('baseline')
        assert isinstance(scenario, BaselineScenario)
        
        scenario = create_scenario('demand_x2', trigger_step=10)
        assert isinstance(scenario, DemandDoubleScenario)
        assert scenario.trigger_step == 10
        
        # Scénario invalide
        with pytest.raises(ValueError):
            create_scenario('inexistant')


@pytest.mark.slow
class IntegrationTest(TestCase):
    """Tests d'intégration pour la simulation complète."""
    
    def test_small_simulation_run(self):
        """Test d'exécution d'une petite simulation."""
        config = {
            'scenario': 'baseline',
            'checkpoint_interval': 5
        }
        manager = SimulationManager(config=config)
        
        # Initialisation
        manager.initialize_market(n_items=3)
        manager.create_agents(n_buyers=5, n_sellers=3)
        
        # Exécution de quelques étapes
        results = manager.run(n_steps=10)
        
        assert isinstance(results, dict)
        assert 'simulation_id' in results
        assert 'summary_metrics' in results
        assert 'total_steps' in results
        assert results['total_steps'] == 10
        assert len(manager.metrics_history) == 10
