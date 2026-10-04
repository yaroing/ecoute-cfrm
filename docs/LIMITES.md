# Limites connues et conditions de réception

État au 4 octobre 2026, issu d'OS4. Aucune acceptation intégrale P1, certification WCAG ou validation organisationnelle n'est revendiquée.

| ID | Gravité | Constat | Critère de levée |
|---|---|---|---|
| A01 | Bloquante | Commit sensible sans commit ordinaire, orphelins après panne | Cohérence durable, détection/reprise, C07 sur base vierge |
| A02 | Bloquante | Bascule interrompue : copie chiffrée présente mais drapeau annulé et texte ordinaire conservé | Aucune copie exposée après toutes les pannes ; réconciliation auditée |
| A03 | Majeure | Référent affiché générique | Contact habilité effectif et canal validés par ONG |
| A04 | Majeure | Escalade et suppléance à 24 h incomplètes | Parcours et reprise avec destinataires fictifs |
| A05 | Majeure | Modèles stockés sans insertion | Sélection, édition et validation testées |
| A06 | Majeure | Courriel référent absent | Adaptateur et boîte de recette ; notification sans récit |
| A07 | Majeure | Taxonomie partageable et filtre d'export insuffisants | Contrat et journal complets |
| A08 | Majeure | Langue locale, cumul R2/R3, droits R4, notification direction et inactivité incomplets | Matrice et gouvernance validées |
| A09 | Majeure | Transport local HTTP | Hébergement HTTPS vérifié |

Le chiffrement de la seconde copie ne corrige pas A02. Les clones de panne conservent les incohérences pour investigation et ne doivent pas devenir des bases de pilote.

## Corrections retestées

A10 : accusé sensible neutre avec référence/échéance. A11 : déconnexion bloquée quand la file est non vide et réponse 204 correctement traitée. A12 : trois contrastes publics corrigés ; contrôle ciblé, pas conformité globale.

## Validation restante

Canaux réels, Kobo, multipart physique, téléphones, Slow 3G, lecteurs d'écran, langue et relecture AAP non validés. Provisionnement réel, rétention des backups, rotation des clés et restauration par tiers à établir.

155 interdictions sur 30 couples route/méthode ne constituent pas une matrice exhaustive par objet/projet. L'oracle est limité ; I03/I06/I09 demandent arbitrage. Le détecteur lexical manque deux récits implicites du lot. Un accusé ou une référence ne signifie pas résolution.

## Décision

Acceptation P1 ajournée : lever les blocages et majeures, refaire les tests applicables, obtenir les validations organisationnelles. Les critères humains peuvent être réalisés ultérieurement ou exclus d'un périmètre réduit explicitement approuvé ; aucun SUS ni temps utilisateur ne doit être inventé.
