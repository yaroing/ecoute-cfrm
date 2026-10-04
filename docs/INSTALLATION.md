# Guide d'installation et de déploiement

Version du 4 octobre 2026. Ce guide décrit une recette locale **sur données fictives**. Les anomalies OS4 doivent être levées avant tout emploi de données réelles.

## Prérequis

| Élément | Utilisation |
|---|---|
| Git | Cloner et identifier la version |
| Docker démarré, Compose v2 | Base, API, worker, proxy, sauvegarde |
| Python 3.12+ | Générer les secrets ; CI actuelle sur Python 3.14 |
| Node.js 22 et npm | Développement natif et vérifications front-end |
| Navigateur récent | JavaScript, IndexedDB, service workers |
| Ports libres | Docker 8080 ; natif 8000 et 5173 |

Prévoir de l'espace pour images, volumes et sauvegardes. Les limites OS4 de 2 CPU/4 Gio ne sont pas une capacité de production certifiée.

```sh
git --version
docker version
docker compose version
python --version
git clone https://github.com/yaroing/ecoute-cfrm.git
cd ecoute-cfrm
git rev-parse HEAD
```

Noter le commit dans le registre de déploiement. Les recettes antérieures à Git étaient figées par SHA256 ; ne pas leur attribuer rétroactivement un commit.

## Configuration

Exécuter `python scripts/init_env.py`. Il génère `.env` et refuse de l'écraser. `.env.example` décrit les variables : ses marqueurs ne permettent pas un démarrage, ne pas le copier tel quel.

| Variables | Fonction |
|---|---|
| APP_ENV, SIMULATION | Recette `local`, simulation `1` |
| ALLOWED_HOSTS | Hôtes Django, séparés par virgules |
| SITE_ADDRESS | Écoute Caddy ; `http://localhost:8080` |
| DJANGO_SECRET | Signature Django |
| FIELD_KEY | 32 octets hexadécimaux, champs et TOTP |
| HMAC_KEY | Empreinte de rattachement des contacts |
| SMS_SECRET, MESSAGING_SECRET | Signatures des webhooks |
| DB_ADMIN_PASSWORD | Compte PostgreSQL d'exploitation/sauvegarde |
| POSTGRES_PASSWORD, SENSITIVE_PASSWORD | Deux comptes SQL applicatifs |
| OWNER_PASSWORD, SENSITIVE_OWNER_PASSWORD | Propriétaires SQL de migration |
| REPORT_PASSWORD | Compte de lecture agrégée |
| BACKUP_KEY | 32 octets hexadécimaux, sauvegardes |

Conserver les clés dans un coffre distinct des sauvegardes. Modifier `.env` ne change pas un mot de passe SQL déjà créé. L'initialisation PostgreSQL ne s'exécute que sur un volume neuf. Ne pas régénérer les clés d'une base existante.

## Installation Docker

```sh
docker compose --env-file .env -f deploy/compose.yml up -d --build
docker compose --env-file .env -f deploy/compose.yml ps -a
docker compose --env-file .env -f deploy/compose.yml logs --tail 80 init api worker
docker compose --env-file .env -f deploy/compose.yml exec -T api python manage.py seed_demo
docker compose --env-file .env -f deploy/compose.yml cp api:/app/demo/credentials.json .demo-docker-credentials.json
```

PostgreSQL devient sain, `init` migre les deux schémas et accorde les droits, puis les services démarrent. `init` terminé avec code 0 est normal. API/worker restent actifs, DB affiche `healthy`. Seul Caddy est publié sur loopback.

Ouvrir `http://localhost:8080/#public`, déposer un texte fictif, noter la référence, puis la retrouver avec `superviseur` à `/#login`. Le schéma se trouve à `/api/v1/schema`.

Les comptes sont générés dans le fichier local copié. R4/R6 exigent TOTP. `seed_demo` conserve les comptes existants ; `seed_demo --reset-passwords` renouvelle les six comptes fictifs en simulation. Recopier ensuite les identifiants et réimporter les secrets TOTP concernés.

## Coexistence de plusieurs instances

Le nom `ecoute-os3` détermine les volumes ; un autre nom ne change pas le port. Pour une deuxième instance, créer `deploy/compose.local.yml`, ignoré par Git :

```yaml
services:
  proxy:
    ports: !override
      - '127.0.0.1:8086:8080'
```

`!override` nécessite Compose 2.24.4+. URL externe : `http://localhost:8086` ; écoute interne : 8080. Toujours utiliser le même nom et les deux fichiers :

```sh
docker compose --env-file .env -p ecoute-recette -f deploy/compose.yml -f deploy/compose.local.yml up -d --build
```

Ne pas réutiliser les volumes de panne OS4 comme base de démonstration ou de pilote.

## Arrêt et mise à jour

```sh
docker compose --env-file .env -f deploy/compose.yml stop
docker compose --env-file .env -f deploy/compose.yml up -d
```

L'arrêt conserve les volumes. `down -v` les détruit ; ce n'est pas une mise à jour. Avant mise à jour : sauvegarde, restauration séparée, version enregistrée, arrêt des écritures, migrations testées sur clone. Voir [EXPLOITATION.md](EXPLOITATION.md).

## Développement natif

Windows : lancer `./start.ps1`. Il crée `.venv`, installe, migre deux bases SQLite, charge les exemples, construit le front-end et démarre API/worker/prévisualisation. `Ctrl+C` termine les processus lancés. URL `http://127.0.0.1:5173` ; comptes `.demo-credentials.json`.

Linux/macOS, commandes manuelles :

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements-dev.txt
.venv/bin/python backend/manage.py migrate
.venv/bin/python backend/manage.py migrate --database sensible
.venv/bin/python backend/manage.py seed_demo
.venv/bin/python backend/manage.py runserver 127.0.0.1:8000
```

Deuxième terminal : `.venv/bin/python backend/manage.py worker`. Troisième terminal :

```sh
cd frontend
npm ci
npm run dev
```

Vite dev n'active pas le service worker. Pour le cache statique : `npm run build`, puis `npm run preview -- --port 5173` avec API/worker actifs. Les secrets natifs sont générés dans `.local-secrets.json`. Django ne lit pas automatiquement `.env` : Docker transmet ses variables ; le natif utilise les variables du processus ou son fichier de secrets.

SQLite ne valide ni les permissions PostgreSQL ni la reprise entre connexions SQL.

## Préparation d'un hébergement HTTPS

Le Compose expose `127.0.0.1:8080` en HTTP. Changer SITE_ADDRESS seul ne suffit pas : adapter écoute et ports 80/443 du proxy, DNS, pare-feu et certificats ; définir ALLOWED_HOSTS, `APP_ENV=production`, `SIMULATION=0` et provisionner les comptes hors `seed_demo`.

Avant un pilote : lever C07 et les exigences ouvertes ; sélectionner les canaux réels ; valider référent, suppléance et rétention ; installer les sauvegardes hors serveur ; vérifier restaurations et droits. Ce guide n'effectue ni n'approuve un déploiement de production.

## Diagnostic

| Symptôme | Vérification/action |
|---|---|
| Docker indisponible | Démarrer Docker ; vérifier `docker version` |
| Port occupé | Identifier l'instance ; isoler projet et port |
| init échoue | Lire ses logs ; vérifier rôles/secrets du volume existant sans le supprimer |
| 502 | Vérifier API/init ; conserver les entrées terrain et resynchroniser |
| Connexion refusée | Compte, TOTP et heure ; après cinq échecs, verrouillage de quinze minutes |
| File non vide | Revenir en ligne, renouveler la session si nécessaire, Envoyer maintenant ; ne pas effacer le stockage |
| Chiffrement illisible | Arrêter les écritures, restaurer FIELD_KEY correcte, pas une clé neuve |
| Sauvegarde échoue | pg_dump 16, base, répertoire et BACKUP_KEY ; ne pas afficher les secrets |

Pour l'assistance : commit, méthode, rôle, code HTTP, exemple fictif et logs expurgés.
