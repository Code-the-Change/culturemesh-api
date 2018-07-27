from flask import Blueprint, request, abort
from api import require_apikey
from api.apiutils import *
from pymysql.err import IntegrityError

networks = Blueprint('network', __name__)


@networks.route("/ping")
@require_apikey
def test():
    return "pong"


def make_new_network_request():
    """
    This will transform a GET /networks query to a POST /new network query by producing a "request" object with
     the necessary request.args values for a "POST networks/new" request. Yeah, sorry it's kinda hacksy.
    :return: The updated request object. Notice this is just a dictionary, since the actual request object
    is an ImmutableDict.
    """
    # this makes req an arbitrary object so I can add attributes (like form and get_json) to it.
    req = type('', (), {})()
    req.form = {}
    conn = mysql.get_db()
    near_ids = request.args['near_location'].split(',')
    index = 0
    for singular, plural in zip(['country', 'region', 'city'], ['countries', 'regions', 'cities']):
        req.form['id_' + singular + '_cur'] = near_ids[index]
        req.form[singular + '_cur'] = get_column_value(conn, 'name', 'id', plural, near_ids[index])
        index += 1
    index = 0
    if "from_location" in request.args:
        # To avoid a key error in execute_post_by_table, we need to set the other parmas to null
        req.form['id_language_origin'] = 'null'
        req.form['language_origin'] = 'null'
        from_ids = request.args['from_location'].split(',')
        for singular, plural in zip(['country', 'region', 'city'], ['countries', 'regions', 'cities']):
            req.form['id_' + singular + '_origin'] = from_ids[index]
            req.form[singular + '_origin'] = get_column_value(conn, 'name', 'id', plural, from_ids[index])
            index += 1
        if near_ids[0] != -1:
            req.form['network_class'] = 'cc'
        elif near_ids[1] != -1:
            req.form['network_class'] = 'rc'
        else:
            req.form['network_class'] = 'co'
    elif "language" in request.args:
        for singular, plural in zip(['country', 'region', 'city'], ['countries', 'regions', 'cities']):
            req.form['id_' + singular + '_origin'] = 'null'
            req.form[singular + '_origin'] = 'null'
        req.form['id_language_origin'] = get_column_value(conn, 'id', 'name', 'languages', request.args['language'])
        req.form['language_origin'] = request.args['language']
        req.form['network_class'] = '_l'
    # To avoid an error, we will make a pseudo function that returns none so that execute_post_by_table will use the
    # function dictionary instead.
    else:
        # This shouldn't happen: the route should handle the input params.
        abort(HTTPStatus.BAD_REQUEST)
        
    def get_json():
        return None
    req.get_json = get_json
    return req


def get_column_value(db_connection, desired_column, query_column, table_name, item_id):
    """
    Fetches name from DB table given id. I also use this for languages.
    :param db_connection: Database connection (use mysql.get_db())
    :param desired_column: column you want to find out
    :param query_column: column you already know that you can use to query
    :param table_name:
    :param item_id: value corresponding to query_column, -1 if supposed to be "null"
    :return: name of area.
    """
    if id == str(-1):
        return "null"
    cursor = db_connection.cursor()
    cursor.execute("SELECT " + desired_column + " FROM " + table_name + " WHERE " + query_column + "=%s", item_id)
    cursor.close()
    return cursor.fetchone()


@networks.route("/networks", methods=["GET"])
@require_apikey
def get_networks(func_counter=0):
    # Validate that we have valid input data (we need a near_location).
    if "near_location" not in request.args:
        return make_response("No near_location specified", HTTPStatus.METHOD_NOT_ALLOWED)
    near_ids = request.args["near_location"].split(",")
    # All requests will start with the same query and query for near_location.
    null_result = generate_sql_query_with_is_null(near_ids, ["id_country_cur", "id_region_cur", "id_city_cur"])
    mysql_string_start = "SELECT * FROM networks WHERE " + null_result['condition']
    near_ids = null_result['ids']
    # Need to check if querying a location or language network. That changes our queries.
    if "from_location" in request.args:
        from_null_result = generate_sql_query_with_is_null(request.args["from_location"].split(","),
                                                           ["id_country_origin", "id_region_origin", "id_city_origin"])
        from_ids = from_null_result['ids']
        near_ids.extend(from_ids)
        response_obj = get_paginated(mysql_string_start + " AND " + from_null_result['condition'],
                             selection_fields=near_ids,
                             args=request.args,
                             order_clause="ORDER BY id DESC",
                             order_index_format="id <= %s",
                             order_arg="max_id")
    elif "language" in request.args:
        near_ids.append(request.args["language"])
        response_obj = get_paginated(mysql_string_start + "AND language_origin=%s",
                             selection_fields=near_ids,
                             args=request.args,
                             order_clause="ORDER BY id DESC",
                             order_index_format="id <= %s",
                             order_arg="max_id")
    else:
        return make_response("No location/language query parameter", HTTPStatus.METHOD_NOT_ALLOWED)
    if len(response_obj.get_json()) == 0:
        # The network doesn't exist. So, let's make it!
        try:
            make_new_network(make_new_network_request())
            func_counter += 1
            if func_counter < 2:
                # We need to avoid a stack overflow error if our make_new_network messes up.
                return get_networks(func_counter)
        except (AttributeError, ValueError, IndexError, IntegrityError) as e:
            abort(HTTPStatus.BAD_REQUEST)
    else:
        # Just return the response object, since it is not empty.
        return response_obj


@networks.route("/<network_id>", methods=["GET"])
@require_apikey
def get_network(network_id):
    return get_by_id("networks", network_id)


@networks.route("/<network_id>/posts", methods=["GET"])
@require_apikey
def get_network_posts(network_id):
    return get_paginated("SELECT * \
                         FROM posts \
                         WHERE id_network=%s",
                         selection_fields=[network_id],
                         args=request.args,
                         order_clause="ORDER BY id DESC",
                         order_index_format="id <= %s",
                         order_arg="max_id")


@networks.route("/<network_id>/post_count", methods=["GET"])
@require_apikey
def get_network_post_count(network_id):
    query = "SELECT count(*) \
             as post_count \
             from posts \
             where id_network=%s"
    return execute_single_tuple_query(query, (network_id,))


@networks.route("/<network_id>/events", methods=["GET"])
@require_apikey
def get_network_events(network_id):
    return get_paginated("SELECT * \
                          FROM events \
                          WHERE id_network=%s",
                          selection_fields=[network_id],
                          args=request.args,
                          order_clause="ORDER BY id DESC",
                          order_index_format="id <= %s",
                          order_arg="max_id")


@networks.route("/<network_id>/users", methods=["GET"])
@require_apikey
def get_network_users(network_id):
    return get_paginated("SELECT users.*, join_date \
                          FROM network_registration \
                          INNER JOIN users \
                          ON users.id = network_registration.id_user \
                          WHERE id_network=%s",
                          selection_fields=[network_id],
                          args=request.args,
                          order_clause="ORDER BY join_date DESC",
                          order_index_format="join_date <= %s",
                          order_arg="max_registration_date")


@networks.route("/<network_id>/user_count", methods=["GET"])
@require_apikey
def get_network_user_count(network_id):
    query = "SELECT count(*) \
             as user_count \
             from network_registration \
             where id_network=%s"
    return execute_single_tuple_query(query, (network_id,))


@networks.route("/new", methods=["POST"])
@require_apikey
def make_new_network(internal_req=None):
    content_fields = ['city_cur', 'id_city_cur', \
                      'region_cur', 'id_region_cur', \
                      'country_cur', 'id_country_cur', \
                      'city_origin', 'id_city_origin', \
                      'region_origin', 'id_region_origin', \
                      'country_origin', 'id_country_origin', \
                      'language_origin', 'id_language_origin', \
                      'network_class']
    if internal_req is not None:
        return execute_post_by_table(internal_req, content_fields, "networks")
    return execute_post_by_table(request, content_fields, "networks")

