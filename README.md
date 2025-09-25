# Tiny Instagram sur Google App Engine

Ce projet est une version minimaliste d'Instagram permettant de :
- Poster un message
- Suivre des utilisateurs
- Lire sa timeline (messages des utilisateurs suivis)

## Prérequis
- Compte Google Cloud Platform (GCP)
- Projet GCP créé
- Google Cloud SDK installé (`gcloud`)
- Python 3.10+

## Installation locale

1. Clone ce dépôt ou copie les fichiers dans un dossier.
2. Installe les dépendances :
   ```sh
   pip install -r requirements.txt
   ```
3. Configure l'authentification GCP (si besoin) :
   ```sh
   gcloud auth application-default login
   ```
4. Lance l'application en local :
   ```sh
   python main.py
   ```
   Accède à http://localhost:8080

## Déploiement sur Google App Engine

1. Initialise le projet GCP si ce n'est pas déjà fait :
   ```sh
   gcloud init
   gcloud app create
   ```
2. Déploie l'application :
   ```sh
   gcloud app deploy
   ```
3. Accède à l'URL fournie par GCP après le déploiement.

## Fonctionnalités
- Connexion par nom d'utilisateur (pas de mot de passe, démo)
- Poster un message
- Suivre un utilisateur
- Timeline : affiche les messages des utilisateurs suivis

## Structure des fichiers
- `main.py` : code principal Flask
- `requirements.txt` : dépendances Python
- `app.yaml` : configuration App Engine

## Notes
- Ce projet est à but pédagogique et n'est pas sécurisé pour la production.
- Pour réinitialiser la base, supprime les entités dans Google Cloud Datastore.
- Pour plus de détails sur partitionnement, cohérence et CAP côté Datastore, voir [`NOTES.md`](./NOTES.md).

## Dépannage (Troubleshooting)

### Erreur: `Failed to create cloud build ... invalid bucket ... service account ... does not have access to the bucket`
Causes possibles:
1. L'API Cloud Build n'est pas activée.
2. Le compte de service App Engine (`PROJECT_ID@appspot.gserviceaccount.com`) n'a pas les rôles nécessaires sur le bucket de staging ou sur le projet.
3. Le bucket de staging a été supprimé ou restreint.

### Résolution
Active les APIs requises (si ce n'est pas déjà fait):
```sh
gcloud services enable appengine.googleapis.com cloudbuild.googleapis.com iam.googleapis.com storage.googleapis.com
```
Assure-toi que le compte de service a les rôles suivants au niveau du projet (ou via une policy fine sur le bucket):
- `roles/storage.admin` (ou a minima `roles/storage.objectAdmin` + lecture bucket)
- `roles/cloudbuild.builds.editor` (souvent implicite si Cloud Build activé)

Commande pour ajouter un rôle minimal sur le projet:
```sh
PROJECT_ID="<ton-project-id>"
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
   --member="serviceAccount:${PROJECT_ID}@appspot.gserviceaccount.com" \
   --role="roles/storage.admin"
```

Si le bucket de staging manque (nom attendu: `staging.$PROJECT_ID.appspot.com`), force une recréation implicite en relançant:
```sh
gcloud app deploy
```
Sinon crée un bucket et donne les droits (optionnel):
```sh
gsutil mb -p "$PROJECT_ID" -l europe-west1 "gs://staging.${PROJECT_ID}.appspot.com"
gsutil iam ch serviceAccount:${PROJECT_ID}@appspot.gserviceaccount.com:objectAdmin "gs://staging.${PROJECT_ID}.appspot.com"
```

Vérifie les permissions actuelles:
```sh
gsutil iam get gs://staging.${PROJECT_ID}.appspot.com | grep appspot || true
```

### Index Datastore
Un fichier `index.yaml` a été ajouté. Déploie les index si demandé:
```sh
gcloud datastore indexes create index.yaml || gcloud app deploy index.yaml
```

## Requêtes GQL (Datastore / Firestore mode Datastore)
L'application utilise une requête GQL pour récupérer la timeline.

### Exemple utilisé
```sql
SELECT * FROM Post WHERE author IN @authors ORDER BY created DESC
```
En Python (lib `google-cloud-datastore`):
```python
gql = client.gql("SELECT * FROM Post WHERE author IN @authors ORDER BY created DESC")
gql.bindings["authors"] = ["alice", "bob"]
results = list(gql.fetch(limit=20))
```

### Quand utiliser GQL
- Lecture rapide avec un style proche SQL.
- Prototypage ou debug (lisibilité).

### Limitations / Rappels
- Pas d'`INSERT/UPDATE/DELETE` en GQL (écritures via l’API objet).
- Pas de JOIN, pas d’agrégations complexes (COUNT global côté serveur absent – il faut compter côté client ou maintenir un compteur).
- Les filtres doivent être compatibles avec les index (composite requis si mélange de filtres + tri sur plusieurs propriétés).
- `IN` compte comme un filtre d’égalité multiple et nécessite que la propriété soit indexée (par défaut elle l’est, sauf exclusion).
- Un ordre décroissant (`ORDER BY created DESC`) nécessite que la propriété soit indexée et, si combiné avec des filtres sur d'autres propriétés, souvent un index composite.

### Alternatives
- API Query native (utilisée en fallback dans `main.py`).
- Cloud Logging + `gcloud datastore indexes list` pour diagnostiquer des besoins d’index.

### Bonnes pratiques
- Limiter le nombre d’entités retournées (`limit` + pagination via curseurs).
- Sur des volumes importants, stocker éventuellement un cache matériel (Memorystore) si latence critique.
- Ajouter des tests simples pour valider qu’un changement de requête ne casse pas la timeline.

## Test de charge (Apache Bench)

Un endpoint JSON a été ajouté: `GET /api/timeline?user=<username>&limit=20`.

### 1. Préparer un utilisateur et quelques posts
Ouvre le site, connecte-toi avec un nom (ex: `loaduser`) et crée quelques posts + suis 1–2 autres utilisateurs.

### 2. Récupérer le cookie de session
En local (Flask dev server) ou après déploiement :
Dans ton navigateur, ouvre les DevTools > Storage > Cookies et récupère la valeur de `session`.

Ensuite, tu peux lancer:
```sh
AB_COOKIE="session=<VALEUR_COOKIE>"
ab -n 500 -c 50 -H "Cookie: $AB_COOKIE" "https://<ton-app-id>.appspot.com/api/timeline?limit=20"
```

### 3. Variante sans cookie
Tu peux directement passer le paramètre `user=` (pas besoin de session) :
```sh
ab -n 500 -c 50 "https://<ton-app-id>.appspot.com/api/timeline?user=loaduser&limit=20"
```
Si l’utilisateur n’existe pas encore dans Datastore, crée-le d’abord via l’interface (ou ajoute une entité `User`).

### 4. En local
```sh
ab -n 200 -c 20 "http://127.0.0.1:8080/api/timeline?user=loaduser&limit=20"
```

### 5. Interprétation rapide des métriques
- `Requests per second` : débit moyen.
- `Time per request (mean)` : latence moyenne globale.
- Vérifie `Failed requests` doit rester à 0 (sinon voir logs).

### 6. Génération rapide de données (optionnel avec curl)
```sh
for i in $(seq 1 30); do \
   curl -X POST -d "content=Post $i" -b "$AB_COOKIE" https://<ton-app-id>.appspot.com/post >/dev/null 2>&1; \
done
```

## Script de peuplement (seed)

Un script `seed.py` permet de créer rapidement des utilisateurs, relations de suivi et posts.

### Installation des dépendances
Assure-toi d'avoir déjà installé :
```sh
pip install -r requirements.txt
```

### Utilisation
```sh
python seed.py --users 8 --posts 80 --follows-min 1 --follows-max 4 --prefix demo
```

Paramètres:
- `--users` : nombre d'utilisateurs (demo1..demoN)
- `--posts` : nombre total de posts créés (répartis aléatoirement)
- `--follows-min` / `--follows-max` : fourchette de follows par utilisateur
- `--prefix` : préfixe des noms
- `--dry-run` : affiche le plan sans écrire

### Exemple dry-run
```sh
python seed.py --users 5 --posts 20 --dry-run
```

### Notes seed
- Idempotent sur la création d'utilisateurs (ne supprime rien).
- Ajoute simplement des posts supplémentaires à chaque exécution.
- Les timestamps sont échelonnés (ordre stable pour les tests).

### Endpoint seed côté serveur
Pour exécuter un seed côté serveur (sans lancer `seed.py`):
```sh
curl -X POST \
   -H "X-Seed-Token: change-me-seed-token" \
   "https://<ton-app-id>.appspot.com/admin/seed?users=5&posts=40&follows_min=1&follows_max=3&prefix=bench"
```
Réponse JSON:
```json
{ "status": "ok", "users_total": 5, "users_created": 5, "posts_created": 40, "prefix": "bench" }
```
Sécurité minimale: change la valeur `SEED_TOKEN` dans `app.yaml` avant déploiement.
Sans token défini côté serveur, l’endpoint accepte tout (développement uniquement).




## Licence
MIT
