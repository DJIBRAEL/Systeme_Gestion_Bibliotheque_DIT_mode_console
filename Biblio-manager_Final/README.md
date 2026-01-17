# Biblio-manager


## Description

Biblio-manager est une application CLI Python permettant de gérer une petite bibliothèque : gestion des livres et exemplaires, utilisateurs, emprunts, réservations, et rapports statistiques.

## Prérequis

- Python 3.10 ou supérieur (3.11 recommandé)
- pip (gestionnaire de paquets)
- Un environnement virtuel (fortement recommandé)

Dépendances Python (principe) :

- `rpds` 

Remarque : le projet utilise uniquement des packages standards + `rpds`.

## Structure du projet

- `Biblio-manager/`
  - `src/` : code source principal
    - `main.py` : point d'entrée CLI
    - `services/` : logique métier (gestion livres, utilisateurs, emprunts, réservations, statistiques, journal)
    - `models/` : modèles de données (Livre, Exemplaire, Emprunt, Reservation, User, enums...)
    - `utils/` : utilitaires (génération d'identifiants, nettoyage...)
    - `data/` : fichiers JSON et logs persistants
      - `livres.json`, `users.json`, `emprunts.json`, `reservations.json`, `notifications.txt`, `logs/`, `stats/`
  - `ids_book.txt` : (auxiliaire)

Fichiers importants :

- [src/main.py](src/main.py) : interface utilisateur et menus
- [src/data/](src/data/) : données persistantes (veillez à faire des sauvegardes)

## Installation

1. Ouvrir un terminal.
2. Se placer dans le dossier projet :

```bash
cd /chemin/vers/Biblio-manager
```

3. Créer et activer un environnement virtuel (optionnel mais recommandé) :

```bash
python -m venv .venv
source .venv/bin/activate
```

4. Installer la dépendance principale :

```bash
pip install rpds
```

Si vous fournissez un `requirements.txt` plus tard, installez-le via `pip install -r requirements.txt`.

## Configuration

- Les données sont stockées dans `src/data/`. Si vous souhaitez partir d'une base propre, sauvegardez ou supprimez les fichiers JSON présents.
- Assurez-vous que votre terminal utilise l'encodage UTF-8 pour afficher correctement les accents.

## Exécution

L'application s'attend à être lancée avec le dossier `src` dans le `PYTHONPATH`. La manière la plus simple :

```bash
cd Biblio-manager/src
python main.py
```

L'interface CLI affichera le menu principal et vous pourrez naviguer pour gérer livres, utilisateurs, emprunts et réservations.

## Principales fonctionnalités

- Gestion des livres : ajouter, modifier, supprimer, lister, rechercher par titre/auteur/ISBN, ajouter/supprimer exemplaires.
- Gestion des utilisateurs : créer, modifier, activer/désactiver, supprimer, rechercher par matricule ou email.
- Emprunts : enregistrer emprunt (par code-barre ou premier exemplaire disponible), retour, liste des emprunts en cours, liste historique, renouvellement, application de pénalités, suspensions.
- Réservations : créer réservation, lister, annuler, notifier le premier de la file, confirmer réservation.
- Rapports / Statistiques : génération et export d'un rapport texte via le module `services.statistiques`.
- Journalisation : actions importantes sont enregistrées via `services.journal.enregistrer_action` et dans `src/data/logs/`.

## Fichiers de données

- `src/data/livres.json` : catalogue et exemplaires
- `src/data/users.json` : utilisateurs
- `src/data/emprunts.json` : emprunts en cours et historiques
- `src/data/reservations.json` : file de réservations
- `src/data/notifications.txt` : notifications de réservations
- `src/data/logs/` : journaux d'activité

Faites toujours une copie avant manipulation directe.

## Bonnes pratiques

- Sauvegardez régulièrement `src/data/` avant tests destructifs.
- Exécutez l'application depuis `src/` pour que les imports relatifs fonctionnent.

## Dépannage

- Erreurs d'import : assurez-vous d'être dans `src/` ou d'avoir ajouté `src` à `PYTHONPATH`.
- Problèmes d'encodage : exporter `LANG=C.UTF-8` ou `export PYTHONIOENCODING=utf-8` avant d'exécuter.

## Extensibilité

- Pour ajouter des dépendances, créez un `requirements.txt` puis documentez les nouvelles étapes d'installation dans ce README.
- Vous pouvez transformer `src` en package Python (ajouter `pyproject.toml` / `setup.cfg`) si vous voulez un import module plus propre.

