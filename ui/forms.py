"""
Formulaires pour l'interface utilisateur.
"""

from django import forms
from simulation.scenarios import AVAILABLE_SCENARIOS


class SimulationForm(forms.Form):
    """
    Formulaire pour configurer et lancer une nouvelle simulation.
    """
    
    # Choix des scénarios
    SCENARIO_CHOICES = [
        (name, name.replace('_', ' ').title()) 
        for name in AVAILABLE_SCENARIOS.keys()
    ]
    
    scenario = forms.ChoiceField(
        choices=SCENARIO_CHOICES,
        initial='baseline',
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'id_scenario'
        }),
        help_text="Type d'expérience à simuler"
    )
    
    n_steps = forms.IntegerField(
        min_value=10,
        max_value=2000,
        initial=100,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'id': 'id_n_steps',
            'min': '10',
            'max': '2000'
        }),
        help_text="Nombre d'étapes de simulation (10-2000)"
    )
    
    n_buyers = forms.IntegerField(
        min_value=1,
        max_value=500,
        initial=30,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'id': 'id_n_buyers',
            'min': '1',
            'max': '500'
        }),
        help_text="Nombre d'agents acheteurs (1-500)"
    )
    
    n_sellers = forms.IntegerField(
        min_value=1,
        max_value=500,
        initial=20,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'id': 'id_n_sellers',
            'min': '1',
            'max': '500'
        }),
        help_text="Nombre d'agents vendeurs (1-500)"
    )
    
    n_items = forms.IntegerField(
        min_value=1,
        max_value=100,
        initial=10,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'id': 'id_n_items',
            'min': '1',
            'max': '100'
        }),
        help_text="Nombre d'objets de collection (1-100)"
    )
    
    seed = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'id': 'id_seed',
            'placeholder': 'Optionnel'
        }),
        help_text="Graine pour la reproductibilité (optionnel)"
    )
    
    def clean(self):
        """Validation croisée des données du formulaire."""
        cleaned_data = super().clean()
        
        n_buyers = cleaned_data.get('n_buyers', 0)
        n_sellers = cleaned_data.get('n_sellers', 0)
        n_steps = cleaned_data.get('n_steps', 0)
        n_items = cleaned_data.get('n_items', 0)
        
        # Vérification que le total d'agents n'est pas trop déséquilibré
        total_agents = n_buyers + n_sellers
        
        if total_agents > 1000:
            raise forms.ValidationError(
                "Le nombre total d'agents ne peut pas dépasser 1000."
            )
        
        if n_buyers == 0 and n_sellers == 0:
            raise forms.ValidationError(
                "Il faut au moins un acheteur ou un vendeur."
            )
        
        # Vérification que le nombre d'objets est raisonnable par rapport aux agents
        if n_items > total_agents:
            self.add_error('n_items', 
                "Le nombre d'objets ne devrait pas dépasser le nombre d'agents.")
        
        # Avertissement pour les simulations longues
        if n_steps > 1000 and total_agents > 100:
            # Pas d'erreur mais on pourrait ajouter un warning
            pass
        
        return cleaned_data
    
    def clean_seed(self):
        """Validation de la graine aléatoire."""
        seed = self.cleaned_data.get('seed')
        
        if seed is not None:
            if seed < 0 or seed > 2**32 - 1:
                raise forms.ValidationError(
                    "La graine doit être comprise entre 0 et 4294967295."
                )
        
        return seed