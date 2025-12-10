"""
Interface d'administration pour l'app market.
"""

from django.contrib import admin
from .models import Order, Transaction, MarketSnapshot


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """Administration des ordres."""
    
    list_display = [
        'id', 'item', 'order_type', 'agent_id', 'price', 
        'quantity', 'filled_quantity', 'status', 'created_at'
    ]
    list_filter = ['order_type', 'status', 'item__category', 'created_at']
    search_fields = ['agent_id', 'item__name']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at', 'filled_quantity']
    
    fieldsets = (
        ('Informations de l\'ordre', {
            'fields': ('item', 'agent_id', 'order_type')
        }),
        ('Détails financiers', {
            'fields': ('price', 'quantity', 'filled_quantity')
        }),
        ('État', {
            'fields': ('status',)
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    """Administration des transactions."""
    
    list_display = [
        'id', 'item', 'buyer_id', 'seller_id', 'price', 
        'quantity', 'total_value', 'timestamp'
    ]
    list_filter = ['item__category', 'timestamp']
    search_fields = ['buyer_id', 'seller_id', 'item__name']
    ordering = ['-timestamp']
    readonly_fields = ['timestamp', 'total_value']
    
    def total_value(self, obj):
        return f"{obj.total_value:.2f}€"
    total_value.short_description = "Valeur totale"


@admin.register(MarketSnapshot)
class MarketSnapshotAdmin(admin.ModelAdmin):
    """Administration des instantanés de marché."""
    
    list_display = [
        'id', 'item', 'best_bid', 'best_ask', 'last_price', 
        'volume_24h', 'created_at'
    ]
    list_filter = ['item__category', 'created_at']
    search_fields = ['item__name']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at']
