"""
Modèles pour l'app market.
Gestion des ordres, transactions et données de marché.
"""

from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal
from core.models import Item
from core.mixins import TimeStampedMixin, SerializableMixin
from typing import Dict, Any


class OrderType(models.TextChoices):
    """Types d'ordres sur le marché."""
    BUY = 'BUY', 'Achat'
    SELL = 'SELL', 'Vente'


class OrderStatus(models.TextChoices):
    """États des ordres."""
    PENDING = 'PENDING', 'En attente'
    PARTIAL = 'PARTIAL', 'Partiellement exécuté'
    FILLED = 'FILLED', 'Complètement exécuté'
    CANCELLED = 'CANCELLED', 'Annulé'
    EXPIRED = 'EXPIRED', 'Expiré'


class Order(TimeStampedMixin, SerializableMixin, models.Model):
    """
    Modèle représentant un ordre d'achat ou de vente.
    
    Attributes:
        item: Objet concerné par l'ordre
        agent_id: Identifiant de l'agent qui place l'ordre
        order_type: Type d'ordre (BUY/SELL)
        price: Prix unitaire proposé
        quantity: Quantité demandée
        filled_quantity: Quantité déjà exécutée
        status: État de l'ordre
    """
    
    item = models.ForeignKey(
        Item,
        on_delete=models.CASCADE,
        verbose_name="Objet",
        related_name="orders"
    )
    
    agent_id = models.CharField(
        max_length=50,
        verbose_name="ID Agent",
        help_text="Identifiant de l'agent qui place l'ordre"
    )
    
    order_type = models.CharField(
        max_length=4,
        choices=OrderType.choices,
        verbose_name="Type d'ordre"
    )
    
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name="Prix unitaire"
    )
    
    quantity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        verbose_name="Quantité"
    )
    
    filled_quantity = models.PositiveIntegerField(
        default=0,
        verbose_name="Quantité exécutée"
    )
    
    status = models.CharField(
        max_length=10,
        choices=OrderStatus.choices,
        default=OrderStatus.PENDING,
        verbose_name="État"
    )
    
    class Meta:
        verbose_name = "Ordre"
        verbose_name_plural = "Ordres"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['item', 'order_type', 'status']),
            models.Index(fields=['agent_id']),
            models.Index(fields=['created_at']),
            models.Index(fields=['price']),
        ]
    
    def __str__(self) -> str:
        return f"{self.get_order_type_display()} {self.quantity}x {self.item.name} @ {self.price}€"
    
    @property
    def remaining_quantity(self) -> int:
        """Quantité restant à exécuter."""
        return self.quantity - self.filled_quantity
    
    @property
    def is_active(self) -> bool:
        """Vérifie si l'ordre est encore actif."""
        return self.status in [OrderStatus.PENDING, OrderStatus.PARTIAL]
    
    @property
    def total_value(self) -> Decimal:
        """Valeur totale de l'ordre."""
        return self.price * self.quantity
    
    def can_match_with(self, other_order: 'Order') -> bool:
        """
        Vérifie si cet ordre peut être matché avec un autre.
        
        Args:
            other_order: Autre ordre à vérifier
            
        Returns:
            True si les ordres peuvent être matchés
        """
        if not (self.is_active and other_order.is_active):
            return False
        
        if self.item_id != other_order.item_id:
            return False
        
        if self.order_type == other_order.order_type:
            return False
        
        if self.agent_id == other_order.agent_id:
            return False
        
        # Vérification des prix compatibles
        if self.order_type == OrderType.BUY:
            return self.price >= other_order.price
        else:
            return self.price <= other_order.price
    
    def update_status(self) -> None:
        """Met à jour le statut de l'ordre selon la quantité exécutée."""
        if self.filled_quantity == 0:
            self.status = OrderStatus.PENDING
        elif self.filled_quantity < self.quantity:
            self.status = OrderStatus.PARTIAL
        else:
            self.status = OrderStatus.FILLED


class Transaction(TimeStampedMixin, SerializableMixin, models.Model):
    """
    Modèle représentant une transaction exécutée.
    
    Attributes:
        buyer_id: Identifiant de l'acheteur
        seller_id: Identifiant du vendeur
        item: Objet échangé
        price: Prix d'exécution
        quantity: Quantité échangée
        buy_order: Ordre d'achat associé
        sell_order: Ordre de vente associé
    """
    
    buyer_id = models.CharField(
        max_length=50,
        verbose_name="ID Acheteur"
    )
    
    seller_id = models.CharField(
        max_length=50,
        verbose_name="ID Vendeur"
    )
    
    item = models.ForeignKey(
        Item,
        on_delete=models.CASCADE,
        verbose_name="Objet",
        related_name="transactions"
    )
    
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name="Prix d'exécution"
    )
    
    quantity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        verbose_name="Quantité"
    )
    
    buy_order = models.ForeignKey(
        Order,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Ordre d'achat",
        related_name="buy_transactions"
    )
    
    sell_order = models.ForeignKey(
        Order,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Ordre de vente",
        related_name="sell_transactions"
    )
    
    # Timestamp héritée de TimeStampedMixin renommée pour clarté
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="Heure d'exécution")
    
    class Meta:
        verbose_name = "Transaction"
        verbose_name_plural = "Transactions"
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['item', 'timestamp']),
            models.Index(fields=['buyer_id']),
            models.Index(fields=['seller_id']),
            models.Index(fields=['timestamp']),
        ]
    
    def __str__(self) -> str:
        return f"Transaction {self.quantity}x {self.item.name} @ {self.price}€"
    
    @property
    def total_value(self) -> Decimal:
        """Valeur totale de la transaction."""
        return self.price * self.quantity


class MarketSnapshot(TimeStampedMixin, models.Model):
    """
    Modèle pour stocker des instantanés du marché.
    
    Attributes:
        item: Objet concerné
        best_bid: Meilleure offre d'achat
        best_ask: Meilleure offre de vente
        last_price: Dernier prix d'exécution
        volume_24h: Volume des dernières 24h
        data: Données additionnelles en JSON
    """
    
    item = models.ForeignKey(
        Item,
        on_delete=models.CASCADE,
        verbose_name="Objet",
        related_name="market_snapshots"
    )
    
    best_bid = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Meilleure offre d'achat"
    )
    
    best_ask = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Meilleure offre de vente"
    )
    
    last_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Dernier prix"
    )
    
    volume_24h = models.PositiveIntegerField(
        default=0,
        verbose_name="Volume 24h"
    )
    
    data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Données additionnelles"
    )
    
    class Meta:
        verbose_name = "Instantané de marché"
        verbose_name_plural = "Instantanés de marché"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['item', 'created_at']),
        ]
    
    def __str__(self) -> str:
        return f"Marché {self.item.name} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"
