"""
Tests pour l'app market.
"""

import pytest
from decimal import Decimal
from django.test import TestCase
from django.core.exceptions import ValidationError

from core.models import Item, ItemCategory
from .models import Order, Transaction, OrderType, OrderStatus
from .engine import MarketEngine


class OrderModelTest(TestCase):
    """Tests pour le modèle Order."""
    
    def setUp(self):
        """Initialisation des données de test."""
        self.item = Item.objects.create(
            name='Test Item',
            category=ItemCategory.TRADING_CARDS,
            total_supply=100
        )
        
        self.order_data = {
            'item': self.item,
            'agent_id': 'buyer_001',
            'order_type': OrderType.BUY,
            'price': Decimal('10.50'),
            'quantity': 5
        }
    
    def test_create_buy_order(self):
        """Test de création d'un ordre d'achat."""
        order = Order.objects.create(**self.order_data)
        
        assert order.item == self.item
        assert order.agent_id == 'buyer_001'
        assert order.order_type == OrderType.BUY
        assert order.price == Decimal('10.50')
        assert order.quantity == 5
        assert order.filled_quantity == 0
        assert order.status == OrderStatus.PENDING
    
    def test_create_sell_order(self):
        """Test de création d'un ordre de vente."""
        data = self.order_data.copy()
        data['order_type'] = OrderType.SELL
        data['agent_id'] = 'seller_001'
        
        order = Order.objects.create(**data)
        assert order.order_type == OrderType.SELL
        assert order.agent_id == 'seller_001'
    
    def test_order_properties(self):
        """Test des propriétés calculées de l'ordre."""
        order = Order.objects.create(**self.order_data)
        
        # Propriétés initiales
        assert order.remaining_quantity == 5
        assert order.is_active is True
        assert order.total_value == Decimal('52.50')  # 10.50 * 5
        
        # Après exécution partielle
        order.filled_quantity = 2
        order.save()
        
        assert order.remaining_quantity == 3
        assert order.is_active is True
    
    def test_order_status_update(self):
        """Test de la mise à jour automatique du statut."""
        order = Order.objects.create(**self.order_data)
        
        # Statut initial
        order.update_status()
        assert order.status == OrderStatus.PENDING
        
        # Exécution partielle
        order.filled_quantity = 2
        order.update_status()
        assert order.status == OrderStatus.PARTIAL
        
        # Exécution complète
        order.filled_quantity = 5
        order.update_status()
        assert order.status == OrderStatus.FILLED
    
    def test_can_match_with(self):
        """Test de la compatibilité entre ordres."""
        buy_order = Order.objects.create(**self.order_data)
        
        # Ordre de vente compatible
        sell_data = self.order_data.copy()
        sell_data.update({
            'order_type': OrderType.SELL,
            'agent_id': 'seller_001',
            'price': Decimal('10.00')  # Prix plus bas que l'achat
        })
        sell_order = Order.objects.create(**sell_data)
        
        assert buy_order.can_match_with(sell_order) is True
        assert sell_order.can_match_with(buy_order) is True
        
        # Même agent (non compatible)
        sell_data['agent_id'] = 'buyer_001'  # Même agent
        same_agent_order = Order.objects.create(**sell_data)
        
        assert buy_order.can_match_with(same_agent_order) is False
        
        # Prix incompatible
        sell_data['agent_id'] = 'seller_002'
        sell_data['price'] = Decimal('15.00')  # Prix trop élevé
        expensive_order = Order.objects.create(**sell_data)
        
        assert buy_order.can_match_with(expensive_order) is False


class TransactionModelTest(TestCase):
    """Tests pour le modèle Transaction."""
    
    def setUp(self):
        """Initialisation des données de test."""
        self.item = Item.objects.create(
            name='Test Item',
            category=ItemCategory.TRADING_CARDS,
            total_supply=100
        )
    
    def test_create_transaction(self):
        """Test de création d'une transaction."""
        transaction = Transaction.objects.create(
            buyer_id='buyer_001',
            seller_id='seller_001',
            item=self.item,
            price=Decimal('12.50'),
            quantity=3
        )
        
        assert transaction.buyer_id == 'buyer_001'
        assert transaction.seller_id == 'seller_001'
        assert transaction.item == self.item
        assert transaction.price == Decimal('12.50')
        assert transaction.quantity == 3
        assert transaction.total_value == Decimal('37.50')
        assert transaction.timestamp is not None


class MarketEngineTest(TestCase):
    """Tests pour le moteur de marché."""
    
    def setUp(self):
        """Initialisation des données de test."""
        self.engine = MarketEngine()
        self.item = Item.objects.create(
            name='Test Item',
            category=ItemCategory.TRADING_CARDS,
            total_supply=100
        )
    
    def test_submit_buy_order_no_match(self):
        """Test de soumission d'ordre sans match."""
        order = Order(
            item=self.item,
            agent_id='buyer_001',
            order_type=OrderType.BUY,
            price=Decimal('10.00'),
            quantity=5
        )
        
        submitted_order = self.engine.submit_order(order)
        
        assert submitted_order.id is not None
        assert submitted_order.status == OrderStatus.PENDING
        assert submitted_order.filled_quantity == 0
    
    def test_submit_matching_orders(self):
        """Test de soumission d'ordres compatibles."""
        # Ordre de vente d'abord
        sell_order = Order(
            item=self.item,
            agent_id='seller_001',
            order_type=OrderType.SELL,
            price=Decimal('10.00'),
            quantity=5
        )
        self.engine.submit_order(sell_order)
        
        # Ordre d'achat compatible
        buy_order = Order(
            item=self.item,
            agent_id='buyer_001',
            order_type=OrderType.BUY,
            price=Decimal('10.50'),  # Prix plus élevé
            quantity=3
        )
        submitted_buy = self.engine.submit_order(buy_order)
        
        # Vérifications
        sell_order.refresh_from_db()
        
        assert submitted_buy.filled_quantity == 3
        assert submitted_buy.status == OrderStatus.FILLED
        assert sell_order.filled_quantity == 3
        assert sell_order.status == OrderStatus.PARTIAL
        
        # Vérification de la transaction
        transactions = Transaction.objects.filter(item=self.item)
        assert transactions.count() == 1
        
        transaction = transactions.first()
        assert transaction.buyer_id == 'buyer_001'
        assert transaction.seller_id == 'seller_001'
        assert transaction.price == Decimal('10.00')  # Prix du vendeur
        assert transaction.quantity == 3
    
    def test_get_order_book(self):
        """Test de récupération du carnet d'ordres."""
        # Création de plusieurs ordres
        Order.objects.create(
            item=self.item,
            agent_id='buyer_001',
            order_type=OrderType.BUY,
            price=Decimal('10.00'),
            quantity=5
        )
        
        Order.objects.create(
            item=self.item,
            agent_id='seller_001',
            order_type=OrderType.SELL,
            price=Decimal('11.00'),
            quantity=3
        )
        
        order_book = self.engine.get_order_book(self.item)
        
        assert 'buy_orders' in order_book
        assert 'sell_orders' in order_book
        assert len(order_book['buy_orders']) == 1
        assert len(order_book['sell_orders']) == 1
        
        # Vérification de l'ordre
        buy_order = order_book['buy_orders'][0]
        assert buy_order['price'] == 10.0
        assert buy_order['quantity'] == 5
    
    def test_get_market_snapshot(self):
        """Test de l'instantané de marché."""
        # Création d'ordres et transaction
        Order.objects.create(
            item=self.item,
            agent_id='buyer_001',
            order_type=OrderType.BUY,
            price=Decimal('9.50'),
            quantity=5
        )
        
        Order.objects.create(
            item=self.item,
            agent_id='seller_001',
            order_type=OrderType.SELL,
            price=Decimal('10.50'),
            quantity=3
        )
        
        Transaction.objects.create(
            buyer_id='buyer_002',
            seller_id='seller_002',
            item=self.item,
            price=Decimal('10.00'),
            quantity=2
        )
        
        snapshot = self.engine.get_market_snapshot(self.item)
        
        assert snapshot['item_id'] == self.item.id
        assert snapshot['item_name'] == 'Test Item'
        assert snapshot['best_bid'] == 9.5
        assert snapshot['best_ask'] == 10.5
        assert snapshot['last_price'] == 10.0
        assert snapshot['spread'] == 1.0  # 10.5 - 9.5
    
    def test_cancel_order(self):
        """Test d'annulation d'ordre."""
        order = Order.objects.create(
            item=self.item,
            agent_id='buyer_001',
            order_type=OrderType.BUY,
            price=Decimal('10.00'),
            quantity=5
        )
        
        # Annulation réussie
        result = self.engine.cancel_order(order.id, 'buyer_001')
        assert result is True
        
        order.refresh_from_db()
        assert order.status == OrderStatus.CANCELLED
        
        # Tentative d'annulation par un autre agent
        result = self.engine.cancel_order(order.id, 'buyer_002')
        assert result is False
