# Reproduire les tests automatisés OS4

Sur une copie propre du dépôt, uniquement avec données fictives. Ces scripts injectent pannes, modifications d'horloge et incohérences. Un nom de projet neuf et ses volumes distincts sont indispensables ; ne jamais utiliser la base active. Les comptes de test ont des mots de passe fictifs connus : ne pas exposer ces clones au public.

## Préparer les images

Générer `.env` selon INSTALLATION. Depuis la racine :

```sh
docker build -t ecoute-os3-api:latest -f deploy/Dockerfile.api .
docker build -t ecoute-os3-proxy:latest -f deploy/Dockerfile.proxy .
docker build -t ecoute-os3-backup:latest -f deploy/Dockerfile.backup .
```

Les campagnes utilisent les sources montées, pas nécessairement le code embarqué de l'image. Enregistrer le commit et les images réellement exécutés. Ne pas confondre les trois images locales avec un registre public d'images.

## Campagne métier et simulations

Compose 2.24.4+ pour le remplacement du port dans functional.override.yml. Les dépendances de campagne (DRF, openpyxl) sont dans requirements.txt. Utiliser un nom neuf ; les scripts refusent certains identifiants déjà présents.

```sh
docker compose --env-file .env -p ecoute-os4-metier-neuf -f docs/os4/compose.yml -f docs/os4/functional.override.yml up -d --build
docker compose --env-file .env -p ecoute-os4-metier-neuf -f docs/os4/compose.yml -f docs/os4/functional.override.yml stop worker
docker compose --env-file .env -p ecoute-os4-metier-neuf -f docs/os4/compose.yml -f docs/os4/functional.override.yml exec -T api python /app/scripts/os4_supplements.py
docker compose --env-file .env -p ecoute-os4-metier-neuf -f docs/os4/compose.yml -f docs/os4/functional.override.yml exec -T -e OS4_RUN=nouvelle-mesure api python /app/scripts/os4_campaign.py
docker compose --env-file .env -p ecoute-os4-metier-neuf -f docs/os4/compose.yml -f docs/os4/functional.override.yml exec -T api python /app/scripts/os4_sessions.py
docker compose --env-file .env -p ecoute-os4-metier-neuf -f docs/os4/compose.yml -f docs/os4/functional.override.yml run --rm --no-deps backup-os4
```

Les tâches worker sont appelées explicitement pour les horloges métier et les pannes. Le proxy de cette instance écoute localhost:8085 ; son réseau n'est pas marqué interne, mais les sorties restent simulées. Aucun fournisseur réel ne doit être configuré. Les verdicts détaillés sont dans docs/os4/nouvelle-mesure, complements et sessions. Un script terminé n'implique pas réussite de ses assertions : lire results.json et les cas bloqués.

La restauration crée une base os4_restore_HORODATAGE ; noter ce nom dans restore-results.json. Exécuter ses contrôles avec cette base explicite :

```sh
docker compose --env-file .env -p ecoute-os4-metier-neuf -f docs/os4/compose.yml -f docs/os4/functional.override.yml exec -T -e POSTGRES_DB=os4_restore_HORODATAGE api python /app/scripts/os4_restore_checks.py
```

Remplacer le marqueur par le nom réel, ne pas l'exécuter littéralement. Les clés doivent être celles de la campagne. La précondition de clé absente n'est pas une procédure complète de coffre.

## Charge longue

Le nom ecoute-os4 est attendu par le collecteur Docker. Vérifier qu'aucun ancien projet de ce nom n'est utilisé ; sinon adapter ses quatre noms de conteneurs et choisir un nouveau nom partout. Avant le lancement, créer docs/os4/load et conserver les anciens résultats hors de ce répertoire : un summary.json existant termine immédiatement le collecteur.

```sh
python -c "from pathlib import Path; Path('docs/os4/load').mkdir(parents=True, exist_ok=True)"
docker compose --env-file .env -f docs/os4/compose.yml up -d db init api worker proxy
```

Lancer le collecteur dans un premier terminal **avant** la charge :

```sh
python scripts/os4_monitor.py
```

Puis, dans un deuxième terminal :

```sh
docker compose --env-file .env -f docs/os4/compose.yml exec -T api python /app/scripts/os4_load.py
```

Le collecteur attend les quatre conteneurs. Le réseau interne sert la charge depuis le conteneur API ; l'accès externe au port 8084 n'est pas requis. Le test dure environ 52 minutes, avec trois rampes 120 s et plateaux 900 s, 20 clients et une attente programmée 1 s. Vérifier summary.json, requests.csv, worker.json, resources.json, écritures attendues/observées et limites cgroups.

Arrêter uniquement le projet de test avec `docker compose ... stop`, sans supprimer ses volumes. Les bases contenant les pannes C07 sont à conserver pour investigation ou à éliminer par une procédure décidée ; ne pas les recycler pour un pilote.

## Validité

Six profils logiciels ne remplacent pas le SUS, le consentement d'une personne, sa compréhension ou son temps autonome. APIClient isole certains scénarios métier et n'est pas une couverture UI exhaustive. Les téléphones, canaux opérateurs, arbitrages ONG et revues humaines restent des activités distinctes. Les résultats historiques sont décrits dans RECETTE ; une reproduction sur les sources publiées peut différer.
