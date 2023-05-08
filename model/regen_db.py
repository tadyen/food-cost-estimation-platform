from psql_interface import Psql_interface
import os
import sys 

PGUSER = "postgres"
PGPASS_FILE = ".pgpass"
DB_NAME = "food_cost_estimator"
TEMPLATE_JSON = "db_tables_template.json"
INGREDIENTS_JSON = "ingredients_eg_data.json"
RECIPES_JSON = "recipes_eg_data.json"
RECIPE_INGREDIENT_PAIR_JSON = "recipe_ingredient_pair_eg_data.json"
USERS_JSON = "eg_admin_account.json"
SRC_PATH = "../src"

if __name__ == "__main__":
    here_abspath = os.path.dirname( os.path.realpath( sys.argv[0] ) )
    src_path = os.path.abspath( os.path.join( here_abspath, SRC_PATH ) )
    pgpass = open(os.path.join(here_abspath, PGPASS_FILE)).read().strip()
    psql = Psql_interface(PGUSER, pgpass, DB_NAME, src_path)
    psql.reset_db()
    
    psql.set_db_template_json_fname(TEMPLATE_JSON)
    psql.setup_tables_from_json()
    
    psql.set_db_seed_json_fname(RECIPES_JSON)
    psql.populate_table_from_json()
    
    psql.set_db_seed_json_fname(INGREDIENTS_JSON)
    psql.populate_table_from_json()
    
    psql.set_db_seed_json_fname(RECIPE_INGREDIENT_PAIR_JSON)
    psql.populate_table_from_json()
    
    psql.set_db_seed_json_fname(USERS_JSON)
    psql.populate_table_from_json()