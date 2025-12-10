"""
Classes d'agents pour la simulation du marché.
"""

import random
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Dict, List, Optional, Any
import logging

from core.models import Item
from core.utils import weighted_random_choice, calculate_price_bounds
from market.models import Order, OrderType
from market.engine import MarketEngine

logger = logging.getLogger('simulation')


class Agent(ABC):
    """
    Classe de base pour tous les agents du marché.
    
    Attributes:
        id: Identifiant unique de l'agent
        cash: Montant d'argent disponible
        inventory: Dictionnaire {item_id: quantité}
    """
    
    def __init__(self, agent_id: str, initial_cash: Decimal = Decimal('1000.00')):
        """
        Initialise un agent.
        
        Args:
            agent_id: Identifiant unique
            initial_cash: Capital initial
        """
        self.id = agent_id
        self.cash = initial_cash
        self.inventory: Dict[int, int] = {}
        self.order_history: List[Order] = []
        self.active_orders: List[int] = []  # IDs des ordres actifs
        
        # Paramètres de personnalité
        self.risk_tolerance = random.uniform(0.1, 0.9)
        self.patience = random.uniform(0.2, 0.8)
        self.market_knowledge = random.uniform(0.3, 0.9)
    
    @abstractmethod
    def act(self, market: MarketEngine, step: int) -> Optional[Order]:
        """
        Action de l'agent à chaque étape de simulation.
        
        Args:
            market: Moteur de marché
            step: Numéro de l'étape courante
            
        Returns:
            Ordre créé ou None
        """
        pass
    
    def get_item_quantity(self, item_id: int) -> int:
        """Récupère la quantité d'un objet dans l'inventaire."""
        return self.inventory.get(item_id, 0)
    
    def add_item(self, item_id: int, quantity: int) -> None:
        """Ajoute des objets à l'inventaire."""
        if item_id not in self.inventory:
            self.inventory[item_id] = 0
        self.inventory[item_id] += quantity
    
    def remove_item(self, item_id: int, quantity: int) -> bool:
        """
        Retire des objets de l'inventaire.
        
        Returns:
            True si successful, False si quantité insuffisante
        """
        if self.get_item_quantity(item_id) >= quantity:
            self.inventory[item_id] -= quantity
            if self.inventory[item_id] == 0:
                del self.inventory[item_id]
            return True
        return False
    
    def can_afford(self, price: Decimal, quantity: int) -> bool:
        """Vérifie si l'agent peut se permettre un achat."""
        return self.cash >= (price * quantity)
    
    def update_cash(self, amount: Decimal) -> None:
        """Met à jour le montant d'argent."""
        self.cash += amount
    
    def get_portfolio_value(self, market: MarketEngine) -> Decimal:
        """
        Calcule la valeur totale du portefeuille.
        
        Args:
            market: Moteur de marché pour obtenir les prix
            
        Returns:
            Valeur totale (cash + inventaire)
        """
        total_value = self.cash
        
        for item_id, quantity in self.inventory.items():
            try:
                item = Item.objects.get(id=item_id)
                market_data = market.get_market_snapshot(item)
                
                # Utilise le dernier prix ou le prix moyen bid/ask
                if market_data['last_price']:
                    price = Decimal(str(market_data['last_price']))
                elif market_data['best_bid'] and market_data['best_ask']:
                    price = (Decimal(str(market_data['best_bid'])) + 
                            Decimal(str(market_data['best_ask']))) / 2
                else:
                    price = Decimal('10.00')  # Prix par défaut
                
                total_value += price * quantity
                
            except Item.DoesNotExist:
                continue
        
        return total_value
    
    def to_dict(self) -> Dict[str, Any]:
        """Sérialise l'agent en dictionnaire."""
        return {
            'id': self.id,
            'type': self.__class__.__name__,
            'cash': float(self.cash),
            'inventory': self.inventory,
            'risk_tolerance': self.risk_tolerance,
            'patience': self.patience,
            'market_knowledge': self.market_knowledge,
            'active_orders_count': len(self.active_orders)
        }


class Buyer(Agent):
    """
    Agent acheteur avec stratégies d'achat.
    """
    
    def __init__(self, agent_id: str, initial_cash: Decimal = Decimal('1000.00')):
        super().__init__(agent_id, initial_cash)
        self.preferred_categories = random.sample(
            ['cards', 'figurines', 'comics', 'toys', 'art'], 
            k=random.randint(1, 3)
        )
        self.budget_per_item = self.cash * Decimal(str(random.uniform(0.05, 0.2)))
    
    def act(self, market: MarketEngine, step: int) -> Optional[Order]:
        """
        Stratégie d'achat de l'agent.
        
        Args:
            market: Moteur de marché
            step: Étape de simulation
            
        Returns:
            Ordre d'achat ou None
        """
        # Probabilité de placer un ordre (dépend de la patience)
        if random.random() > 0.1 + (self.patience * 0.3):
            return None
        
        # Sélection d'un objet à acheter
        available_items = Item.objects.filter(
            category__in=self.preferred_categories
        )
        
        if not available_items.exists():
            available_items = Item.objects.all()
        
        if not available_items.exists():
            return None
        
        item = self.buying_strategy(market, available_items, step)
        
        if item:
            return self._create_buy_order(item, market)
        
        return None
    
    def buying_strategy(self, market: MarketEngine, items: List[Item], step: int) -> Optional[Item]:
        """
        Stratégie de sélection d'objet à acheter.
        
        Args:
            market: Moteur de marché
            items: Objets disponibles
            step: Étape courante
            
        Returns:
            Objet sélectionné ou None
        """
        # Évalue chaque objet selon différents critères
        item_scores = []
        
        for item in items:
            market_data = market.get_market_snapshot(item)
            
            # Critères d'évaluation
            liquidity_score = min(market_data.get('volume_24h', 0) / 10, 1.0)
            
            # Prix attractif (spread faible = bon)
            spread = market_data.get('spread')
            spread_score = 1.0 - min(spread / 10 if spread else 0, 1.0)
            
            # Tendance de prix (préfère les objets en hausse)
            trend_score = 0.8 if item.get_market_data().get('price_trend') == 'up' else 0.5
            
            # Score combiné
            total_score = (
                liquidity_score * 0.3 +
                spread_score * 0.4 +
                trend_score * 0.3
            ) * self.market_knowledge
            
            if total_score > 0.1:
                item_scores.append((item, total_score))
        
        # Sélection pondérée
        if item_scores:
            return weighted_random_choice(item_scores)
        
        return random.choice(list(items)) if items else None
    
    def _create_buy_order(self, item: Item, market: MarketEngine) -> Optional[Order]:
        """
        Crée un ordre d'achat pour un objet.
        
        Args:
            item: Objet à acheter
            market: Moteur de marché
            
        Returns:
            Ordre créé ou None
        """
        market_data = market.get_market_snapshot(item)
        
        # Détermination du prix d'offre
        if market_data['best_ask']:
            base_price = Decimal(str(market_data['best_ask']))
            # Offre légèrement en dessous du meilleur ask
            price = base_price * Decimal(str(random.uniform(0.95, 0.99)))
        elif market_data['last_price']:
            base_price = Decimal(str(market_data['last_price']))
            price = base_price * Decimal(str(random.uniform(0.9, 1.1)))
        else:
            # Prix par défaut basé sur la catégorie
            price = Decimal(str(random.uniform(5.0, 50.0)))
        
        # Ajustement selon la tolérance au risque
        price *= Decimal(str(1 + (self.risk_tolerance - 0.5) * 0.2))
        
        # Quantité basée sur le budget
        max_quantity = int(self.budget_per_item / price) if price > 0 else 1
        quantity = random.randint(1, max(1, max_quantity))
        
        # Vérification de la capacité d'achat
        if not self.can_afford(price, quantity):
            # Ajustement de la quantité
            quantity = int(self.cash / price) if price > 0 else 0
        
        if quantity > 0 and price > 0:
            order = Order(
                item=item,
                agent_id=self.id,
                order_type=OrderType.BUY,
                price=price.quantize(Decimal('0.01')),
                quantity=quantity
            )
            
            logger.debug(f"Agent {self.id} crée ordre d'achat: {quantity}x {item.name} @ {price}€")
            return order
        
        return None


class Seller(Agent):
    """
    Agent vendeur avec stratégies de vente.
    """
    
    def __init__(self, agent_id: str, initial_cash: Decimal = Decimal('500.00')):
        super().__init__(agent_id, initial_cash)
        # Les vendeurs commencent avec des objets dans leur inventaire
        self._initialize_inventory()
        self.profit_target = Decimal(str(random.uniform(1.1, 1.5)))  # 10-50% de profit
    
    def _initialize_inventory(self) -> None:
        """Initialise l'inventaire du vendeur avec des objets aléatoires."""
        items = list(Item.objects.all()[:10])  # Limite aux 10 premiers objets
        
        for _ in range(random.randint(3, 8)):
            if items:
                item = random.choice(items)
                quantity = random.randint(1, 5)
                self.add_item(item.id, quantity)
    
    def act(self, market: MarketEngine, step: int) -> Optional[Order]:
        """
        Stratégie de vente de l'agent.
        
        Args:
            market: Moteur de marché
            step: Étape de simulation
            
        Returns:
            Ordre de vente ou None
        """
        # Probabilité de placer un ordre
        if random.random() > 0.15 + (self.patience * 0.2):
            return None
        
        # Sélection d'un objet à vendre
        if not self.inventory:
            return None
        
        item_id = self.selling_strategy(market, step)
        
        if item_id:
            try:
                item = Item.objects.get(id=item_id)
                return self._create_sell_order(item, market)
            except Item.DoesNotExist:
                pass
        
        return None
    
    def selling_strategy(self, market: MarketEngine, step: int) -> Optional[int]:
        """
        Stratégie de sélection d'objet à vendre.
        
        Args:
            market: Moteur de marché
            step: Étape courante
            
        Returns:
            ID de l'objet sélectionné ou None
        """
        if not self.inventory:
            return None
        
        # Évalue chaque objet en inventaire
        item_scores = []
        
        for item_id, quantity in self.inventory.items():
            try:
                item = Item.objects.get(id=item_id)
                market_data = market.get_market_snapshot(item)
                
                # Critères d'évaluation pour la vente
                demand_score = min(market_data.get('volume_24h', 0) / 5, 1.0)
                
                # Prix favorable (prix élevé = bon pour vendre)
                price_score = 0.5
                if market_data.get('best_bid'):
                    price_score = min(market_data['best_bid'] / 100, 1.0)
                
                # Urgence (plus l'inventaire est important, plus urgent de vendre)
                urgency_score = min(quantity / 10, 1.0)
                
                total_score = (
                    demand_score * 0.4 +
                    price_score * 0.4 +
                    urgency_score * 0.2
                ) * self.market_knowledge
                
                if total_score > 0.1:
                    item_scores.append((item_id, total_score))
                    
            except Item.DoesNotExist:
                continue
        
        # Sélection pondérée
        if item_scores:
            return weighted_random_choice(item_scores)
        
        return random.choice(list(self.inventory.keys()))
    
    def _create_sell_order(self, item: Item, market: MarketEngine) -> Optional[Order]:
        """
        Crée un ordre de vente pour un objet.
        
        Args:
            item: Objet à vendre
            market: Moteur de marché
            
        Returns:
            Ordre créé ou None
        """
        available_quantity = self.get_item_quantity(item.id)
        
        if available_quantity <= 0:
            return None
        
        market_data = market.get_market_snapshot(item)
        
        # Détermination du prix de vente
        if market_data['best_bid']:
            base_price = Decimal(str(market_data['best_bid']))
            # Prix légèrement au-dessus du meilleur bid
            price = base_price * Decimal(str(random.uniform(1.01, 1.05)))
        elif market_data['last_price']:
            base_price = Decimal(str(market_data['last_price']))
            price = base_price * self.profit_target
        else:
            # Prix par défaut
            price = Decimal(str(random.uniform(10.0, 100.0)))
        
        # Ajustement selon la tolérance au risque
        price *= Decimal(str(1 + (self.risk_tolerance - 0.5) * 0.1))
        
        # Quantité à vendre (entre 1 et disponible)
        max_sell = min(available_quantity, random.randint(1, 3))
        quantity = random.randint(1, max_sell)
        
        if quantity > 0 and price > 0:
            order = Order(
                item=item,
                agent_id=self.id,
                order_type=OrderType.SELL,
                price=price.quantize(Decimal('0.01')),
                quantity=quantity
            )
            
            logger.debug(f"Agent {self.id} crée ordre de vente: {quantity}x {item.name} @ {price}€")
            return order
        
        return None