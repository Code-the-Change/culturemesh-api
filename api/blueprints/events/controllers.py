from flask import Blueprint, request
from api.blueprints.accounts.controllers import auth
from api.blueprints.users.utils import _add_user_to_event, get_curr_user_id
from api.apiutils import *

events = Blueprint('event', __name__)


@events.route("/ping")
def test():
    return "pong"


@events.route("/<event_id>", methods=["GET"])
def get_event(event_id):
    return get_by_id("events", event_id)


@events.route("/<event_id>/reg", methods=["GET"])
def get_event_registration(event_id):
    return get_paginated("SELECT * \
                          FROM event_registration \
                          WHERE id_event=%s",
                          selection_fields=[event_id],
                          args=request.args,
                          order_clause="ORDER BY date_registered DESC",
                          order_index_format="date_registered <= %s",
                          order_arg="max_registration_date")


@events.route("/<event_id>/reg_count", methods=["GET"])
def get_event_registration_count(event_id):
    query = "SELECT count(*) \
             as reg_count \
             from event_registration \
             where id_event=%s"
    return execute_single_tuple_query(query, (event_id,))


@events.route("/new", methods=["POST", "PUT"])
@auth.login_required
def make_new_event():
    req_obj = make_fake_request_obj(request)
    req_obj.form["id_host"] = get_curr_user_id()
    if request.method == 'POST':
        # POST
        content_fields = ['id_network', 'id_host',
                          'event_date', 'title',
                          'address_1', 'address_2',
                          'country', 'city',
                          'region', 'description']
        response = execute_post_by_table(request, content_fields, "events")
        # Unfortunately, we have to get the event id
        content = request.get_json()
        if not content:
            content = request.form
        query = "SELECT id FROM events WHERE id_host=%s AND id_" \
                "network=%s ORDER BY id DESC LIMIT 1"
        args = (content["id_host"], content["id_network"])
        item, desc = execute_get_one(query, args)
        event_id = convert_objects([item], desc)[0]["id"]
        # We also need to "register" them attending their own event.
        _add_user_to_event(content["id_host"], event_id, "host")
        return response
    else:
        # PUT
        # Check if user is authorized to update this event
        event = get_by_id("events", req_obj.form["id"], [])
        event = get_response_content_as_json(event)
        if event and "id_host" in event and event["id_host"] == \
                get_curr_user_id():
            return execute_put_by_id(req_obj, "events")
        # TODO: Should return an error if these conditions are not met


@events.route("/currentUserEventsByNetwork/<network_id>", methods=["GET"])
@auth.login_required
def user_events_for_network(network_id):
    user_id = get_curr_user_id()
    return get_paginated("SELECT * \
                         FROM event_registration INNER JOIN events ON events.id = event_registration.id_event \
                         WHERE (id_guest=%s OR id_host=%s) AND id_network=%s",
                         selection_fields=[user_id, user_id, network_id],
                         args=request.args,
                         order_clause="ORDER BY id DESC",
                         order_index_format="id <= %s",
                         order_arg="id")


@events.route("/delete", methods=["DELETE"])
@auth.login_required
def delete_event():
    # TODO: Only an event's host or creator should be able to delete it
    event_id = request.args.get('id')
    if not event_id or not event_id.isdigit():
        return make_response("Invalid Input", HTTPStatus.BAD_REQUEST)
    execute_mod('DELETE FROM event_registration WHERE id_event=%s', event_id)
    execute_mod('DELETE FROM events WHERE id=%s', event_id)
    return make_response("OK", HTTPStatus.OK)
