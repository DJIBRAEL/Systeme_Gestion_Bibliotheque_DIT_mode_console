"""Modèle représentant un livre du catalogue.

Ce module fournit la classe `Livre` qui contient les métadonnées d'un
livre (ISBN, titre, auteur, éditeur, année, catégorie, mots-clés) ainsi
que la gestion des exemplaires associés, le calcul du statut
(disponible/indisponible/emprunté) et des fonctions utilitaires pour la
recherche et la sérialisation.
"""

import uuid
from datetime import datetime
from typing import List, Optional
import utils.clean as clean
from models.enums import StatutLivre, CategorieLivre
from models.exemplaire import Exemplaire
from utils.generateur import generer_id_unique


class Livre:
    """Représente un livre du catalogue.

    Arguments du constructeur :
    - `isbn`, `titre`, `auteur`, `editeur`, `annee_publication` : métadonnées
    - `categorie` : instance de `CategorieLivre` (par défaut AUTRE)
    - `mots_cles` : liste de mots-clés (optionnel)

    La classe effectue des validations d'entrée via les utilitaires
    `utils.clean`. Elle maintient une liste privée d'exemplaires et des
    compteurs/statuts utiles pour la logique métier.
    """

    def __init__(
        self,
        isbn: str,
        titre: str,
        auteur: str,
        editeur: str,
        annee_publication: int,
        categorie: CategorieLivre = CategorieLivre.AUTRE,
        mots_cles: Optional[List[str]] = None
    ):
        # === VALIDATIONS ===
        if not clean.valider_isbn(isbn):
            raise ValueError("ISBN invalide")
        if not clean.valider_annee(annee_publication):
            raise ValueError("Annee de publication invalide")
        if not clean.nettoyer_chaine(titre):
            raise ValueError("Titre invalide")
        if not clean.nettoyer_chaine(auteur):
            raise ValueError("Auteur invalide")
        if not clean.nettoyer_chaine(editeur):
            raise ValueError("Editeur invalide")
        if not isinstance(categorie, CategorieLivre):
            raise ValueError("Categorie invalide")
        if not clean.valider_mots_cles(mots_cles):
            raise ValueError("Mots cles invalides")

        # === ATTRIBUTS METIER ===
        self.__id_livre = generer_id_unique("LIV")
        self._isbn = isbn
        self._titre = titre
        self._auteur = auteur
        self._editeur = editeur
        self._annee_publication = annee_publication
        self._categorie = categorie
        self._mots_cles = mots_cles or []

        # Liste privée d'objets Exemplaire
        self.__exemplaires: List[Exemplaire] = []
        # Statut métier (enum StatutLivre)
        self.__statut = StatutLivre.INDISPONIBLE
        self.__compteur_emprunts = 0
        self.__date_ajout = datetime.now()

        # Met à jour le statut initial en fonction des exemplaires
        self.mettre_a_jour_statut()

    # ======================
    # IDENTITE & METADONNEES
    # ======================
    @property
    def id(self) -> str:
        """Identifiant interne généré automatiquement."""
        return self.__id_livre

    @property
    def isbn(self) -> str:
        """Code ISBN du livre."""
        return self._isbn

    @isbn.setter
    def isbn(self, isbn: str):
        """Met à jour l'ISBN après validation."""
        if clean.valider_isbn(isbn):
            self._isbn = isbn
        else:
            raise ValueError("ISBN invalide")

    @property
    def titre(self) -> str:
        """Titre du livre."""
        return self._titre

    @titre.setter
    def titre(self, titre: str):
        """Met à jour le titre si la chaîne est valide."""
        if clean.nettoyer_chaine(titre):
            self._titre = titre
        else:
            raise ValueError("Titre invalide")

    @property
    def auteur(self) -> str:
        """Nom de l'auteur."""
        return self._auteur

    @auteur.setter
    def auteur(self, auteur: str):
        """Met à jour l'auteur après validation."""
        if clean.nettoyer_chaine(auteur):
            self._auteur = auteur
        else:
            raise ValueError("Auteur invalide")

    @property
    def editeur(self) -> str:
        """Maison d'édition."""
        return self._editeur

    @editeur.setter
    def editeur(self, editeur: str):
        """Met à jour l'éditeur après validation."""
        if clean.nettoyer_chaine(editeur):
            self._editeur = editeur
        else:
            raise ValueError("Editeur invalide")

    @property
    def annee_publication(self) -> int:
        """Année de publication."""
        return self._annee_publication

    @annee_publication.setter
    def annee_publication(self, annee: int):
        """Met à jour l'année si elle est valide."""
        if clean.valider_annee(annee):
            self._annee_publication = annee
        else:
            raise ValueError("Annee de publication invalide")

    @property
    def categorie(self) -> CategorieLivre:
        """Catégorie du livre (énumération)."""
        return self._categorie

    @categorie.setter
    def categorie(self, categorie: CategorieLivre):
        """Met à jour la catégorie après vérification du type."""
        if isinstance(categorie, CategorieLivre):
            self._categorie = categorie
        else:
            raise ValueError("Categorie invalide")

    @property
    def mots_cles(self) -> List[str]:
        """Liste des mots-clés associés."""
        return self._mots_cles

    @mots_cles.setter
    def mots_cles(self, mots_cles: List[str]):
        """Met à jour les mots-clés après validation."""
        if clean.valider_mots_cles(mots_cles):
            self._mots_cles = mots_cles
        else:
            raise ValueError("Mots cles invalides")

    # ======================
    # STATISTIQUES
    # ======================
    @property
    def nombre_exemplaires(self) -> int:
        """Nombre total d'exemplaires associés à ce livre."""
        return len(self.__exemplaires)

    @property
    def exemplaires_disponibles(self) -> int:
        """Compte des exemplaires ayant le statut `DISPONIBLE`."""
        return sum(1 for ex in self.__exemplaires if ex.statut_enum == StatutLivre.DISPONIBLE)

    @property
    def statut(self) -> StatutLivre:
        """Statut courant du livre (énumération)."""
        return self.__statut

    @property
    def compteur_emprunts(self) -> int:
        """Compteur d'emprunts pour ce titre (statistique simple)."""
        return self.__compteur_emprunts

    @property
    def date_ajout(self) -> datetime:
        """Date d'ajout du livre dans le catalogue."""
        return self.__date_ajout

    @property
    def exemplaires(self) -> List[Exemplaire]:
        """Renvoie une copie de la liste d'exemplaires (préserve l'encapsulation)."""
        return list(self.__exemplaires)

    # ======================
    # GESTION DES EXEMPLAIRES
    # ======================
    def ajouter_exemplaire(self, exemplaire: Optional[Exemplaire] = None) -> Exemplaire:
        """Ajoute un exemplaire au livre et met à jour le statut.

        Si aucun exemplaire n'est fourni, un nouvel objet `Exemplaire` est
        instancié (attention : l'initialisation de `Exemplaire` peut
        exiger des paramètres selon son implémentation).
        """
        if exemplaire is None:
            exemplaire = Exemplaire()
        self.__exemplaires.append(exemplaire)
        self.mettre_a_jour_statut()
        return exemplaire

    def retirer_exemplaire(self, code_barre: str) -> bool:
        """Retire l'exemplaire correspondant au `code_barre` si trouvé.

        Retourne `True` si la suppression a eu lieu, `False` sinon.
        """
        for ex in self.__exemplaires:
            if ex.code_barre == code_barre:
                self.__exemplaires.remove(ex)
                self.mettre_a_jour_statut()
                return True
        return False

    def mettre_a_jour_statut(self):
        """Met à jour le statut du livre en fonction des exemplaires.

        Règles :
        - Pas d'exemplaires -> INDISPONIBLE
        - Au moins un exemplaire disponible -> DISPONIBLE
        - Exemplaires présents mais aucun disponible -> EMPRUNTE
        """
        if self.nombre_exemplaires == 0:
            self.__statut = StatutLivre.INDISPONIBLE
        elif self.exemplaires_disponibles > 0:
            self.__statut = StatutLivre.DISPONIBLE
        else:
            # Exemplaires présents, mais tous empruntés/réservés
            self.__statut = StatutLivre.EMPRUNTE

    # ======================
    # LOGIQUE METIER
    # ======================
    def incrementer_compteur(self):
        """Incrémente le compteur d'emprunts pour ce livre."""
        self.__compteur_emprunts += 1

    def est_disponible(self) -> bool:
        """Retourne True si au moins un exemplaire est disponible."""
        return self.exemplaires_disponibles > 0

    def prochain_exemplaire(self) -> Optional[Exemplaire]:
        """Renvoie le premier exemplaire disponible ou `None` s'il n'y en a pas."""
        for ex in self.__exemplaires:
            if ex.statut_enum == StatutLivre.DISPONIBLE:
                return ex
        return None

    def rechercher(self, mot_cle: str) -> bool:
        """Recherche si `mot_cle` est présent dans le titre, l'auteur, l'éditeur
        ou les mots-clés. La recherche est insensible à la casse.
        """
        mot = mot_cle.lower()
        if (
            mot in self.titre.lower()
            or mot in self.auteur.lower()
            or mot in self.editeur.lower()
        ):
            return True
        return any(mot in mc.lower() for mc in self.mots_cles)

    def data_format(self) -> dict:
        """Sérialise le livre en dictionnaire prêt pour JSON.

        Contient les métadonnées et la liste sérialisée des exemplaires.
        """
        return {
            "isbn": self.isbn,
            "titre": self.titre,
            "auteur": self.auteur,
            "editeur": self.editeur,
            "annee_publication": self.annee_publication,
            "categorie": self.categorie.name,
            "mots_cles": self.mots_cles,
            "date_ajout": self.date_ajout.isoformat(),
            "exemplaires": [ex.data_format() for ex in self.exemplaires]
        }

    def __str__(self):
        return f"{self.id}-{self.titre} | {self.auteur} | ISBN: {self.isbn}"

    def __repr__(self):
        return self.__str__()