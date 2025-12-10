"""
Exceptions personnalisées pour l'app market.
"""


class MarketException(Exception):
    """Exception de base pour les erreurs de marché."""
    pass


class InvalidOrderException(MarketException):
    """Exception levée pour un ordre invalide."""
    pass


class InsufficientLiquidityException(MarketException):
    """Exception levée quand il n'y a pas assez de liquidité."""
    pass


class OrderNotFoundException(MarketException):
    """Exception levée quand un ordre n'est pas trouvé."""
    pass


class UnauthorizedOrderActionException(MarketException):
    """Exception levée pour une action non autorisée sur un ordre."""
    pass


class MarketClosedException(MarketException):
    """Exception levée quand le marché est fermé."""
    pass


class InvalidAgentException(MarketException):
    """Exception levée pour un agent invalide."""
    pass


class PriceOutOfRangeException(MarketException):
    """Exception levée quand un prix est hors des limites acceptables."""
    pass