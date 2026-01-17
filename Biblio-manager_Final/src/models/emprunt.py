"""
Module Emprunt - Gestion des emprunts de livres

Ce module contient la classe Emprunt qui représente un emprunt de livre
dans la bibliothèque. Elle gère :
- Le cycle de vie complet d'un emprunt (création, renouvellement, retour)
- Le statut de l'emprunt (emprunté, en retard, retourné)
- Les dates limites et les renouvellements possibles
- La sérialisation/désérialisation en JSON
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from utils.generateur import generer_id_unique
from utils import clean


class Emprunt:
    """
    Représente un emprunt de livre par un utilisateur.
    
    Un emprunt lie un utilisateur (via son matricule) à une copie physique d'un livre
    (via son ISBN et code-barre), avec une durée de prêt et des dates clés.
    
    Attributs de classe:
        DUREE_PAR_DEFAUT (int): Durée standard d'un emprunt en jours (14 jours)
        MAX_RENOUVELLEMENTS (int): Nombre maximum de renouvellements autorisés (2 fois)
    
    """
    DUREE_PAR_DEFAUT = 14
    MAX_RENOUVELLEMENTS = 2

    def __init__(
        self,
        matricule_user: str,
        isbn: str,
        code_barre: str,
        date_emprunt: Optional[datetime] = None,
        date_echeance: Optional[datetime] = None
    ):
        """
        Initialise un nouvel emprunt.
        
        Args:
            matricule_user (str): Identifiant unique de l'utilisateur qui emprunte
            isbn (str): ISBN du livre emprunté
            code_barre (str): Code-barre unique de l'exemplaire emprunté
            date_emprunt (Optional[datetime]): Date de l'emprunt (défaut: maintenant)
            date_echeance (Optional[datetime]): Date limite de retour (défaut: date_emprunt + 14 jours)
            
        Raises:
            ValueError: Si le code-barre est invalide
            
        Note:
            - L'ID d'emprunt est généré automatiquement avec le préfixe "EMP"
            - Les matricule et ISBN sont immuables une fois créés
            - Les dates sont converties en datetime si nécessaire
        """
        # Génération de l'identifiant unique
        self.__id_emprunt = generer_id_unique("EMP")

        # Références utilisateur et livre (
        
        self._matricule_user = matricule_user
        self._isbn = isbn

        # Validation et stockage du code-barres 
        if not clean.valider_code_barre(code_barre):
            raise ValueError("Code-barres invalide pour emprunt")
        self._code_barre = code_barre

        # Initialisation des dates
        
        self.__date_emprunt = date_emprunt or datetime.now()
        
        # date_echeance est calculée automatiquement si non fournie
        self.__date_echeance = date_echeance or (
            self.__date_emprunt + timedelta(days=self.DUREE_PAR_DEFAUT)
        )
        
        # date_retour est None jusqu'à ce que le livre soit retourné
        self.__date_retour: Optional[datetime] = None

        # Compteur de renouvellements
        self.__renouvellements = 0

    # ===================== PROPRIETES (READ-ONLY) =====================

    @property
    def id_emprunt(self) -> str:
        """Retourne l'identifiant unique de l'emprunt (immuable)."""
        return self.__id_emprunt

    @property
    def matricule_user(self) -> str:
        """Retourne le matricule de l'utilisateur qui a emprunté (immuable)."""
        return self._matricule_user

    @property
    def isbn(self) -> str:
        """Retourne l'ISBN du livre emprunté (immuable)."""
        return self._isbn

    @property
    def code_barre(self) -> str:
        """Retourne le code-barre de l'exemplaire emprunté."""
        return self._code_barre

    @code_barre.setter
    def code_barre(self, val: str):
        """
        Modifie le code-barre (utile pour corriger les erreurs de saisie).
        
        Args:
            val (str): Nouveau code-barre
            
        Raises:
            ValueError: Si le code-barre est invalide
        """
        if not clean.valider_code_barre(val):
            raise ValueError("Code-barres invalide")
        self._code_barre = val

    @property
    def date_emprunt(self) -> datetime:
        """Retourne la date et heure de l'emprunt (immuable)."""
        return self.__date_emprunt

    @property
    def date_echeance(self) -> datetime:
        """Retourne la date limite de retour (peut être modifiée via renouveler())."""
        return self.__date_echeance

    @property
    def date_retour(self) -> Optional[datetime]:
        """Retourne la date et heure du retour, ou None si non encore retourné."""
        return self.__date_retour

    @property
    def statut(self) -> str:
        """
        Retourne le statut calculé de l'emprunt.
        
        Valeurs possibles:
            - "retourne": L'exemplaire a été retourné dans les délais
            - "en_retard": L'exemplaire a été retourné après la date limite
                           OU toujours en possession et dépassé la limite
            - "emprunte": L'exemplaire est toujours emprunté et dans les délais
            
        Returns:
            str: Le statut courant de l'emprunt
        """
        if self.__date_retour is not None:
            # Le livre a été retourné, vérifier si en retard
            if self.__date_retour > self.__date_echeance:
                return "en_retard"
            else:
                return "retourne"
        
        if datetime.now() > self.__date_echeance:
            return "en_retard"
        
        return "emprunte"

    @property
    def renouvellements(self) -> int:
        """Retourne le nombre de fois que cet emprunt a été renouvelé."""
        return self.__renouvellements

    # ===================== METHODES LOGIQUES =====================
    # Opérations métier sur l'emprunt

    def est_en_retard(self) -> bool:
        """
        Vérifie si l'emprunt est actuellement en retard.
        
        Un emprunt est en retard si:
        - Il n'a pas été retourné ET
        - La date/heure actuelle dépasse la date d'échéance
        
        Returns:
            bool: True si en retard, False sinon
            
        Note:
            Cette méthode retourne False pour les emprunts déjà retournés,
            utiliser le statut pour déterminer si le retour était en retard.
        """
        return self.__date_retour is None and datetime.now() > self.__date_echeance

    def peut_renouveler(self) -> bool:
        """
        Vérifie si l'emprunt peut être renouvelé (prolongé).
        
        Les conditions pour pouvoir renouveler sont:
        - L'exemplaire n'a pas encore été retourné
        - L'emprunt n'est pas en retard
        - Le nombre de renouvellements n'a pas atteint la limite (MAX_RENOUVELLEMENTS)
        
        Returns:
            bool: True si l'emprunt peut être renouvelé, False sinon
            
        """
        if self.__date_retour is not None:
            return False  # Déjà retourné, impossible à renouveler
        
        if self.est_en_retard():
            return False  # En retard, pas de renouvellement autorisé
        
        return self.__renouvellements < self.MAX_RENOUVELLEMENTS

    def renouveler(self, jours: int = 7) -> bool:
        """
        Renouvelle l'emprunt en prolongeant la date d'échéance.
        
        Args:
            jours (int): Nombre de jours à ajouter (défaut: 7 jours)
            
        Returns:
            bool: True si le renouvellement a réussi, False sinon
            
        Raises:
            - False si l'emprunt n'est pas renouvelable (voir peut_renouveler())
            
        Side effects:
            - Incrémente le compteur de renouvellements
            - Prolonge la date d'échéance
            
        """
        if not self.peut_renouveler():
            return False
        
        # Ajoute les jours à la date d'échéance
        self.__date_echeance += timedelta(days=jours)
        
        # Incrémente le compteur
        self.__renouvellements += 1
        
        return True

    def retourner(self, date_retour: Optional[datetime] = None) -> None:
        """
        Enregistre le retour de l'exemplaire emprunté.
        
        Args:
            date_retour (Optional[datetime]): Date et heure du retour
                                            (défaut: maintenant)
        
        Note:
            - Une fois retourné, l'emprunt ne peut plus être renouvelé
            - Cette opération ne peut pas être annulée
            - La date_retour détermine si le retour était en retard
            
        Example:
            >>> emprunt.retourner()  # Enregistre le retour maintenant
            >>> print(emprunt.statut)  # "retourne" ou "en_retard"
        """
        self.__date_retour = date_retour or datetime.now()

    # ===================== SERIALISATION / DESERIALISATION =====================

    def data_format(self) -> Dict[str, Any]:
        """
        Exporte l'emprunt dans un format sérialisable pour JSON.
        
        Inclut tous les attributs de l'emprunt et des valeurs calculées (statut).
        Les dates sont converties au format ISO 8601.
        
        Returns:
            Dict[str, Any]: Dictionnaire contenant:
                - id_emprunt: ID unique de l'emprunt
                - matricule_user: Matricule de l'utilisateur
                - isbn: ISBN du livre
                - code_barre: Code-barre de l'exemplaire
                - date_emprunt: Date de début (format ISO)
                - date_echeance: Date limite (format ISO)
                - date_retour: Date de retour ou None (format ISO)
                - statut: Statut calculé (emprunte/en_retard/retourne)
                - renouvellements: Nombre de renouvellements
                
        """
        return {
            "id_emprunt": self.id_emprunt,
            "matricule_user": self.matricule_user,
            "isbn": self.isbn,
            "code_barre": self.code_barre,
            "date_emprunt": self.date_emprunt.isoformat(timespec='seconds'),
            "date_echeance": self.date_echeance.isoformat(timespec='seconds'),
            "date_retour": (
                self.date_retour.isoformat(timespec='seconds')
                if self.date_retour else None
            ),
            "statut": self.statut,  # Valeur calculée au moment de la sérialisation
            "renouvellements": self.renouvellements
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Emprunt":
        """
        Désérialise un emprunt depuis un dictionnaire (JSON chargé).
        
        Cette méthode:
        - Valide les données
        - Reconstruit l'objet Emprunt avec son état exact
        - Restaure l'ID original et tous les compteurs
        
        Args:
            data (Dict[str, Any]): Dictionnaire contenant les clés:
                - id_emprunt: ID à restaurer
                - matricule_user, isbn, code_barre
                - date_emprunt, date_echeance (format ISO)
                - date_retour (format ISO ou None)
                - renouvellements: Nombre de renouvellements effectués
                
        Returns:
            Emprunt: Nouvel objet Emprunt reconstruit avec l'état exact
            
        Raises:
            ValueError: Si le code-barre est invalide dans les données
            KeyError: Si une clé obligatoire est manquante
            
        Implementation note:
            - Utilise cls.__new__() pour créer l'objet sans passer par __init__
            - Cela évite de générer un nouvel ID et de recalculer les dates
            - Restaure directement l'ID d'emprunt d'origine depuis les données
            
        """
        # Validation du code-barres
        code_barre = data["code_barre"]
        if not clean.valider_code_barre(code_barre):
            raise ValueError(f"Code-barres invalide dans les données chargées : {code_barre}")

        # Conversion des dates depuis le format ISO 8601
        date_emprunt = datetime.fromisoformat(data["date_emprunt"])
        date_echeance = datetime.fromisoformat(data["date_echeance"])
        date_retour = (
            datetime.fromisoformat(data["date_retour"])
            if data.get("date_retour") else None
        )

        # Création de l'instance sans appeler __init__
        emprunt = cls.__new__(cls)
        
        # Restauration de l'ID original depuis les données
        emprunt.__id_emprunt = data["id_emprunt"]
        
       
        emprunt._matricule_user = data["matricule_user"]
        emprunt._isbn = data["isbn"]
        emprunt._code_barre = code_barre
        
        # Restauration des dates
        emprunt.__date_emprunt = date_emprunt
        emprunt.__date_echeance = date_echeance
        emprunt.__date_retour = date_retour
        
        # Restauration du compteur de renouvellements
        emprunt.__renouvellements = int(data.get("renouvellements", 0))

        return emprunt

    # ===================== AFFICHAGE =====================
    # Représentation texte de l'emprunt pour le débogage

    def __str__(self):
        """
        Retourne une représentation lisible de l'emprunt.
        
        Utile pour l'affichage en console ou le débogage.
        Format: Emprunt(id=..., isbn=..., exemplaire=..., statut=...)
        
        Returns:
            str: Représentation textuelle compacte de l'emprunt
        """
        return (
            f"Emprunt(id={self.id_emprunt}, isbn={self.isbn}, "
            f"exemplaire={self.code_barre}, statut={self.statut})"
        )

    def __repr__(self):
        """
        Retourne la même représentation que __str__.
        
        Permet l'affichage correct lors de la sérialisation en liste ou dictionnaire.
        """
        return self.__str__()