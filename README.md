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


## Licence
MIT
