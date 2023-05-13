from waitress import serve
import flaskapp
serve(flaskapp.app)