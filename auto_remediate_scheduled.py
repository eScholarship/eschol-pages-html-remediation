"""
This is a pared-down version of auto_remediate, designed to be run
monthly on the pub-oapi-tools EC2.

This program finds and remediates empty HTML elements in the eScholarship pages
(specifically, pages.attrs.html).

In the "gather" step, it pulls down all the HTML, and assesses if the page needs remediation.
The existing page HTML is saved to a backup.

In the "remediate" step, it removes the empty elements and updates the database.
"""

from pub_oapi_tools_common import eschol_db, aws_lambda
import html_operations
from datetime import datetime
from time import sleep
import subprocess
import csv
import os

# Env to read the pages from
read_env = "prod"
write_env = read_env

# If true, only files will be output, no dbs updated.
test_output_only = True

# People to email with run report
email_recipients = ['devin', 'justin', 'chad']


def main():
    """
    Main function:
    - Creates output dir
    - Queries eSchol DB for pages
    - Runs remediation on pages
    - If any remediation is needed, updates the pages on eSchol DB
    """

    # Set up output directory
    runtime = (datetime.now()).isoformat()
    output_dir = f"./output/{runtime}"
    os.makedirs(output_dir)

    # Get the pages' HTML
    pages = get_pages_html()

    if not pages:
        print("No results returned from page query. Exiting.")
        exit(0)
    else:
        output_pages_csv(dict_list=pages,
                         output_dir=output_dir,
                         filename="input_pages.csv")

    # Remediation
    remediated_pages = remediate_pages(pages)
    if not remediated_pages:
        print("No pages needing remediation. Exiting.")
        exit(0)
    else:
        output_pages_csv(dict_list=remediated_pages,
                         output_dir=output_dir,
                         filename="remediated_pages.csv")

    # Update DB with remediated HTML
    if test_output_only:
        print("Running in test_output_only mode. Exiting.")
        exit(0)
    else:
        print("Updating prod DB with remediations.")
        update_db_with_remediation(remediated_pages, write_env)
        email_updates(remediated_pages, output_dir)


def get_db_conn(env):
    """
    Gets a connection to the eScholarship DB.

    :param env: Env string for connection, 'prod' or 'stg
    :return: A pymysql connection object
    """
    database = "eschol" if env == 'prod' else 'eschol-test'
    conn = eschol_db.get_connection(env=env, database=database)
    return conn


def get_pages_html(id_list: list = None):
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

    with read_conn.cursor() as cursor:
        cursor.execute(query)
        pages = cursor.fetchall()

    return pages


def remediate_pages(pages):
    """
    Loops the pages array, checking each HTML for empty elements,
    and adding remediated HTML to the page dict if necessary.

    This uses the "safe" version of the remediator, which notes
    but *does not remove* empty elements with children.


    :param pages: A list of dicts containing page info and HTML.
    :return: List of page dicts that needed remediation, including their remediated HTML.
    """
    for page in pages:
        print(f"\nRemediating: {page['unit_id']}, {page['slug']}")

        remediated_html, \
            empty_elements, \
            empty_elements_with_children\
            = html_operations.remove_empty_elements_safe(page['html'])

        if empty_elements:
            page['needs_remediation'] = True
            page['empty_element_count'] = len(empty_elements)
        else:
            page['needs_remediation'] = False
            page['empty_element_count'] = 0

        page['empty_elements_removed'] = ';'.join(empty_elements)
        page['empty_elements_with_children_not_removed'] = ';'.join(empty_elements_with_children)
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
    :param write_env: The db env to write remediated HTML. (Defaults to read env.)
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
            sleep(1)


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


def output_email_csv(dict_list, output_dir, filename):
    output_path = f"{output_dir}/{filename}"
    print(f"Outputting file to: {output_path}")

    with open(output_path, mode='w') as f:
        fieldnames = list(dict_list[0].keys())
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(dict_list)

    return output_path


def email_updates(remediated_pages, output_dir):

    # Email clients typically reject HTML in attachments
    for page in remediated_pages:
        del page['html']
        del page['remediated_html']

    report_path = output_email_csv(dict_list=remediated_pages,
                                   output_dir=output_dir,
                                   filename='remediated_pages_report.csv')

    subprocess_setup = ['mail',
                        '-s', 'eSchol pages: Empty Element remediation report',
                        '-a', report_path]

    subprocess_setup += get_email_addresses()

    email_body = b"Please see the attached CSV for the results of the monthly " \
                 b"eScholarship pages HTML empty-element remover. Please note the " \
                 b"elements in the 'with_children' column have *not* been removed." \
                 b"\n\nAdditional details, along with the before-and-after HTML " \
                 b"can be found on the EC2."

    email_footer = b"\n\nThis is an automated email sent from the pub-oapi-tools EC2. " \
                   b"Repo: https://github.com/eScholarship/eschol-pages-html-remediation" \
                   b"\n\nRemember to stay hydrated and get plenty of rest!"

    email_body += email_footer

    print("Running mail subprocess.")
    subprocess.run(subprocess_setup,
                   input=email_body,
                   capture_output=True)


def get_email_addresses():
    param_req = {
        'emails': {
            'folder': 'pub-oapi-tools/emails',
            'names': email_recipients}
    }

    email_params = aws_lambda.get_parameters(param_req=param_req)
    emails = list(email_params['emails'].values())
    return emails


if __name__ == "__main__":
    main()
