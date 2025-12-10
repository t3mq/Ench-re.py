"""
Scénarios de simulation pour différentes expériences de marché.
"""

import random
from abc import ABC, abstractmethod
from typing import List, Any
from decimal import Decimal
import logging

from market.engine import MarketEngine

logger = logging.getLogger('simulation')


class BaseScenario(ABC):
    """
    Classe de base pour tous les scénarios de simulation.
    
    Un scénario définit des événements ou modifications du comportement
    du marché à des moments spécifiques de la simulation.
    """
    
    def __init__(self, name: str = "Base Scenario"):
        """
        Initialise le scénario.
        
        Args:
            name: Nom du scénario
        """
        self.name = name
        self.parameters = {}
        
    @abstractmethod
    def apply_step_effects(self, step: int, agents: List[Any], market: MarketEngine) -> None:
        """
        Applique les effets du scénario à une étape donnée.
        
        Args:
            step: Numéro de l'étape courante
            agents: Liste des agents participant
            market: Moteur de marché
        """
        pass
    
    def get_description(self) -> str:
        """Retourne une description du scénario."""
        return f"Scénario: {self.name}"


class BaselineScenario(BaseScenario):
    """
    Scénario de base sans modifications particulières.
    
    Utilise les comportements normaux des agents sans intervention externe.
    """
    
    def __init__(self):
        super().__init__("Baseline")
        self.parameters = {
            'description': 'Simulation standard sans événements particuliers',
            'market_stability': 1.0,
            'agent_activity': 1.0
        }
    
    def apply_step_effects(self, step: int, agents: List[Any], market: MarketEngine) -> None:
        """
        Scénario baseline - aucune intervention.
        
        Args:
            step: Étape courante
            agents: Agents participants
            market: Moteur de marché
        """
        # Aucune modification dans le scénario de base
        pass
    
    def get_description(self) -> str:
        return "Scénario de base sans événements externes"


class DemandDoubleScenario(BaseScenario):
    """
    Scénario avec doublement de la demande à un moment donné.
    
    Simule un événement qui double la probabilité d'achat des agents
    pendant une période définie.
    """
    
    def __init__(self, trigger_step: int = 50, duration: int = 30):
        """
        Initialise le scénario de doublement de demande.
        
        Args:
            trigger_step: Étape où l'événement se déclenche
            duration: Durée de l'effet (en étapes)
        """
        super().__init__("Demand x2")
        self.trigger_step = trigger_step
        self.duration = duration
        self.end_step = trigger_step + duration
        
        self.parameters = {
            'description': 'Doublement de la demande pendant une période',
            'trigger_step': trigger_step,
            'duration': duration,
            'demand_multiplier': 2.0
        }
        
        logger.info(f"Scénario Demand x2: début étape {trigger_step}, durée {duration} étapes")
    
    def apply_step_effects(self, step: int, agents: List[Any], market: MarketEngine) -> None:
        """
        Applique les effets de doublement de demande.
        
        Args:
            step: Étape courante
            agents: Agents participants
            market: Moteur de marché
        """
        if self.trigger_step <= step < self.end_step:
            # Période de demande accrue
            self._boost_buying_activity(agents, step)
            
            # Log du déclenchement
            if step == self.trigger_step:
                logger.info(f"Étape {step}: Activation du boost de demande x2")
        
        elif step == self.end_step:
            logger.info(f"Étape {step}: Fin du boost de demande")
    
    def _boost_buying_activity(self, agents: List[Any], step: int) -> None:
        """
        Augmente l'activité d'achat des agents.
        
        Args:
            agents: Liste des agents
            step: Étape courante
        """
        from .agents import Buyer
        
        buyers = [agent for agent in agents if isinstance(agent, Buyer)]
        
        for buyer in buyers:
            # Augmentation temporaire du budget disponible
            if not hasattr(buyer, '_original_budget'):
                buyer._original_budget = buyer.budget_per_item
            
            # Double le budget temporairement (effet psychologique)
            buyer.budget_per_item = buyer._original_budget * Decimal('1.5')
            
            # Augmente la tolérance au risque temporairement
            if not hasattr(buyer, '_original_risk'):
                buyer._original_risk = buyer.risk_tolerance
            
            buyer.risk_tolerance = min(buyer._original_risk * 1.3, 0.95)
    
    def get_description(self) -> str:
        return f"Doublement de la demande de l'étape {self.trigger_step} à {self.end_step}"


class VolatilitySpike(BaseScenario):
    """
    Scénario avec pic de volatilité des prix.
    
    Augmente temporairement la volatilité des prix en modifiant
    les comportements des agents.
    """
    
    def __init__(self, trigger_step: int = 75, intensity: float = 2.0):
        """
        Initialise le scénario de volatilité.
        
        Args:
            trigger_step: Étape de déclenchement
            intensity: Intensité de la volatilité (multiplicateur)
        """
        super().__init__("Volatility Spike")
        self.trigger_step = trigger_step
        self.intensity = intensity
        
        self.parameters = {
            'description': 'Pic de volatilité des prix',
            'trigger_step': trigger_step,
            'volatility_multiplier': intensity
        }
    
    def apply_step_effects(self, step: int, agents: List[Any], market: MarketEngine) -> None:
        """
        Applique les effets de volatilité.
        
        Args:
            step: Étape courante
            agents: Agents participants
            market: Moteur de marché
        """
        if step == self.trigger_step:
            self._trigger_volatility(agents)
            logger.info(f"Étape {step}: Déclenchement du pic de volatilité x{self.intensity}")
    
    def _trigger_volatility(self, agents: List[Any]) -> None:
        """
        Déclenche la volatilité en modifiant les agents.
        
        Args:
            agents: Liste des agents
        """
        for agent in agents:
            # Augmente temporairement l'aversion au risque ou l'inverse
            if random.random() < 0.5:
                # Certains agents deviennent plus prudents
                agent.risk_tolerance *= 0.7
            else:
                # D'autres deviennent plus agressifs
                agent.risk_tolerance *= 1.4
            
            # Borne les valeurs
            agent.risk_tolerance = max(0.1, min(0.9, agent.risk_tolerance))


class MarketCrash(BaseScenario):
    """
    Scénario de krach de marché.
    
    Simule un événement de vente massive qui fait chuter les prix.
    """
    
    def __init__(self, trigger_step: int = 60):
        """
        Initialise le scénario de krach.
        
        Args:
            trigger_step: Étape de déclenchement
        """
        super().__init__("Market Crash")
        self.trigger_step = trigger_step
        self.triggered = False
        
        self.parameters = {
            'description': 'Krach de marché avec vente massive',
            'trigger_step': trigger_step,
            'crash_intensity': 0.7
        }
    
    def apply_step_effects(self, step: int, agents: List[Any], market: MarketEngine) -> None:
        """
        Applique les effets du krach.
        
        Args:
            step: Étape courante
            agents: Agents participants
            market: Moteur de marché
        """
        if step == self.trigger_step and not self.triggered:
            self._trigger_crash(agents)
            self.triggered = True
            logger.warning(f"Étape {step}: Déclenchement du krach de marché")
    
    def _trigger_crash(self, agents: List[Any]) -> None:
        """
        Déclenche le krach en forçant des ventes.
        
        Args:
            agents: Liste des agents
        """
        from .agents import Seller
        
        sellers = [agent for agent in agents if isinstance(agent, Seller)]
        
        # Force une partie des vendeurs à vendre en urgence
        panic_sellers = random.sample(sellers, min(len(sellers), len(sellers) // 2))
        
        for seller in panic_sellers:
            # Réduit drastiquement le target de profit
            seller.profit_target = Decimal('0.8')  # Vente à perte
            # Augmente l'urgence
            if hasattr(seller, 'patience'):
                seller.patience = 0.1


class LiquidityDrain(BaseScenario):
    """
    Scénario de drain de liquidité.
    
    Retire temporairement des agents du marché pour simuler
    une réduction de liquidité.
    """
    
    def __init__(self, trigger_step: int = 40, affected_ratio: float = 0.3):
        """
        Initialise le scénario de drain de liquidité.
        
        Args:
            trigger_step: Étape de déclenchement
            affected_ratio: Proportion d'agents affectés (0.0 à 1.0)
        """
        super().__init__("Liquidity Drain")
        self.trigger_step = trigger_step
        self.affected_ratio = affected_ratio
        self.affected_agents = []
        
        self.parameters = {
            'description': 'Réduction temporaire de la liquidité',
            'trigger_step': trigger_step,
            'affected_ratio': affected_ratio
        }
    
    def apply_step_effects(self, step: int, agents: List[Any], market: MarketEngine) -> None:
        """
        Applique les effets de drain de liquidité.
        
        Args:
            step: Étape courante
            agents: Agents participants
            market: Moteur de marché
        """
        if step == self.trigger_step:
            self._start_liquidity_drain(agents)
            logger.info(f"Étape {step}: Début du drain de liquidité ({len(self.affected_agents)} agents)")
        
        elif step == self.trigger_step + 20:  # Fin après 20 étapes
            self._end_liquidity_drain()
            logger.info(f"Étape {step}: Fin du drain de liquidité")
    
    def _start_liquidity_drain(self, agents: List[Any]) -> None:
        """
        Commence le drain en réduisant l'activité de certains agents.
        
        Args:
            agents: Liste des agents
        """
        n_affected = int(len(agents) * self.affected_ratio)
        self.affected_agents = random.sample(agents, n_affected)
        
        for agent in self.affected_agents:
            # Sauvegarde les valeurs originales
            agent._original_patience = getattr(agent, 'patience', 0.5)
            # Réduit drastiquement l'activité
            agent.patience = 0.05  # Très peu probable de placer des ordres
    
    def _end_liquidity_drain(self) -> None:
        """Restaure l'activité des agents affectés."""
        for agent in self.affected_agents:
            if hasattr(agent, '_original_patience'):
                agent.patience = agent._original_patience
                delattr(agent, '_original_patience')
        
        self.affected_agents.clear()


# Factory pour créer les scénarios
AVAILABLE_SCENARIOS = {
    'baseline': BaselineScenario,
    'demand_x2': DemandDoubleScenario,
    'volatility_spike': VolatilitySpike,
    'market_crash': MarketCrash,
    'liquidity_drain': LiquidityDrain
}


def create_scenario(scenario_name: str, **kwargs) -> BaseScenario:
    """
    Factory pour créer un scénario.
    
    Args:
        scenario_name: Nom du scénario
        **kwargs: Paramètres du scénario
        
    Returns:
        Instance du scénario
        
    Raises:
        ValueError: Si le scénario n'existe pas
    """
    if scenario_name not in AVAILABLE_SCENARIOS:
        available = ', '.join(AVAILABLE_SCENARIOS.keys())
        raise ValueError(f"Scénario '{scenario_name}' inconnu. Disponibles: {available}")
    
    scenario_class = AVAILABLE_SCENARIOS[scenario_name]
    return scenario_class(**kwargs)