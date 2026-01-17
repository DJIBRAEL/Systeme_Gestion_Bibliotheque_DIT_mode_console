"""
Script principal pour l'interface CLI de Biblio-manager
Gère la gestion complète d'une bibliothèque (livres, utilisateurs, emprunts, réservations)
"""

import os

from rpds import List
from services.gestion_livre import GestionLivre
from services.gestion_user import GestionUtilisateur as GestionUser
from services.gestion_emprunt import ExemplaireIndisponible, GestionEmprunt, LimiteAtteinte, EmpruntError, EmpruntNonTrouve
from models.exemplaire import Exemplaire
from models.livre import Livre
from models.enums import CategorieLivre, TypeUtilisateur
import random
from services.gestion_reservation import GestionReservation
from services.statistiques import Statistiques
from services.journal import enregistrer_action

# ===================== INITIALISATION DES SERVICES =====================

gestion_livre = GestionLivre()
gestion_user = GestionUser()

# Les gestionnaires ont besoin de se connaître mutuellement pour coordonner les opérations
# On configure d'abord la réservation sans la gestion d'emprunt, puis on ajoute les références circulaires
gestion_reservation = GestionReservation(gestion_livre=gestion_livre, gestion_emprunt=None, gestion_user=gestion_user)
gestion_livre._gestion_reservation = gestion_reservation

# Création du gestionnaire d'emprunt avec toutes les dépendances
gestion_emprunt = GestionEmprunt(gestion_livre, gestion_user, gestion_reservation)

# Complète la chaîne de dépendances pour éviter les références circulaires lors de l'instanciation
gestion_reservation._gestion_emprunt = gestion_emprunt




#======================= UTILITAIRES D'AFFICHAGE =======================
# Fonctions pour faciliter l'affichage et l'interaction utilisateur

def input_nonempty(prompt):
    """
    Demande une saisie utilisateur et la valide pour qu'elle ne soit pas vide.
    Continue à demander jusqu'à obtenir une entrée valide.
    
    Args:
        prompt: Le message à afficher à l'utilisateur
        
    Returns:
        str: La saisie utilisateur validée (non vide)
    """
    while True:
        v = input(prompt).strip()
        if v:
            return v


def print_table(headers, rows):
    """
    Affiche les données dans un tableau formaté avec bordures ASCII.
    Calcule automatiquement la largeur de chaque colonne en fonction du contenu.
    
    Args:
        headers: Liste des en-têtes de colonnes
        rows: Liste de listes contenant les données à afficher
    """
    # Calcule la largeur minimale basée sur les en-têtes
    widths = [len(h) for h in headers]
    
    # Met à jour les largeurs en fonction du contenu des lignes
    for r in rows:
        for i, cell in enumerate(r):
            widths[i] = max(widths[i], len(str(cell)))

    # Crée la ligne de séparation avec les + et -
    sep = '+' + '+'.join('-' * (w + 2) for w in widths) + '+'

    # Format des cellules d'en-tête avec espaces de padding
    header_cells = [' ' + headers[i].ljust(widths[i]) + ' ' for i in range(len(headers))]
    print(sep)
    print('|' + '|'.join(header_cells) + '|')
    print(sep)

    # Affiche chaque ligne de données avec le même formatage
    for row in rows:
        row_cells = [' ' + str(row[i]).ljust(widths[i]) + ' ' for i in range(len(headers))]
        print('|' + '|'.join(row_cells) + '|')
        print(sep)



def print_section(title: str, content_lines: List[str] = None):
    """Affiche une section avec un titre encadré et un contenu indenté."""
    width = 70
    title_line = f" {title} ".center(width, "=")
    print(f"\n{title_line}")
    if content_lines:
        for line in content_lines:
            print(f"  {line}")

def print_header(title: str, width: int = 70):
    """Affiche un en-tête bien centré avec des bordures."""
    print("=" * width)
    print(title.center(width))
    print("=" * width)


def to_attr(obj, attr_list):
    """
    Essaie d'accéder à plusieurs attributs d'un objet jusqu'à trouver une valeur non-None.
    Utile pour gérer différentes conventions de nommage (français/anglais).
    
    Args:
        obj: L'objet ou dictionnaire à consulter
        attr_list: Liste de noms d'attributs à essayer
        
    Returns:
        La première valeur trouvée non-None, ou chaîne vide si aucune trouvée
    """
    # Essaie d'accéder comme attribut d'objet
    for a in attr_list:
        v = getattr(obj, a, None)
        if v is not None:
            return v
    
    # Si l'objet est un dictionnaire, essaie les clés
    try:
        for a in attr_list:
            if a in obj:
                return obj[a]
    except Exception:
        pass
    return ''


def display_livres(livres):
    """
    Affiche une liste de livres dans un tableau formaté.
    Récupère les attributs de manière flexible pour gérer différentes structures de données.
    
    Args:
        livres: Liste d'objets Livre ou dictionnaires contenant les informations des livres
    """
    headers = ["ISBN", "Titre", "Auteur", "Éditeur", "Année", "Catégorie", "Statut", "Mots-clés"]
    rows = []
    
    for l in livres:
        # Utilise to_attr pour gérer les variations de noms d'attributs
        isbn = to_attr(l, ["isbn", "ISBN"])
        titre = to_attr(l, ["titre", "title"]) or ''
        auteur = to_attr(l, ["auteur", "author"]) or ''
        editeur = to_attr(l, ["editeur", "publisher"]) or ''
        annee = to_attr(l, ["annee_publication", "annee", "year"]) or ''
        cat = to_attr(l, ["categorie", "category"]) or ''
        statut = to_attr(l, ["statut", "status"]) or ''
        mots = to_attr(l, ["mots_cles", "motscles", "keywords"]) or ''
        
        # Convertit les listes de mots-clés en chaîne séparée par des virgules
        if isinstance(mots, (list, tuple)):
            mots = ','.join(mots)
        
        rows.append([isbn, titre, auteur, editeur, str(annee), str(cat), statut, mots])
    
    print_table(headers, rows)

#========================================================================================================

# ================================= COMMANDES CLI =======================================================
# Cette section regroupe toutes les fonctions de commande appelées par les différents menus

# ================= SECTION 1: Commandes sur les Livres et exemplaires =================

def cmd_add_book():
    """
    Ajoute un nouveau livre à la bibliothèque.
    Demande tous les détails du livre et crée une instance de Livre.
    """
    isbn = input_nonempty('ISBN: ')
    titre = input('Titre: ').strip()
    auteur = input('Auteur: ').strip()
    editeur = input('Éditeur: ').strip()

    # --- Choix de la catégorie du livre avec affichage des options
    print("\nCatégorie de livre disponible :")
    print("1) Science")
    print("2) Littérature")
    print("3) Informatique")
    print("4) Technologie")
    print("5) Intelligence Artificielle")
    print("6) Autre")
    
    # Mapping entre choix utilisateur et énumération de catégories
    categorie_map = {
        '1': CategorieLivre.SCIENCE,
        '2': CategorieLivre.LITTERATURE,
        '3': CategorieLivre.INFORMATIQUE,
        '4': CategorieLivre.TECHNOLOGIE,
        '5': CategorieLivre.IA,
        '6': CategorieLivre.AUTRE
    }

    # Boucle de validation jusqu'à un choix valide
    while True:
        choix_categorie = input("Choisissez une catégorie (1-6) : ").strip()
        if choix_categorie in categorie_map:
            categorie = categorie_map[choix_categorie]
            break
        else:
            print("Veuillez entrer 1, 2, 3, 4, 5 ou 6.")

    annee = input('Année de publication: ').strip()
    mots = input('Mots-clés (séparés par ,): ').split(',')
    mots = [m.strip() for m in mots if m.strip()]

    # Validation de l'année
    try:
        annee_i = int(annee)
    except Exception:
        print('Année invalide.')
        return

    # Création de l'objet Livre avec gestion d'erreurs
    try:
        livre = Livre(isbn=isbn, titre=titre, auteur=auteur, editeur=editeur, 
                     annee_publication=annee_i, categorie=categorie, mots_cles=mots)
    except Exception as e:
        print('Erreur création livre:', e)
        return

    # Tentative d'ajout du livre
    try:
        fn = getattr(gestion_livre, 'ajouter_livre', None)
        if callable(fn):
            fn(livre)
            print('Livre ajouté.')
        else:
            print("Méthode d'ajout non trouvée dans GestionLivre")
    except Exception as e:
        print('Erreur:', e)


def cmd_list_books():
    """Liste tous les livres de la bibliothèque dans un tableau formaté."""
    try:
        
        fn = getattr(gestion_livre, 'lister_livres', None)
        if callable(fn):
            data = fn()
            display_livres(data)
        else:
            print('Méthode de listage non trouvée dans GestionLivre')
    except Exception as e:
        print('Erreur:', e)


def cmd_delete_book():
    """Supprime un livre par son ISBN."""
    isbn = input_nonempty('ISBN à supprimer: ')
    try:
        fn = getattr(gestion_livre, 'supprimer_livre', None) or getattr(gestion_livre, 'delete_livre', None)
        if callable(fn):
            fn(isbn)
            print('Livre supprimé.')
        else:
            print('Méthode de suppression non trouvée dans GestionLivre')
    except Exception as e:
        print('Erreur:', e)
        # Enregistrement de l'erreur dans le journal
        enregistrer_action(
            acteur="Admin",
            action="ERREUR_SUPPRESSION_LIVRE",
            cible=isbn,
            details=f"Erreur lors de la suppression du livre : {e}",
            niveau="ERROR"
        )


def cmd_add_exemplaire():
    """Ajoute une copie physique (exemplaire) d'un livre existant."""
    isbn = input_nonempty('ISBN du livre: ')
    code = input('Code barre exemplaire : ').strip() or None
    try:
        fn = getattr(gestion_livre, 'ajouter_exemplaire', None)
        if callable(fn):
            ex = Exemplaire(code_barre=code)
            fn(isbn, ex)
            print('Exemplaire ajouté.')
        else:
            print("Méthode d'ajout d'exemplaire non trouvée")
    except Exception as e:
        print('Erreur:', e)
        enregistrer_action(
            acteur="Admin",
            action="ERREUR_AJOUT_EXEMPLAIRE",
            cible=isbn,
            details=f"Erreur lors de l'ajout de l'exemplaire : {e}",
            niveau="ERROR"
        )



def cmd_search_books():
    """Recherche les livres par titre, auteur, ISBN ou mots-clés."""
    mot = input_nonempty('Rechercher par titre, auteur, ISBN ou mot-clé: ')
    try:
        fn = getattr(gestion_livre, 'rechercher', None)
        if callable(fn):
            res = fn(mot)
            display_livres(res)
        else:
            print('Fonction de recherche non disponible')
    except Exception as e:
        print('Erreur:', e)


def cmd_show_book():
    """Affiche les détails complets d'un livre incluant ses exemplaires."""
    isbn = input_nonempty('ISBN: ')
    livre = None
    
    # Recherche le livre avec gestion d'erreur
    try:
        fn = getattr(gestion_livre, 'get_livre', None)
        if callable(fn):
            livre = fn(isbn)
    except Exception:
        livre = None

    if not livre:
        print('Livre introuvable.')
        return

    # Affiche les informations principales du livre
    print(f"Titre: {livre.titre}\nAuteur: {livre.auteur}\nEditeur: {livre.editeur}\nAnnée: {livre.annee_publication}\nNombre exemplaires: {livre.nombre_exemplaires}\nDisponibles: {livre.exemplaires_disponibles}\nStatut: {livre.statut}")
    
    # Affiche les exemplaires si disponibles
    exs = getattr(livre, 'exemplaires', [])
    if exs:
        print('Exemplaires:')
        for ex in exs:
            print(f" - ID: {getattr(ex, 'code_barre', '')} | statut: {getattr(ex, 'statut', '')} | etat: {getattr(ex, 'etat', '')}")


def cmd_modify_book():
    """Modifie les informations d'un livre existant."""
    isbn = input_nonempty('ISBN du livre à modifier: ')
    livre = gestion_livre.get_livre(isbn)
    
    if not livre:
        print('Livre introuvable.')
        return
    
    print('Laisser vide pour ne pas modifier.')
    
    # --- Modification du titre ---
    titre = input('Nouveau titre: ').strip()
    if titre:
        try:
            livre.titre = titre
        except Exception as e:
            print('Titre invalide:', e)
    
    # --- Modification de l'auteur ---
    auteur = input('Nouvel auteur: ').strip()
    if auteur:
        try:
            livre.auteur = auteur
        except Exception as e:
            print('Auteur invalide:', e)
    
    # --- Modification de l'éditeur ---
    editeur = input('Nouvel éditeur: ').strip()
    if editeur:
        try:
            livre.editeur = editeur
        except Exception as e:
            print('Editeur invalide:', e)
    
    # --- Modification de l'année ---
    annee = input('Nouvelle année (nombre): ').strip()
    if annee:
        try:
            livre.annee_publication = int(annee)
        except Exception as e:
            print('Année invalide:', e)
    
    # Sauvegarde des modifications
    try:
        if hasattr(gestion_livre, 'sauvegarder'):
            gestion_livre.sauvegarder()
            enregistrer_action(
                acteur="Admin",
                action="MODIFICATION_LIVRE",
                cible=isbn,
                details=f"Modification des informations du livre '{livre.titre}' (ISBN: {isbn})"   
            )
        print('Livre modifié.')
    except Exception as e:
        print('Erreur sauvegarde:', e)
        enregistrer_action(
            acteur="Admin",
            action="ERREUR_SAUVEGARDE_LIVRE",
            cible=isbn,
            details=f"Erreur lors de la sauvegarde du livre '{livre.titre}' (ISBN: {isbn}) : {e}",
            niveau="ERROR"
        )


def cmd_remove_exemplaire():
    """Supprime un exemplaire spécifique d'un livre."""
    isbn = input_nonempty('ISBN du livre: ')
    id_ex = input_nonempty('Code barre exemplaire: ')
    try:
        fn = getattr(gestion_livre, 'retirer_exemplaire', None)
        if callable(fn):
            ok = fn(isbn, id_ex)
            print('Exemplaire supprimé.' if ok else 'Exemplaire non trouvé ou non supprimable.')
        else:
            print('Fonction de suppression d\'exemplaire non trouvée')
    except Exception as e:
        print('Erreur:', e)
        enregistrer_action(
            acteur="Admin",
            action="ERREUR_SUPPRESSION_EXEMPLAIRE",
            cible=id_ex,
            details=f"Erreur lors de la suppression de l'exemplaire : {e}",
            niveau="ERROR"
        )


def cmd_list_exemplaires():
    """Liste tous les exemplaires d'un livre spécifique."""
    isbn = input_nonempty('ISBN du livre: ')
    try:
        fn = getattr(gestion_livre, 'afficher_exemplaires', None)
        if callable(fn):
            exs = fn(isbn)
            headers = ['Code barre', 'Statut']
            rows = []
            for ex in exs:
                rows.append([getattr(ex, 'code_barre', ''), getattr(ex, 'statut', '')])
            print_table(headers, rows)
        else:
            print('Fonction d\'affichage des exemplaires non trouvée')
    except Exception as e:
        print('Erreur:', e)

# ================= SECTION 2: Commandes sur les Utilisateurs =================

def cmd_list_users():
    """Affiche la liste de tous les utilisateurs."""
    try:
        # La méthode lister_utilisateurs affiche déjà un tableau formaté
        fn = getattr(gestion_user, 'lister_utilisateurs', None)
        if callable(fn):
            fn()
        else:
            print('Méthode de listage non trouvée dans GestionUser')
    except Exception as e:
        print('Erreur:', e)


def cmd_create_user():
    """Crée un nouvel utilisateur (étudiant, enseignant ou personnel administratif)."""
    nom = input_nonempty('Nom: ')
    prenom = input_nonempty('Prénom: ')
    email = input_nonempty('Email: ')
    telephone = input_nonempty('Téléphone: ')

    # --- Affichage des types d'utilisateurs disponibles ---
    print("\nTypes d'utilisateurs disponibles :")
    print("1) Étudiant")
    print("2) Enseignant")
    print("3) Personnel administratif")

    # Mapping entre choix utilisateur et énumération de type
    type_map = {
        '1': TypeUtilisateur.ETUDIANT,
        '2': TypeUtilisateur.PROFESSEUR,
        '3': TypeUtilisateur.EXTERNE
    }

    # Boucle de validation pour le choix du type
    while True:
        choix_type = input("Choisissez un type (1-3) : ").strip()
        if choix_type in type_map:
            type_utilisateur = type_map[choix_type]
            break
        else:
            print("Veuillez entrer 1, 2 ou 3.")

    try:
        fn = getattr(gestion_user, 'creer_utilisateur', None)
        if callable(fn):
            u = fn(
                nom=nom,
                prenom=prenom,
                email=email,
                telephone=telephone,
                type_utilisateur=type_utilisateur
            )
            print(f'Utilisateur créé. Matricule: {u.matricule} | Type: {type_utilisateur.label}')
        else:
            print('Méthode de création non trouvée dans GestionUser')
    except ValueError as e:
        print('Erreur de validation :', e)
        enregistrer_action(
            acteur="Admin",
            action="ERREUR_CREATION_UTILISATEUR",
            cible=email,
            details=f"Erreur de validation lors de la création de l'utilisateur avec email {email} : {e}",
            niveau="WARNING"
        )
    except Exception as e:
        print('Erreur inattendue :', e)
        enregistrer_action(
            acteur="Admin",
            action="ERREUR_CREATION_UTILISATEUR",
            cible=email,
            details=f"Erreur inattendue lors de la création de l'utilisateur avec email {email} : {e}",
            niveau="ERROR"
        )


def cmd_search_user_by_matricule():
    """Recherche et affiche un utilisateur par son matricule."""
    m = input_nonempty('Matricule: ')
    try:
        fn = getattr(gestion_user, 'get_utilisateur_par_matricule', None)
        if callable(fn):
            u = fn(m)
            if u:
                print(f"Matricule: {u.matricule} | Nom: {u.nom_complet()} | Email: {u.email} | Statut: {u.statut}")
            else:
                print('Utilisateur non trouvé')
        else:
            print('Fonction de recherche non disponible')
    except Exception as e:
        print('Erreur:', e)


def cmd_search_user_by_email():
    """Recherche et affiche un utilisateur par son adresse email."""
    email = input_nonempty('Email: ')
    try:
        fn = getattr(gestion_user, 'get_utilisateur_par_email', None)
        if callable(fn):
            u = fn(email)
            if u:
                print(f"Matricule: {u.matricule} | Nom: {u.nom_complet()} | Email: {u.email} | Statut: {u.statut}")
            else:
                print('Utilisateur non trouvé')
        else:
            print('Fonction de recherche par email non disponible')
    except Exception as e:
        print('Erreur:', e)


def cmd_deactivate_user():
    """Désactive un utilisateur (révoque ses droits d'accès)."""
    m = input_nonempty('Matricule: ')
    try:
        fn = getattr(gestion_user, 'desactiver_utilisateur', None)
        if callable(fn):
            ok = fn(m)
            print('Utilisateur désactivé.' if ok else 'Utilisateur non trouvé')
        else:
            print('Fonction de désactivation non disponible')
    except Exception as e:
        print('Erreur:', e)
        enregistrer_action(
            acteur="Admin",
            action="ERREUR_DESACTIVATION_UTILISATEUR",
            cible=m,
            details=f"Erreur lors de la désactivation de l'utilisateur : {e}",
            niveau="ERROR"
        )


def cmd_activate_user():
    """Réactive un utilisateur (restaure ses droits d'accès)."""
    m = input_nonempty('Matricule: ')
    try:
        fn = getattr(gestion_user, 'activer_utilisateur', None)
        if callable(fn):
            ok = fn(m)
            print('Utilisateur activé.' if ok else 'Utilisateur non trouvé')
        else:
            print('Fonction d\'activation non disponible')
    except Exception as e:
        print('Erreur:', e)
        enregistrer_action(
            acteur="Admin",
            action="ERREUR_ACTIVATION_UTILISATEUR",
            cible=m,
            details=f"Erreur lors de l'activation de l'utilisateur : {e}",
            niveau="ERROR"
        )

def cmd_edit_user():
    """Modifie les informations d'un utilisateur existant."""
    m = input_nonempty('Matricule: ')
    utilisateur = gestion_user.get_utilisateur_par_matricule(m)
    
    if not utilisateur:
        print('Utilisateur introuvable.')
        return

    print(f"\nModification de : {utilisateur.nom_complet()} (actuel : {utilisateur.type_utilisateur.label}, statut: {utilisateur.statut})")
    print('Laisser vide pour ne pas modifier.')

    # ---- Modification du nom ----
    nom = input('Nouveau nom: ').strip()
    if nom:
        try:
            utilisateur.nom = nom
        except Exception as e:
            print('Nom invalide:', e)

    # ---- Modification du prénom ----
    prenom = input('Nouveau prénom: ').strip()
    if prenom:
        try:
            utilisateur.prenom = prenom
        except Exception as e:
            print('Prénom invalide:', e)

    # ---- Modification de l'email ----
    email = input('Nouvel email: ').strip()
    if email:
        try:
            # Vérifier que l'email n'est pas déjà utilisé par un autre utilisateur
            autre = gestion_user.get_utilisateur_par_email(email)
            if autre and autre.matricule != utilisateur.matricule:
                print('Email déjà utilisé par un autre utilisateur.')
            else:
                utilisateur.email = email
        except Exception as e:
            print('Email invalide:', e)

    # ---- Modification du téléphone ----
    telephone = input('Nouveau téléphone: ').strip()
    if telephone:
        try:
            utilisateur.telephone = telephone
        except Exception as e:
            print('Téléphone invalide:', e)

    # ---- Modification du type d'utilisateur ----
    print("\nTypes disponibles :")
    print("1) Étudiant")
    print("2) Professeur")
    print("3) Personnel administratif")
    print(f"Actuel : {utilisateur.type_utilisateur.label}")
    
    from models.enums import TypeUtilisateur
    type_map = {
        '1': TypeUtilisateur.ETUDIANT,
        '2': TypeUtilisateur.PROFESSEUR,
        '3': TypeUtilisateur.EXTERNE
    }

    type_input = input("Nouveau type (1-3, ou Entrée pour conserver) : ").strip()
    if type_input in type_map:
        nouvel_type = type_map[type_input]
        if nouvel_type != utilisateur.type_utilisateur:
            # Accès direct à l'attribut privé pour modifier le type
            utilisateur._User__type_utilisateur = nouvel_type  
            print(f"Type mis à jour : {nouvel_type.label}")
    elif type_input:
        print("Type non reconnu. Aucune modification.")

    # ---- Sauvegarde des modifications ----
    try:
        gestion_user.sauvegarder()
        print('Utilisateur modifié et sauvegardé.')
    except Exception as e:
        print(' Erreur sauvegarde:', e)


def cmd_remove_user():
    """Supprime définitivement un utilisateur de la base de données."""
    matricule = input_nonempty("Matricule: ")
    try:
        if gestion_user.supprimer_utilisateur(matricule):
            print("Utilisateur supprimé.")
        else:
            print("Utilisateur non trouvé")
    except Exception as e:
        print("Erreur :", e)
        enregistrer_action(
            acteur="Admin",
            action="ERREUR_SUPPRESSION_UTILISATEUR",
            cible=matricule,
            details=f"Erreur lors de la suppression de l'utilisateur : {e}",
            niveau="ERROR"
        )


# ================= SECTION 3: Commandes d'emprunts d'ouvrage =================

def cmd_borrow():
    """Enregistre un nouvel emprunt pour un utilisateur."""
    uid = input_nonempty('ID User: ')
    isbn = input_nonempty('ISBN du livre: ')
    code = input('Code barre exemplaire : ').strip() or None
    
    try:
        # Emprunt avec code barre spécifique ou premier exemplaire disponible
        if code:
            gestion_emprunt.emprunter(uid, isbn, code)
        else:
            gestion_emprunt.emprunter(uid, isbn)
        print('Emprunt enregistré.')
    except ValueError as e:
        print('Erreur :', e)
        enregistrer_action(
            acteur="Admin",
            action="EMPRUNT",
            cible= code or isbn,
            details= f"Erreur de validation lors de l'emprunt pour l'utilisateur {uid} : {e}",
            niveau="WARNING"
        )
    except ExemplaireIndisponible:
        print('Aucun exemplaire disponible pour ce livre.')
        enregistrer_action(
            acteur="Admin",
            action="EMPRUNT",
            cible= code,
            details= f"Aucun exemplaire disponible pour ce livre avec le code barre {code}",
            niveau="WARNING"
        )
    except LimiteAtteinte:
        print('Vous avez atteint la limite d\'emprunts autorisée.')
        enregistrer_action(
            acteur="Admin",
            action="EMPRUNT",
            cible= code,
            details= f"Limite d'emprunts atteinte pour l'utilisateur {uid}",
            niveau="WARNING"
        )
    except EmpruntError as e:
        print('Impossible d\'emprunter :', e)
        enregistrer_action(
            acteur="Admin",
            action="EMPRUNT",
            cible= code,
            details= f"Erreur lors de l'emprunt pour l'utilisateur {uid} : {e}",
            niveau="ERROR"
        )
    except Exception as e:
        print('Erreur inattendue :', e)
        enregistrer_action(
            acteur="Admin",
            action="EMPRUNT",
            cible= code,
            details= f"Erreur inattendue lors de l'emprunt pour l'utilisateur {uid} : {e}",
            niveau="ERROR"
        )


def cmd_return():
    """Enregistre le retour d'un ouvrage emprunté."""
    eid = input_nonempty('ID emprunt: ')
    try:
        gestion_emprunt.retourner(eid)
        print('Retour enregistré.')
    except EmpruntNonTrouve:
        print('Emprunt introuvable.')
        enregistrer_action(
            acteur="Admin",
            action="RETOUR",
            cible= eid,
            details= f"Emprunt introuvable pour l'ID {eid} lors du retour",
            niveau="WARNING"
        )
    except Exception as e:
        print('Erreur :', e)
        enregistrer_action(
            acteur="Admin",
            action="RETOUR",
            cible= eid,
            details= f"Erreur lors du retour pour l'emprunt ID {eid} : {e}",
            niveau="ERROR"
        )


def cmd_list_emprunts():
    """Affiche la liste de tous les emprunts actuellement en cours."""
    try:
        es = gestion_emprunt.lister_en_cours()
        headers = ['ID', 'Matricule', 'Nom et Prénom', 'ISBN', 'Titre', 'Exemplaire', 'Date emprunt', 'Date échéance']
        rows = []
        
        for e in es:
            # Récupère les informations de l'utilisateur
            user = gestion_user.get_utilisateur_par_matricule(e.matricule_user)
            nom_prenom = f"{user.nom} {user.prenom}" if user else "Inconnu"

            # Récupère les informations du livre
            livre = gestion_livre.get_livre(e.isbn)
            titre = livre.titre if livre else "Titre inconnu"

            rows.append([
                e.id_emprunt,
                e.matricule_user,
                nom_prenom,
                e.isbn,
                titre,
                e.code_barre,
                e.date_emprunt.strftime('%Y-%m-%d'),
                e.date_echeance.strftime('%Y-%m-%d')
            ])
        print_table(headers, rows)
        
        # Journalisation réussie
        enregistrer_action(
            acteur="Admin",
            action="LISTE_EMPRUNTS",
            cible="N/A",
            details=f"{len(es)} emprunt(s) en cours affiché(s)"
        )

    except Exception as e:
        print('Erreur :', e)
        enregistrer_action(
            acteur="Admin",
            action="LISTE_EMPRUNTS",
            cible="N/A",
            details=f"Erreur lors de la liste des emprunts en cours : {e}",
            niveau="ERROR"
        )

def cmd_list_all_emprunts():
    """Affiche la liste historique de tous les emprunts (passés et présents)."""
    try:
        es = gestion_emprunt.lister_tous()
        headers = ['ID', 'Matricule', 'Nom et Prénom', 'ISBN', 'Titre', 'Exemplaire', 'Date emprunt', 'Date échéance', 'Date retour', 'Statut']
        rows = []
        
        for e in es:
            user = gestion_user.get_utilisateur_par_matricule(e.matricule_user)
            nom_prenom = f"{user.nom} {user.prenom}" if user else "Utilisateur supprimé"
            livre = gestion_livre.get_livre(e.isbn)
            titre = livre.titre if livre else "Livre supprimé"
            # Affiche la date de retour seulement si elle existe
            date_retour = e.date_retour.strftime('%Y-%m-%d') if e.date_retour else ''
            rows.append([
                e.id_emprunt,
                e.matricule_user,
                nom_prenom,
                e.isbn,
                titre,
                e.code_barre,
                e.date_emprunt.strftime('%Y-%m-%d'),
                e.date_echeance.strftime('%Y-%m-%d'),
                date_retour,
                e.statut
            ])
        print_table(headers, rows)
        enregistrer_action("Admin", "LISTE_TOUS_EMPRUNTS", "N/A", f"{len(es)} emprunt(s) historisés")
    except Exception as e:
        print('Erreur :', e)
        enregistrer_action("Admin", "LISTE_TOUS_EMPRUNTS", "N/A", f"Erreur: {e}", "ERROR")


def cmd_show_emprunt_by_id():
    """Affiche les détails complets d'un emprunt spécifique."""
    eid = input_nonempty('ID emprunt: ')
    try:
        e = gestion_emprunt.get_emprunt(eid)
        if not e:
            print('Emprunt non trouvé')
            enregistrer_action("Admin", "AFFICHER_EMPRUNT", eid, "Non trouvé", "WARNING")
            return
        
        # Récupère les informations liées
        user = gestion_user.get_utilisateur_par_matricule(e.matricule_user)
        nom_prenom = f"{user.nom} {user.prenom}" if user else "Utilisateur supprimé"
        livre = gestion_livre.get_livre(e.isbn)
        titre = livre.titre if livre else "Livre supprimé"
        
        # Affiche tous les détails de l'emprunt
        print(f"ID emprunt     : {e.id_emprunt}")
        print(f"Utilisateur    : {nom_prenom} ({e.matricule_user})")
        print(f"Livre          : {titre} ({e.isbn})")
        print(f"Exemplaire     : {e.code_barre}")
        print(f"Date emprunt   : {e.date_emprunt.strftime('%Y-%m-%d %H:%M')}")
        print(f"Date échéance  : {e.date_echeance.strftime('%Y-%m-%d %H:%M')}")
        if e.date_retour:
            print(f"Date retour    : {e.date_retour.strftime('%Y-%m-%d %H:%M')}")
        print(f"Statut         : {e.statut}")
        
        enregistrer_action("Admin", "AFFICHER_EMPRUNT", eid, "Détail affiché")
    except Exception as ex:
        print('Erreur :', ex)
        enregistrer_action("Admin", "AFFICHER_EMPRUNT", eid, f"Erreur: {ex}", "ERROR")


def cmd_list_suspensions():
    """Affiche la liste des utilisateurs suspendus (dépassement de limite)."""
    try:
        s = gestion_emprunt.lister_suspensions()
        if not s:
            print('Aucune suspension')
            return
        # Affiche chaque suspension avec la date ISO
        for matricule, iso in s.items():
            print(f"{matricule} -> {iso}")
    except Exception as e:
        print('Erreur :', e)


def cmd_list_emprunts_user():
    """Affiche la liste des emprunts d'un utilisateur spécifique."""
    m = input_nonempty('Matricule utilisateur: ')
    try:
        es = gestion_emprunt.lister_par_user(m)
        if not es:
            print('Aucun emprunt trouvé pour cet utilisateur.')
            enregistrer_action("Admin", "LISTE_EMPRUNTS_USER", m, "Aucun emprunt")
            return
        
        headers = ['ID', 'ISBN', 'Titre', 'Exemplaire', 'Date emprunt', 'Date échéance']
        rows = []
        for e in es:
            livre = gestion_livre.get_livre(e.isbn)
            titre = livre.titre if livre else "Livre supprimé"
            rows.append([
                e.id_emprunt,
                e.isbn,
                titre,
                e.code_barre,
                e.date_emprunt.strftime('%Y-%m-%d'),
                e.date_echeance.strftime('%Y-%m-%d')
            ])
        print_table(headers, rows)
        enregistrer_action("Admin", "LISTE_EMPRUNTS_USER", m, f"{len(es)} emprunt(s) affiché(s)")
    except Exception as e:
        print('Erreur :', e)
        enregistrer_action("Admin", "LISTE_EMPRUNTS_USER", m, f"Erreur: {e}", "ERROR")


def cmd_list_emprunts_retard():
    """Affiche la liste de tous les emprunts en retard (dépassement de date d'échéance)."""
    try:
        es = gestion_emprunt.lister_en_retard()
        headers = ['ID', 'Matricule', 'Nom et Prénom', 'ISBN', 'Titre', 'Exemplaire', 'Date emprunt', 'Date échéance']
        rows = []
        
        for e in es:
            user = gestion_user.get_utilisateur_par_matricule(e.matricule_user)
            nom_prenom = f"{user.nom} {user.prenom}" if user else "Utilisateur supprimé"
            livre = gestion_livre.get_livre(e.isbn)
            titre = livre.titre if livre else "Livre supprimé"
            rows.append([
                e.id_emprunt,
                e.matricule_user,
                nom_prenom,
                e.isbn,
                titre,
                e.code_barre,
                e.date_emprunt.strftime('%Y-%m-%d'),
                e.date_echeance.strftime('%Y-%m-%d')
            ])
        print_table(headers, rows)
        enregistrer_action("Admin", "LISTE_EMPRUNTS_RETARD", "N/A", f"{len(es)} en retard")
    except Exception as e:
        print('Erreur :', e)
        enregistrer_action("Admin", "LISTE_EMPRUNTS_RETARD", "N/A", f"Erreur: {e}", "ERROR")


def cmd_renew():
    """Prolonge la date d'échéance d'un emprunt."""
    id_em = input_nonempty('ID emprunt: ')
    jours = input('Jours supplémentaires (par défaut 7): ').strip()
    try:
        # Convertit l'entrée en nombre, par défaut 7 jours
        jours_i = int(jours) if jours else 7
        if gestion_emprunt.renouveler(id_em, jours_i):
            print('Renouvellement réussi.')
        else:
            print('Renouvellement impossible (déjà retourné, en retard, ou limite de renouvellements atteinte).')
    except EmpruntNonTrouve:
        print('Emprunt introuvable.')
        enregistrer_action(
            acteur="Admin",
            action="RENOUVELER",
            cible=id_em,
            details=f"Emprunt introuvable lors du renouvellement pour l'ID {id_em}",
            niveau="WARNING" 
        )
    except Exception as e:
        print('Erreur :', e)
        enregistrer_action(
            acteur="Admin",
            action="RENOUVELER",
            cible=id_em,
            details=f"Erreur lors du renouvellement pour l'emprunt ID {id_em} : {e}",
            niveau="ERROR"
        )


def cmd_apply_penalties():
    """Applique les pénalités aux utilisateurs en retard d'emprunt."""
    try:
        gestion_emprunt.appliquer_penalites()
        print('Pénalités appliquées.')
    except Exception as e:
        print('Erreur :', e)
        enregistrer_action(
            acteur="Admin",
            action="APPLIQUER_PENALTIES",
            cible="N/A",
            details=f"Erreur lors de l'application des pénalités : {e}",
            niveau="ERROR"
        )


# ================= SECTION 4: Commandes de Réservations =================
def cmd_create_reservation():
    """Crée une nouvelle réservation pour un utilisateur sur un livre."""
    matricule = input_nonempty('Matricule utilisateur: ')
    isbn = input_nonempty('ISBN: ')
    try:
        r = gestion_reservation.reserver(matricule, isbn)
        print(f'Réservation créée : {r.id} (statut={r.statut})')
    except ValueError as e:
        print('Impossible de réserver :', e)
        enregistrer_action(
            acteur="Admin",
            action="CREER_RESERVATION",
            cible=isbn,
            details=f"Erreur de validation lors de la création de la réservation pour l'utilisateur {matricule} : {e}",
            niveau="WARNING"
        )
    except Exception as e:
        print('Erreur :', e)
        enregistrer_action(
            acteur="Admin",
            action="CREER_RESERVATION",
            cible=isbn,
            details=f"Erreur lors de la création de la réservation pour l'utilisateur {matricule} : {e}",
            niveau="ERROR"
        )


def cmd_list_reservations():
    """Affiche la liste de toutes les réservations."""
    try:
        rs = gestion_reservation.lister_toutes()
        if not rs:
            print('Aucune réservation.')
            enregistrer_action("Admin", "LISTE_RESERVATIONS", "N/A", "Aucune réservation")
            return
        
        headers = ['ID', 'Matricule', 'Nom et Prénom', 'ISBN', 'Titre', 'Date', 'Statut']
        rows = []
        for r in rs:
            user = gestion_user.get_utilisateur_par_matricule(r.matricule_user)
            nom_prenom = f"{user.nom} {user.prenom}" if user else "Utilisateur supprimé"
            livre = gestion_livre.get_livre(r.isbn)
            titre = livre.titre if livre else "Livre supprimé"
            rows.append([
                r.id,
                r.matricule_user,
                nom_prenom,
                r.isbn,
                titre,
                r.date_reservation.strftime('%Y-%m-%d %H:%M'),
                r.statut
            ])
        print_table(headers, rows)
        enregistrer_action("Admin", "LISTE_RESERVATIONS", "N/A", f"{len(rs)} réservation(s) affichée(s)")
    except Exception as e:
        print('Erreur :', e)
        enregistrer_action("Admin", "LISTE_RESERVATIONS", "N/A", f"Erreur: {e}", "ERROR")


def cmd_list_reservations_user():
    """Affiche la liste des réservations d'un utilisateur spécifique."""
    m = input_nonempty('Matricule utilisateur: ')
    try:
        rs = gestion_reservation.lister_par_user(m)
        if not rs:
            print('Aucune réservation pour cet utilisateur.')
            enregistrer_action("Admin", "LISTE_RESERVATIONS_USER", m, "Aucune réservation")
            return
        headers = ['ID', 'ISBN', 'Titre', 'Date', 'Statut']
        rows = []
        for r in rs:
            livre = gestion_livre.get_livre(r.isbn)
            titre = livre.titre if livre else "Livre supprimé"
            rows.append([
                r.id,
                r.isbn,
                titre,
                r.date_reservation.strftime('%Y-%m-%d %H:%M'),
                r.statut
            ])
        print_table(headers, rows)
        enregistrer_action("Admin", "LISTE_RESERVATIONS_USER", m, f"{len(rs)} réservation(s) affichée(s)")
    except Exception as e:
        print('Erreur :', e)
        enregistrer_action("Admin", "LISTE_RESERVATIONS_USER", m, f"Erreur: {e}", "ERROR")

def cmd_show_reservation_by_id():
    """Affiche les détails complets d'une réservation spécifique."""
    rid = input_nonempty('ID réservation: ')
    try:
        r = gestion_reservation.get_reservation(rid)
        if not r:
            print('Réservation non trouvée')
            enregistrer_action("Admin", "AFFICHER_RESERVATION", rid, "Non trouvée", "WARNING")
            return
        
        user = gestion_user.get_utilisateur_par_matricule(r.matricule_user)
        nom_prenom = f"{user.nom} {user.prenom}" if user else "Utilisateur supprimé"
        livre = gestion_livre.get_livre(r.isbn)
        titre = livre.titre if livre else "Livre supprimé"
        
        # Affiche les détails avec une belle mise en forme
        print("------------------------------------")
        print("Détails de la réservation :")
        print("------------------------------------")
        print(f"ID réservation : {r.id}")
        print(f"Utilisateur    : {nom_prenom} ({r.matricule_user})")
        print(f"Livre          : {titre} ({r.isbn})")
        print(f"Date           : {r.date_reservation.strftime('%Y-%m-%d %H:%M')}")
        print(f"Statut         : {r.statut}")
        
        enregistrer_action("Admin", "AFFICHER_RESERVATION", rid, "Détail affiché")
    except Exception as ex:
        print('Erreur :', ex)
        enregistrer_action("Admin", "AFFICHER_RESERVATION", rid, f"Erreur: {ex}", "ERROR")


def cmd_cancel_reservation():
    """Annule une réservation existante."""
    rid = input_nonempty('ID réservation: ')
    try:
        if gestion_reservation.annuler(rid):
            print('Réservation annulée.')
        else:
            print('Réservation non trouvée ou déjà annulée.')
    except Exception as e:
        print('Erreur :', e)


def cmd_process_queue():
    """Traite la file d'attente de réservations pour un ISBN et notifie le premier utilisateur."""
    isbn = input_nonempty('ISBN: ')
    try:
        rid = gestion_reservation.traiter_file(isbn)
        if rid:
            print(f'Réservation notifiée : {rid}')
            print('Un message a été enregistré ')
        else:
            print('Aucune notification envoyée livre est indisponible ou la file est vide.')
    except Exception as e:
        print('Erreur :', e)


def cmd_confirm_reservation():
    """Confirme une réservation après notification."""
    rid = input_nonempty('ID réservation à confirmer: ')
    try:
        if gestion_reservation.confirmer(rid):
            print('Réservation confirmée.')
        else:
            print('Confirmation impossible (réservation non notifiée ou introuvable).')
    except Exception as e:
        print('Erreur :', e)


def cmd_show_notifications():
    """Affiche les notifications de réservation en attente."""
    notif_file = os.path.join("data", "notifications.txt")
    if not os.path.exists(notif_file):
        print("Aucune notification.")
        return
    try:
        with open(notif_file, 'r', encoding='utf-8') as f:
            contenu = f.read()
        if contenu.strip():
            print("\n=== Notifications ===")
            print(contenu)
        else:
            print("Aucune notification.")
    except Exception as e:
        print('Erreur lecture notifications :', e)


# ================= SECTION 5: Rapports et Statistiques =================

def cmd_show_dashboard():
    """
    Affiche le tableau de bord statistique complet avec:
    - Nombre total de livres, utilisateurs, emprunts
    - Statistiques sur les réservations et les emprunts en retard
    - Informations sur les categories les plus empruntées
    """
    try:
        # Crée l'objet statistiques avec les gestionnaires
        stats = Statistiques(
            gestion_livre=gestion_livre,
            gestion_emprunt=gestion_emprunt,
            gestion_user=gestion_user
        )
        rapport = stats.generer_rapport_texte()
        print(rapport)
    except Exception as e:
        print('Erreur lors de la génération du rapport :', e)

def cmd_export_rapport():
    """
    Exporte le rapport statistique complet dans un fichier texte
    stocké dans le dossier data/stats/
    """
    try:
        stats = Statistiques(gestion_livre, gestion_emprunt, gestion_user)
        chemin = stats.exporter()  
        print(f" Rapport enregistré avec succès : {chemin}")
    except Exception as e:
        print(f" Erreur lors de l'export du rapport : {e}")


#=================================================================================================
#                       MENUS ET BOUCLE PRINCIPALE D'INTERACTION
#=================================================================================================
# Cette section définit les structures de menus et gère l'interaction avec l'utilisateur

# ================== MENU PRINCIPAL ==================
MENU_MAIN = {
    '1': ('Gestion des livres', None),
    '2': ('Gestion des utilisateurs', None),
    '3': ('Gestion des emprunts', None),
    '4': ('Gestion des réservations', None),
    '5': ('Rapport et Statistiques', None),
    'q': ('Quitter', None),
}

# ==================== SOUS-MENUS ====================

def livres_menu():
    """Menu de gestion des livres - permet de lister, ajouter, modifier, supprimer des livres et leurs exemplaires."""
    OPTS = {
        '1': ('Ajouter un livre', cmd_add_book),
        '2': ('Lister les livres', cmd_list_books),
        '3': ('Rechercher un livre', cmd_search_books),
        '4': ('Afficher un livre (détails)', cmd_show_book),
        '5': ('Modifier un livre', cmd_modify_book),
        '6': ('Supprimer un livre', cmd_delete_book),
        '7': ('Lister exemplaires d\'un livre', cmd_list_exemplaires),
        '8': ('Ajouter exemplaire', cmd_add_exemplaire),
        '9': ('Supprimer exemplaire', cmd_remove_exemplaire),
        '0': ('Retour', None),
    }
    while True:
        print('\n=== Gestion des livres ===')
        for k, v in OPTS.items():
            print(f"{k}) {v[0]}")
        c = input('Choix: ').strip()
        if c == '0':
            break
        action = OPTS.get(c)
        if not action:
            print('Choix invalide')
            continue
        try:
            action[1]()
        except Exception as e:
            print('Erreur:', e)

def users_menu():
    """Menu de gestion des utilisateurs - permet de créer, modifier, consulter et supprimer des utilisateurs."""
    OPTS = {
        '1': ('Lister les utilisateurs', cmd_list_users),
        '2': ('Créer un utilisateur', cmd_create_user),
        '3': ('Modifier un utilisateur', cmd_edit_user),
        '4': ('Supprimer un utilisateur', cmd_remove_user),
        '5': ('Rechercher par matricule', cmd_search_user_by_matricule),
        '6': ('Rechercher par email', cmd_search_user_by_email),
        '7': ('Activer un utilisateur', cmd_activate_user),
        '8': ('Désactiver un utilisateur', cmd_deactivate_user),
        '0': ('Retour', None),
    }
    while True:
        print('\n=== Gestion des utilisateurs ===')
        for k, v in OPTS.items():
            print(f"{k}) {v[0]}")
        c = input('Choix: ').strip()
        if c == '0':
            break
        action = OPTS.get(c)
        if not action:
            print('Choix invalide')
            continue
        try:
            action[1]()
        except Exception as e:
            print('Erreur:', e)

def emprunts_menu():
    """Menu de gestion des emprunts - permet de consulter, créer et gérer les emprunts de livres."""
    OPTS = {
        '1': ('Lister emprunts en cours', cmd_list_emprunts),
        '2': ('Lister emprunts d\'un utilisateur', cmd_list_emprunts_user),
        '3': ('Lister tous les emprunts', cmd_list_all_emprunts),
        '4': ('Lister emprunts en retard', cmd_list_emprunts_retard),
        '5': ('Afficher emprunt par ID', cmd_show_emprunt_by_id),
        '6': ('Lister suspensions', cmd_list_suspensions),
        '7': ('Emprunter', cmd_borrow),
        '8': ('Retourner', cmd_return),
        '9': ('Renouveler emprunt', cmd_renew),
        '10': ('Appliquer pénalités', cmd_apply_penalties),
        '0': ('Retour', None),
    }
    while True:
        print('\n=== Gestion des emprunts ===')
        for k, v in OPTS.items():
            print(f"{k}) {v[0]}")
        c = input('Choix: ').strip()
        if c == '0':
            break
        action = OPTS.get(c)
        if not action:
            print('Choix invalide')
            continue
        try:
            action[1]()
        except Exception as e:
            print('Erreur:', e)

def reservations_menu():
    """Menu de gestion des réservations - permet de créer, consulter et gérer les réservations de livres."""
    OPTS = {
        '1': ('Créer une réservation', cmd_create_reservation),
        '2': ('Lister toutes les réservations', cmd_list_reservations),
        '3': ('Lister réservations par utilisateur', cmd_list_reservations_user),
        '4': ('Afficher réservation par ID', cmd_show_reservation_by_id),
        '5': ('Annuler une réservation', cmd_cancel_reservation),
        '6': ('Traiter la file d\'un ISBN (notifier tête)', cmd_process_queue),
        '7': ('Confirmer une réservation', cmd_confirm_reservation),
        '8': ('Afficher les notifications', cmd_show_notifications),
        '0': ('Retour', None),
    }
    while True:
        print('\n=== Gestion des réservations ===')
        for k, v in OPTS.items():
            print(f"{k}) {v[0]}")
        c = input('Choix: ').strip()
        if c == '0':
            break
        action = OPTS.get(c)
        if not action:
            print('Choix invalide')
            continue
        try:
            action[1]()
        except Exception as e:
            print('Erreur:', e)


def stats_menu():
    """Menu des statistiques et rapports - permet de consulter et exporter les analyses de la bibliothèque."""
    OPTS = {
        '1': ('Afficher le tableau de bord complet', cmd_show_dashboard),
        '2': ("Imprimer le rapport dans un fichier texte", cmd_export_rapport),
        '0': ('Retour', None),
    }
    while True:
        print('\n=== Statistiques ===')
        for k, v in OPTS.items():
            print(f"{k}) {v[0]}")
        c = input('Choix: ').strip()
        if c == '0':
            break
        action = OPTS.get(c)
        if action:
            try:
                action[1]()
            except Exception as e:
                print('Erreur :', e)
        else:
            print('Choix invalide')

# =========================== POINT D'ENTRÉE PRINCIPAL ================================

def main():
    """
    Fonction principale - affiche le menu principal et gère la navigation
    entre les différents sous-menus de l'application.
    """
    print('=== CLI Biblio-manager ===')
    while True:
        print('\n--- Menu principal ---')
        for k, v in MENU_MAIN.items():
            print(f"{k}) {v[0]}")
        choice = input('Choix: ').strip()
        
        # Gestion des choix du menu principal
        if choice == 'q':
            print("Merci d'avoir utilisé Biblio-manager. Au revoir !")
            break
        if choice == '1':
            livres_menu()
        elif choice == '2':
            users_menu()
        elif choice == '3':
            emprunts_menu()
        elif choice == '4':
            reservations_menu()
        elif choice == '5':
            stats_menu()
        else:
            print('Choix invalide')


if __name__ == '__main__':
    main()
