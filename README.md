# food-cost-estimation-platform

![image_of_landing_page](/readme_stuff/landing_page.png)

This project is a platform for users (particularly chefs) to run food cost estimation.
Users can update ingredient cost and recipes for food cost estimation in preparing restaurant needs.

Currently deployed on food-cost-estimation-platform.onrender.com

<details>
  <summary>Click to expand : Project motivators</summary>
  <img src="/readme_stuff/project_desc.png"></img>
  <img src="/readme_stuff/short_discord.png"></img>
</details>

## Features

- User Authentication
- Database connected
- Online hosted
- Dynamically loaded and searchable fields
- Friendly UI (hopefully the site users actually think that)

## APIs

(Subject to change)
![image_of_apis_page](/readme_stuff/apis.png)

## Frameworks used

- Flask / Jinja2
- PostgreSQL
- JQuery
- [Fomantic UI](https://fomantic-ui.com/)

## Deployment

- [Render](https://render.com/)

## Overall Approach

This project is a milestone check for the following:

- Web Framework (Flask)
- MVC Framework
- CRUD operations
- Deployed site
- Site functionality

Most of these have been checkboxed from the project requirements itself.

#### Models (M in MVC)

I wrote a module that lets me interface with Postgres completely. Key Features:

- Class that contains the connection info and setup interfacing with the database
- Query methods that parses just the query and returns results to reduce boilerplate in psycopg2 and/or subprocesses.
- Method to check if database and/or tables already exist
- Method to drop/create said database and tables
- JSON templates for tables and seed data
- Method to setup database tables
- Method to populate tables from JSON
- Method to obtain table fields (column_name and data_type)

#### Controller (C in MVC)

In flask, I wrote a whole class for querying the data and storing parameters with the query.
This class handles the querying logic of singular tables (ie no Joins).

This was mostly for tables on the site so that if a search was done on a specific string or set of parameters, a query wouldn't need to be re-performed if only a slice of the results is desired.

I seperated my app routes into HTMLs (pages that are rendered) and into APIs (pages that return API jsons).

#### Views (V in MVC)

On the pages itself, I initially tried to work with Jinja only but ran into lots of difficulties with forms and data flow.

Eventually I re-did my approach and created APIs within the application.
These APIs were used to allow dynamics in the page.

#### Frameworks

For a CSS Framework, I went with Fomantic UI just because and I found something I needed there and it looked promising. Searchable Dropdowns was what I found in Fomantic that made me pick it over Bootstrap.

As Fomantic also requires JQuery, I conveniently started learning and using JQuery as well.

Eventually, my template htmls were mostly JQuery-JS and less native HTML/CSS + Jinja.

#### Database relation

A recipe may require multiple ingredients and amounts.
An ingredient may be used accross multiple recipes with different amounts per recipe.
To make this many-to-many relation work, a third table was needed to link these 2 together.

```json
{
    "name" : "recipes",
    "columns": 
    {
        "id" : "serial PRIMARY KEY",
        "name" : "varchar(64) NOT NULL",
        "description" : "varchar(256)",
        "tags" : "varchar(256)"
    }
},
{
    "name" : "ingredients",
    "columns": 
    {
        "id" : "serial PRIMARY KEY",
        "name" : "varchar(64) NOT NULL",
        "unit" : "varchar(64) NOT NULL",
        "cost_per_unit": "double precision NOT NULL"
    }
},
{
    "name" : "recipe_ingredient_pairs",
    "columns": 
    {
        "id" : "serial PRIMARY KEY",
        "recipe_id" : "bigint NOT NULL",
        "ingredient_id" : "bigint NOT NULL",
        "amount_of_units" : "double precision NOT NULL"
    }
}
```

#### Struggles

- Moving data between the backend and frontend normally requires forms that invoke page reloads.
  Created APIs, used JQuery AJAX to solve this
- Pasing Jinja variables to Javascript
  `var foo = {{ foo }}`
- Assigning variables in jinja and typecasting it
  `{% set foo = from_python[0] | int %}`
  `<div>{{ foo }}</div>`
- Jinja variable scope is tight.
  So, I used Namespaces: `{% set ns = namespace(foo = from_python[0], bar = from_python[1] )%}`
  `<div>{{ ns.foo }}{{ ns.bar }}</div>`
- and just lots of time and energy spent, lots of refactoring and constant bug-fixing

## Known Issues & Further work

#### It's incomplete

- Craft Recipe page not fleshed out
- Edit Ingredients page completely missing

#### Further work

![further_work_img](/readme_stuff/further_work.png)

I'm planning to deploy on Firebase + GCP and assign it a custom domain.
This will be part of my portfolio work when I finally get to making my personal site.
