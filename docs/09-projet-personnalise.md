# Projet personnalise d'accompagnement

Mise en oeuvre technique : 18 juillet 2026.

Le module transpose dans l'application les droits prevus par l'article L.311-3 du Code de
l'action sociale et des familles : accompagnement individualise, recherche du consentement,
confidentialite, acces aux informations et participation directe de la personne a la conception
et a la mise en oeuvre de son projet.

## Donnees et cycle de vie

Le projet distingue la parole et les attentes de la personne, ses forces, les besoins evalues,
les objectifs, les actions, les modalites de participation, le consentement et la date de revue.
Un brouillon peut etre travaille avant publication. Chaque enregistrement cree une nouvelle
version immuable; les consultations et modifications sont auditees.

## Securite

- acces reserve aux professionnels disposant de la permission et rattaches a l'unite active ;
- contenu chiffre en AES-256-GCM avant stockage, avec nonce aleatoire et contexte lie au projet ;
- cle separee fournie par `APP_FIELD_ENCRYPTION_KEY`, jamais stockee en base ;
- metadonnees limitees a l'etat, aux dates, aux auteurs et aux numeros de version ;
- controle de concurrence par ETag et protection CSRF sur toute modification.

En production, la cle doit etre generee aleatoirement, conservee dans un gestionnaire de secrets,
sauvegardee separement et faire l'objet d'une procedure documentee de rotation et de restauration.
Perdre cette cle rend les projets irrecuperables.

Ce module fournit des moyens techniques et ne constitue pas, a lui seul, une preuve de conformite.
L'organisme doit valider le contenu, les habilitations, les durees de conservation, l'information
des personnes et les modalites d'exercice de leurs droits avec son DPO et ses responsables metier.
