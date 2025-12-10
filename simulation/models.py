"""
Modèles pour stocker les résultats de simulation.
"""

from django.db import models
from core.mixins import TimeStampedMixin
from typing import Dict, Any


class SimulationRun(TimeStampedMixin, models.Model):
    """
    Modèle pour stocker les informations d'une simulation exécutée.
    """
    
    simulation_id = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="ID de simulation"
    )
    
    scenario = models.CharField(
        max_length=50,
        verbose_name="Scénario utilisé"
    )
    
    total_steps = models.PositiveIntegerField(
        verbose_name="Nombre d'étapes"
    )
    
    total_agents = models.PositiveIntegerField(
        verbose_name="Nombre d'agents"
    )
    
    start_time = models.DateTimeField(
        verbose_name="Heure de début"
    )
    
    end_time = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Heure de fin"
    )
    
    duration_seconds = models.FloatField(
        null=True,
        blank=True,
        verbose_name="Durée (secondes)"
    )
    
    status = models.CharField(
        max_length=20,
        choices=[
            ('running', 'En cours'),
            ('completed', 'Terminée'),
            ('failed', 'Échouée'),
            ('cancelled', 'Annulée')
        ],
        default='running',
        verbose_name="Statut"
    )
    
    config = models.JSONField(
        default=dict,
        verbose_name="Configuration"
    )
    
    results_summary = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Résumé des résultats"
    )
    
    results_file_path = models.CharField(
        max_length=500,
        blank=True,
        verbose_name="Chemin du fichier de résultats"
    )
    
    class Meta:
        verbose_name = "Exécution de simulation"
        verbose_name_plural = "Exécutions de simulation"
        ordering = ['-created_at']
    
    def __str__(self) -> str:
        return f"Simulation {self.simulation_id} - {self.scenario}"
    
    @property
    def is_running(self) -> bool:
        """Vérifie si la simulation est en cours."""
        return self.status == 'running'
    
    @property
    def is_completed(self) -> bool:
        """Vérifie si la simulation est terminée."""
        return self.status == 'completed'


class SimulationMetric(TimeStampedMixin, models.Model):
    """
    Modèle pour stocker les métriques détaillées par étape.
    """
    
    simulation = models.ForeignKey(
        SimulationRun,
        on_delete=models.CASCADE,
        related_name="metrics",
        verbose_name="Simulation"
    )
    
    step_number = models.PositiveIntegerField(
        verbose_name="Numéro d'étape"
    )
    
    orders_created = models.PositiveIntegerField(
        default=0,
        verbose_name="Ordres créés"
    )
    
    transactions_executed = models.PositiveIntegerField(
        default=0,
        verbose_name="Transactions exécutées"
    )
    
    total_volume = models.PositiveIntegerField(
        default=0,
        verbose_name="Volume total"
    )
    
    total_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Valeur totale"
    )
    
    active_agents = models.PositiveIntegerField(
        default=0,
        verbose_name="Agents actifs"
    )
    
    pending_orders = models.PositiveIntegerField(
        default=0,
        verbose_name="Ordres en attente"
    )
    
    execution_time = models.FloatField(
        default=0,
        verbose_name="Temps d'exécution (ms)"
    )
    
    additional_data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Données supplémentaires"
    )
    
    class Meta:
        verbose_name = "Métrique de simulation"
        verbose_name_plural = "Métriques de simulation"
        ordering = ['simulation', 'step_number']
        unique_together = ['simulation', 'step_number']
        indexes = [
            models.Index(fields=['simulation', 'step_number']),
        ]
    
    def __str__(self) -> str:
        return f"Métrique {self.simulation.simulation_id} - Étape {self.step_number}"
