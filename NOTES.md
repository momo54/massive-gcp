# NOTE — PaaS (App Engine) et focus Datastore (GQL, CAP, pricing, sharding)

Ce mémo sert de guide pédagogique pour une séance de TP autour de Google App Engine (PaaS) et du datastore managé de Google (Datastore / Firestore en mode Datastore). Il met en avant les points clés: coût, élasticité, serverless, consistance, expressivité des requêtes et bonnes pratiques de sharding.

Important: les prix et caractéristiques évoluent. Les montants ci‑dessous sont indicatifs; vérifiez toujours la page officielle de pricing Google Cloud le jour du TP.

---

## 1) PaaS en bref (avec App Engine)

- Définition PaaS: plateforme managée pour déployer du code applicatif sans gérer l’OS, les VM, le patching, l’orchestration ni l’auto‑scaling bas niveau. Vous fournissez du code + config (p. ex. `app.yaml`), la plateforme s’occupe du reste.
- Caractéristiques clés d’App Engine (Standard):
  - Déploiement simple (zéro VM à administrer).
  - Auto‑scaling horizontal selon la charge (RPS/latence/CPU). Paramétrable (`min_instances`, `max_instances`, etc.).
  - Facturation à l’usage (instance‑seconds, CPU/Mémoire, egress réseau) + services adjacents (Datastore/Firestore, Storage, etc.).
  - Observabilité intégrée (logs, traces, métriques, page « Instances » pour le scaling).
  - Environnements Standard vs Flexible: Standard démarre plus vite et scale finement; Flexible (conteneurs) offre plus de contrôle mais avec une granularité/coût différents.
- Pourquoi « serverless computing »: App Engine Standard est « serverless » côté dev (pas de serveur à gérer, scale automatique jusqu’à zéro si `min_instances=0`, cold starts possibles). On le constate par:
  - Pas d’accès SSH aux VM, pas de gestion d’OS.
  - Scale à zéro en idle (si config par défaut) puis cold start au premier hit.
  - Runtimes gérés par la plateforme.

### Élasticité: comment la montrer en TP

- Expérience: créer un endpoint HTTP (p. ex. `/work`) qui fait un petit calcul ou une lecture Datastore.
- Lancer une charge croissante (p. ex. 10 → 200 RPS) et observer:
  - Le nombre d’instances App Engine qui monte (console > App Engine > Instances).
  - La latence p50/p95 qui reste maîtrisée si le scaling suit.
- Paramètres utiles (`app.yaml`, Standard):
  - `automatic_scaling`: `target_cpu_utilization`, `min_instances`, `max_instances`, `max_concurrent_requests`.
  - Fixer `max_instances` (ex: 3–5) pour préserver le budget du TP.

### Budget: combien « dépenser » de vos 50$ ? (ordre de grandeur)

- App Engine Standard (petites instances): quelques centimes par heure et par instance active (facturation à la seconde). Une séance courte (1–2h) avec `max_instances ≤ 5` reste typiquement dans la fourchette 1–5$.
- Datastore/Firestore (mode Datastore): facturation à l’opération et au stockage. 100k lectures ≈ quelques centimes; 100k écritures ≈ quelques dizaines de centimes (voir section « Pricing » pour des repères).
- Réseau egress hors GCP: facturé; intra‑région souvent gratuit.
- Bonnes pratiques budget: limiter `max_instances`, durée des tests, jeux de données, et éviter des boucles débridées côté client.

---

## 2) Focus Datastore (Firestore en mode Datastore)

Datastore est une base NoSQL managée, orientée entités/indices. Aujourd’hui, on la rencontre via Firestore en mode Datastore (API héritée: kinds, entités, GQL…).

### Modèle de données
- Entité: objet typé (kind) avec une clé (key) et des propriétés.
- Clés hiérarchiques (ancêtres) → Entity groups: unité de transaction et de consistance forte locale.
- Indexation:
  - Index simples (par propriété)
  - Index composites (requêtes multi‑propriétés, IN/OR/ORDER BY) — à déclarer; coût en écriture et stockage.

### CAP et consistance
- Accès par clé (lookup) et requêtes « ancestor »: consistance forte (strong) dans l’entity group.
- Requêtes globales (sans ancêtre): historiquement « eventually consistent ». Selon le mode/région, des améliorations existent, mais pour le TP: considérez
  - transactions limitées à un entity group;
  - forte consistance locale;
  - éventuelle globalement.
- Lecture CAP (pédagogique): Datastore met l’accent sur Consistency + Partition tolerance (CP) au niveau d’un entity group; l’échelle globale vise la disponibilité avec consistance éventuelle.

### Expressivité de GQL (Google Query Language)
- Points forts:
  - Filtres: égalité (=), IN, et une inégalité (<, <=, >, >=) sur une seule propriété.
  - ORDER BY sur propriétés indexées, compatible avec les filtres.
  - Requêtes ancêtres pour la consistance forte locale.
# Cohérence, Partitionnement et CAP — Google Cloud Datastore (Firestore mode Datastore)
- Limitations:
  - Pas de JOINs, peu/pas d’agrégations côté serveur (les comptes globaux sont à manier avec précaution).

### Pricing (repères indicatifs)
  - Écritures: ≈ $0.18 / 100k
  - Suppressions: ≈ $0.02 / 100k
- Stockage: ≈ $0.18 / Go / mois (index inclus → taille supérieure au brut).
- À surveiller:
  - Une requête qui scanne 10k entités = 10k lectures facturées.
  - Les index composites augmentent le coût en écriture (mises à jour d’index).
  - Les scans larges et itérations complètes côté client « brûlent » les crédits.

### Sharding et hotspotting
- Transactions limitées à un entity group → débit d’écriture par groupe borné.
  - Sharded counters: N sous‑compteurs (ex: 16/32) puis somme côté lecture.
  - Éviter les entités « chaudes » (compteur global unique, file unique) → partitionner.
### Consistency patterns
- Garantie forte requise (lire ce qui vient d’être écrit):
  - ou lookup par clé.
- Tolérance à l’eventual consistency (feeds, listes): requêtes globales et UX tolérante à la latence de propagation.

1) Consistance locale vs globale
- Écrire une entité dans un groupe A, puis lire immédiatement par clé (strong) vs requête globale (peut être eventual); mesurer le délai de visibilité.

- Construire une requête avec tri + inégalité; provoquer l’erreur d’index requis, ajouter l’index, relancer; observer latence et nombre d’entités lues (coût).

3) Sharded counter
- Implémenter un compteur sharded (N=16). Pousser des écritures en parallèle; comparer erreurs/latences vs un compteur unique.

---

## 3) Voir « serverless » et l’élasticité en pratique

- Serverless (App Engine):
  - `min_instances: 0` → laisser l’appli devenir idle; constater le cold start sur le premier hit.
  - Aucun serveur à gérer; uniquement code + config.
- Élasticité:
  - Fixer `max_instances: 3–5`; envoyer une charge graduelle.
  - Suivre « Instances » (compte/CPU) et métriques (latence p50/p95, RPS).
  - Ajuster `max_concurrent_requests` et `target_cpu_utilization` et observer l’effet.

---

## 4) Garde‑fous budget (≤ ~50$)

- Encadrer `max_instances`, limiter la durée des tests.
- Datastore: préférer lookup/ancestor aux scans globaux; éviter les index composites inutiles; nettoyer les données après TP.
- Mettre des alertes budgétaires et surveiller la page « Coûts ».

---

## 5) Check‑list rapide TP

- [ ] Déployer une petite app App Engine (endpoints `/work`, `/db-test`).
- [ ] Activer Datastore/Firestore (mode Datastore), créer 1–2 kinds.
- [ ] Lancer une charge progressive, `max_instances` borné.
- [ ] Démontrer la consistance: lookup (strong) vs requête globale (eventual).
- [ ] Démontrer un index composite requis par GQL.
- [ ] Implémenter un sharded counter et pousser des écritures concurrentes.
- [ ] Estimer les coûts (ops + stockage) via la console.

---

### Références

- Documentation App Engine (concepts, scaling, pricing)
- Datastore / Firestore en mode Datastore (modèle, GQL, index, consistency, pricing)
- Patterns: sharded counters, entity groups, ancestor queries

> Besoin d’un starter (endpoint + Datastore) et d’un mini script de charge? Je peux l’ajouter au repo pour accompagner la séance.