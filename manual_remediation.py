"""
This script updates a single item in the pages table, setting its
attrs.html to the HTML contained in manual_remediation_page.html
"""
from pub_oapi_tools_common import eschol_db

# REPLACE WITH PAGE ID for the HTML you're remediating
page_id = "13059"

env = "prod"
database = "eschol" if env == 'prod' else 'eschol-test'
conn = eschol_db.get_connection(env=env, database=database)

with open("manual_remediation_page.html", 'r') as f:
    remediated_html = f.read()

with conn.cursor() as cursor:

    query = f"""
        UPDATE pages 
        SET attrs = JSON_SET(attrs, '$.html', %(remediated_html)s)
        WHERE id = %(page_id)s;"""

    params = {"page_id": page_id,
              "remediated_html": remediated_html}

    cursor.execute(query, params)
    conn.commit()
