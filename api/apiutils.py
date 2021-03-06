from flask import jsonify, make_response
from api.extensions import mysql
from http import HTTPStatus

import hashlib
import json

"""
Contains utility routines for API controller logic. Mostly
dirty work and repeated logic.
"""

# Our buffer size for file reads is
BUF_SIZE = 2 << ((10 * 1) + 4)  # 16 KB
MAX_SIZE = 2 << ((10 * 2) + 1)  # 2 MB
ALLOWED_EXTENSIONS = {'gif', 'png', 'jpg'}


def execute_get_one(sql_q_format, args):
    """
    Get one item from the database.

    :param sql_q_format: SQL command to execute, with ``%s`` to fill ``args``
    :param args: Arguments used to replace ``%s`` in ``sql_q_format``
    :return: Tuple of the form ``(item, description)`` where ``item`` is the
    object retrieved from the database and ``description`` is the cursor
    description that names the attributes in the object.
    """
    connection = mysql.get_db()
    cursor = connection.cursor()
    cursor.execute(sql_q_format, args)
    result = cursor.fetchone()
    description = cursor.description
    cursor.close()
    return result, description


def convert_objects(tuple_arr, description):
    """
    A DB cursor returns an array of tuples, without attribute names.
    This function converts these tuples into objects
    with key-value pairs.
    :param tuple_arr:  An array of tuples
    :param description: The cursor's description, which allows you to find the attribute names.
    :return: An array of objects with attribute names according to key-value pairs"""
    obj_arr = []
    for tuple_obj in tuple_arr:
        obj_arr.append({description[index][0]: column for index, column in enumerate(tuple_obj)})
    return obj_arr


def make_response_from_single_tuple(sql_fetched, cursor_description,
                                    fields_to_omit=["password", "email"]):
    """
    Given a database cursor from which we expect only one result to be
    returned, extracts that tuple into an object and makes a response
    from it.

    If there are no results in the cursor, this method also returns
    the correct response.

    NOTE: the cursor must be closed by the caller.

    :param sql_fetched: The object returned by the SQL cursor
    :param cursor_description: The description from ``cursor.description``
    :param fields_to_omit: a list of fields to cut out.
    :return: A response object ready to return to the client
    """
    obj = sql_fetched
    if obj is not None:
        obj = convert_objects([obj], cursor_description)[0]
        for field in fields_to_omit:
            obj.pop(field, None)
    status = HTTPStatus.METHOD_NOT_ALLOWED if obj is None else HTTPStatus.OK
    return make_response(jsonify(obj), status)


def execute_single_tuple_query(sql_q_format, args):
    """
    Returns a single tuple of results from a SQL query
    format string and correpsonding arguments.

    :param sql_q_format: A complete SQL query with zero or more %s
    :param args: List of parameters to be substituted into the SQL query
    :return: A response object ready to return to the client
    """
    sql_object, description = execute_get_one(sql_q_format, args)
    response = make_response_from_single_tuple(sql_object, description)
    return response


def execute_insert(sql_q_format, args):
    """
    Executes an insert statement. This simply calls :py:func:`execute_mod` with
    the same parameters as it is provided with.

    :param sql_q_format: A complete SQL query with zero or more %s
    :param args: List of parameters to be substituted into the SQL query
    """
    execute_mod(sql_q_format, args)


def execute_mod(sql_q_format, args):
    """
    Executes a SQL statement that modifies the database without getting data.

    :param sql_q_format: A complete SQL query with zero or more %s
    :param args: List of parameters to be substituted into the SQL query
    """
    connection = mysql.get_db()
    cursor = connection.cursor()
    try:
        cursor.execute(sql_q_format, args)
    except Exception as e:
        connection.commit()
        raise e
    connection.commit()


def get_by_id(table_name, id_, cut_out_fields=[]):
    """
    Given a table name and an id to search for, queries the table
    and returns a response object ready to be returned to the client.

    :param table_name: The name of the table to query
    :param id_: The id of the object to fetch
    :param cut_out_fields: a list of fields that should be removed for privacy reasons.
    :returns: A response object ready to return to the client.
    """

    # Note table_name is never supplied by a client, so we do not
    # need to escape it.
    query = "SELECT * FROM `%s` WHERE id=%%s" % (table_name,)
    sql_object, description = execute_get_one(query, id_)
    response = make_response_from_single_tuple(sql_object, description,
                                               cut_out_fields)
    return response


def execute_put_by_id(request, table_name):
    """
    Executes a PUT command (a SQL update) on a table
    by the tuple's 'id' field.  All elements specified
    in the request JSON except id are updated.

    :param request: The request received
    :param table_name: The name of the table to update
    :returns: A response object ready to return to the client
    """
    content = request.get_json()
    if not content:
        content = request.form

    columns = content.keys()

    if "id" not in columns:
        return make_response("ID not specified", HTTPStatus.METHOD_NOT_ALLOWED)

    query = "UPDATE %s SET " % table_name
    query_clauses = []
    args = []
    for col in columns:
        if col == "id":
          continue
        query_clauses.append("%s=%%s" % col)
        args.append(content[col])
    query += ", ".join(query_clauses)
    query += " WHERE id=%s"
    args.append(content['id'])

    execute_insert(query, tuple(args))
    return make_response("OK", HTTPStatus.OK)


def execute_post_by_table(request, content_fields, table_name):
    """
    Executes a POST command to a certain table.

    This function is smart enough to detect NULLs in content fields
    to leverage default database schema values.

    :param request: The request received
    :param content_fields: A tuple containing the field/column names
                     to extract from the request and insert into
                     the table.
    :param table_name: The table to insert into
    :returns: A response object ready for the client.
    """

    content = request.get_json()
    if not content:
        content = request.form

    # Sanitize content fields.  If we 'null' or 'NULL' or '-1' for any
    # of the fields, we exclude them from the post_by_table since they will
    # automatically default to NULL.  We also only keep content fields
    # that are actually in the form.
    non_null_content_fields = []
    for content_field in content_fields:
      if content_field in content and \
                    content[content_field] and \
                    str(content[content_field]) != "-1" and \
                    str(content[content_field]).lower().strip() != 'null':
        non_null_content_fields.append(content_field)

    query = "INSERT INTO %s (%s) " % (
        table_name, ','.join(non_null_content_fields)
    )
    query += " values ("
    for _ in non_null_content_fields:
        query += "%s, "
    if query[-2] == ",":
        query = query[:-2]
    query += ");"

    args = []
    for col in non_null_content_fields:
        args.append(content[col])
    execute_insert(query, tuple(args))
    return make_response("OK", HTTPStatus.OK)


def get_paginated(sql_q_format, selection_fields, args,
                  order_clause, order_index_format, order_arg):
    """
    Utility function for getting paginated results from a
    database.

    See OneNote documentation for Pagination mechanics.

    NOTE: only works if the WHERE class of the SQL statement
          matches a single id.

    NOTE: the only thing here not provided by the user is args.

    We call get_paginated_objects.

    :param sql_q_format: A partial SQL query with zero or more %s
    :param selection_fields: A list of the values to be substituted into sql_q_format
    :param args: The query parameters (request.args)
    :param order_clause: The SQL part that dictates order on the final results
    :param order_index_format: The partial SQL query to be used for pagination
                                ordering, of the form "FIELD <= %s"
    :param order_arg: The query param on which order is based for pagination
    :returns: A response object ready to return to the client
    """
    count = int(args.get("count", 100))
    if order_arg in args:
        order_arg_val = args[order_arg]
        sql_q_format += " AND " + order_index_format
        args = (*selection_fields, order_arg_val)
    else:
        args = (*selection_fields,)
    items, descr = execute_get_many(sql_q_format + order_clause, args, count)
    if len(items) == 0:
        return make_response(jsonify([]), HTTPStatus.OK)
    items = convert_objects(items, descr)
    return make_response(jsonify(items), HTTPStatus.OK)


def execute_get_many(sql_q_format, args, count):
    """
    Get many items from the database.

    :param sql_q_format: SQL command to execute, with ``%s`` to fill ``args``
    :param args: Arguments used to replace ``%s`` in ``sql_q_format``
    :param count: The maximum number of items to return
    :return: Tuple of the form ``(items, description)`` where ``items`` is a
    tuple of objects retrieved from the database and ``description`` is the
    cursor description that names the attributes in the objects.
    """
    conn = mysql.get_db()
    cursor = conn.cursor()
    cursor.execute(sql_q_format, args)
    items = cursor.fetchmany(count)
    descr = cursor.description
    cursor.close()
    return items, descr


def execute_get_all(sql_q_format, args):
    """
    Get all available items from the database that match a query.

    :param sql_q_format: SQL command to execute, with ``%s`` to fill ``args``
    :param args: Arguments used to replace ``%s`` in ``sql_q_format``
    :return: Tuple of the form ``(items, description)`` where ``items`` is a
    tuple of objects retrieved from the database and ``description`` is the
    cursor description that names the attributes in the objects.
    """
    conn = mysql.get_db()
    cursor = conn.cursor()
    cursor.execute(sql_q_format, args)
    items = cursor.fetchall()
    descr = cursor.description
    cursor.close()
    return items, descr


def event_exists(event_id):
    """
    This function is used to validate endpoint input.
    This function checks if the passed event id is a valid event id
    (there is a corresponding event with that id.)
    :param event_id: the event id.
    :return: true if valid, false if no event found.
    """
    connection = mysql.get_db()
    event_registration_check_cursor = connection.cursor()
    event_registration_check_cursor.execute("SELECT * \
                                             FROM events \
                                             WHERE id=%s",
                                             (event_id,))
    possible_event = event_registration_check_cursor.fetchone()
    event_registration_check_cursor.close()
    return possible_event is not None


def user_exists(user_id):
    """
     This function is used to validate endpoint input.
     This function checks if the passed user id is a valid user id
    (there is a corresponding user with that id.)
    :param user_id:
    :return: true if valid, false if no user found.
    """
    connection = mysql.get_db()
    user_check = connection.cursor()
    user_check.execute("SELECT * \
                        FROM users \
                        WHERE id=%s",
                        (user_id,))
    possible_user = user_check.fetchone()
    user_check.close()
    return possible_user is not None


def network_exists(network_id):
    """
    This function is used to validate endpoint input.
    This function checks if the passed network id is a valid
    network id (there is a corresponding network with that id.)
    :param network_id:
    :return: true if valid, false if no network found.
    """
    connection = mysql.get_db()
    network_check = connection.cursor()
    network_check.execute("SELECT * \
                           FROM networks \
                           WHERE id=%s",
                           (network_id,))
    possible_network = network_check.fetchone()
    network_check.close()
    return possible_network is not None


def hash_file(file):
    """
    Generates a string hex hash (using md5) of the image file. We use a buffer to separate the file into
    memory-manageable chunks.
    This also throws TooLargeImageException if the file buffer manages to read more than 2MB of data.
    :param file: should be a python file.
    :return: string of hash in hex.
    """
    md5 = hashlib.md5()
    data = file.read(BUF_SIZE)
    file_size = BUF_SIZE
    while data:
        md5.update(data)
        data = file.read(BUF_SIZE)
        file_size += BUF_SIZE
        if file_size >= MAX_SIZE:
            raise MemoryError("file size too large")
    # Reset cursor for file write
    file.seek(0, 0)
    return md5.hexdigest()


def valid_file_type(file):
    """
    Checks if file type is either PNG, JPG, or GIF, which are our valid image formats.
    :param file: python file.
    :return: true if file is .png, .jpg, or .gif, false otherwise.
    """
    return file.filename.split(".")[-1] in ALLOWED_EXTENSIONS


def validate_request_body(json, content_fields):
    """
    Validates that this request has the required fields.
    :param json:
    :param content_fields: list of necessary dict attributes.
    :return: true if each field is contained, false otherwise.
    """
    for field in content_fields:

        if field not in json or json[field] is None:
            return False
    return True


def generate_sql_query_with_is_null(ids, column_fields):
    """
    For ease of use on client requests, NULL ids (such as those in locations) are represented as -1.
    This function generates our SQL queries based on whether each column is supposed to be null or equal some non-null id.
    :param ids: list of ids
    :param column_fields: list of column fields in corresponding order to ids.
    :return: {condition part of SQL query of format <field1=%s> AND ... AND <fieldn IS NULL> and remaining ids that aren't -1}
    """
    condition = ""
    remaining_ids = []
    for field_id, field in zip(ids, column_fields):
        if field_id == -1:
            condition += field + " IS NULL AND "

        else:
            condition += field + "=%s AND "
            remaining_ids.append(field_id)
    return {'condition': condition[:-5], 'ids': remaining_ids}  # cutoff last " AND "


def make_fake_request_obj(request):
    """
    Some of the other apiutils functions require request objects. Sometimes, we want to modify the
    request object fields, but the flask object's fields are immutable. Our workaround is to genearte
    a fake request object that has a .form dictionary.
    :param request: original request object.
    :return: fake request object
    """
    # First, we make a generic object so we can set attributes (via .form as opposed to ['form'])
    req_obj = type('', (), {})()
    req_obj.form = request.get_json()
    if not req_obj.form:
        req_obj.form = {}
    req_obj.get_json = lambda: None
    return req_obj


def get_response_content_as_json(response):
    """
    Returns the content of a Flask "Response" object
    as a JSON (dictionary).
    :param response: the Flask Response object.
    :return: JSON dictionary of response content, or None if there is an error.
    """
    if not response:
        return None
    try:
        json_dict = json.loads(response.get_data(as_text=True))
    except Exception:
        return None
    return json_dict
