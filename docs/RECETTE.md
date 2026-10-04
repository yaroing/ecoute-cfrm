# Synthèse de recette OS4

Campagne du 4 octobre 2026, données fictives, six profils logiciels, aucun participant humain. Le plan utilisateur T01–T18/C01–C07 a été décliné en campagnes API/PostgreSQL, sessions simulées, tests de file IndexedDB, contrôles navigateur, restauration et charge. Les exigences humaines, physiques ou organisationnelles ne sont pas transformées en réussites logicielles.

## Résultats par lot

| Lot | Résultat et limite |
|---|---|
| Jeu métier | 60 cas générés : 20 réglage, 40 mesure ; annotations logicielles, sans double lecture AAP |
| Lot final | 98 sous-cas : 75 réussis, 13 échoués, 10 bloqués |
| Compléments | 38 sous-cas, conservés séparément ; configuration, liens et purge |
| Réception K01 | Web 20/20 et SMS simulés 20/20 ; 40 créations nouvelles |
| Rejeux K02 | 20 originaux + 60 rejeux + 8 concurrents ; aucun dossier supplémentaire |
| Reprise K03 | 100 UUID ordinaires, 30 puis 70, confirmations/rejeux ; téléphone physique absent |
| Accusés K04 | Mesures jusqu'au retour API ; 17/20 SMS ont une sortie simulée, 3 sans sortie par anonymat/refus ; aucune livraison opérateur prouvée |
| Droits K05 | 155/155 interdictions sur 30 couples route/méthode ; matrice partielle, droits positifs R4 en échec |
| Sensible K06 | TP 4, FN 2, FP 2, TN 32 ; explicites 4/4 ; rappel 4/6 = 66,67 %, faux positifs 2/34 = 5,88 % |
| Thèmes K07 | Non applicable, suggestion EF15 différée P2 |
| Temps K08 et utilisabilité K09 | Non mesurés chez des personnes ; aucun score SUS |
| Sessions | Six profils, 36 tâches API réussies ; 120 parcours Excel et 120 Écoute ; temps machine uniquement |
| Non-régression | 21 tests serveur et 7 front-end réussis ; couverture core 93,99 %, migrations/commandes exclues |

Les sous-cas ne constituent pas un taux global de conformité. Une exigence obligatoire en échec empêche la réception de sa fiche, même si ses autres sous-cas réussissent.

## Charge T16

Base fictive 5 000 dossiers, un message et une note initiale chacun. Trois répétitions : montée 120 s, plateau 900 s, 20 clients, mix 50 % listes filtrées/40 % fiches/10 % notes, attente programmée 1 s entre requêtes. Cgroups totaux 2 CPU/4 Gio, hôte partagé, générateur dans API.

| Essai | Requêtes plateau | p95 listes ms | p95 fiches ms | Erreurs HTTP |
|---|---:|---:|---:|---:|
| 1 | 17 361 | 75,19 | 84,04 | 0 |
| 2 | 17 388 | 67,45 | 71,89 | 0 |
| 3 | 17 304 | 93,23 | 98,64 | 0 |

5 547 écritures acceptées et retrouvées, 5 000 dossiers conservés. CPU/RAM commencent pendant le deuxième essai ; premier essai non intégralement instrumenté. Ces résultats ne qualifient pas un serveur physique dédié. Les corrections V2 ne modifient pas les routes de lecture mesurées sur les processus V1.

## Restauration et panne

Dump PostgreSQL 16 chiffré restauré dans une base dédiée : comptages identiques, 156 contacts déchiffrables, lecture sensible R4 autorisée, autres rôles refusés, chaîne d'audit valide. Durée du banc 2,979 s. Quotidien sur plusieurs jours, rétention, rotation et opérateur tiers non validés.

C07 échoue : les transactions de deux connexions ne sont pas atomiques ensemble. Orphelins sensibles et copie ordinaire conservée après bascule interrompue sont constatés. Les données d'investigation ne sont pas supprimées pour donner une apparence de conformité. Voir A01/A02 dans [LIMITES.md](LIMITES.md).

## Ajustements et décision

AR sensible neutre complété ; déconnexion protégée avec file en attente et réponse 204 corrigée ; trois contrastes publics améliorés. Contrôles ciblés, pas certification WCAG.

Acceptation P1 ajournée. Modèles, escalade, référent effectif, courriel/suppléance, taxonomie, langue, droits/gouvernance et HTTPS restent incomplets. Les validations humaines, appareils physiques, fournisseurs et arbitrages ne sont pas signés par les profils logiciels.

## Rejouer les campagnes

Les scripts de campagne `scripts/os4_*.py` et les fichiers Compose `docs/os4/` sont livrés pour reproduction sur clones fictifs ; voir [le protocole d'exécution](os4/REPRODUCTION.md). Les outils locaux de fabrication des rapports ne font pas partie du dépôt public. Les mesures brutes, identifiants de campagne, captures privées et rapports Word locaux sont conservés dans le dossier de preuves remis au porteur, pas publiés dans ce dépôt.

Les tests serveur rapides utilisent SQLite ; les essais de métier/charge PostgreSQL restent indispensables. La CI distante doit être vérifiée après publication. La présence du workflow ne transforme pas les résultats locaux OS4 en résultats d'un commit publié.
