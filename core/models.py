"""
Modèles de base pour l'app core.
Contient les objets de collection échangés sur le marché.
"""

from django.db import models
from django.core.validators import MinValueValidator
from typing import Dict, Any


class ItemCategory(models.TextChoices):
    """Catégories d'objets de collection."""
    TRADING_CARDS = 'cards', 'Cartes à collectionner'
    FIGURINES = 'figurines', 'Figurines'
    COMICS = 'comics', 'Bandes dessinées'
    VINTAGE_TOYS = 'toys', 'Jouets vintage'
    ART = 'art', 'Art et illustrations'
    OTHER = 'other', 'Autres'


class Item(models.Model):
    """
    Modèle représentant un objet de collection.
    
    Attributes:
        name: Nom de l'objet
        category: Catégorie de l'objet
        edition: Édition ou série de l'objet
        total_supply: Quantité totale en circulation
        description: Description détaillée
        created_at: Date de création
        updated_at: Date de dernière modification
    """
    
    name = models.CharField(
        max_length=200,
        verbose_name="Nom de l'objet",
        help_text="Nom descriptif de l'objet de collection"
    )
    
    category = models.CharField(
        max_length=20,
        choices=ItemCategory.choices,
        default=ItemCategory.OTHER,
        verbose_name="Catégorie"
    )
    
    edition = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Édition",
        help_text="Édition ou série de l'objet"
    )
    
    total_supply = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        verbose_name="Offre totale",
        help_text="Quantité totale d'objets en circulation"
    )
    
    description = models.TextField(
        blank=True,
        verbose_name="Description",
        help_text="Description détaillée de l'objet"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Objet de collection"
        verbose_name_plural = "Objets de collection"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['category', 'name']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self) -> str:
        """Représentation string de l'objet."""
        if self.edition:
            return f"{self.name} ({self.edition})"
        return self.name
    
    def get_market_data(self) -> Dict[str, Any]:
        """
        Récupère les données de marché pour cet objet.
        
        Returns:
            Dict contenant les informations de marché
        """
        from market.models import Transaction
        
        recent_transactions = Transaction.objects.filter(
            item=self
        ).order_by('-timestamp')[:10]
        
        if not recent_transactions.exists():
            return {
                'last_price': None,
                'avg_price_24h': None,
                'volume_24h': 0,
                'price_trend': 'stable'
            }
        
        prices = [t.price for t in recent_transactions]
        quantities = [t.quantity for t in recent_transactions]
        
        return {
            'last_price': prices[0] if prices else None,
            'avg_price_24h': sum(prices) / len(prices) if prices else None,
            'volume_24h': sum(quantities),
            'price_trend': self._calculate_trend(prices)
        }
    
    def _calculate_trend(self, prices: list) -> str:
        """Calcule la tendance des prix."""
        if len(prices) < 2:
            return 'stable'
        
        recent_avg = sum(prices[:3]) / min(3, len(prices))
        older_avg = sum(prices[3:6]) / max(1, len(prices[3:6]))
        
        if recent_avg > older_avg * 1.05:
            return 'up'
        elif recent_avg < older_avg * 0.95:
            return 'down'
        return 'stable'
