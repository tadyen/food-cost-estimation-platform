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


@app.route("/", methods=["POST","GET"])
def html_home():
    # username = session["username"] if "username" in session else None
    # is_admin = session["is_admin"] if "is_admin" in session else False
    # return render_template("home.html", username=username, is_admin=is_admin)\
    sel_recipe_id = "None"
    ingredients = "None"
    query = f"SELECT * FROM recipes;"
    recipes = psql.psql_psycopg2_query(query)
    if request.method == "GET":
        try:
            recipe_id = request.args.get("recipe_id")
            sel_recipe_id=recipe_id
            query = f"""SELECT name, unit, amount_of_units, cost_per_unit FROM 
            (recipe_ingredient_pairs as p INNER JOIN ingredients as i ON p.ingredient_id = i.id)
            WHERE p.recipe_id = {recipe_id}
            ;
            """
            ingredients = psql.psql_psycopg2_query(query)
            print(ingredients)
        except:
            return render_template("home.html", recipes=recipes, sel_recipe_id=sel_recipe_id, ingredients=ingredients)
    return render_template("home.html", recipes=recipes, sel_recipe_id=sel_recipe_id, ingredients=ingredients)

if __name__ == "__main__":
    app.run(debug=True)