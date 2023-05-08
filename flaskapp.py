from flask import Flask, render_template, redirect, url_for, session, request as req

from model.psql_interface import Psql_interface
import bcrypt

import requests
import os
import sys

PGUSER = "postgres"
PGPASS_FILE = "./model/.pgpass"
DB_NAME = "food_cost_estimator"
SRC_PATH = "./src"
IMG_PATH = "static/imgs/"

here_abspath = os.path.dirname( os.path.realpath( sys.argv[0] ) )
src_path = os.path.abspath( os.path.join( here_abspath, SRC_PATH ) )
pgpass = open(os.path.join(here_abspath, PGPASS_FILE)).read().strip()
    
psql = Psql_interface(PGUSER, pgpass, DB_NAME, src_path)
app = Flask(__name__)
app.config["SECRET_KEY"] = "Some secret key lmao"

@app.route("/")
def html_home():
    username = session["username"] if "username" in session else None
    is_admin = session["is_admin"] if "is_admin" in session else False
    return render_template("home.html", username=username, is_admin=is_admin)