"""
Utilitaires et fonctions helper pour l'application.
"""

import json
import random
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Any, Union, Optional
import logging

logger = logging.getLogger(__name__)


class JSONEncoder(json.JSONEncoder):
    """Encodeur JSON personnalisé pour les types Django."""
    
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, Decimal):
            return float(obj)
        elif hasattr(obj, 'to_dict'):
            return obj.to_dict()
        return super().default(obj)


def save_json(data: Dict[str, Any], filepath: Union[str, Path]) -> bool:
    """
    Sauvegarde des données en format JSON.
    
    Args:
        data: Données à sauvegarder
        filepath: Chemin du fichier de destination
        
    Returns:
        True si succès, False sinon
    """
    try:
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, cls=JSONEncoder, indent=2, ensure_ascii=False)
        
        logger.info(f"Données sauvegardées dans {filepath}")
        return True
        
    except Exception as e:
        logger.error(f"Erreur lors de la sauvegarde JSON: {e}")
        return False


def load_json(filepath: Union[str, Path]) -> Optional[Dict[str, Any]]:
    """
    Charge des données depuis un fichier JSON.
    
    Args:
        filepath: Chemin du fichier à charger
        
    Returns:
        Dict avec les données ou None si erreur
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        logger.info(f"Données chargées depuis {filepath}")
        return data
        
    except FileNotFoundError:
        logger.warning(f"Fichier non trouvé: {filepath}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Erreur de format JSON: {e}")
        return None
    except Exception as e:
        logger.error(f"Erreur lors du chargement JSON: {e}")
        return None


def generate_simulation_id() -> str:
    """Génère un ID unique pour une simulation."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    random_suffix = random.randint(1000, 9999)
    return f"sim_{timestamp}_{random_suffix}"


def calculate_price_bounds(current_price: Decimal, volatility: float = 0.1) -> tuple:
    """
    Calcule les bornes de prix pour les ordres.
    
    Args:
        current_price: Prix actuel
        volatility: Volatilité (pourcentage de variation)
        
    Returns:
        Tuple (prix_min, prix_max)
    """
    if current_price <= 0:
        return (Decimal('1.0'), Decimal('100.0'))
    
    variation = current_price * Decimal(str(volatility))
    price_min = max(current_price - variation, Decimal('0.01'))
    price_max = current_price + variation
    
    return (price_min, price_max)


def weighted_random_choice(choices: List[tuple]) -> Any:
    """
    Sélection aléatoire pondérée.
    
    Args:
        choices: Liste de tuples (valeur, poids)
        
    Returns:
        Valeur sélectionnée
    """
    if not choices:
        return None
    
    total_weight = sum(weight for _, weight in choices)
    if total_weight <= 0:
        return random.choice([value for value, _ in choices])
    
    r = random.uniform(0, total_weight)
    cumulative = 0
    
    for value, weight in choices:
        cumulative += weight
        if r <= cumulative:
            return value
    
    # Fallback
    return choices[-1][0]


class SimulationTimer:
    """Utilitaire pour mesurer les performances des simulations."""
    
    def __init__(self, name: str):
        self.name = name
        self.start_time = None
        self.end_time = None
    
    def __enter__(self):
        self.start_time = datetime.now()
        logger.info(f"Début de {self.name}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = datetime.now()
        duration = self.end_time - self.start_time
        logger.info(f"Fin de {self.name} - Durée: {duration}")
    
    @property
    def duration(self) -> float:
        """Durée en secondes."""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0


def format_currency(amount: Union[Decimal, float], currency: str = '€') -> str:
    """
    Formate un montant en devise.
    
    Args:
        amount: Montant à formater
        currency: Symbole de devise
        
    Returns:
        String formatée
    """
    if isinstance(amount, (int, float, Decimal)):
        return f"{amount:.2f} {currency}"
    return f"0.00 {currency}"


def calculate_statistics(values: List[Union[int, float, Decimal]]) -> Dict[str, float]:
    """
    Calcule des statistiques de base.
    
    Args:
        values: Liste de valeurs numériques
        
    Returns:
        Dict avec min, max, moyenne, médiane
    """
    if not values:
        return {'min': 0, 'max': 0, 'mean': 0, 'median': 0, 'count': 0}
    
    values = [float(v) for v in values]
    values.sort()
    
    n = len(values)
    
    return {
        'min': values[0],
        'max': values[-1],
        'mean': sum(values) / n,
        'median': values[n // 2] if n % 2 == 1 else (values[n // 2 - 1] + values[n // 2]) / 2,
        'count': n
    }