"""Modèle d'un exemplaire physique d'un livre.

Ce module définit la classe `Exemplaire` représentant une copie physique
disponible dans la bibliothèque. Chaque exemplaire possède un identifiant
unique interne, un code-barres, un état (ex: "bon", "abîmé"), une
localisation (ex:  "stock") et un statut (disponible, emprunté,
réservé, ...). La classe fournit des validateurs et des sérialisations
simples pour l'export JSON.
"""

from datetime import datetime
from typing import Optional
from utils import clean
from utils.generateur import generer_id_unique
from models.enums import StatutLivre


class Exemplaire:
    """Représente une copie physique d'un livre.

    Attributs publics (accès via propriétés) :
    - `id_exemplaire` : identifiant interne généré automatiquement
    - `code_barre` : code-barres unique (doit être valide)
    - `etat` : état physique de l'exemplaire (chaîne)
    - `localisation` : emplacement actuel (chaîne)
    - `statut` : statut exploitable en sortie (chaîne)
    - `statut_enum` : statut sous forme d'énumération `StatutLivre` (utile
      pour la logique métier)
    - `date_acquisition` : date d'acquisition (datetime)
    """

    def __init__(
        self,
        code_barre: Optional[str] = None,
        etat: str = "bon",
        localisation: str = "stock",
        statut: StatutLivre = StatutLivre.DISPONIBLE,
        date_acquisition: Optional[datetime] = None
    ):
        # Identifiant interne unique pour chaque exemplaire
        self.__id_exemplaire = generer_id_unique("EX")

        # Le code-barres est obligatoire et doit être validé
        if code_barre is None:
            raise ValueError("Le code-barres est obligatoire")
        if not clean.valider_code_barre(code_barre):
            raise ValueError("Code-barres invalide")

        # Affectations via les setters pour bénéficier des validations
        self.__code_barre = code_barre
        self.etat = etat
        self.localisation = localisation
        self.statut = statut
        # Date d'acquisition 
        self.__date_acquisition = date_acquisition or datetime.now()

    @property
    def id_exemplaire(self) -> str:
        """Identifiant interne immuable de l'exemplaire."""
        return self.__id_exemplaire

    @property
    def code_barre(self) -> str:
        """Retourne le code-barres de l'exemplaire."""
        return self.__code_barre

    @code_barre.setter
    def code_barre(self, val: str):
        """Valide et met à jour le code-barres.

        Utilise `utils.clean.nettoyer_chaine` pour vérifier la valeur.
        """
        if clean.nettoyer_chaine(val):
            self.__code_barre = val
        else:
            raise ValueError("Code barre invalide")

    @property
    def etat(self) -> str:
        """État physique (chaîne) de l'exemplaire."""
        return self.__etat

    @etat.setter
    def etat(self, val: str):
        """Valide et met à jour l'état physique."""
        if clean.nettoyer_chaine(val):
            self.__etat = val
        else:
            raise ValueError("État invalide")

    @property
    def localisation(self) -> str:
        """Emplacement courant de l'exemplaire."""
        return self.__localisation

    @localisation.setter
    def localisation(self, val: str):
        """Valide et met à jour la localisation."""
        if clean.nettoyer_chaine(val):
            self.__localisation = val
        else:
            raise ValueError("Localisation invalide")

    @property
    def statut(self) -> str:
        """Retourne le statut sous forme de chaîne.

        Utile pour sérialisation (ex: JSON) où l'on souhaite une valeur
        lisible plutôt que l'enum.
        """
        return self.__statut.value

    @statut.setter
    def statut(self, val):
        """Accepte soit un `StatutLivre`, soit une chaîne correspondant
        à une valeur de l'énumération.
        """
        if isinstance(val, StatutLivre):
            self.__statut = val
        elif isinstance(val, str):
            try:
                self.__statut = StatutLivre(val)
            except ValueError:
                raise ValueError(f"Statut invalide : {val}")
        else:
            raise ValueError("Le statut doit être une chaîne ou un StatutLivre")

    @property
    def statut_enum(self) -> StatutLivre:
        """Retourne le statut sous forme d'`enum` pour la logique métier."""
        return self.__statut

    @property
    def date_acquisition(self) -> datetime:
        """Date d'acquisition de l'exemplaire."""
        return self.__date_acquisition

    def data_format(self) -> dict:

        return {
            "id_exemplaire": self.id_exemplaire,
            "code_barre": self.code_barre,
            "etat": self.etat,
            "localisation": self.localisation,
            "statut": self.statut,
            "date_acquisition": self.date_acquisition.isoformat()
        }

    def __str__(self) -> str:
        return f"Exemplaire(code_barre={self.code_barre}, statut={self.statut})"

    def __repr__(self) -> str:
        return self.__str__()