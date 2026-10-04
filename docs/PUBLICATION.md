# Publication du code sous licence MIT

Destination retenue par le porteur : dépôt **public** `yaroing/ecoute-cfrm`, branche `main`, licence MIT. Cette procédure décrit la publication ; sa présence ne prouve pas que le dépôt existe déjà. La confirmation doit inclure URL, commit distant, visibilité, licence et vérification des fichiers.

## Contenu publiable

Code backend/frontend, images et fichiers de déploiement, migrations, tests, scripts de campagne OS4, guides originaux, OpenAPI, workflow CI, LICENSE et exemple d'environnement sans clé. Les documents métier fournis au projet conservent leurs droits et ne sont pas inclus.

Exclure `.env`, fichiers de secrets et de comptes, bases, sauvegardes, logs privés, caches, dépendances installées, builds, rapports Word, archives privées et données d'investigation. `.gitignore` ne retire pas un fichier déjà suivi : vérifier la liste indexée et l'historique avant tout push.

```sh
git status --short
git ls-files
git diff --cached --check
```

Contrôler les clés réellement utilisées sur le poste et les marqueurs de jetons dans les fichiers destinés au commit, sans afficher les valeurs. Les mots de passe fictifs des scripts OS4 ne sont pas des comptes de déploiement ; les clones correspondants ne doivent pas être exposés.

## Création et premier envoi

Créer un nouveau dépôt GitHub `ecoute-cfrm` dans le compte `yaroing`, visibilité Public, sans initialisation automatique README/licence/gitignore puisque ces fichiers sont livrés. Ne pas remplacer un dépôt existant sans l'inspecter. Depuis la copie Git préparée :

```sh
git remote add origin https://github.com/yaroing/ecoute-cfrm.git
git push -u origin main
git rev-parse HEAD
git ls-remote origin refs/heads/main
```

Utiliser l'authentification GitHub standard avec gestionnaire de credentials ; ne pas mettre de jeton dans l'URL, une commande, un fichier du dépôt ou un message. Aucun push forcé n'est nécessaire. Si le dépôt existe et n'est pas vide, arrêter cette procédure initiale et examiner ses branches avant de proposer une intégration.

## Vérifier après publication

Ouvrir l'URL publique sans authentification, vérifier README et sa navigation, guides, LICENSE MIT, sources et historique sans secret. Comparer SHA local/distant, puis examiner GitHub Actions du commit publié. Si la CI échoue, lire son diagnostic et corriger le problème ; ne pas qualifier l'exécution distante de réussie avant sa terminaison.

Un dépôt public est un partage du code, pas un hébergement de l'application ou une réception P1. Les anomalies et limites de la recette restent visibles dans README/LIMITES. Les dépendances conservent leurs licences, même sous une licence MIT du code original.
