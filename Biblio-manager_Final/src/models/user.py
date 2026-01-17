from datetime import datetime
from typing import Optional, List
from utils.generateur import generer_id_unique
from utils import clean
from models.enums import TypeUtilisateur


class Personne:
    def __init__(
        self,
        nom: str,
        prenom: str,
        email: str,
        telephone: str,
        date_inscription: Optional[datetime] = None
    ):
        if not clean.nettoyer_chaine(nom):
            raise ValueError("Nom invalide")
        if not clean.nettoyer_chaine(prenom):
            raise ValueError("Prénom invalide")
        if not clean.valider_email(email):
            raise ValueError("Email invalide")
        if not clean.valider_telephone(telephone):
            raise ValueError("Téléphone invalide")

        self.__id_personne = generer_id_unique("P")
        self.__nom = nom
        self.__prenom = prenom
        self.__email = email
        self.__telephone = telephone
        self.__date_inscription = date_inscription or datetime.now()

    @property
    def id_personne(self):
        return self.__id_personne
    
    @property
    def date_inscription(self):
        return self.__date_inscription
    
    @property
    def nom(self):
        return self.__nom

    @nom.setter
    def nom(self, value: str):
        if not clean.nettoyer_chaine(value):
            raise ValueError("Nom invalide")
        self.__nom = value

    @property
    def prenom(self):
        return self.__prenom

    @prenom.setter
    def prenom(self, value: str):
        if not clean.nettoyer_chaine(value):
            raise ValueError("Prénom invalide")
        self.__prenom = value

    @property
    def email(self):
        return self.__email

    @email.setter
    def email(self, value: str):
        if not clean.valider_email(value):
            raise ValueError("Email invalide")
        self.__email = value

    @property
    def telephone(self):
        return self.__telephone

    @telephone.setter
    def telephone(self, value: str):
        if not clean.valider_telephone(value):
            raise ValueError("Téléphone invalide")
        self.__telephone = value



    def nom_complet(self) -> str:
        return f"{self.__prenom} {self.__nom}"

    def data_format(self) -> dict:
        return {
            "id": self.id_personne,
            "nom": self.nom,
            "prenom": self.prenom,
            "email": self.email,
            "telephone": self.telephone,
            "date_inscription": self.date_inscription.isoformat()
        }

    def __str__(self):
        return f"Personne(id={self.id_personne}, nom={self.nom_complet()})"
    
    def __repr__(self):
        return self.__str__()


class User(Personne):

    def __init__(
        self,
        nom: str,
        prenom: str,
        email: str,
        telephone: str,
        type_utilisateur: TypeUtilisateur = TypeUtilisateur.ETUDIANT
    ):
        super().__init__(nom, prenom, email, telephone)
        self.__matricule = generer_id_unique("U")
        self.__type_utilisateur = type_utilisateur
        self.__statut = "actif"
        self.__livres_empruntes: List[dict] = []
        self.__historique: List[dict] = []
        self.__limite_emprunts = type_utilisateur.limite_emprunt


    # --------- propriétés ---------

    @property
    def matricule(self):
        return self.__matricule

    @property
    def type_utilisateur(self):
        return self.__type_utilisateur

    @property
    def statut(self):
        return self.__statut

    @property
    def livres_empruntes(self):
        return list(self.__livres_empruntes)

    @property
    def historique(self):
        return list(self.__historique)
    
    @property
    def limite_emprunts(self) -> int:
        return self.__limite_emprunts

    # --------- méthodes publiques ---------

    def definir_statut(self, statut: str) -> None:
        """Modifie le statut de l'utilisateur (actif/inactif)."""
        if statut not in ("actif", "inactif"):
            raise ValueError("Le statut doit être 'actif' ou 'inactif'")
        self.__statut = statut

    def restaurer_etat(self, donnees: dict) -> None:
        """
        Restaure l'état interne de l'utilisateur à partir d'un dictionnaire
         chargé depuis un fichier JSON.
        
        """
        # Matricule
        if 'matricule' in donnees:
            self.__matricule = str(donnees['matricule'])

        # Statut
        if 'statut' in donnees:
            statut = donnees['statut']
            if statut in ("actif", "inactif"):
                self.__statut = statut

        # Livres empruntés
        if 'livres_empruntes' in donnees:
            emprunts = donnees['livres_empruntes']
            if isinstance(emprunts, list):
                # S'assurer que les dates sont bien des objets datetime si présentes
                self.__livres_empruntes = [
                    self._normaliser_date_emprunt(e) for e in emprunts
                ]

        # Historique
        if 'historique' in donnees:
            historique = donnees['historique']
            if isinstance(historique, list):
                self.__historique = [
                    self._normaliser_date_historique(e) for e in historique
                ]

    def _normaliser_date_emprunt(self, emprunt: dict) -> dict:
        """Convertit les dates ISO en objets datetime si nécessaire."""
        emprunt = emprunt.copy()
        if 'date_emprunt' in emprunt and isinstance(emprunt['date_emprunt'], str):
            emprunt['date_emprunt'] = datetime.fromisoformat(emprunt['date_emprunt'])
        return emprunt

    def _normaliser_date_historique(self, entree: dict) -> dict:
        """Convertit les dates ISO en objets datetime dans l'historique."""
        entree = entree.copy()
        for key in ('date_emprunt', 'date_retour'):
            if key in entree and isinstance(entree[key], str):
                entree[key] = datetime.fromisoformat(entree[key])
        return entree

    # --------- règles ---------

    def peut_emprunter(self) -> bool:
        return (
            self.__statut == "actif"
            and len(self.__livres_empruntes) < self.__limite_emprunts
        )

    def enregistrer_emprunt(self, isbn: str, id_exemplaire: str):
        info = {
            "isbn": isbn,
            "id_exemplaire": id_exemplaire,
            "date_emprunt": datetime.now()
        }
        self.__livres_empruntes.append(info)
        self.__historique.append({**info, "action": "emprunt"})

    def enregistrer_retour(self, isbn: str, id_exemplaire: str):
        self.__livres_empruntes = [
            e for e in self.__livres_empruntes
            if not (e["isbn"] == isbn and e["id_exemplaire"] == id_exemplaire)
        ]
        self.__historique.append({
            "isbn": isbn,
            "id_exemplaire": id_exemplaire,
            "date_retour": datetime.now(),
            "action": "retour"
        })

    def data_format(self) -> dict:
        """Exporte l'utilisateur au format sérialisable (JSON)."""
        data = super().data_format()
        # On convertit les dates en chaînes ISO pour la sauvegarde
        livres_serial = []
        for e in self.__livres_empruntes:
            e_copy = e.copy()
            if 'date_emprunt' in e_copy and isinstance(e_copy['date_emprunt'], datetime):
                e_copy['date_emprunt'] = e_copy['date_emprunt'].isoformat()
            livres_serial.append(e_copy)

        historique_serial = []
        for h in self.__historique:
            h_copy = h.copy()
            for key in ('date_emprunt', 'date_retour'):
                if key in h_copy and isinstance(h_copy[key], datetime):
                    h_copy[key] = h_copy[key].isoformat()
            historique_serial.append(h_copy)

        data.update({
            "matricule": self.matricule,
            "type_utilisateur": self.type_utilisateur.name,
            "statut": self.statut,
            "livres_empruntes": livres_serial,
            "historique": historique_serial
        })
        return data

    def __str__(self):
        return f"Utilisateur(matricule={self.matricule}, nom={self.nom_complet()}, statut={self.statut})"  
    
    def __repr__(self):
        return self.__str__()


