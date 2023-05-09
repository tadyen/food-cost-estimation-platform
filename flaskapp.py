from flask import Flask, render_template, redirect, url_for, session, request

from model.psql_interface import Psql_interface
import bcrypt

import requests
import os
import sys

PGUSER = "postgres"
PGPASS_FILE = "./model/.pgpass"
DB_HOST = "localhost"
DB_NAME = "food_cost_estimator"

SRC_PATH = "./src"
IMG_PATH = "static/imgs/"

TABLE_USERS = "users"
TABLE_RECIPES = "recipes"
TABLE_INGREDIENTS = "ingredients"
TABLE_PAIRS = "recipe_ingredient_pairs"

here_abspath = os.path.dirname( os.path.realpath( sys.argv[0] ) )
src_path = os.path.abspath( os.path.join( here_abspath, SRC_PATH ) )
pgpass = open(os.path.join(here_abspath, PGPASS_FILE)).read().strip()
    
psql = Psql_interface(PGUSER, pgpass, DB_NAME, src_path, pghost=DB_HOST)
app = Flask(__name__)
app.config["SECRET_KEY"] = "Some secret key lmao"


@app.route("/", methods=["GET"])
def html_home():
    username = session["username"] if "username" in session else "None"
    is_admin = session["is_admin"] if "is_admin" in session else False
    is_admin = "True" if is_admin else "False"
    # return render_template("home.html", username=username, is_admin=is_admin)
    query = f"SELECT * FROM recipes;"
    recipes = psql.psql_psycopg2_query(query)
    if request.method == "GET":
        sel_recipe_id = "None"
        ingredients = "None"
        try:
            recipe_id = request.args.get("recipe_id")
            int(recipe_id)
            sel_recipe_id=recipe_id
            query = f"""SELECT name, unit, amount_of_units, cost_per_unit FROM 
            (recipe_ingredient_pairs as p INNER JOIN ingredients as i ON p.ingredient_id = i.id)
            WHERE p.recipe_id = {recipe_id}
            ;
            """
            ingredients = psql.psql_psycopg2_query(query)
        except:
            return render_template("home.html", username=username, is_admin=is_admin, recipes=recipes, sel_recipe_id=sel_recipe_id, ingredients=ingredients)
    return render_template("home.html", username=username, is_admin=is_admin, recipes=recipes, sel_recipe_id=sel_recipe_id, ingredients=ingredients)

@app.route("/signin", methods=["GET","POST"])
def html_signin():
    username = session["username"] if "username" in session else "None"
    is_admin = session["is_admin"] if "is_admin" in session else False
    is_admin = "True" if is_admin else "False"
    if request.method == "GET":
        if username is not "None":
            return redirect("/")
        return render_template("signin.html", username="None", invalid_user="False", is_admin=is_admin)
    if request.method == "POST":
        user = request.form.get("username")
        users = psql.psql_psycopg2_query("SELECT username FROM users;")
        users = [tup[0] for tup in users]
        if not (user in users):
            return render_template("signin.html", username="None", invalid_user="True", is_admin=is_admin)
        sql_query = f"SELECT password_hash FROM users WHERE username = '{user}'"
        hashed_password = psql.psql_psycopg2_query(sql_query)[0][0]
        isValidPassword = bcrypt.checkpw(request.form.get("password").encode(), hashed_password.encode())
        if not (isValidPassword):
            return render_template("signin.html", username="None", invalid_user="True", is_admin=is_admin)
        session["username"] = user
        sql_query = f"SELECT is_admin FROM users WHERE username = '{user}'"
        session["is_admin"] = psql.psql_psycopg2_query(sql_query)[0][0]
        return redirect("/")

@app.route("/logout")
def page_logout():
    session.clear()
    return redirect("/")

@app.route("/bad_page")
def html_bad_page():
    return render_template("bad.html", username=None)

if __name__ == "__main__":
    app.run(debug=True)