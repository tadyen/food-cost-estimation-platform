from waitress import serve
import flaskapp
serve(flaskapp.app, host='127.0.0.1', port=8080)