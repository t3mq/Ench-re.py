"""
Mixins réutilisables pour les modèles et vues.
"""

from django.db import models
from django.utils import timezone
from typing import Dict, Any
import uuid


class TimeStampedMixin(models.Model):
    """
    Mixin ajoutant des timestamps de création et modification.
    """
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date de création"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Dernière modification"
    )
    
    class Meta:
        abstract = True


class UUIDMixin(models.Model):
    """
    Mixin ajoutant un champ UUID comme clé primaire.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    class Meta:
        abstract = True


class SoftDeleteMixin(models.Model):
    """
    Mixin pour la suppression logique (soft delete).
    """
    is_deleted = models.BooleanField(default=False, verbose_name="Supprimé")
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name="Date de suppression")
    
    class Meta:
        abstract = True
    
    def delete(self, using=None, keep_parents=False):
        """Suppression logique au lieu de suppression physique."""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(using=using)
    
    def hard_delete(self, using=None, keep_parents=False):
        """Suppression physique réelle."""
        super().delete(using=using, keep_parents=keep_parents)
    
    def restore(self):
        """Restaure un objet supprimé logiquement."""
        self.is_deleted = False
        self.deleted_at = None
        self.save()


class SerializableMixin:
    """
    Mixin ajoutant des méthodes de sérialisation.
    """
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convertit l'instance en dictionnaire.
        
        Returns:
            Dict représentant l'objet
        """
        data = {}
        
        for field in self._meta.fields:
            value = getattr(self, field.name)
            
            # Gestion des types spéciaux
            if hasattr(value, 'isoformat'):  # datetime
                data[field.name] = value.isoformat()
            elif hasattr(value, '__str__') and not isinstance(value, str):
                data[field.name] = str(value)
            else:
                data[field.name] = value
        
        return data
    
    def from_dict(self, data: Dict[str, Any]) -> None:
        """
        Met à jour l'instance depuis un dictionnaire.
        
        Args:
            data: Dictionnaire avec les nouvelles valeurs
        """
        for key, value in data.items():
            if hasattr(self, key):
                setattr(self, key, value)


class ActiveManager(models.Manager):
    """Manager personnalisé pour filtrer les objets actifs (non supprimés)."""
    
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class AllObjectsManager(models.Manager):
    """Manager pour accéder à tous les objets, y compris les supprimés."""
    
    def get_queryset(self):
        return super().get_queryset()