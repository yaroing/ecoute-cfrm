# Contribuer à Écoute

Le code et les guides originaux sont sous MIT. Proposer uniquement des contributions dont vous possédez les droits et acceptez la distribution sous cette licence.

1. Lire README, ARCHITECTURE et LIMITES ; expliquer le problème avec un scénario fictif.
2. Créer une branche depuis `main` dans votre fork. Ne jamais ajouter secrets, comptes générés, bases, sauvegardes ou documents privés.
3. Modifier code et guides concernés ; garder les droits côté serveur.
4. Vérifier les régressions métier/sécurité et les reprises après panne. Les permissions SQL exigent PostgreSQL, pas seulement SQLite.
5. Exécuter les contrôles du README ; préciser résultat, risques, migrations et limites dans la PR.

OS4 injecte volontairement pannes et incohérences : utiliser un projet Docker et un volume neufs, fictifs, avec worker contrôlé, jamais la base active.

Issue/PR : commit, rôle, étapes, attendu, obtenu, code HTTP et preuves expurgées. Les contrôles logiciels ne valident pas l'autonomie humaine. Les défauts de confidentialité et d'intégrité sont prioritaires ; suivre SECURITY pour les signalements confidentiels.
