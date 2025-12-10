"""
Interface d'administration pour l'app core.
"""

from django.contrib import admin
from .models import Item


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    """Administration des objets de collection."""
    
    list_display = ['name', 'category', 'edition', 'total_supply', 'created_at']
    list_filter = ['category', 'created_at']
    search_fields = ['name', 'edition', 'description']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Informations de base', {
            'fields': ('name', 'category', 'edition')
        }),
        ('Détails', {
            'fields': ('description', 'total_supply')
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
