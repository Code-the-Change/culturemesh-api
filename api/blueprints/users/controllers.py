from flask import Blueprint, request
from hashlib import md5
from pymysql.err import IntegrityError
from api.blueprints.accounts.controllers import auth
from api.blueprints.users.utils import *
from api.blueprints.users.utils import _add_user_to_event, _remove_user_from_event

users = Blueprint('user', __name__)

"""
Modified by Drew Gregory 04/26/18
Controller for all user endpoints. Check the Swagger spec for more information on each endpoint.
"""


@users.route("/ping")
def test():
    return "pong"


def handle_users_get(request):
    if "near_location" not in request.args:
        return make_response("No near location", HTTPStatus.METHOD_NOT_ALLOWED)
    count = int(request.args.get("count", 100))
    # Parse id's into collection
    near_ids = request.args["near_location"].split(",")
    near_loc_query = "id_country_cur=%s AND id_region_cur=%s AND id_city_cur=%s"
    if "language" in request.args:
        near_ids.extend([str(request.args["language"])])
        query = "SELECT id FROM networks WHERE " + near_loc_query + \
                " AND id_language_origin=%s"
    elif "from_location" in request.args:
        near_ids.extend(request.args["from_location"].split(","))
        query = "SELECT id FROM networks WHERE " + near_loc_query + " AND " \
                + near_loc_query.replace("cur", "origin")
    else:
        return make_response("No language/from location",
                             HTTPStatus.METHOD_NOT_ALLOWED)
    network_ids, network_des = execute_get_all(query, tuple(near_ids))

    if len(network_ids) == 0:
        return make_response(jsonify([]), HTTPStatus.OK)
    # Now we need to get all the users subscribed to these networks.
    sql_query_string = "SELECT id_user FROM network_registration " \
                       "WHERE id_network IN %s"
    sql_order_string = "ORDER BY id_user DESC"
    if "max_id" in request.args:
        sql_query_string += " AND id_user<=%s"
        args = (network_ids, request.args["max_id"])
    else:
        args = (network_ids,)
    user_ids, user_id_des = \
        execute_get_many(sql_query_string + sql_order_string, args, count)

    if len(user_ids) == 0:
        return make_response(jsonify([]), HTTPStatus.OK)
    user_query = "SELECT * FROM users WHERE id IN %s"
    user_arg = (tuple(user_ids),)
    user_items, user_descr = execute_get_all(user_query, user_arg)

    users_obj = convert_objects(user_items, user_descr)
    for user_obj in users_obj:
        user_obj.pop('password', None)
        user_obj.pop('email', None)

    return make_response(jsonify(users_obj), HTTPStatus.OK)


def validate_new_user(form, content_fields):
    """
    Validates form data for a valid new user with a unique email.
    :param form: json of request
    :param content_fields: list of required fields.
    :return: true if has necessary fields and username is unique, false otherwise
    """
    # image link is optional
    content_fields.pop(content_fields.index("img_link"))
    if not validate_request_body(form, content_fields):
        return False
    content_fields.append("img_link")
    return get_user_by_email(form['email']) is None and get_user_by_username(form['username']) is None


@users.route("/users", methods=["GET", "POST"])
def users_query():
    if request.method == 'GET':
        return handle_users_get(request)
    elif request.method == 'POST':
        content_fields = ['username', 'first_name', \
                          'last_name', 'email', \
                          'password', 'role', \
                          'img_link', 'about_me', \
                          'gender']
        # Make another pseudo request object (yeah, kinda hacksy)
        # First, we make a generic object so we can set attributes (via .form as opposed to ['form'])
        req_obj = make_fake_request_obj(request)
        # validate that username/email doesn't already exist.
        if validate_new_user(req_obj.form, content_fields):
            # We now need to convert the user password into a hash.
            password = str(req_obj.form['password'])
            req_obj.form['password'] = md5(password.encode('utf-8')).hexdigest()
            return execute_post_by_table(req_obj, content_fields, "users")
        else:
            return make_response("Username already taken or invalid params", HTTPStatus.BAD_REQUEST)


@users.route("/update_user", methods=["PUT"])
@auth.login_required
def update_user():
    req_obj = make_fake_request_obj(request)
    req_obj.form["id"] = get_curr_user_id()
    if 'password' in req_obj.form:
        # We now need to convert the user password into a hash.
        password = str(req_obj.form['password'])
        req_obj.form['password'] = md5(password.encode('utf-8')).hexdigest()
    return execute_put_by_id(request, "users")


@users.route("/<user_id>", methods=["GET"])
def get_user(user_id):
    return get_by_id("users", user_id, ["email", "password"])


@users.route("/<user_id>/networks", methods=["GET"])
def get_user_networks(user_id):
    return get_paginated("SELECT networks.*, join_date \
                          FROM network_registration \
                          INNER JOIN networks \
                          ON networks.id = network_registration.id_network \
                          WHERE network_registration.id_user=%s",
                         selection_fields=[user_id],
                         args=request.args,
                         order_clause="ORDER BY join_date DESC",
                         order_index_format="join_date <= %s",
                         order_arg="max_registration_date")


@users.route("/<user_id>/posts", methods=["GET"])
def get_user_posts(user_id):
    return get_paginated("SELECT * \
                          FROM posts \
                          WHERE id_user=%s",
                         selection_fields=[user_id],
                         args=request.args,
                         order_clause="ORDER BY id DESC",
                         order_index_format="id <= %s",
                         order_arg="max_id")


@users.route("/<user_id>/events", methods=["GET"])
def get_user_events(user_id):
    return get_paginated("SELECT events.* \
                          FROM event_registration \
                          INNER JOIN events \
                          ON events.id = event_registration.id_event \
                          WHERE event_registration.id_guest=%s AND event_registration.job=%s",
                         selection_fields=[user_id, request.args["role"]],
                         args=request.args,
                         order_clause="ORDER BY id_event DESC",
                         order_index_format="id <= %s",
                         order_arg="max_id")


@users.route("/joinEvent/<event_id>", methods=["POST"])
@auth.login_required
def add_user_to_event(event_id):
    # First, check that event and user are valid
    if not event_exists(event_id):
        return make_response("Invalid Event Id", HTTPStatus.METHOD_NOT_ALLOWED)
    user_id = get_curr_user_id()
    if "role" not in request.args or (request.args["role"] != "host" and request.args["role"] != "guest"):
        return make_response("Invalid role parameter.", HTTPStatus.METHOD_NOT_ALLOWED)
    _add_user_to_event(user_id, event_id, request.args["role"])
    return make_response("OK", HTTPStatus.OK)


@users.route("/leaveEvent/<event_id>", methods=["DELETE"])
@auth.login_required
def remove_user_from_event(event_id):
    if not event_exists(event_id):
        return make_response("Invalid Event Id", HTTPStatus.BAD_REQUEST)
    user_id = get_curr_user_id()
    _remove_user_from_event(user_id, event_id)
    return make_response("OK", HTTPStatus.OK)


@users.route("/joinNetwork/<network_id>", methods=["POST"])
@auth.login_required
def add_user_to_network(network_id):
    user_id = get_curr_user_id()
    if not network_exists(network_id):
        return make_response("Invalid Network Id",
                             HTTPStatus.METHOD_NOT_ALLOWED)
    query = "INSERT INTO network_registration VALUES " \
            "(%s, %s, CURRENT_TIMESTAMP)"
    args = (str(user_id), str(network_id))
    try:
        execute_mod(query, args)
    except IntegrityError:
        return make_response("User already subscribed",
                             HTTPStatus.METHOD_NOT_ALLOWED)
    return make_response("OK", HTTPStatus.OK)


@users.route("/leaveNetwork/<network_id>", methods=["DELETE"])
@auth.login_required
def remove_user_from_network(network_id):
    user_id = get_curr_user_id()
    query = "DELETE FROM network_registration WHERE id_user=%s AND " \
            "id_network=%s"
    args = (user_id, network_id)
    execute_mod(query, args)
    return make_response("User " + str(user_id) + " left network " +
                         str(network_id), HTTPStatus.OK)
