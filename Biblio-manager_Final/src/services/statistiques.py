"""Génération de rapports et statistiques pour la bibliothèque.

Ce module regroupe des fonctions pour extraire des métriques simples
et produire un rapport textuel destiné à l'interface CLI ou à
l'exportation dans un fichier.
"""

from collections import Counter
from typing import List, Dict, Tuple
from models.livre import Livre
from models.user import User
from services.gestion_livre import GestionLivre
from services.gestion_emprunt import GestionEmprunt
from services.gestion_user import GestionUtilisateur
from datetime import datetime
import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DATA_DIR = os.path.join(BASE_DIR, 'data')
STATS_FILE = os.path.join(DATA_DIR, 'stats')


class Statistiques:
    """Génère des rapports statistiques à partir des données de la bibliothèque."""

    def __init__(self, gestion_livre: GestionLivre, gestion_emprunt: GestionEmprunt, gestion_user: GestionUtilisateur):
        """Initialise le générateur de rapports avec les gestionnaires requis."""
        self._gestion_livre = gestion_livre
        self._gestion_emprunt = gestion_emprunt
        self._gestion_user = gestion_user

    def etat_inventaire(self) -> Dict[str, int]:
        """Retourne le nombre de livres par statut."""
        compteur = {
            "disponible": 0,
            "emprunte": 0,
            "reserve": 0,
            "perdu": 0,
            "endommage": 0,
            "total": 0
        }

        for livre in self._gestion_livre.lister_livres():
            for ex in livre.exemplaires:
                compteur["total"] += 1
                statut = ex.statut
                if statut in compteur:
                    compteur[statut] += 1
        return compteur

    def total_emprunts(self) -> int:
        """Nombre total d'emprunts (historique complet)."""
        return len(self._gestion_emprunt.lister_tous())

    def livres_jamais_empruntes(self) -> List[Livre]:
        """Liste des livres qui n'ont jamais été empruntés."""
        emprunts = self._gestion_emprunt.lister_tous()
        isbns_empruntes = {e.isbn for e in emprunts}
        livres = self._gestion_livre.lister_livres()
        return [livre for livre in livres if livre.isbn not in isbns_empruntes]

    def top_livres_empruntes(self, n: int = 5) -> List[Tuple[str, int]]:
        """Top N des livres les plus empruntés (ISBN, nombre d'emprunts)."""
        emprunts = self._gestion_emprunt.lister_tous()
        compteur = Counter(e.isbn for e in emprunts)
        return compteur.most_common(n)

    def top_utilisateurs_actifs(self, n: int = 5) -> List[Tuple[str, int]]:
        """Top N des utilisateurs les plus actifs (matricule, nombre d'emprunts)."""
        emprunts = self._gestion_emprunt.lister_tous()
        compteur = Counter(e.matricule_user for e in emprunts)
        return compteur.most_common(n)

    def generer_rapport_texte(self) -> str:
        """Génère un rapport textuel complet avec mise en forme alignée."""
        from io import StringIO
        output = StringIO()
        width = 70

        # === ÉTAT DE L'INVENTAIRE ===
        output.write("=" * width + "\n")
        output.write(" ÉTAT DE L'INVENTAIRE".center(width) + "\n")
        output.write("=" * width + "\n")
        etat = self.etat_inventaire()
        output.write(f"{'Statut':<15} | {'Quantité':<10}\n")
        output.write("-" * 30 + "\n")
        output.write(f"{'Total':<15} | {etat['total']:<10}\n")
        output.write(f"{'Disponible':<15} | {etat['disponible']:<10}\n")
        output.write(f"{'Emprunté':<15} | {etat['emprunte']:<10}\n")
        output.write(f"{'Réservé':<15} | {etat['reserve']:<10}\n")
        output.write(f"{'Perdu':<15} | {etat['perdu']:<10}\n")
        output.write(f"{'Endommagé':<15} | {etat['endommage']:<10}\n")

        # === ACTIVITÉ GLOBALE ===
        output.write("\n" + "=" * width + "\n")
        output.write(" ACTIVITÉ GLOBALE".center(width) + "\n")
        output.write("=" * width + "\n")
        total_emprunts = self.total_emprunts()
        output.write(f"• Total des emprunts (historique) : {total_emprunts}\n")

        # === LIVRES JAMAIS EMPRUNTÉS ===
        output.write("\n" + "=" * width + "\n")
        output.write(" LIVRES JAMAIS EMPRUNTÉS".center(width) + "\n")
        output.write("=" * width + "\n")
        livres_jamais = self.livres_jamais_empruntes()
        if livres_jamais:
            output.write(f"Nombre : {len(livres_jamais)}\n")
            for livre in livres_jamais[:10]:
                output.write(f"  → {livre.titre} ({livre.isbn})\n")
        else:
            output.write("Aucun livre n'est resté sans emprunt.\n")

        # === TOP LIVRES ===
        output.write("\n" + "=" * width + "\n")
        output.write(" TOP 5 DES LIVRES LES PLUS EMPRUNTÉS".center(width) + "\n")
        output.write("=" * width + "\n")
        top_livres = self.top_livres_empruntes()
        if top_livres:
            output.write(f"{'Rang':<6} {'Titre':<30} {'Emprunts':<10}\n")
            output.write("-" * 60 + "\n")
            for i, (isbn, count) in enumerate(top_livres, 1):
                livre = self._gestion_livre.get_livre(isbn)
                titre = (livre.titre if livre else isbn)[:28]
                output.write(f"{i:<6} {titre:<30} {count:<10}\n")
        else:
            output.write("Aucun emprunt enregistré.\n")

        # === TOP UTILISATEURS ===
        output.write("\n" + "=" * width + "\n")
        output.write(" TOP 5 DES UTILISATEURS LES PLUS ACTIFS".center(width) + "\n")
        output.write("=" * width + "\n")
        top_users = self.top_utilisateurs_actifs()
        if top_users:
            output.write(f"{'Rang':<6} {'Nom':<30} {'Emprunts':<10}\n")
            output.write("-" * 60 + "\n")
            for i, (matricule, count) in enumerate(top_users, 1):
                user = self._gestion_user.get_utilisateur_par_matricule(matricule)
                nom = (user.nom_complet() if user else matricule)[:28]
                output.write(f"{i:<6} {nom:<30} {count:<10}\n")
        else:
            output.write("Aucun emprunt enregistré.\n")

        output.write("\n" + "=" * width + "\n")
        return output.getvalue()
    

    def exporter(self, dossier: str = STATS_FILE) -> str:
        """
        Exporte le rapport statistique dans un fichier texte horodaté.
        
        :param dossier: Chemin du dossier de destination
        :return: Chemin absolu du fichier créé
        """
        # Créer le dossier s'il n'existe pas
        os.makedirs(dossier, exist_ok=True)
        
        # Générer un nom de fichier unique
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        nom_fichier = f"rapport_biblio_{timestamp}.txt"
        chemin = os.path.join(dossier, nom_fichier)
        
        # Générer et écrire le rapport
        contenu = self.generer_rapport_texte()
        with open(chemin, "w", encoding="utf-8") as f:
            f.write(contenu)
        
        return os.path.abspath(chemin)