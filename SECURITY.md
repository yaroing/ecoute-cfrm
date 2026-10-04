# Sécurité

Prototype sans version approuvée pour des signalements réels. Les anomalies bloquantes de cohérence sensible sont recensées dans [LIMITES.md](docs/LIMITES.md).

Utiliser « Report a vulnerability » dans Security si le signalement privé est activé ; sinon demander au mainteneur un canal confidentiel sans publier les détails d'exploitation. Aucun délai contractuel de réponse n'est annoncé. Le dépôt n'est pas un canal de signalement humanitaire.

Fournir commit, préconditions, scénario fictif minimal, impact et traces expurgées. Ne transmettre ni clés, jetons, TOTP, mots de passe, coordonnées ou récits réels.

Les audits sont datés, sans garantie d'absence de faille. Toute correction de droits, chiffrement, synchronisation ou bascule doit rejouer les scénarios concernés sur PostgreSQL et la non-régression. Les sources modifiées ne mettent pas à jour les images déjà chargées : reconstruire et vérifier un clone.
