from flask import Flask, render_template, redirect, url_for, session, request, jsonify, abort
from enum import Enum

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

HTML_TABLE_DISPLAY_LIMIT = 10

class IngredientUnits(Enum):
    UNIT_G = "g"
    UNIT_ML = "ml"
    UNIT_unit = "unit"

# ===================================================================================
#  Flaskapp and psql Setup
# ===================================================================================

here_abspath = os.path.dirname( os.path.realpath( sys.argv[0] ) )
src_path = os.path.abspath( os.path.join( here_abspath, SRC_PATH ) )
pgpass = open(os.path.join(here_abspath, PGPASS_FILE)).read().strip()
    
psql = Psql_interface(PGUSER, pgpass, DB_NAME, src_path, pghost=DB_HOST)
app = Flask(__name__)
app.config["SECRET_KEY"] = "Some secret key lmao"

# ===================================================================================
#  Declarations
# ===================================================================================
class ApiGetQueryTable():
    """ Usage: Init class(table_name), use .set_params(<params>), then use .results()"""
    # Decision made to store/cache all query results into working memory
    # as opposed to re-querying and using TOP, OFFSET nor BETWEEN.
    # This is VERY BAD practice for large db, but I don't think this project will be THAT large
    full_query_result: list[tuple] = []
    
    # params for GET query
    table_name: str = ""
    entries_per_page: int = 0
    page_number: int = 0
    search_string: str = ""
    sort_by: str = 0
    order: str = 0
    
    # params of GET query
    total_num_of_results: int = 0
    total_num_of_pages: int = 0
    starting_entry_index: int = 0
    ending_entry_num: int = 0
    results_in_page: list[tuple] = []
    
    # others
    columns: list[str] = []         # column names of table
    configured: bool = False        # flag to make sure params have been appropriately set
    requery_needed: bool = True     # flag to say re-query of results needed
    
    def __init__(self, table_name):
        try:
            columns = psql.obtain_table_fields(table_name)
        except:
            return
        self.table_name = table_name
        self.columns = [x[0] for x in columns]
        self.configured = False     # Must perform setters first
        self.requery_needed = True  # Nothing queried yet
        return
    
    def set_params(self, entries_per_page, page_number, search_string, sort_by, order) -> bool:
        """Returns True if params set okay, otherwise returns False. Allocates flags"""
        try:
            int(entries_per_page)
            int(page_number)
            str(search_string)
            str(sort_by)
            str(order)
            order=str(order).upper()
            assert(entries_per_page >= 1)
            assert(page_number >= 1)
            assert(sort_by in [*self.columns,""])
            assert(order in ["ASC","DESC",""])
        except:
            return False
        # flags
        self.requery_needed = self.check_requery_needed(search_string, sort_by, order)
        self.configured = True
        # set values
        self.entries_per_page = entries_per_page
        self.page_number = page_number
        self.search_string = search_string
        self.sort_by = sort_by
        self.order = order
        return True
    
    def check_requery_needed(self, search_string, sort_by, order):
        """Returns True or False if re-query needed. """
        if(    (self.search_string != search_string)
            or (self.sort_by != sort_by)
            or (self.order != order)):
            # if any of the above params change, the query results change. Order matters
            # entries_per_page and page_number ignored as full_query_results are stored in memory
            return True
        else:
            return False
    
    def add_sort_stuff(self, query_string: str):
        query = query_string
        if self.sort_by != "":
            query += f" ORDER BY {self.sort_by}"
            if self.order != "":
                query += f" {self.order}"
        return query
        
    def perform_query(self):
        """Checks for requery_needed flag. If True, performs the query and stores the result in class variable"""
        if not self.configured:
            return
        if not self.requery_needed:
            return
        # Without search string
        if self.search_string == "":
            query = f"SELECT * FROM {self.table_name}"
            query = self.add_sort_stuff(query)
            query += ";"
            self.full_query_result = psql.psql_psycopg2_query(query)
            return
        
        # otherwise, With search string
        search_components = segregate_search_string(self.search_string.lower())
        exact_search_query = (f"SELECT * FROM {self.table_name}" 
            + f" WHERE LOWER(name) LIKE '%{self.search_string.lower()}%'")
        
        # if only 1 component ie 1 word:
        if len(search_components) == 1:
            query = self.add_sort_stuff(exact_search_query)
            query += ";"
            self.full_query_result = psql.psql_psycopg2_query(query)
            return
        # otherwise more bits:
        and_search_query = (f"SELECT * FROM {self.table_name} WHERE"
            + f" LOWER(name) LIKE '%{search_components[0]}%'")
        or_search_query = (f"SELECT * FROM {self.table_name} WHERE"
            + f" LOWER(name) LIKE '%{search_components[0]}%'")
        
        for component in search_components[1::]:
            and_search_query += f" AND LOWER(name) LIKE '%{component}%'"
            or_search_query += f" OR LOWER(name) LIKE '%{component}%'"
        
        # Combining them:
        query = (
            f"WITH exact_search AS ({exact_search_query}),"
            + f" and_search AS ({and_search_query}),"
            + f" or_search AS ({or_search_query}),"
            + " unordered_union AS"
                + (" (SELECT * FROM exact_search"
                + " UNION"
                + " SELECT * FROM and_search"
                + " UNION"
                + " SELECT * FROM or_search"
                + "),")
            + " and_u_or AS (SELECT * FROM unordered_union EXCEPT SELECT * FROM exact_search),"
            + " rem_or AS (SELECT * FROM and_u_or EXCEPT SELECT * FROM and_search),"
            + " rem_and AS (SELECT * FROM and_u_or EXCEPT SELECT * FROM rem_or)"
            + self.add_sort_stuff(" SELECT * FROM exact_search")
            + " UNION ALL"
            + self.add_sort_stuff(" SELECT * FROM rem_and")
            + " UNION ALL"
            + self.add_sort_stuff(" SELECT * FROM rem_or")
            + ";"
        )
        self.full_query_result = psql.psql_psycopg2_query(query)
        return
    
    def results(self):
        self.perform_query()
        # params of GET query
        self.total_num_of_results: int = len(self.full_query_result)
        self.total_num_of_pages: int = math.ceil(self.total_num_of_results / self.entries_per_page)
        self.starting_entry_index: int = (self.page_number - 1) * self.entries_per_page
        self.ending_entry_num: int = self.starting_entry_index + self.entries_per_page
        if self.ending_entry_num > self.total_num_of_results:
            self.ending_entry_num = self.total_num_of_results
        if self.starting_entry_index >= self.ending_entry_num:
            return None
        if self.page_number > self.total_num_of_pages:
            return None
        self.results_in_page = self.full_query_result[self.starting_entry_index:self.ending_entry_num]
        results = {
            # params for GET query
            "table_name": self.table_name,
            "entries_per_page": self.entries_per_page,
            "page_number": self.page_number,
            "search_string": self.search_string,
            "sort_by": self.sort_by,
            "order": self.order,
            # params of GET query
            "total_num_of_results": self.total_num_of_results,
            "total_num_of_pages": self.total_num_of_pages,
            "starting_entry_index": self.starting_entry_index,
            "ending_entry_num": self.ending_entry_num,
            "results_in_page": self.results_in_page,
        }
        return results
    
def get_user_session():        
    username = session["username"] if "username" in session else "None"
    is_admin = session["is_admin"] if "is_admin" in session else False
    is_admin = "True" if is_admin else "False"
    return (username, is_admin)

def segregate_search_string(search_string:str):
    """Converts all symbols in string to spaces then breaks it into bits"""
    # not gonna implement a sanitiser for %20 etc. Gonna just use + for now
    alphanums = "qwertyuiopasdfghjklzxcvbnm1234567890"
    sanitised = ""
    for x in search_string:
        sanitised += (x if x in alphanums else " ")
    components = sanitised.split()
    return components

def get_query_table(QueryTable: ApiGetQueryTable):
    table_name = QueryTable.table_name
    columns = psql.obtain_table_fields(table_name)
    columns = [x[0] for x in columns]
    if request.method == "GET":
        entries_per_page    = request.args.get('entries_per_page')
        page_number         = request.args.get('page_number')
        search_string       = request.args.get('search_string')
        sort_by             = request.args.get('sort_by')
        order               = request.args.get('order')
        entries_per_page    = entries_per_page  if entries_per_page     is not None else HTML_TABLE_DISPLAY_LIMIT
        page_number         = page_number       if page_number          is not None else 1
        search_string       = search_string     if search_string        is not None else ""
        sort_by             = sort_by           if sort_by              is not None else ""
        order               = order             if order                is not None else ""
    try:
        entries_per_page    = int(entries_per_page)
        page_number         = int(page_number)
        search_string       = str(search_string)
        sort_by             = str(sort_by)
        order               = str(order).upper()
        assert(entries_per_page >= 1)
        assert(page_number >= 1)
        assert(sort_by in [*columns,""])
        assert(order in ["ASC","DESC",""])
    except:
        return ({"success": False, "payload": None})
    if(QueryTable.set_params(entries_per_page, page_number, search_string, sort_by, order)):
        results_table = QueryTable.results()
    if results_table is None:
        results_table = {
            # params for GET query
            "table_name": table_name,
            "entries_per_page": entries_per_page,
            "page_number": page_number,
            "search_string": search_string,
            "sort_by": sort_by,
            "order": order,
            # params of GET query
            "total_num_of_results": 0,
            "total_num_of_pages": 0,
            "starting_entry_index": 0,
            "ending_entry_num": 0,
            "results_in_page": 0,
        }
        return ({"success": False, "payload": results_table})
    return ({"success": True, "payload": results_table})
    
def api_get_query_table(QueryTable: ApiGetQueryTable):
    results = get_query_table(QueryTable)
    if results["success"] is not True and results["payload"] is None:
        return abort(400, "Invalid GET parameters")
    return jsonify({"message": results["payload"], "status": 200, "mimetype": 'application/json', "success": True})
    
def page_get_query_table(QueryTable: ApiGetQueryTable):
    results = get_query_table(QueryTable)
    return results["payload"]
    
# ===================================================================================
#  Routes
# ===================================================================================
@app.route("/", methods=["GET","POST"])
def html_home():
    (username, is_admin) = get_user_session()
    recipe_table = page_get_query_table(RecipeTable)
    if recipe_table is None:
        return redirect("/bad_page")
    return render_template("home.html", username=username, is_admin=is_admin, recipe_table=recipe_table)

@app.route("/old_home", methods=["GET"])
def html_home_old():
    (username, is_admin) = get_user_session()
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
            return render_template("home_old.html", username=username, is_admin=is_admin, recipes=recipes, sel_recipe_id=sel_recipe_id, ingredients=ingredients)
    return render_template("home_old.html", username=username, is_admin=is_admin, recipes=recipes, sel_recipe_id=sel_recipe_id, ingredients=ingredients)

@app.route("/signin", methods=["GET","POST"])
def html_signin():
    (username, is_admin) = get_user_session()
    if username != "None":
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
    (username, is_admin) = get_user_session()
    if is_admin != "True":
        return redirect("/")
    recipe_table = page_get_query_table(RecipeTable)
    if recipe_table is None:
        return redirect("/bad_page")
    return render_template("edit_recipes.html", username=username, is_admin=is_admin, recipe_table=recipe_table)

@app.route("/craft_ingredient", methods=["GET","POST"])
def html_craft_ingredient():
    (username, is_admin) = get_user_session()
    if is_admin != "True":
        return redirect("/")
    allowed_units = list(IngredientUnits)
    allowed_units = [ x.value for x in allowed_units]
    if request.method == "GET":
        return render_template("craft_ingredient.html", username=username, is_admin=is_admin, allowed_units=allowed_units)
    if request.method == "POST":
        try:
            name = str( request.form.get("name") )
            unit = str( request.form.get("unit") )
            cost = float( request.form.get("cost") )
            assert( unit in allowed_units )
            assert( name != "" and name is not None )
            assert( cost is not None )
        except:
            return redirect(html_bad_page, username=username)
        query = f"""
            INSERT INTO ingredients(name, unit, cost_per_unit)
            VALUES(%s, %s, %s)
            ; 
        """
        psql.psql_psycopg2_query(query, [name, unit, cost])
        return render_template("craft_ingredient.html", username=username, is_admin=is_admin, allowed_units=allowed_units)
        
@app.route("/logout")
def page_logout():
    session.clear()
    return redirect("/")

@app.route("/bad_page")
def html_bad_page():
    (username, is_admin) = get_user_session()
    return render_template("bad.html", username=username)
        
@app.route("/test")
def html_test_page():
    (username, is_admin) = get_user_session()
    return render_template("test.html", username=username)

# ===================================================================================
#  GET API Routes
# ===================================================================================

RecipeTable = ApiGetQueryTable("recipes")
@app.route("/api/get_recipes_table", methods=["GET"])
def api_get_recipes_table():
    return api_get_query_table(RecipeTable)
    
IngredientsTable = ApiGetQueryTable("ingredients")
@app.route("/api/get_ingredients_table", methods=["GET"])
def api_get_ingredients_table():
    return api_get_query_table(IngredientsTable)

@app.route("/api/get_recipe_ingredients", methods=["GET"])
def api_get_recipe_ingredients():
    query = f"SELECT COUNT(*) FROM recipes;"
    total_num_of_recipes = psql.psql_psycopg2_query(query)[0][0]
    if request.method == "GET":
        recipe_id = request.args.get("recipe_id")
        recipe_id = recipe_id if recipe_id is not None else ""
    try:
        recipe_id = int(recipe_id)
        assert( recipe_id >= 0 )
        assert( recipe_id <= total_num_of_recipes)
        query = f"""SELECT name, unit, amount_of_units, cost_per_unit FROM 
        (recipe_ingredient_pairs as p INNER JOIN ingredients as i ON p.ingredient_id = i.id)
        WHERE p.recipe_id = {recipe_id}
        ;
        """
        ingredients = psql.psql_psycopg2_query(query)
    except:
        return abort(400, "Invalid GET parameters")
    return jsonify({"message":ingredients, "status":200, "mimetype":'application/json', "success":True})

if __name__ == "__main__":
    app.run(debug=True)