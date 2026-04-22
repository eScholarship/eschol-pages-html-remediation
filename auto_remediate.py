"""
This program finds and remediates empty HTML elements in the eScholarship pages
(specifically, pages.attrs.html).

In the "gather" step, it pulls down all the HTML, and assesses if the page needs remediation.
The existing page HTML is saved to a backup.

In the "remediate" step, it removes the empty elements and updates the database.
"""

from pub_oapi_tools_common import eschol_db
import html_operations
from bs4 import BeautifulSoup
from datetime import datetime
from time import sleep
import csv
import os

# Env to read the pages from
read_env = "prod"

# If supplied, reads a newline-delimited file of IDs
id_list = None

# If true, only files will be output, no dbs updated.
test_output_only = True

# If true, new pages will be created on staging for spot-checking.
test_create_new_stg_pages = False


def get_db_conn(env):
    database = "eschol" if env == 'prod' else 'eschol-test'
    conn = eschol_db.get_connection(env=env, database=database)
    return conn


def gather_page_html(id_list: list = None):
    """
    Queries the eSchol database table 'pages' for HTML.

    :param id_list: If a newline-delimited list of slugs is
        specified in args, only pages from the list will be gotten.
    :return: A list of dicts containing page IDs, slugs, and HTML.
    """
    read_conn = get_db_conn(read_env)

    if read_env == 'prod':
        eschol_url = 'https://escholarship.org'
    else:
        eschol_url = 'https://pub-jschol2-stg.escholarship.org'

    query = f"""
        select
            id, unit_id, title, slug,
            case when unit_id = 'root'
                then concat('{eschol_url}/', slug)
            else 
                concat('{eschol_url}/uc/', unit_id, '/', slug)
            end as page_url,
            attrs ->> "$.html" as html
        from pages"""

    if id_list:
        with open(id_list, 'r') as f:
            page_ids = f.read().splitlines()
        joined_page_ids = ','.join(page_ids)
        query += f' where id in ({joined_page_ids})'

    with read_conn.cursor() as cursor:
        cursor.execute(query)
        pages = cursor.fetchall()

    return pages


def remediate_pages(pages):
    for page in pages:
        print(f"\nRemediating: {page['unit_id']}, {page['slug']}")
        remediated_html, empty_elements = html_operations.remove_empty_elements(page['html'])

        if empty_elements:
            page['needs_remediation'] = True
            page['empty_element_count'] = len(empty_elements)
        else:
            page['needs_remediation'] = False
            page['empty_element_count'] = 0

        page['empty_elements'] = ';'.join(empty_elements)
        page['remediated_html'] = remediated_html

    # Removes any pages that don't need remediation
    pages_needing_remediation = [p for p in pages if p['needs_remediation']]

    # Remove newlines for compactness
    pages_needing_remediation = html_operations.remove_newlines(pages_needing_remediation)

    return pages_needing_remediation


def update_db_with_remediation(pages, write_env):
    """
    Updates the eScholDB's pages table colum w/ remediated HTML
    :param pages: A list of dicts containing the slugs and remediated HTML
    """

    write_conn = get_db_conn(env=write_env)
    with write_conn.cursor() as cursor:
        for page in pages:
            print(f"Updating: {page['id']}")

            query = f"""
                UPDATE pages 
                SET attrs = JSON_SET(attrs, '$.html', %(remediated_html)s)
                WHERE id = %(id)s;"""

            cursor.execute(query, page)
            write_conn.commit()
            sleep(0.5)


def create_new_stg_pages(pages, write_env):
    """
    Creates new pages on staging with the remediated HTML.
    :param pages: A list of dictionaries with remediated HTMLs
    :param write_env: The environment to write to (should always be write_env)
    """

    write_conn = get_db_conn(env=write_env)
    with write_conn.cursor() as cursor:
        for page in pages:

            # Modify slug and title to note remediation
            page['slug'] = f"{page['slug']}_rem"
            page['title'] = f"{page['title']} PROD REM. FOR MANUAL REVIEW"
            page['staging_link'] = (f"https://pub-jschol2-stg.escholarship.org/uc/"
                                    f"{page['unit_id']}/{page['slug']}")

            # Check to see if the rem page already exists
            find_rem_page_query = (f"SELECT id FROM pages WHERE " 
                                   f"slug = %(slug)s AND unit_id = %(unit_id)s")
            write_conn.execute(find_rem_page_query, page)
            existing_page = (cursor.getchone())['id']

            if existing_page:
                print(f"UPDATING reem page on stg: {page['staging_link']}")

                query = f"""
                    UPDATE pages 
                    SET attrs = JSON_SET(attrs, '$.html', %(remediated_html)s)
                    WHERE id = {existing_page};"""

            else:
                print(f"INSERTING new page on stg: {page['staging_link']}")

                query = """
                    INSERT INTO pages (unit_id, name, title, slug, attrs)
                    VALUES (
                        %(unit_id)s, %(title)s, %(title)s, %(slug)s,
                        JSON_OBJECT('html', %(remediated_html)s)
                    );"""

            cursor.execute(query, page)
            write_conn.commit()
            sleep(0.5)

    return pages


def output_pages_csv(dict_list, output_dir, filename):
    output_path = f"{output_dir}/{filename}"
    print(f"Outputting file to: {output_path}")

    with open(output_path, mode='w', encoding='utf-8') as f:
        fieldnames = list(dict_list[0].keys())
        writer = csv.DictWriter(f,
                                fieldnames=fieldnames,
                                escapechar='\\',
                                delimiter='\t',
                                quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(dict_list)


if __name__ == "__main__":

    # Setting up output directory
    runtime = (datetime.now()).isoformat()
    output_dir = f"./output/{runtime}"
    os.makedirs(output_dir)

    # Gathering
    pages = gather_page_html()

    if not pages:
        print("No results returned from page query. Exiting")
        exit(0)
    else:
        output_pages_csv(dict_list=pages,
                         output_dir=output_dir,
                         filename="input_pages.csv")

    # Remediation
    remediated_pages = remediate_pages(pages)
    if not remediated_pages:
        print("No pages needing remediation. Exiting")
        exit(0)
    else:
        output_pages_csv(dict_list=remediated_pages,
                         output_dir=output_dir,
                         filename="remediated_pages.csv")

    # Update DB with remediations
    if test_output_only:
        print("Running in test_output_only mode. Exiting.")
        exit(0)
    else:
        if test_create_new_stg_pages:
            print("Uploading remediations to new/existing stg pages.")
            staging_test_pages = create_new_stg_pages(remediated_pages, "stg")
            output_pages_csv(dict_list=staging_test_pages,
                             output_dir=output_dir,
                             filename="remediated_pages_staging_uploads.csv")
        else:
            print("Updating prod DB with remediations.")
            update_db_with_remediation(remediated_pages, read_env)
