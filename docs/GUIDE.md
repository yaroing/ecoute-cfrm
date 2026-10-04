# Manuel d'utilisation ONG

Version du 4 octobre 2026, mise à jour après OS4. Ce manuel décrit les fonctions réellement disponibles. Utiliser exclusivement des exemples fictifs : les anomalies bloquantes du circuit sensible empêchent une réception complète. Ce logiciel ne remplace pas la procédure de protection de l'ONG. L'installation et les clés relèvent du technicien ; voir [INSTALLATION.md](INSTALLATION.md).

## Préparer une session de démonstration

Ouvrir http://localhost:8080 et utiliser le compte correspondant dans le fichier local `.demo-docker-credentials.json`, fourni par le technicien. Le formulaire public est accessible sans connexion via `/#public`. Choisir `superviseur` pour commencer. Ne pas partager les mots de passe ni le secret TOTP ; utiliser des comptes distincts pour les différents rôles. Le modèle actuel ne permet pas de cumuler deux rôles.

R4/R6 exigent un code TOTP à six chiffres. Vérifier l'heure de l'appareil si le code est refusé. Après cinq tentatives infructueuses, le compte est verrouillé quinze minutes. Les jetons d'accès sont courts et renouvelés ; une session inactive doit être reconnectée. Ne pas répéter les essais avec des identifiants supposés.

| Rôle | Espace de travail |
|---|---|
| Public R0 | Déposer un retour ; conserver sa référence, pas consulter un dossier |
| Agent R1 | Collecte terrain et ses dossiers récents |
| Gestionnaire R2 | Dossiers attribués, notes, réponse, référencement |
| Superviseur R3 | Vue d'ensemble, triage, attribution, validation et actions |
| Référent R4 | Circuit sensible nominal ; droits ordinaires/audit incomplets |
| Direction R5 | Agrégats et actions ; pas de récit individuel |
| Administrateur R6 | Comptes et référentiels ; pas de contenu sensible |

## Déposer un retour public

1. Ouvrir **Formulaire public** et saisir un texte fictif décrivant question, difficulté ou proposition.
2. Vérifier le type, la zone et le projet. Les choix proposés ne constituent pas une qualification définitive.
3. Laisser le contact vide pour un dépôt anonyme, ou renseigner un contact fictif et cocher le consentement au rappel. Sans contact consenti, aucune réponse individuelle n'est possible.
4. Envoyer une fois, lire la confirmation, conserver la référence `FB-AAAA-NNNNNN` et l'échéance indicative.

La confirmation signifie réception, pas résolution. Aucun message réel n'est envoyé. Ne pas retaper un récit sensible pour rechercher sa référence : utiliser le canal sécurisé convenu avec le référent. En cas d'erreur réseau, l'état du serveur doit être vérifié avant une nouvelle saisie indépendante ; une répétition avec une nouvelle clé n'est pas nécessairement dédupliquée.

## Lire les états d'un dossier

| État | Signification |
|---|---|
| Reçu | Retour enregistré ; triage restant |
| Trié | Qualification effectuée avant attribution |
| Attribué | Gestionnaire désigné |
| En traitement | Analyse et préparation de réponse |
| Réponse préparée | Contrôle du superviseur attendu |
| Réponse transmise | Envoi simulé réussi ou transmission manuelle documentée |
| Clôturé | Motif enregistré ; ne signifie pas toujours résolu |

Les gardes métier peuvent refuser une action pourtant proposée dans un contexte invalide. Lire l'erreur, vérifier qualification, titulaire, consentement et état ; ne pas contourner le circuit avec un autre rôle.

## Superviseur et gestionnaire

1. Le superviseur ouvre **Simulateur multicanal**, choisit un identifiant fictif inédit et envoie un message ordinaire. La boîte d’envoi montre l’accusé avec sa référence. **Rejouer** vérifie l’idempotence.
2. Dans **Dossiers**, rechercher cette référence et ouvrir la fiche. **Qualifier** renseigne type, thème et urgence. Une qualification est indispensable avant l’attribution.
3. **Attribuer** au gestionnaire. En se connectant comme gestionnaire, la fiche apparaît dans sa liste ; les dossiers des autres gestionnaires sont refusés par l’API.
4. **Prendre en traitement**, saisir une note, documenter éventuellement un référencement. L’onglet **Réponse & suivi** permet de préparer une réponse de fond.
5. Le superviseur valide ou refuse avec motif. Pour un canal simulé, la réponse rejoint la boîte simulée. Pour WEB/AGENT, il documente une transmission manuelle effectivement réalisée par le moyen consenti ; sans consentement ou après STOP, elle est refusée.
6. **Clôturer** avec motif ; **résolu** nécessite une réponse transmise. **Non joignable** exige trois tentatives documentées. Une réouverture exige un motif et incrémente le compteur.
7. Depuis **Actions correctives**, lier plusieurs dossiers, préciser responsable et échéance. Une réalisation exige une preuve. Enregistrer ensuite la restitution ; le tableau de bord signale les réalisations sans restitution.

La fusion demande l’UUID de la fiche source (présent dans la réponse API) et un motif. Elle conserve les dossiers et historiques sources, déplace les messages, et reste annulable sur la fiche cible. Cette interaction est fonctionnelle mais doit encore être simplifiée pour un utilisateur terrain.

## Agent hors ligne

Ouvrir au moins une fois la version construite de l’application et se connecter comme **agent**. L’application met en cache uniquement ses fichiers statiques ; aucun résultat d’API ou dossier sensible n’est mis en cache.

Couper le réseau sur l’appareil. Le formulaire reste accessible dans l’onglet déjà connecté ; les retours ordinaires sont placés dans IndexedDB avec une clé UUID. La file indique les saisies en attente. Au retour du réseau, la synchronisation reprend automatiquement ; **Envoyer maintenant** permet également de la relancer après une erreur serveur. Les entrées non confirmées restent en file. Un rechargement dans le même onglet conserve la session de travail ; une nouvelle session nécessite une connexion préalable en ligne.

Cocher **Abus, exploitation, fraude ou danger** efface la saisie du formulaire, bloque l’enregistrement et affiche le contact du référent. La détection locale applique aussi les mots-clés téléchargés à la dernière connexion. Elle ne garantit pas la détection de tout récit sensible : le choix explicite de l’agent reste indispensable.

La déconnexion est **bloquée tant que la file locale contient une entrée**. Revenir en ligne, utiliser **Envoyer maintenant** et attendre la confirmation de chaque saisie. Le bouton **Supprimer la saisie locale** abandonne explicitement l'entrée : l'utiliser uniquement si l'abandon est voulu, jamais pour contourner une erreur de transmission. Une fois la file vide, se déconnecter. L'affichage et la synchronisation sélectionnent les entrées de l'agent ; la garde de déconnexion contrôle l'ensemble de la file locale. Sur un appareil partagé, une file résiduelle d'un autre agent nécessite l'aide du technicien sans effacer les données.

Ne pas effacer les données du navigateur ni désinstaller l'application quand une saisie attend une confirmation. IndexedDB n'est pas une sauvegarde chiffrée des dossiers. Les essais OS4 ont vérifié la file simulée et une panne serveur sur navigateur ; les coupures en mode avion, redémarrages et expirations sur téléphones physiques restent à tester.

## Référent sensible

Importer le secret TOTP fictif dans une application d’authentification, puis saisir le code à six chiffres à la connexion. Chaque code est à usage unique dans sa fenêtre de 30 secondes. L’espace sensible permet de lire, prendre en charge, transférer au circuit spécialisé puis clôturer après accusé de prise en charge. Les noms de destinataires et accusés sont chiffrés avec le contenu.

Une détection automatique cloisonne le contenu dans le parcours nominal ; elle repose sur des mots-clés et peut manquer un récit implicite. Le référent confirme la prise en charge. Une bascule manuelle déplace notes/réponses vers le stockage chiffré dans le parcours nominal, mais une panne peut interrompre la cohérence entre les connexions. Ne pas effectuer de tels exercices sur un récit réel. Le prototype n'envoie pas de courriel de notification et n'assure pas encore une suppléance spécifique à 24 heures.

## Direction et administration

La direction consulte les indicateurs agrégés et agit sur le registre des actions. Elle ne consulte pas les fiches. L’administrateur, avec TOTP, crée et désactive les comptes et gère les référentiels. Il ne peut pas accéder aux contenus sensibles. Le paramétrage métier utilise un éditeur JSON dans ce prototype ; les langues locales ne doivent être activées qu’après traduction et validation adaptées.

Les paramètres doivent conserver la structure JSON attendue : listes de thèmes, zones, projets et mots-clés ; délais par type/urgence ; durée de rétention ; modèles et langues. Sauvegarder les valeurs précédentes et tester chaque changement sur exemples fictifs. Enregistrer une langue ou un modèle ne traduit pas l'interface et n'ajoute pas un bouton d'insertion de réponse.

## Tableau de bord et exports

Choisir projet et période avant d'interpréter les chiffres. Une valeur absente signifie dénominateur nul ou absence de mesure, pas nécessairement zéro. Les dossiers fusionnés et sensibles ne suivent pas les mêmes populations que les ordinaires. Le détail des formules implémentées est dans [ARCHITECTURE.md](ARCHITECTURE.md) ; les définitions I03/I06/I09 restent à arbitrer.

Les exports ordinaires retirent récits, coordonnées et dossiers sensibles. Vérifier néanmoins la population et les petits effectifs avant partage. Ne pas ajouter manuellement des coordonnées dans le fichier exporté. Les agrégats de démonstration incluent les exemples et les essais ; ils ne sont pas des statistiques d'une intervention réelle.

## Exercice guidé ONG

Avec le simulateur, déposer « EXERCICE : un point d'eau annoncé reste fermé », puis noter sa référence. Passer R3 pour qualifier et attribuer ; R2 pour prendre en traitement et préparer une réponse fictive ; R3 pour la valider. Vérifier la sortie simulée, clôturer avec un motif adapté, créer une action avec responsable/échéance, documenter une preuve fictive puis une restitution. Comparer fiche, historique et tableau de bord. Pour un canal WEB/AGENT, documenter une transmission manuelle plutôt qu'un envoi simulé.

Cet exercice illustre le circuit ; il ne mesure pas l'autonomie ou le SUS. Ne pas simuler des signatures de validation au nom d'un partenaire.

## Incidents et bonnes pratiques

| Situation | Conduite à tenir |
|---|---|
| Session expirée | Se reconnecter en ligne puis synchroniser ; conserver le stockage local |
| Retour en attente | Vérifier réseau/serveur ; Envoyer maintenant ; pas de nouvelle saisie indépendante |
| Accès refusé | Vérifier rôle et attribution avec le superviseur ; ne pas partager son compte |
| Dossier sensible détecté | Utiliser le circuit habilité ; aucun récit dans export, notification ou capture de dépannage |
| Référent générique | Demander à l'ONG le canal sécurisé effectif ; le texte générique n'est pas un contact opérationnel |
| Mauvaise fusion | Demander au superviseur l'annulation tracée ; ne pas supprimer les dossiers |
| Mauvaise clôture | Réouvrir avec motif ; ne pas modifier silencieusement l'historique |
| Erreur technique persistante | Transmettre commit, rôle, référence fictive, heure et code d'erreur au technicien |

Ne pas envoyer de mot de passe, TOTP ou récit dans une issue GitHub. Fermer la session sur un appareil partagé après vidage de la file. Une disparition de contact après purge ne doit pas être contournée en le recopiant dans une note.

## Glossaire

CFRM : mécanisme de feedback et de réponse communautaire. MEAL : suivi, évaluation, redevabilité et apprentissage. Référencement : orientation vers un acteur compétent, distincte de la résolution. Restitution : information sur une action réalisée. Idempotence : un même dépôt technique rejoué avec la même clé ne crée pas un nouveau dossier. Consulter [LIMITES.md](LIMITES.md) avant toute réception du prototype.
