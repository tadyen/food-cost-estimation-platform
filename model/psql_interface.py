import subprocess
import json
import psycopg2
import re
import platform
class Psql_interface():
    """
        src_path is where the json files are contained
        src_path should be an abspath
    """
    pguser: str
    _password: str
    db_name: str
    db_template_json_fname: str
    db_seed_json_fname: str
    src_path: str 
    sh_command: str
    pghost: str
    pgport: int
    
    def __init__(self, pguser:str, pgpass:str, db_name:str,  src_path:str, pghost:str=None, pgport:int = None):
        self.pguser = pguser
        self._password = pgpass
        self.db_name = db_name
        self.src_path = src_path
        self.pghost = "localhost" if pghost is None else pghost
        self.pgport = 5432 if pgport is None else pgport
        if platform.system() == 'Windows':
            self.sh_psql_login = f'psql "postgresql://{self.pguser}:{self._password}@{self.pghost}:{self.pgport}"'
            self.sh_psql_dbconnect = f'psql "postgresql://{self.pguser}:{self._password}@{self.pghost}:{self.pgport}/{self.db_name}"'
        else:
            self.sh_psql_login = f"PGPASSWORD={self._password} psql -U {self.pguser} -h {self.pghost} -p {self.pgport}"
            self.sh_psql_dbconnect = f"PGPASSWORD={self._password} psql -U {self.pguser} -h {self.pghost} -p {self.pgport} -d {self.db_name}"
        return
    
    def set_db_template_json_fname(self, db_template_json_fname):
        self.db_template_json_fname = db_template_json_fname
        return
    
    def set_db_seed_json_fname(self, db_seed_json_fname):
        self.db_seed_json_fname = db_seed_json_fname
        return
    
    def psql_shell_query(self, sql_query: str, verbose:bool = None):
        sh_command = self.sh_psql_dbconnect
        proc = subprocess.Popen(sh_command, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = proc.communicate(input=sql_query.encode())
        stdout = stdout.decode()
        stderr = stderr.decode()
        ret = (stdout,stderr)
        if verbose != None and verbose:
            print(*ret)
        proc.terminate()
        return ret
    
    def psql_psycopg2_query(self, sql_query: str, field_values: list = None):
        if not self.check_db_exists():
            raise Exception("DB has not been created yet. Cannot populate DB that does not exist.")
        connection = psycopg2.connect(dbname=self.db_name, user=self.pguser, password=self._password)
        cursor = connection.cursor()
        if field_values != None:
            cursor.execute(sql_query, field_values)
        else:
            cursor.execute(sql_query)
        try:
            results = cursor.fetchall()
        except:
            results = None
        connection.commit()
        connection.close()
        return results

    def check_db_exists(self):
        sh_command = self.sh_psql_dbconnect
        proc = subprocess.Popen(sh_command, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        _, stderr = proc.communicate()
        err = stderr.decode()
        proc.terminate()
        if f'database "{self.db_name}" does not exist' in err:
            return False
        return True
    
    def check_table_exists(self, table_name):
        console_out = self.psql_shell_query(f"\d {table_name}")
        if f'Did not find any relation named "{table_name}".' in " ".join(console_out):
            return False
        return True
    
    def obtain_table_fields(self, table_name) -> list[str]:
        console_out = self.psql_shell_query(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{table_name}'")
        stdout = console_out[0]
        # Example output:
        #   column_name   |     data_type     
        # ----------------+-------------------
        #  id             | integer
        #  name           | character varying
        #  category       | character varying
        #  price_in_cents | integer
        #  description    | character varying
        #  image_url      | character varying
        # (6 rows)
        regex = re.compile(r'^\s*(\w+)\s*\|\s*([\w\s]+)\s*$', re.MULTILINE)
        matched = regex.findall(stdout)
        matched = matched[1:] # exclude ('column_name','data_type')
        table_fields = []
        for match in matched:
            table_fields.append(match)
        return table_fields
    
    def drop_db(self):
        if self.check_db_exists():
            sh_command = self.sh_psql_login
            proc = subprocess.Popen(sh_command, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            _, _ = proc.communicate(input=f"DROP DATABASE {self.db_name}".encode())
            proc.terminate()
        return
    
    def create_db(self):
        if not self.check_db_exists():
            sh_command = self.sh_psql_login
            proc = subprocess.Popen(sh_command, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            _, _ = proc.communicate(input=f"CREATE DATABASE {self.db_name}".encode())
            proc.terminate()
        return
    
    def setup_tables_from_json(self):
        if self.db_template_json_fname is None:
            print("JSON fname not set yet")
            return
        with open(f"{self.src_path}/{self.db_template_json_fname}") as fp:
            setup_info = json.load(fp)
        for table in setup_info["db_tables"]:
            if self.check_table_exists(table["name"]):
                print(f"Table {table['name']} already exists. Skipping setup for this table...")
                continue
            psql_command = f"CREATE TABLE {table['name']}"
            psql_command += "("
            for column, type in table["columns"].items():
                psql_command += f"{column} {type}," 
            psql_command = psql_command[:-1]    # remove last comma
            psql_command += ");"
            self.psql_psycopg2_query(psql_command)
        return
    
    def populate_table_from_json(self):
        if self.db_seed_json_fname is None:
            print("JSON fname not set yet")
            return
        with open(f"{self.src_path}/{self.db_seed_json_fname}") as fp:
            data = json.load(fp)
        table_name = data["table_name"]
        table_fields = self.obtain_table_fields(table_name)
        for entry in data['entries']:
            field_values = []
            field_names = []
            for field in table_fields:
                col_name = field[0]
                col_define = field[1] 
                if "PRIMARY KEY" in col_define:
                    continue
                try:
                    value = entry[ col_name ]
                except:
                    # entry does not have this column which may have been intentionally omitted
                    continue
                field_names.append( col_name )
                if any( substring in col_define.lower() for substring in ["text", "char"] ):
                    field_values.append( str(value) )
                elif( "int" in col_define.lower() ):
                    field_values.append( int(value) )
                elif( "bool" in col_define.lower() ):
                    field_values.append( str(value) )
                else:
                    field_values.append( value )
            placeholders_str = ", ".join([ "%s" for x in range(len(field_names)) ])
            psql_command = f"""
                INSERT INTO {table_name}({', '.join(field_names)})
                VALUES ({placeholders_str})
                ;
            """
            self.psql_psycopg2_query(psql_command, field_values)
        return
    
    def reset_db(self):
        self.drop_db()
        self.create_db()
        return
    
if __name__ == "__main__":
    pass