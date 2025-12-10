# 🏷️ Ench-re.py - Simulateur de Marché d'Enchères

Un simulateur de marché secondaire d'objets de collection utilisant la modélisation agent-based (ABM) développé avec Django et Python.

## 📋 Table des Matières

- [Description](#-description)
- [Caractéristiques](#-caractéristiques)
- [Architecture](#-architecture)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Usage](#-usage)
- [Scénarios de Simulation](#-scénarios-de-simulation)
- [API et Interface](#-api-et-interface)
- [Tests](#-tests)
- [Structure du Projet](#-structure-du-projet)
- [Contribuer](#-contribuer)
- [Licence](#-licence)

## 🎯 Description

Ench-re.py est un simulateur qui modélise un marché secondaire d'objets de collection (cartes à collectionner, figurines, comics, etc.) en utilisant des agents autonomes (acheteurs et vendeurs). Le système simule les interactions de marché, l'évolution des prix, et l'impact de différents événements sur la liquidité et la volatilité.

### Objectifs Pédagogiques

- Comprendre la dynamique des marchés financiers
- Observer l'impact d'événements sur les prix
- Analyser le comportement des agents en situation d'incertitude
- Étudier la formation des prix par l'offre et la demande

## ✨ Caractéristiques

### Core Features

- **Agents Intelligents** : Acheteurs et vendeurs avec personnalités et stratégies différentes
- **Moteur de Marché** : Système de matching d'ordres avec carnet d'ordres en temps réel
- **Scénarios Configurables** : Différents événements de marché simulables
- **Interface Web** : Dashboard pour lancer et suivre les simulations
- **Persistance des Données** : PostgreSQL/SQLite avec exports JSON/CSV
- **Métriques Détaillées** : Suivi complet des performances et transactions

### Principes de Design

- **KISS** (Keep It Simple and Stupid)
- **Separation of Concerns** (SoC)
- **Single Responsibility** par module
- **Éviter la duplication de code**
- **Programmation Orientée Objet** claire

## 🏗️ Architecture

### Apps Django

```
📦 enchre_market/
├── 📁 core/           # Modèles de base (Item), utilitaires
├── 📁 market/         # Logique de marché (Orders, Transactions, MarketEngine)
├── 📁 simulation/     # Agents, SimulationManager, scénarios
├── 📁 ui/            # Interface web Django templates
└── 📁 api/           # Endpoints REST (optionnel)
```

### Classes Principales

```python
# Core
class Item                 # Objets de collection
class MarketEngine        # Moteur de matching
class SimulationManager   # Orchestrateur de simulation

# Agents
class Agent               # Classe de base
class Buyer              # Agent acheteur
class Seller             # Agent vendeur

# Scénarios
class BaseScenario       # Simulation standard
class DemandDoubleScenario # Doublement de demande
```

## 🚀 Installation

### Prérequis

- Python 3.11+
- PostgreSQL (optionnel, SQLite par défaut)
- Git

### Étapes d'Installation

1. **Cloner le repository**
   ```bash
   git clone https://github.com/t3mq/Ench-re.py.git
   cd Ench-re.py
   ```

2. **Créer l'environnement virtuel**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # Linux/Mac
   # ou
   venv\\Scripts\\activate    # Windows
   ```

3. **Installer les dépendances**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configuration de l'environnement**
   ```bash
   cp .env.example .env
   # Éditer .env selon vos besoins
   ```

5. **Migrations de base de données**
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

6. **Créer un superutilisateur**
   ```bash
   python manage.py createsuperuser
   ```

7. **Lancer le serveur de développement**
   ```bash
   python manage.py runserver
   ```

L'interface sera accessible à : http://127.0.0.1:8000

## ⚙️ Configuration

### Variables d'Environnement (.env)

```bash
# Django Configuration
DJANGO_SECRET_KEY=votre-clé-secrète-très-longue-et-complexe
DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1

# Database Configuration (PostgreSQL)
DATABASE_URL=postgres://user:password@localhost:5432/enchre_market

# Ou SQLite (fallback)
DATABASE_ENGINE=django.db.backends.sqlite3
DATABASE_NAME=db.sqlite3

# Simulation Configuration
SIM_OUTPUT_DIR=./output
SIM_DEFAULT_AGENTS=50
SIM_DEFAULT_STEPS=100
SIM_CHECKPOINT_INTERVAL=50

# Logging
LOG_LEVEL=INFO
```

## 🎮 Usage

### Interface Web

1. **Dashboard** : Vue d'ensemble des simulations
2. **Nouvelle Simulation** : Configuration et lancement
3. **Historique** : Liste des simulations passées
4. **Marché** : État actuel des objets et prix

### Commande en Ligne

#### Lancer une Simulation Baseline
```bash
python manage.py run_simulation --scenario=baseline --steps=100 --agents=50
```

#### Simulation avec Doublement de Demande
```bash
python manage.py run_simulation \\
    --scenario=demand_x2 \\
    --steps=200 \\
    --agents=100 \\
    --items=15 \\
    --seed=12345
```

## 🎭 Scénarios de Simulation

### 1. Baseline (baseline)
Simulation standard sans événements particuliers.

### 2. Doublement de Demande (demand_x2)
Simule un événement qui double la probabilité d'achat.
- **Déclenchement** : Étape 50
- **Durée** : 30 étapes
- **Effet** : Augmentation des prix, volume accru

## 🧪 Tests

### Lancer les Tests

```bash
# Tous les tests
python -m pytest

# Tests spécifiques
python -m pytest core/tests.py
python -m pytest market/tests.py
python -m pytest simulation/tests.py
```

## 💡 Exemple d'Usage

```bash
# Simulation baseline simple
python manage.py run_simulation --scenario=baseline --steps=100 --verbose

# Expérience doublement de demande
python manage.py run_simulation --scenario=demand_x2 --steps=200 --agents=100 --seed=42
```

**Fichiers générés** :
- `output/simulation_*.json` : Résultats détaillés
- Dashboard web avec graphiques interactifs
- Logs dans `logs/simulation.log`

## 🤝 Contribuer

1. Fork du repository
2. Créer une branche feature
3. Commits avec messages clairs
4. Tests pour nouvelles fonctionnalités
5. Pull Request

## 📄 Licence

MIT License - voir le fichier [LICENSE](LICENSE) pour plus de détails.

---

**🚀 Prêt à simuler ? Lancez votre première simulation avec :**

```bash
python manage.py run_simulation --scenario=baseline --steps=100 --verbose
```