from flask import Flask, render_template, redirect, url_for, send_from_directory, request, session, jsonify
from flask_bootstrap import Bootstrap
from PIL import Image
from werkzeug.utils import secure_filename
from werkzeug.exceptions import HTTPException
from dotenv import load_dotenv, find_dotenv
from functools import wraps
from authlib.integrations.flask_client import OAuth
import urllib.parse
import os
import constants

# Load Env variables
ENV_FILE = find_dotenv()
if ENV_FILE:
    load_dotenv(ENV_FILE)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY')
Bootstrap(app)

AUTH0_CALLBACK_URL = os.environ.get(constants.AUTH0_CALLBACK_URL)
AUTH0_CLIENT_ID = os.environ.get(constants.AUTH0_CLIENT_ID)
AUTH0_CLIENT_SECRET = os.environ.get(constants.AUTH0_CLIENT_SECRET)
AUTH0_DOMAIN = os.environ.get(constants.AUTH0_DOMAIN)
AUTH0_BASE_URL = 'https://' + AUTH0_DOMAIN

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
images_directory = os.path.join(APP_ROOT, 'images')
thumbnails_directory = os.path.join(APP_ROOT, 'thumbnails')
if not os.path.isdir(images_directory):
    os.mkdir(images_directory)
if not os.path.isdir(thumbnails_directory):
    os.mkdir(thumbnails_directory)


@app.errorhandler(Exception)
def handle_auth_error(ex):
    response = jsonify(message=str(ex))
    response.status_code = (ex.code if isinstance(ex, HTTPException) else 500)
    return response


oauth = OAuth(app)

auth0 = oauth.register(
    'auth0',
    client_id=AUTH0_CLIENT_ID,
    client_secret=AUTH0_CLIENT_SECRET,
    api_base_url=AUTH0_BASE_URL,
    access_token_url=AUTH0_BASE_URL + '/oauth/token',
    authorize_url=AUTH0_BASE_URL + '/authorize',
    client_kwargs={
        'scope': 'openid profile email',
    },
)


# Requires authentication decorator
def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if is_logged_in():
            return f(*args, **kwargs)
        return redirect('/')

    return decorated


def is_logged_in():
    return constants.PROFILE_KEY in session


@app.route('/')
def index():
    return render_template('index.html', env=os.environ, logged_in=is_logged_in())


@app.route('/gallery')
def gallery():
    thumbnail_names = os.listdir('./thumbnails')
    return render_template('gallery.html', thumbnail_names=thumbnail_names)


@app.route('/thumbnails/<filename>')
def thumbnails(filename):
    return send_from_directory('thumbnails', filename)


@app.route('/images/<filename>')
def images(filename):
    return send_from_directory('images', filename)


@app.route('/public/<path:filename>')
def static_files(filename):
    return send_from_directory('./public', filename)


@app.route('/upload', methods=['GET', 'POST'])
@requires_auth
def upload():
    if request.method == 'POST':
        for upload in request.files.getlist('images'):
            filename = upload.filename
            # Always a good idea to secure a filename before storing it
            filename = secure_filename(filename)
            # This is to verify files are supported
            ext = os.path.splitext(filename)[1][1:].strip().lower()
            if ext in {'jpg', 'jpeg', 'png'}:
                print('File supported moving on...')
            else:
                return render_template('error.html', message='Uploaded files are not supported...')
            destination = '/'.join([images_directory, filename])
            # Save original image
            upload.save(destination)
            # Save a copy of the thumbnail image
            image = Image.open(destination)
            image.thumbnail((300, 170))
            image.save('/'.join([thumbnails_directory, filename]))
        return redirect(url_for('gallery'))
    return render_template('upload.html', user=session[constants.PROFILE_KEY])


@app.route('/login')
def login():
    return auth0.authorize_redirect(redirect_uri=AUTH0_CALLBACK_URL)


@app.route('/logout')
def logout():
    session.clear()
    params = {'returnTo': url_for('index', _external=True), 'client_id': AUTH0_CLIENT_ID}
    return redirect(auth0.api_base_url + '/v2/logout?' + urllib.parse.urlencode(params))


@app.route('/callback')
def callback_handling():
    auth0.authorize_access_token()
    resp = auth0.get('userinfo')
    userinfo = resp.json()

    session[constants.JWT_PAYLOAD] = userinfo
    session[constants.PROFILE_KEY] = {
        'user_id': userinfo['sub'],
        'name': userinfo['name'],
        'picture': userinfo['picture']
    }
    return redirect(url_for('upload'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=os.environ.get('PORT', 3000))
