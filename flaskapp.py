from flask import Flask, render_template, redirect, url_for, session, request, jsonify, abort
from enum import Enum
from dotenv import load_dotenv

from model.psql_interface import Psql_interface

import bcrypt
import math
import os
import sys
import re

ENV_FILE = ".env"

HERE_ABSPATH = os.path.dirname( os.path.realpath( sys.argv[0] ) )

if os.path.isfile(ENV_FILE):
    load_dotenv()
    PGUSER=os.getenv('PGUSER')
    PGPASS=os.getenv('PGPASS')
    DB_HOST=os.getenv('DB_HOST')
    DB_NAME=os.getenv('DB_NAME')
    DB_PORT=os.getenv('DB_PORT')
else:
    PGUSER = "postgres"
    PGPASS_FILE = "./model/.pgpass"
    PGPASS = open(os.path.join(HERE_ABSPATH, PGPASS_FILE)).read().strip()
    DB_HOST = "localhost"
    DB_NAME = "food_cost_estimator"
    DB_PORT = 5432

print(PGUSER)
print(DB_HOST)
print(DB_NAME)
print(DB_PORT)

SRC_PATH = "./src"
IMG_PATH = "static/imgs/"

TABLE_USERS = "users"
TABLE_RECIPES = "recipes"
TABLE_INGREDIENTS = "ingredients"
TABLE_PAIRS = "recipe_ingredient_pairs"

DEFAULT_TABLE_DISPLAY_LIMIT = 5
DEFAULT_MAX_RESULTS = 999 

src_path = os.path.abspath( os.path.join( HERE_ABSPATH, SRC_PATH ) )
class IngredientUnits(Enum):
    UNIT_G = "g"
    UNIT_ML = "ml"
    UNIT_unit = "unit"

# ===================================================================================
#  Flaskapp and psql Setup
# ===================================================================================
    
psql = Psql_interface(PGUSER, PGPASS, DB_NAME, src_path, pghost=DB_HOST, pgport=DB_PORT)
app = Flask(__name__)
app.config["SECRET_KEY"] = "Some secret key lmao"

print("Sanity Psycopg2 Query")
query = f"""
    SELECT tablename, schemaname, tableowner
    FROM pg_catalog.pg_tables
    WHERE schemaname != 'pg_catalog'
    AND schemaname != 'information_schema'
    ORDER BY tablename ASC;"""
print(psql.psql_psycopg2_query(query))
print()
print("Sanity psqlshell Query")
print(psql.psql_shell_query(query))
print()
# ===================================================================================
#  Declarations - Classes
# ===================================================================================
class ApiGetQueryTable():
    """ Usage: Init class(table_name), use .set_params(<params>), then use .results()"""
    # Decision made to store/cache all query results into working memory
    # as opposed to re-querying and using TOP, OFFSET nor BETWEEN.
    # This is VERY BAD practice for large db, but I don't think this project will be THAT large
    full_query_result: list[tuple] = []
    
    # params for GET query
    table_name: str = ""
    entries_per_page: int = 0   # If set to 0, no limit
    page_number: int = 0
    search_string: str = ""
    sort_by: str = 0
    order: str = 0
    max_results: str = 0        # If set to 0, no limit
    
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
    cud_event: bool = False         # flag to say a cud event occured (create update delete)
    
    def __init__(self, table_name: str):
        try:
            columns = psql.obtain_table_fields(table_name)
        except:
            return
        self.table_name = table_name
        self.columns = [x[0] for x in columns]
        self.configured = False     # Must perform setters first
        self.requery_needed = True  # Nothing queried yet
        self.cud_event = False      # No cud event yet
        return
    
    def request_get_params(self, get_entries_per_page: bool = None, get_page_number: bool = None, 
        get_search_string: bool = None, get_sort_by: bool = None, get_order: bool = None, 
        get_max_results: bool = None):
        """GET Request Params used to query this table. Also used to test if params are valid.
        
        Usage:
            - Leave 'gets' as None to try getting values, otherwise applies defaults
            - Set 'gets' to True to enforce GET params.
            - Set 'gets' to False to force default values
            - Set 'gets' to int or str values to specify values
            - Returns None if required request not found or invalid
        """
        def _apply_gets(arg_name: str, get_arg: any, default_val: any):
            arg_val = request.args.get(arg_name)
            if get_arg is True:
                pass
            elif get_arg is False:
                arg_val = default_val
            elif get_arg is None:
                arg_val = arg_val if arg_val is not None else default_val
            elif type(get_arg) in [int,str]:
                arg_val = get_arg
            else:
                arg_val = None
            return arg_val
        entries_per_page    = _apply_gets('entries_per_page',   get_entries_per_page,   DEFAULT_TABLE_DISPLAY_LIMIT)
        page_number         = _apply_gets('page_number',        get_page_number,        1)
        search_string       = _apply_gets('search_string',      get_search_string,      "")
        sort_by             = _apply_gets('sort_by',            get_sort_by,            "")
        order               = _apply_gets('order',              get_order,              "")
        max_results         = _apply_gets('max_results',        get_max_results,        DEFAULT_MAX_RESULTS)
        try:
            entries_per_page    = int(entries_per_page)
            page_number         = int(page_number)
            search_string       = str(search_string)
            sort_by             = str(sort_by)
            order               = str(order)
            max_results         = int(max_results)
            order=str(order).upper()
            assert(entries_per_page >= 0)
            assert(page_number >= 1)
            assert(sort_by in [*self.columns,""])
            assert(order in ["ASC","DESC",""])
            assert(max_results >= 0)
        except:
            return None
        params_dict = {
            "entries_per_page"  : entries_per_page,
            "page_number"       : page_number,
            "search_string"     : search_string,
            "sort_by"           : sort_by,
            "order"             : order,
            "max_results"       : max_results,
        }        
        if(any(x is None for x in list(params_dict.values()))):
            return None
        return params_dict

    def set_params(self, params: dict) -> bool:
        """Returns True if params set okay, otherwise returns False. Allocates flags"""
        if params is None:
            return False
        if not self.request_get_params(*params.values()):
            return False
        entries_per_page   = params["entries_per_page"]
        page_number        = params["page_number"]
        search_string      = params["search_string"]
        sort_by            = params["sort_by"]
        order              = params["order"]
        max_results        = params["max_results"]
        # flags. Compare incoming against old self values. Do not update values to self yet
        self.requery_needed = self.check_requery_needed(search_string, sort_by, order, max_results)
        self.configured = True
        # set values
        self.entries_per_page   = params["entries_per_page"]
        self.page_number        = params["page_number"]
        self.search_string      = params["search_string"]
        self.sort_by            = params["sort_by"]
        self.order              = params["order"]
        self.max_results        = params["max_results"]
        return True
    
    def check_requery_needed(self, search_string: str, sort_by: str, order: str, max_results: int):
        """Returns True or False if re-query needed. """
        if(    (self.search_string != search_string)
            or (self.sort_by != sort_by)
            or (self.order != order)
            or (self.max_results != max_results)
            or (self.cud_event is True)):
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
        
    def add_limit_stuff(self, query_string: str):
        query = query_string
        if self.max_results == 0:
            query += f" LIMIT {self.max_results}"
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
        search_components = self.segregate_search_string(self.search_string.lower())
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
            + self.add_limit_stuff("")
            + ";"
        )
        self.full_query_result = psql.psql_psycopg2_query(query)
        return
    
    def results(self):
        self.perform_query()
        # params of GET query
        self.total_num_of_results: int = len(self.full_query_result)
        if self.entries_per_page == 0:
            entries_per_page = self.total_num_of_results
        else:
            entries_per_page = self.entries_per_page
            # not using self.entries_per_page to preserve the '0' setting
        if entries_per_page == 0:
            self.total_num_of_pages = 0
        else:
            self.total_num_of_pages: int = math.ceil(self.total_num_of_results / entries_per_page)
        self.starting_entry_index: int = (self.page_number - 1) * entries_per_page
        self.ending_entry_num: int = self.starting_entry_index + entries_per_page
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
            "max_results": self.max_results,
            # params of GET query
            "total_num_of_results": self.total_num_of_results,
            "total_num_of_pages": self.total_num_of_pages,
            "starting_entry_index": self.starting_entry_index,
            "ending_entry_num": self.ending_entry_num,
            "results_in_page": self.results_in_page,
        }
        return results
    
    def get_query_table(self, params):
        if(not self.set_params(params)):
            return ({"success": False, "payload": None})
        else:
            results_table = self.results()
        if results_table is None:
            # Bad query due to bad or invalid params. Respond with the same bad params in GET request
            results_table = {
                # params for GET query
                "table_name": self.table_name,
                "entries_per_page": params["entries_per_page"],
                "page_number": params["page_number"],
                "search_string": params["search_string"],
                "sort_by": params["sort_by"],
                "order": params["order"],
                "max_results" : params["max_results"],
                # params of GET query
                "total_num_of_results": 0,
                "total_num_of_pages": 0,
                "starting_entry_index": 0,
                "ending_entry_num": 0,
                "results_in_page": 0,
            }
            return ({"success": False, "payload": results_table})
        return ({"success": True, "payload": results_table})

    def set_cud_event(self):
        self.cud_event = True
        return
    
    @staticmethod
    def segregate_search_string(search_string:str):
        """Converts all symbols in string to spaces then breaks it into bits"""
        # not gonna implement a sanitiser for %20 etc. Gonna just use + for now
        alphanums = "qwertyuiopasdfghjklzxcvbnm1234567890"
        sanitised = ""
        for x in search_string:
            sanitised += (x if x in alphanums else " ")
        components = sanitised.split()
        return components
    
# ===================================================================================
#  Declarations - Methods
# ===================================================================================

def get_user_session():        
    username = session["username"] if "username" in session else "None"
    is_admin = session["is_admin"] if "is_admin" in session else False
    is_admin = "True" if is_admin else "False"
    return (username, is_admin)

def api_get_query_table(QueryTable: ApiGetQueryTable):
    params = QueryTable.request_get_params()
    results = QueryTable.get_query_table(params)
    if results["success"] is not True and results["payload"] is None:
        return jsonify(error = "Invalid Get Parameters", status = 400, success = False)
    return jsonify(results = results["payload"], status = 200, mimetype = 'application/json', success = True)

def api_get_query_table_mini(QueryTable: ApiGetQueryTable):
    """Modified version for html search bars"""
    # https://fomantic-ui.com/modules/search.html#/usage
    # Require search_string only
    params = QueryTable.request_get_params(get_entries_per_page=0, get_page_number=False, get_search_string=True,
            get_sort_by="id" ,get_order="ASC", get_max_results=False)
    results = QueryTable.get_query_table(params)
    if results["success"] is not True or results["payload"] is None:
        return jsonify(error = "Invalid Get Parameters", status = 400, success = False)
    payload = {
        "results"   : [],
        "action"    : {},
        "mimetype"  : "aplication/json",
        "status"    : 200,
        "success"   : True,
    }
    for x in results["payload"]["results_in_page"]:
        payload["results"].append({
            "title" : x["name"],
            "id" : x["id"],
        })
    return jsonify(payload)

def noapi_get_query_table(QueryTable: ApiGetQueryTable):
    params = QueryTable.request_get_params()
    results = QueryTable.get_query_table(params)
    return results["payload"]

def api_get_item_by_id(table_name:str):
    """Caution with this method, could leak users info if improperly used"""
    id = request.args.get("id")
    try:
        id = int(id)
        assert(id > 0)
    except:
        return jsonify(results = {}, status = 400, mimetype = 'application/json', success = False)
    try:
        query = f"SELECT COUNT(*) FROM {table_name};"
        total_num_of_items = psql.psql_psycopg2_query(query)[0]["count"]
        assert(id <= total_num_of_items)
    except:
        return jsonify(results = {}, status = 400, mimetype = 'application/json', success = False)
    query = f"SELECT * FROM {table_name} WHERE id={id};"
    item = psql.psql_psycopg2_query(query)
    if len(item) == 0:
        return jsonify(results = None, status = 204, mimetype = 'application/json', success = True)
    return jsonify(results = item, status = 200, mimetype = 'application/json', success = True)

def api_get_recipe_ingredients():
    recipe_id = request.args.get("recipe_id")
    try:
        recipe_id = int(recipe_id)
        assert( recipe_id > 0 )
    except:
        return jsonify(results = {}, status = 400, mimetype = 'application/json', success = False)
    try:
        query = f"SELECT COUNT(*) FROM recipes;"
        total_num_of_recipes = psql.psql_psycopg2_query(query)[0]["count"]
        assert( recipe_id <= total_num_of_recipes)
    except:
        return jsonify(results = {}, status = 400, mimetype = 'application/json', success = False)
    query = f"""SELECT i.id, i.name, i.unit, p.amount_of_units, i.cost_per_unit FROM 
    (recipe_ingredient_pairs as p INNER JOIN ingredients as i ON p.ingredient_id = i.id)
    WHERE p.recipe_id = {recipe_id}
    ;
    """
    ingredients = psql.psql_psycopg2_query(query)
    if len(ingredients) == 0:
        return jsonify(results = None, status = 204, mimetype = 'application/json', success = True)    
    return jsonify(results = ingredients, status = 200, mimetype = 'application/json', success = True)

def api_craft_ingredient():
    allowed_units = list(IngredientUnits)
    allowed_units = [ x.value for x in allowed_units]
    if request.method == "POST":
        try:
            name = str( request.form.get("name") )
            unit = str( request.form.get("unit") )
            cost = str( request.form.get("cost") )
            assert( unit in allowed_units )
            assert( name != "" and name is not None )
            assert( cost != "" and cost is not None )
            isInt = bool(re.match(r"^[1-9]\d*$", cost))
            isFloat = bool(re.match(r"^\d+\.?\d+$", cost))
            assert( isInt or isFloat )
        except:
            return abort(403, "Bad Request - Invalid POST params")
    query = f"""
        INSERT INTO ingredients(name, unit, cost_per_unit)
        VALUES(%s, %s, %s)
        ; 
    """
    psql.psql_psycopg2_query(query, [name, unit, cost])
    IngredientsTable.set_cud_event()
    return jsonify(results = {}, status = 200, mimetype = 'application/json', success = True)
# ===================================================================================
#  Routes
# ===================================================================================

@app.route("/", methods=["GET","POST"])
def html_home():
    (username, is_admin) = get_user_session()
    recipe_table = noapi_get_query_table(RecipeTable)
    if recipe_table is None:
        return redirect("/bad_page")
    return render_template("home.html", username=username, is_admin=is_admin, recipe_table=recipe_table)

@app.route("/api")
def html_api():
    (username, is_admin) = get_user_session()
    return render_template("api.html", username=username, is_admin=is_admin)

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
        hashed_password = psql.psql_psycopg2_query(sql_query)[0]["password_hash"]
        isValidPassword = bcrypt.checkpw(request.form.get("password").encode(), hashed_password.encode())
        if not (isValidPassword):
            return render_template("signin.html", username="None", invalid_user="True", is_admin="False")
        session["username"] = user
        sql_query = f"SELECT is_admin FROM users WHERE username = '{user}'"
        session["is_admin"] = psql.psql_psycopg2_query(sql_query)[0]["is_admin"]
        return redirect("/")

@app.route("/edit_recipes", methods=["GET","POST"])
def html_edit_recipes():
    (username, is_admin) = get_user_session()
    if is_admin != "True":
        return redirect("/")
    recipe_table = noapi_get_query_table(RecipeTable)
    if recipe_table is None:
        return redirect("/bad_page")
    return render_template("edit_recipes.html", username=username, is_admin=is_admin, recipe_table=recipe_table)

@app.route("/craft_ingredient", methods=["GET"])
def html_craft_ingredient():
    (username, is_admin) = get_user_session()
    if is_admin != "True":
        return redirect("/")
    if request.method != "GET":
        return abort(404, "Not Found")
    allowed_units = list(IngredientUnits)
    allowed_units = [ x.value for x in allowed_units]
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
def apipage_get_recipes_table():
    if request.method != "GET": 
        return abort(404, "Not Found")
    return api_get_query_table(RecipeTable)
    
IngredientsTable = ApiGetQueryTable("ingredients")
@app.route("/api/get_ingredients_table", methods=["GET"])
def apipage_get_ingredients_table():
    if request.method != "GET": 
        return abort(404, "Not Found")
    return api_get_query_table(IngredientsTable)

@app.route("/api/search_recipes_mini", methods=["GET"])
def apipage_search_recipes_mini():
    if request.method != "GET": 
        return abort(404, "Not Found")
    return api_get_query_table_mini(RecipeTable)

@app.route("/api/search_ingredients_mini", methods=["GET"])
def apipage_search_ingredients_mini():
    if request.method != "GET": 
        return abort(404, "Not Found")
    return api_get_query_table_mini(IngredientsTable)

@app.route("/api/get_ingredient_by_id", methods=["GET"])
def apipage_get_ingredient_by_id():
    if request.method != "GET": 
        return abort(404, "Not Found")
    return api_get_item_by_id("ingredients")

@app.route("/api/get_recipe_by_id", methods=["GET"])
def apipage_get_recipe_by_id():
    if request.method != "GET": 
        return abort(404, "Not Found")
    return api_get_item_by_id("recipes")

@app.route("/api/get_recipe_ingredients", methods=["GET"])
def apipage_get_recipe_ingredients():
    if request.method != "GET": 
        return abort(404, "Not Found")
    return api_get_recipe_ingredients()

@app.route("/api/craft_ingredient", methods=["POST"])
def apipage_craft_ingredient():
    if request.method != "POST":
        return abort(404, "Not Found")
    (username, is_admin) = get_user_session()
    if is_admin != "True":
        return abort(403, "Forbidden")
    return api_craft_ingredient()

if __name__ == "__main__":
    app.run(debug=True)