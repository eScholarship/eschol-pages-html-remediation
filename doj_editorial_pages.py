"""
This script is specifically for remediation DOJ's editorial board pages.
It reads the newline-delimited IDs in page_ids.txt, and performs string
operations that remove the <small> tags, and reformats the "|" pseudo-
tables into <br/>.
"""

from pub_oapi_tools_common import eschol_db
from time import sleep

env = "prod"
database = "eschol" if env == 'prod' else 'eschol-test'
conn = eschol_db.get_connection(env=env, database=database)


def main():

    with open("page_ids.txt", 'r') as f:
        page_ids = f.read().splitlines()

    for page_id in page_ids:
        with conn.cursor() as cursor:

            query = f"select attrs->>\"$.html\" as html from pages where id = {page_id}"
            cursor.execute(query)
            page_html = cursor.fetchone()['html']

            page_html = remediate_page_html(page_html)
            print("Page remediated. Uploading.")

            query = f"""
                UPDATE pages 
                SET attrs = JSON_SET(attrs, '$.html', %(remediated_html)s)
                WHERE id = %(page_id)s;"""

            params = {"page_id": page_id,
                      "remediated_html": page_html}

            cursor.execute(query, params)
            conn.commit()
            sleep(0.5)


def remediate_page_html(html):
    html = " ".join(html.split())
    html = html.replace("<small>", "")
    html = html.replace("</small>", "")
    html = html.replace("<br>", "<br/>")
    html = html.replace("|", "<br/>")
    html = " ".join(html.split())
    html = html.replace("<br/> ", "<br/>")
    html = html.replace(" <br/>", "<br/>")
    html = html.replace("<br/><br/>", "<br/>")

    h4_split = html.split("<h4>")
    h4_split_remediated = []

    for h4_segment in h4_split:

        if "</h4>" not in h4_segment:
            h4_split_remediated.append(h4_segment)

        else:
            internal_split = h4_segment.split("</h4>")
            h4_heading = internal_split[0]

            person_list_split = internal_split[1].split("<br/>")
            person_list_li_elements = [
                f"<li>{p}</li>" for p in person_list_split if p]
            person_list_ul = f"<ul>{' '.join(person_list_li_elements)}</ul>"

            h4_remediated = f"<h4>{h4_heading}</h4>{person_list_ul}"
            h4_split_remediated.append(h4_remediated)

    remediated_html = "\n".join(h4_split_remediated)
    return remediated_html


if __name__ == "__main__":
    main()
