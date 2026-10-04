# API du prototype

Base : `/api/v1`. Le schéma OpenAPI est disponible à `/api/v1/schema` ; sa copie versionnée est `openapi.yaml`. Les requêtes métier utilisent `Authorization: Bearer <token>`. Un accès interdit à une fiche renvoie 404 ; les autres refus de rôle renvoient 403. Les erreurs contiennent `type`, `title`, `status`, `detail`.

## Authentification

`POST /auth/login` : `username`, `password`, et `otp` pour R4/R6. Réponse : `token`, `refresh`, `expires_in=900`, `user`. Le renouvellement est rotatif via `POST /auth/refresh` avec `refresh`. Après 15 minutes d’inactivité pour R4, 30 minutes pour les autres, une reconnexion est nécessaire. Les sessions sont conservées en sessionStorage, les mots de passe jamais. `POST /auth/logout` révoque la session.

## Réception

`POST /public/retours` : `text`, `type`, `zone`, `project`, `language`, `address` facultatif, `consent`, `key`. L’en-tête `Idempotency-Key` prime sur `key`. La réponse fournit la référence et l’échéance ; aucune lecture publique du contenu n’est exposée.

`POST /agent/sync` : `{ "items": [...] }` (R1, 100 maximum). Chaque item contient une `key` UUID stable. La réponse associe chaque clé à une référence ou à une erreur. Ne supprimer que les entrées confirmées ; les entrées reconnues sensibles doivent être retirées et orientées vers le référent.

`POST /webhooks/sms/simule` et `/webhooks/messagerie/simule` : même charge utile, `key` obligatoire. Ajouter `X-Timestamp` (secondes Unix) et `X-Signature` = HMAC-SHA256 en hexadécimal du corps `timestamp + '.' + octets JSON`, avec le secret du canal. Dérive maximale : 300 secondes. `STOP` bloque les sorties. `REF FB-AAAA-NNNNNN ...` rattache uniquement si l’empreinte de l’expéditeur correspond. Le simulateur authentifié signe côté serveur, jamais dans le navigateur.

## Traitement

`GET /dossiers` accepte `q`, `state`, `theme`, `zone`, `owner`, `project`, `late=1` et un `cursor` signé. Résultat : `results`, `next`, `count` ; 30 lignes maximum. R2 ne reçoit que ses dossiers ; R1 sa collecte des sept derniers jours ; R3 les ordinaires.

`GET /dossiers/{id}` fournit messages, historique, réponses, actions, état du consentement. Le contact en clair nécessite une lecture explicite et journalisée de `/dossiers/{id}/contact` (R2 titulaire ou R3, consentement requis).

- `PATCH .../qualification` : `type`, `theme`, `urgency`, `zone`, `project`, `sensitive` (R3).
- `POST .../transitions` : `state`, `owner` pour attribuer, `reason` pour réattribuer, clôturer ou rouvrir.
- `POST .../notes` : `text`, `attempt=true` pour documenter une tentative de contact.
- `POST .../referencements` : `recipient`, `issue` ; ajouter `id` pour mettre à jour une issue.
- `POST .../reponses` : `text`. `POST .../reponses/{rid}/validation` : `accepted`, `reason` si refus (R3).
- `POST .../reponses/{rid}/transmission-manuelle` : `evidence` (R3, WEB/AGENT). Atteste une transmission par le moyen consenti ; aucun envoi automatique réel.
- `POST .../reponses/{rid}/comprehension` : confirmation explicite de la compréhension.
- `POST .../fusion` : `source` (UUID), `reason`, ou `undo` (identifiant de fusion). Conserve le dossier source et ses historiques ; déplace les messages de manière réversible.

## Sensible, apprentissage et pilotage

R4 : `GET /sensible` et `GET/POST /sensible/{id}`. Transitions : `PRIS_EN_CHARGE`, `TRANSFERE` avec `recipient`, `CLOTURE` avec `receipt`. Le contenu et le transfert restent dans la connexion dédiée. Les lectures sont journalisées.

R3/R5 : `GET/POST /actions`, `PATCH /actions/{id}` ; champs `title`, `project`, `owner`, `due`, `status`, `proof`, `dossiers`. Une action réalisée exige une preuve. `POST /actions/{id}/restitutions` : `date`, `channel`, `zone`, `message`.

R3/R5 : `GET /indicateurs` avec `from`, `to`, `project`. `POST /exports` avec les mêmes filtres et `format=csv|xlsx`. Aucun message, note, contact ou dossier sensible dans l’export.

R3/R6 : `GET/PATCH /admin/settings`. R6 : `POST /admin/users`, `PATCH /admin/users/{id}`. L’enrôlement TOTP n’est retourné qu’à la création d’un compte nécessitant ce facteur. R3/R5 voient uniquement l’annuaire de travail. `GET /audit` est en lecture seule, sans les identifiants des objets sensibles. `GET /notifications` renvoie seulement les alertes de l’utilisateur courant.
