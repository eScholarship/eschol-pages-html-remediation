# eScholarship Pages HTML Accessibility remediation

This program was created to address Accessibility-related issues
found in eScholarship's pages.

## Requirements:
- pub_oapi_tools_common (for database connections)
- Beautiful Soup (for HTML operations)

## auto_remediate_scheduled.py:
This is a pared-down version of auto_remediate.py, that is scheduled to run monthly on the `pub-oapi-tools` EC2:
- Additional try/catch blocks added to ensure well-formed HTML.

## auto_remediate.py
This script has a few different modes of operation. Set the
following global vars:
- read_env: "prod" or "stg"
- id_list: You can specify a newline-delimited text file containing page_ids. Otherwise, the "gather" query will retrieve all the pages in the table.
- test_output_only: Set to "True" to exit the program after outputting a file with the HTML remediations.
- test_create_new_stg_pages: Set to "True" to upload the remediated HTML (regardless of origin) to 
   - A new page on staging if the page's unit_id and slug are not already present
   - Or update the existing page on staging if they are.

Presently, the only remediation performed is removing empty elements (see `html_operations.py`),
however other operations could be added.

## manual_remediation
This program does one-off updates to the `pages` table. Change the page_id value (line 8)
to the page to update, and add the remediated HTML to `manual_remediation_page.html`

## doj_editorial_pages.py
DOJ's dozen-or-so editorial board pages used a very unusual formatting, this script remediates them.