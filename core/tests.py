"""
Tests pour l'app core.
"""

import pytest
from decimal import Decimal
from django.test import TestCase
from django.core.exceptions import ValidationError

from .models import Item, ItemCategory


class ItemModelTest(TestCase):
    """Tests pour le modèle Item."""
    
    def setUp(self):
        """Initialisation des données de test."""
        self.item_data = {
            'name': 'Carte Pikachu',
            'category': ItemCategory.TRADING_CARDS,
            'edition': 'Base Set',
            'total_supply': 1000,
            'description': 'Carte Pokémon rare'
        }
    
    def test_create_item(self):
        """Test de création d'un objet Item."""
        item = Item.objects.create(**self.item_data)
        
        assert item.name == 'Carte Pikachu'
        assert item.category == ItemCategory.TRADING_CARDS
        assert item.edition == 'Base Set'
        assert item.total_supply == 1000
        assert item.created_at is not None
        assert item.updated_at is not None
    
    def test_item_str_with_edition(self):
        """Test de la représentation string avec édition."""
        item = Item.objects.create(**self.item_data)
        expected = "Carte Pikachu (Base Set)"
        assert str(item) == expected
    
    def test_item_str_without_edition(self):
        """Test de la représentation string sans édition."""
        data = self.item_data.copy()
        data['edition'] = ''
        item = Item.objects.create(**data)
        
        assert str(item) == "Carte Pikachu"
    
    def test_item_validation_min_supply(self):
        """Test de validation pour la quantité minimale."""
        data = self.item_data.copy()
        data['total_supply'] = 0
        
        item = Item(**data)
        with pytest.raises(ValidationError):
            item.full_clean()
    
    def test_get_market_data_no_transactions(self):
        """Test des données de marché sans transactions."""
        item = Item.objects.create(**self.item_data)
        market_data = item.get_market_data()
        
        expected = {
            'last_price': None,
            'avg_price_24h': None,
            'volume_24h': 0,
            'price_trend': 'stable'
        }
        
        assert market_data == expected
    
    def test_item_categories(self):
        """Test des différentes catégories d'objets."""
        categories = [
            ItemCategory.TRADING_CARDS,
            ItemCategory.FIGURINES,
            ItemCategory.COMICS,
            ItemCategory.VINTAGE_TOYS,
            ItemCategory.ART,
            ItemCategory.OTHER
        ]
        
        for category in categories:
            data = self.item_data.copy()
            data['category'] = category
            data['name'] = f'Objet {category}'
            
            item = Item.objects.create(**data)
            assert item.category == category
    
    def test_item_ordering(self):
        """Test de l'ordre par défaut des objets."""
        # Création de plusieurs objets
        item1 = Item.objects.create(name='Item 1', total_supply=100)
        item2 = Item.objects.create(name='Item 2', total_supply=200)
        item3 = Item.objects.create(name='Item 3', total_supply=300)
        
        # Récupération dans l'ordre par défaut
        items = list(Item.objects.all())
        
        # Vérification que l'ordre est décroissant par date de création
        assert items[0] == item3  # Le plus récent en premier
        assert items[1] == item2
        assert items[2] == item1
