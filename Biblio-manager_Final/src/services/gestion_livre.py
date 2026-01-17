"""Service de gestion du catalogue de livres.

Ce module expose `GestionLivre` qui centralise la lecture/persistance
des livres (dans `data/livres.json`), la recherche, l'ajout/suppression
et la gestion des exemplaires physiques.
"""

from typing import List, Optional
from models.livre import Livre
from models.exemplaire import Exemplaire
from models.enums import CategorieLivre, StatutLivre
from utils import clean
from services.journal import enregistrer_action


import json
import os

# Chemins
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DATA_DIR = os.path.join(BASE_DIR, 'data')
DATA_FILE = os.path.join(DATA_DIR, 'livres.json')


class GestionLivre:
    """Classe service responsable de la gestion des livres :
    - ajout / suppression
    - recherche
    - unicité ISBN
    - gestion des exemplaires
    """

    def __init__(self, gestion_reservation=None):
        self._livres: List[Livre] = []
        self._gestion_reservation = gestion_reservation
        # charger les données existantes si présent
        self.__charger()

    def __charger(self) -> None:
        """Charge les livres depuis le fichier JSON si présent.

        Les exemplaires inclus dans chaque entrée sont également instanciés
        et ajoutés au `Livre` correspondant. Les erreurs de lecture d'une
        entrée sont silencieusement ignorées pour garantir la robustesse.
        """
        if not os.path.exists(DATA_FILE):
            return
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            return

        for d in data:
            try:
                cat = d.get('categorie')
                if cat:
                    try:
                        categorie = CategorieLivre[cat]
                    except Exception:
                        # essayer par valeur
                        try:
                            categorie = CategorieLivre(cat)
                        except Exception:
                            categorie = CategorieLivre.AUTRE
                else:
                    categorie = CategorieLivre.AUTRE

                livre = Livre(
                    isbn=d.get('isbn'),
                    titre=d.get('titre'),
                    auteur=d.get('auteur'),
                    editeur=d.get('editeur'),
                    annee_publication=int(d.get('annee_publication', 0) or 0),
                    categorie=categorie,
                    mots_cles=d.get('mots_cles', [])
                )

                # ajouter exemplaires si présents
                for ex in d.get('exemplaires', []) or []:
                    code = ex.get('code_barre')
                    if code:
                        try:
                            exemplaire = Exemplaire(code_barre=code, etat=ex.get('etat', 'bon'), localisation=ex.get('localisation', 'stock'), statut=ex.get('statut', 'disponible'))
                            livre.ajouter_exemplaire(exemplaire)
                        except Exception:
                            # ignorer exemplaire invalide
                            pass

                self._livres.append(livre)
            except Exception:
                # ignorer en cas d'erreur de lecture d'un élément
                pass

    def recharger(self) -> None:
        """Relit le fichier JSON et remplace la liste courante de livres."""
        self._livres = []
        self.__charger()

    # ==========================
    #   LIVRES
    # ==========================

    def isbn_existe(self, isbn: str) -> bool:
        """Vérifie si un ISBN existe déjà"""
        return any(livre.isbn == isbn for livre in self._livres)

    def ajouter_livre(self, livre: Livre) -> None:
        """Ajoute un livre au catalogue après vérification d'unicité ISBN.

        Persiste automatiquement le catalogue et journalise l'action.
        """
        if self.isbn_existe(livre.isbn):
            raise ValueError("ISBN déjà existant dans la bibliothèque")

        self._livres.append(livre)
        self.sauvegarder()

        enregistrer_action(
            acteur="Admin",
            action="AJOUT_LIVRE",
            cible=livre.isbn,
            details=f"Ajout du livre '{livre.titre}' par {livre.auteur} (ISBN: {livre.isbn})"
        )


    def supprimer_livre(self, isbn: str) -> bool:
        """Supprime un livre par ISBN.

        Retourne `True` si la suppression a été effectuée, `False` sinon.
        """
        for i, livre in enumerate(self._livres):
            if livre.isbn == isbn:
                del self._livres[i]
                return True
            
        enregistrer_action(
            acteur="Admin",
            action="SUPPRESSION_LIVRE",
            cible=isbn,
            details=f"Suppression du livre avec ISBN: {isbn}"
        )
        return False

    def get_livre(self, isbn: str) -> Optional[Livre]:
        """Retourne un livre par ISBN"""
        for livre in self._livres:
            if livre.isbn == isbn:
                return livre
        return None

    def lister_livres(self) -> List[Livre]:
        """Retourne tous les livres"""
        return self._livres
    
    def sauvegarder(self) -> None:
        os.makedirs(DATA_DIR, exist_ok=True)

        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(
                [livre.data_format() for livre in self._livres],
                f,
                indent=4,
                ensure_ascii=False
            )


    # ==========================
    #   EXEMPLAIRES
    # ==========================

    def code_barre_existe(self, code_barre: str) -> bool:
        """
        Vérifie si un code-barres existe déjà dans toute la bibliothèque
        """
        if not code_barre or not isinstance(code_barre, str):
            return False

        code = code_barre.strip().lower()

        for livre in self._livres:
            for ex in livre.exemplaires:
                if ex.code_barre.strip().lower() == code:
                    return True

        return False


    def ajouter_exemplaire(self, isbn: str, exemplaire: Exemplaire) -> None:
        """Ajoute un exemplaire à un livre identifié par `isbn`.

        Vérifie l'unicité du code-barres dans l'ensemble du catalogue et
        notifie la gestion des réservations le cas échéant.
        """
        livre = self.get_livre(isbn)
        if livre is None:
            raise ValueError("Livre introuvable")

        if self.code_barre_existe(exemplaire.code_barre):
            raise ValueError("Code-barres déjà utilisé dans le système")

        livre.ajouter_exemplaire(exemplaire)
        self.sauvegarder()

        # Notifier les réservations si besoin
        if self._gestion_reservation:
            self._gestion_reservation.traiter_file(isbn)
        
        enregistrer_action(
            acteur="Admin",
            action="AJOUT_EXEMPLAIRE",
            cible=isbn,
            details=f"Ajout de l'exemplaire {exemplaire.code_barre} au livre {livre.titre} (ISBN: {isbn})"
        )

    def retirer_exemplaire(self, isbn: str, code_barre: str) -> bool:
        """Retire un exemplaire d'un livre"""
        livre = self.get_livre(isbn)
        if livre is None:
            return False

        enregistrer_action(
            acteur="Admin",
            action="RETRAIT_EXEMPLAIRE",
            cible=isbn,
            details=f"Retrait de l'exemplaire {code_barre} du livre {livre.titre} (ISBN: {isbn})"
        )

        return livre.retirer_exemplaire(code_barre)
    
    def nombre_exemplaires(self, isbn: str) -> int:
        """Retourne le nombre d'exemplaires pour un livre"""
        livre = self.get_livre(isbn)
        if livre is None:
            return 0
        return len(livre.exemplaires)
    
    def afficher_exemplaires(self, insb: str) -> list:
        """Retourne la liste des exemplaires pour un livre"""
        livre = self.get_livre(insb)
        if livre is None:
            return []
        return livre.exemplaires

    # ==========================
    #   RECHERCHE
    # ==========================

    def rechercher(
        self,
        isbn: Optional[str] = None,
        titre: Optional[str] = None,
        auteur: Optional[str] = None,
        editeur: Optional[str] = None,
        categorie: Optional[CategorieLivre] = None,
        annee: Optional[int] = None,
        statut: Optional[StatutLivre] = None,
        mot_cle: Optional[str] = None
    ) -> List[Livre]:
        """
        Recherche élargie (OU logique) : retourne les livres correspondant à AU MOINS UN critère.
        
        Paramètres (tous optionnels) :
            isbn      : recherche exacte (sans tenir compte des tirets)
            titre     : sous-chaîne (insensible à la casse)
            auteur    : sous-chaîne
            editeur   : sous-chaîne
            categorie : correspondance exacte
            annee     : année exacte
            statut    : statut global du livre (DISPONIBLE, EMPRUNTE, etc.)
            mot_cle   : recherche dans titre, auteur, éditeur ou mots-clés
        """
        # Si aucun critère, on retourne tous les livres
        if all(v is None for v in [isbn, titre, auteur, editeur, categorie, annee, statut, mot_cle]):
            return list(self._livres.values()) if isinstance(self._livres, dict) else self._livres

        resultats = set()

        for livre in (self._livres.values() if isinstance(self._livres, dict) else self._livres):
            match = False

            # ISBN (normalisé)
            if isbn is not None:
                isbn_nettoye = isbn.replace("-", "").lower()
                if livre.isbn.replace("-", "").lower() == isbn_nettoye:
                    match = True

            # Titre
            if not match and titre is not None:
                if titre.lower() in livre.titre.lower():
                    match = True

            # Auteur
            if not match and auteur is not None:
                if auteur.lower() in livre.auteur.lower():
                    match = True

            # Éditeur
            if not match and editeur is not None:
                if editeur.lower() in livre.editeur.lower():
                    match = True

            # Catégorie
            if not match and categorie is not None:
                if livre.categorie == categorie:
                    match = True

            # Année
            if not match and annee is not None:
                if livre.annee_publication == annee:
                    match = True

            # Statut
            if not match and statut is not None:
                if livre.statut == statut:
                    match = True

            # Mot-clé (recherche globale)
            if not match and mot_cle is not None:
                mot = mot_cle.lower()
                if (mot in livre.titre.lower() or
                    mot in livre.auteur.lower() or
                    mot in livre.editeur.lower() or
                    any(mot in mc.lower() for mc in livre.mots_cles)):
                    match = True

            if match:
                resultats.add(livre)

        return list(resultats)

    # ==========================
    #   STATISTIQUES SIMPLES
    # ==========================

    def nombre_livres(self) -> int:
        return len(self._livres)

    def livres_disponibles(self) -> List[Livre]:
        return [l for l in self._livres if l.est_disponible()]
    
    def livres_empruntes(self) -> List[Livre]:
        return [l for l in self._livres if not l.est_disponible()]