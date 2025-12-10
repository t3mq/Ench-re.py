"""
Moteur de marché pour l'exécution des ordres et le matching.
"""

from typing import List, Dict, Any, Optional, Tuple
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
import logging

from .models import Order, Transaction, MarketSnapshot, OrderType, OrderStatus
from core.models import Item

logger = logging.getLogger('market')


class MarketEngine:
    """
    Moteur de marché responsable de l'exécution des ordres.
    
    Gère:
    - Soumission d'ordres
    - Matching des ordres compatibles
    - Exécution des transactions
    - Mise à jour des données de marché
    """
    
    def __init__(self):
        """Initialise le moteur de marché."""
        self._order_books: Dict[int, Dict[str, List[Order]]] = {}
        self._market_data: Dict[int, Dict[str, Any]] = {}
    
    def submit_order(self, order: Order) -> Order:
        """
        Soumet un ordre sur le marché.
        
        Args:
            order: Ordre à soumettre
            
        Returns:
            L'ordre sauvegardé et potentiellement exécuté
        """
        logger.info(f"Soumission d'ordre: {order}")
        
        with transaction.atomic():
            # Sauvegarde de l'ordre
            order.save()
            
            # Tentative de matching
            matching_orders = self._find_matching_orders(order)
            
            if matching_orders:
                transactions = self._execute_matches(order, matching_orders)
                logger.info(f"Ordre partiellement/complètement exécuté: {len(transactions)} transactions")
            
            # Mise à jour du carnet d'ordres
            self._update_order_book(order)
            
            return order
    
    def _find_matching_orders(self, new_order: Order) -> List[Order]:
        """
        Trouve les ordres compatibles avec le nouvel ordre.
        
        Args:
            new_order: Nouvel ordre à matcher
            
        Returns:
            Liste des ordres compatibles, triés par priorité
        """
        opposite_type = OrderType.SELL if new_order.order_type == OrderType.BUY else OrderType.BUY
        
        # Récupération des ordres opposés actifs pour le même objet
        matching_orders = Order.objects.filter(
            item=new_order.item,
            order_type=opposite_type,
            status__in=[OrderStatus.PENDING, OrderStatus.PARTIAL]
        ).exclude(agent_id=new_order.agent_id)
        
        # Filtrage par prix compatible
        if new_order.order_type == OrderType.BUY:
            # Pour un ordre d'achat, on cherche des ventes <= prix d'achat
            matching_orders = matching_orders.filter(price__lte=new_order.price)
            # Tri par prix croissant (meilleurs prix en premier)
            matching_orders = matching_orders.order_by('price', 'created_at')
        else:
            # Pour un ordre de vente, on cherche des achats >= prix de vente
            matching_orders = matching_orders.filter(price__gte=new_order.price)
            # Tri par prix décroissant (meilleurs prix en premier)
            matching_orders = matching_orders.order_by('-price', 'created_at')
        
        return list(matching_orders)
    
    def _execute_matches(self, new_order: Order, matching_orders: List[Order]) -> List[Transaction]:
        """
        Exécute les matches entre ordres compatibles.
        
        Args:
            new_order: Nouvel ordre
            matching_orders: Ordres compatibles
            
        Returns:
            Liste des transactions créées
        """
        transactions = []
        remaining_quantity = new_order.remaining_quantity
        
        for matching_order in matching_orders:
            if remaining_quantity <= 0:
                break
            
            # Calcul de la quantité à échanger
            trade_quantity = min(remaining_quantity, matching_order.remaining_quantity)
            
            # Détermination du prix d'exécution (prix de l'ordre existant)
            execution_price = matching_order.price
            
            # Création de la transaction
            if new_order.order_type == OrderType.BUY:
                buyer_id = new_order.agent_id
                seller_id = matching_order.agent_id
                buy_order = new_order
                sell_order = matching_order
            else:
                buyer_id = matching_order.agent_id
                seller_id = new_order.agent_id
                buy_order = matching_order
                sell_order = new_order
            
            transaction_obj = Transaction.objects.create(
                buyer_id=buyer_id,
                seller_id=seller_id,
                item=new_order.item,
                price=execution_price,
                quantity=trade_quantity,
                buy_order=buy_order,
                sell_order=sell_order
            )
            
            # Mise à jour des quantités exécutées
            new_order.filled_quantity += trade_quantity
            matching_order.filled_quantity += trade_quantity
            
            # Mise à jour des statuts
            new_order.update_status()
            matching_order.update_status()
            
            new_order.save()
            matching_order.save()
            
            transactions.append(transaction_obj)
            remaining_quantity -= trade_quantity
            
            logger.info(f"Transaction exécutée: {trade_quantity}x {new_order.item.name} @ {execution_price}€")
        
        return transactions
    
    def _update_order_book(self, order: Order) -> None:
        """
        Met à jour le carnet d'ordres en mémoire.
        
        Args:
            order: Ordre à ajouter/mettre à jour
        """
        item_id = order.item_id
        
        if item_id not in self._order_books:
            self._order_books[item_id] = {'BUY': [], 'SELL': []}
        
        # Suppression de l'ordre s'il n'est plus actif
        if not order.is_active:
            for order_list in self._order_books[item_id].values():
                if order in order_list:
                    order_list.remove(order)
        # Ajout de l'ordre s'il est actif et pas déjà présent
        elif order not in self._order_books[item_id][order.order_type]:
            self._order_books[item_id][order.order_type].append(order)
    
    def get_order_book(self, item: Item) -> Dict[str, List[Dict[str, Any]]]:
        """
        Récupère le carnet d'ordres pour un objet.
        
        Args:
            item: Objet concerné
            
        Returns:
            Dict avec les listes d'ordres d'achat et de vente
        """
        # Récupération depuis la base de données pour garantir la fraîcheur
        buy_orders = Order.objects.filter(
            item=item,
            order_type=OrderType.BUY,
            status__in=[OrderStatus.PENDING, OrderStatus.PARTIAL]
        ).order_by('-price', 'created_at')
        
        sell_orders = Order.objects.filter(
            item=item,
            order_type=OrderType.SELL,
            status__in=[OrderStatus.PENDING, OrderStatus.PARTIAL]
        ).order_by('price', 'created_at')
        
        return {
            'buy_orders': [self._order_to_dict(order) for order in buy_orders],
            'sell_orders': [self._order_to_dict(order) for order in sell_orders]
        }
    
    def _order_to_dict(self, order: Order) -> Dict[str, Any]:
        """Convertit un ordre en dictionnaire."""
        return {
            'id': order.id,
            'price': float(order.price),
            'quantity': order.remaining_quantity,
            'total': float(order.price * order.remaining_quantity),
            'created_at': order.created_at.isoformat()
        }
    
    def get_market_snapshot(self, item: Item = None) -> Dict[str, Any]:
        """
        Récupère un instantané du marché.
        
        Args:
            item: Objet spécifique ou None pour tous
            
        Returns:
            Dict avec les données de marché
        """
        if item:
            return self._get_item_market_data(item)
        
        # Données pour tous les objets
        items = Item.objects.all()
        market_data = {}
        
        for item in items:
            market_data[item.id] = self._get_item_market_data(item)
        
        return market_data
    
    def _get_item_market_data(self, item: Item) -> Dict[str, Any]:
        """
        Calcule les données de marché pour un objet spécifique.
        
        Args:
            item: Objet concerné
            
        Returns:
            Dict avec les données de marché
        """
        # Meilleurs prix
        best_bid = Order.objects.filter(
            item=item,
            order_type=OrderType.BUY,
            status__in=[OrderStatus.PENDING, OrderStatus.PARTIAL]
        ).order_by('-price').first()
        
        best_ask = Order.objects.filter(
            item=item,
            order_type=OrderType.SELL,
            status__in=[OrderStatus.PENDING, OrderStatus.PARTIAL]
        ).order_by('price').first()
        
        # Dernière transaction
        last_transaction = Transaction.objects.filter(
            item=item
        ).order_by('-timestamp').first()
        
        # Volume 24h
        from django.db.models import Sum, F
        since_24h = timezone.now() - timezone.timedelta(hours=24)
        volume_24h = Transaction.objects.filter(
            item=item,
            timestamp__gte=since_24h
        ).aggregate(
            total_quantity=Sum('quantity'),
            total_value=Sum(F('quantity') * F('price'))
        )
        
        return {
            'item_id': item.id,
            'item_name': item.name,
            'best_bid': float(best_bid.price) if best_bid else None,
            'best_ask': float(best_ask.price) if best_ask else None,
            'last_price': float(last_transaction.price) if last_transaction else None,
            'volume_24h': volume_24h['total_quantity'] or 0,
            'value_24h': float(volume_24h['total_value'] or 0),
            'spread': float(best_ask.price - best_bid.price) if (best_bid and best_ask) else None,
            'updated_at': timezone.now().isoformat()
        }
    
    def match_orders(self) -> List[Transaction]:
        """
        Effectue un matching global des ordres en attente.
        
        Returns:
            Liste des transactions créées
        """
        transactions = []
        
        # Récupération de tous les ordres actifs
        pending_orders = Order.objects.filter(
            status__in=[OrderStatus.PENDING, OrderStatus.PARTIAL]
        ).order_by('created_at')
        
        for order in pending_orders:
            if order.is_active and order.remaining_quantity > 0:
                matching_orders = self._find_matching_orders(order)
                if matching_orders:
                    new_transactions = self._execute_matches(order, matching_orders)
                    transactions.extend(new_transactions)
        
        return transactions
    
    def cancel_order(self, order_id: int, agent_id: str) -> bool:
        """
        Annule un ordre.
        
        Args:
            order_id: ID de l'ordre
            agent_id: ID de l'agent (vérification de propriété)
            
        Returns:
            True si l'annulation a réussi
        """
        try:
            order = Order.objects.get(id=order_id, agent_id=agent_id)
            
            if order.is_active:
                order.status = OrderStatus.CANCELLED
                order.save()
                
                # Suppression du carnet d'ordres
                self._update_order_book(order)
                
                logger.info(f"Ordre annulé: {order}")
                return True
            
        except Order.DoesNotExist:
            logger.warning(f"Tentative d'annulation d'un ordre inexistant: {order_id}")
        
        return False