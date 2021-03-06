#
# Utility functions for the networks API.
#

from flask import Blueprint, request, abort
from http import HTTPStatus

### Helpers for the GET networks function.

def get_near_location_sql_string_start(near_location):
    """Returns the first half of the SQL query string to use
    for a GET networks call.

    :param near_location: the query string passed into the request.
    :return: (sql string format, values to include in sql string format)
    """
    near_location = near_location.split(",")
    if len(near_location) != 3:
        abort(HTTPStatus.BAD_REQUEST)

    country_id, region_id, city_id = near_location

    # Build string.
    sql_string_start = "SELECT * FROM networks "

    # If country id null?
    if country_id == "-1" or country_id.lower() == "null":
        sql_string_start += "WHERE id_country_cur is NULL "
        country_id = None
    else:
        sql_string_start += "WHERE id_country_cur=%s "

     # If region id null?
    if region_id == "-1" or region_id.lower() == "null":
        sql_string_start += "AND id_region_cur is NULL "
        region_id = None
    else:
        sql_string_start += "AND id_region_cur=%s "

     # If city id null?
    if city_id == "-1" or city_id.lower() == "null":
        sql_string_start += "AND id_city_cur is NULL "
        city_id = None
    else:
        sql_string_start += "AND id_city_cur=%s "

    ids_to_return = [
        id_ for id_ in [country_id, region_id, city_id] if id_
    ]
    return (sql_string_start, ids_to_return)

def get_from_location_sql_string_end(from_location):
    """Returns the second half of the SQL query string to use
    for a GET networks call with from_location specified.

    :param from_location: the query string passed into the request.
    :return: (sql string format, values to include in sql string format)
    """
    from_location = from_location.split(",")
    if len(from_location) != 3:
        abort(HTTPStatus.BAD_REQUEST)

    country_id, region_id, city_id = from_location

    # Build string.
    sql_string_end = ""

    # If country id null?
    if country_id == "-1" or country_id.lower() == "null":
        sql_string_end += "AND id_country_origin is NULL "
        country_id = None
    else:
        sql_string_end += "AND id_country_origin=%s "

     # If region id null?
    if region_id == "-1" or region_id.lower() == "null":
        sql_string_end += "AND id_region_origin is NULL "
        region_id = None
    else:
        sql_string_end += "AND id_region_origin=%s "

     # If city id null?
    if city_id == "-1" or city_id.lower() == "null":
        sql_string_end += "AND id_city_origin is NULL "
        city_id = None
    else:
        sql_string_end += "AND id_city_origin=%s "

    ids_to_return = [
        id_ for id_ in [country_id, region_id, city_id] if id_
    ]
    return (sql_string_end, ids_to_return)
