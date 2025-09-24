from flask import Flask, request, redirect, url_for, render_template_string, session
from google.cloud import datastore

app = Flask(__name__)
app.secret_key = 'dev-key'  # À changer en prod
client = datastore.Client()

# Templates HTML minimalistes
TEMPLATE_INDEX = '''
<h2>Bienvenue sur Tiny Instagram</h2>
{% if user %}
  Connecté en tant que <b>{{ user }}</b> | <a href="/logout">Déconnexion</a><br><br>
  <form action="/post" method="post">
    <input name="content" placeholder="Votre message" required>
    <button>Poster</button>
  </form>
  <h3>Timeline</h3>
  {% for post in timeline %}
    <div><b>{{ post['author'] }}</b>: {{ post['content'] }}</div>
  {% endfor %}
  <h3>Suivre un utilisateur</h3>
  <form action="/follow" method="post">
    <input name="to_follow" placeholder="Nom d'utilisateur" required>
    <button>Suivre</button>
  </form>
{% else %}
  <form action="/login" method="post">
    <input name="username" placeholder="Nom d'utilisateur" required>
    <button>Connexion</button>
  </form>
{% endif %}
'''

@app.route('/', methods=['GET'])
def index():
    user = session.get('user')
    timeline = []
    if user:
        # Récupérer les utilisateurs suivis avec protection si l'entité n'existe pas encore
        follow_key = client.key('User', user)
        user_entity = client.get(follow_key)
        follows = []
        if user_entity:
            follows = user_entity.get('follows', [])
        # Inclure soi-même et dédoublonner
        follows = list({*follows, user})

        # Tentative GQL (peut ne pas être supporté selon version lib / environnement)
        # On isole uniquement la partie potentiellement sujette à exception
        used_gql = False
        try:
            if hasattr(client, 'gql'):
                gql = client.gql("SELECT * FROM Post WHERE author IN @authors ORDER BY created DESC")
                gql.bindings["authors"] = follows
                timeline = list(gql.fetch(limit=20))
                used_gql = True
        except Exception:
            # Ignorer et retomber sur la query classique
            pass

        if not used_gql:
            # Fallback: API Query classique avec filtre IN (si supporté) sinon agrégation manuelle
            try:
                query = client.query(kind='Post')
                query.add_filter('author', 'IN', follows)
                query.order = ['-created']
                timeline = list(query.fetch(limit=20))
            except Exception:
                # Si le filtre IN n'est pas supporté (émulateur ancien), on agrège manuellement
                posts = []
                for author in follows:
                    q = client.query(kind='Post')
                    q.add_filter('author', '=', author)
                    q.order = ['-created']
                    posts.extend(list(q.fetch(limit=20)))
                # Trier globalement et limiter
                timeline = sorted(posts, key=lambda p: p.get('created'), reverse=True)[:20]
    return render_template_string(TEMPLATE_INDEX, user=user, timeline=timeline)

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    key = client.key('User', username)
    if not client.get(key):
        entity = datastore.Entity(key)
        entity.update({'follows': []})
        client.put(entity)
    session['user'] = username
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('index'))

@app.route('/post', methods=['POST'])
def post():
    user = session.get('user')
    if not user:
        return redirect(url_for('index'))
    content = request.form['content']
    entity = datastore.Entity(client.key('Post'))
    entity.update({
        'author': user,
        'content': content,
        'created': datastore.helpers.datetime.datetime.utcnow()
    })
    client.put(entity)
    return redirect(url_for('index'))

@app.route('/follow', methods=['POST'])
def follow():
    user = session.get('user')
    to_follow = request.form['to_follow']
    if not user or user == to_follow:
        return redirect(url_for('index'))
    user_key = client.key('User', user)
    user_entity = client.get(user_key)
    if to_follow not in user_entity['follows']:
        user_entity['follows'].append(to_follow)
        client.put(user_entity)
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8080, debug=True)
