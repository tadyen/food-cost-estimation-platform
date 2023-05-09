from flask import Flask, render_template, redirect, url_for, session, request

from model.psql_interface import Psql_interface
import bcrypt

import math
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
    if username is not "None":
        return redirect("/")
    if request.method == "GET":
        return render_template("signin.html", username="None", invalid_user="False", is_admin="False")
    if request.method == "POST":
        user = request.form.get("username")
        users = psql.psql_psycopg2_query("SELECT username FROM users;")
        users = [tup[0] for tup in users]
        if not (user in users):
            return render_template("signin.html", username="None", invalid_user="True", is_admin="False")
        sql_query = f"SELECT password_hash FROM users WHERE username = '{user}'"
        hashed_password = psql.psql_psycopg2_query(sql_query)[0][0]
        isValidPassword = bcrypt.checkpw(request.form.get("password").encode(), hashed_password.encode())
        if not (isValidPassword):
            return render_template("signin.html", username="None", invalid_user="True", is_admin="False")
        session["username"] = user
        sql_query = f"SELECT is_admin FROM users WHERE username = '{user}'"
        session["is_admin"] = psql.psql_psycopg2_query(sql_query)[0][0]
        return redirect("/")

@app.route("/edit_recipes", methods=["GET","POST"])
def html_edit_recipes():
    username = session["username"] if "username" in session else "None"
    is_admin = session["is_admin"] if "is_admin" in session else False
    is_admin = "True" if is_admin else "False"
    if is_admin is not "True":
        return redirect("/")
    if request.method == "GET":
        table_num = request.args.get('tableNum')
    
    if table_num is not None:
        current_page=int(table_num)
    else:
        current_page=1
    query = f"SELECT COUNT(id) FROM recipes;"
    no_of_recipes = psql.psql_psycopg2_query(query)[0][0]
    query = f"SELECT * FROM recipes;"
    all_recipes = psql.psql_psycopg2_query(query)
    entries_per_table = 5
    no_of_pages = math.ceil(no_of_recipes/entries_per_table)
    starting_index = int( (current_page - 1) * entries_per_table  )
    rem_num = no_of_recipes - starting_index 
    if rem_num >= entries_per_table:
        recipes = all_recipes[ starting_index : (starting_index + entries_per_table ) ]
    else:
        recipes = all_recipes[ starting_index : rem_num ]
    if request.method == "GET":
        return render_template("edit_recipes.html", 
            username=username, is_admin=is_admin, recipes=recipes, no_of_pages=no_of_pages, starting_index=starting_index,
            current_page=current_page, entries_per_table=entries_per_table)
    if request.method == "GET":
        table_num = request.args.get('tableNum')
        return render_template("edit_recipes.html", 
            username=username, is_admin=is_admin, recipes=recipes, no_of_pages=no_of_pages, starting_index=starting_index,
            current_page=current_page, entries_per_table=entries_per_table)

@app.route("/logout")
def page_logout():
    session.clear()
    return redirect("/")

@app.route("/bad_page")
def html_bad_page():
    return render_template("bad.html", username=None)

if __name__ == "__main__":
    app.run(debug=True)