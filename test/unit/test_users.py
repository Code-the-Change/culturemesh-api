from test.unit import client
import json
import mock
from hashlib import md5
import datetime
from pymysql.err import IntegrityError
from mock import call


def test_ping(client):
    response = client.get('/user/ping')
    assert response.data.decode() == 'pong'


user_def = {"username": "MyUserName3!",
            "first_name": "Human2!",
            "last_name": "Being4!",
            "email": "humanbeing@example.com",
            "password": "Password1!",
            "role": 0,
            "about_me": "",
            "gender": ""}

user_obj = user_def.copy()
user_obj['id'] = 1
user_obj['password'] = \
    md5(str(user_obj["password"]).encode('utf-8')).hexdigest()


get_user_by_des = (('id', 8, None, 20, 20, 0, False),
                   ('username', 253, None, 30, 30, 0, True),
                   ('first_name', 253, None, 30, 30, 0, True),
                   ('last_name', 253, None, 30, 30, 0, True),
                   ('email', 253, None, 50, 50, 0, False),
                   ('password', 253, None, 32, 32, 0, True),
                   ('role', 2, None, 1, 1, 0, True),
                   ('register_date', 7, None, 19, 19, 0, False),
                   ('last_login', 7, None, 19, 19, 0, False),
                   ('gender', 253, None, 1, 1, 0, True),
                   ('about_me', 253, None, 500, 500, 0, True),
                   ('events_upcoming', 2, None, 1, 1, 0, True),
                   ('events_interested_in', 2, None, 1, 1, 0, True),
                   ('company_news', 2, None, 1, 1, 0, True),
                   ('network_activity', 2, None, 1, 1, 0, True),
                   ('confirmed', 1, None, 1, 1, 0, False),
                   ('act_code', 253, None, 32, 32, 0, False),
                   ('img_link', 253, None, 50, 50, 0, True),
                   ('fp_code', 254, None, 96, 96, 0, True))
get_user_by_obj = (user_obj['id'], user_obj['username'],
                   user_obj['first_name'], user_obj['last_name'],
                   user_obj['email'],
                   user_obj['password'], 0,
                   datetime.datetime(2018, 7, 29, 10, 51, 51),
                   '0000-00-00 00:00:00', 'n', '', None, None, None,
                   None, 0, '764efa883dda1e11db47671c4a3bbd9e',
                   'https://www.culturemesh.com/user_images/null',
                   None)


@mock.patch("api.apiutils.execute_insert")
@mock.patch("api.blueprints.users.utils.execute_get_one",
            return_value=(None, get_user_by_des))
def test_create_user(get_one, execute_insert, client):
    user_def_json = json.dumps(user_def)
    response = client.post("/user/users", data=user_def_json,
                           content_type="application/json")

    by_email_query = "SELECT * FROM users WHERE email=%s"
    call_email = call(by_email_query, (user_obj['email'],))
    by_username_query = "SELECT * FROM users WHERE username=%s"
    call_username = call(by_username_query, (user_obj['username'],))

    get_one.assert_has_calls([call_email, call_username], any_order=False)

    form = 'INSERT INTO users (username,first_name,last_name,email,password)' \
           '  values (%s, %s, %s, %s, %s);'
    args = ('MyUserName3!', 'Human2!', 'Being4!', 'humanbeing@example.com',
            md5(str(user_def["password"]).encode('utf-8')).hexdigest())
    execute_insert.assert_called_with(form, args)

    assert response.status_code == 200
    assert response.data.decode() == "OK"


def mock_execute_get_one_create_user_username_taken(sql_q_format, args):
    if 'WHERE email=' in sql_q_format:
        return None, get_user_by_des
    elif 'WHERE username=' in sql_q_format:
        return get_user_by_obj, get_user_by_des
    else:
        raise ValueError('execute_get_one for username creation should include'
                         'either `WHERE email=` or `WHERE username=` in the'
                         'query.')


@mock.patch("api.apiutils.execute_insert")
@mock.patch("api.blueprints.users.utils.execute_get_one",
            side_effect=mock_execute_get_one_create_user_username_taken)
def test_create_user_username_taken_fail(get_one, execute_insert, client):
    user_def_json = json.dumps(user_def)
    response = client.post("/user/users", data=user_def_json,
                           content_type="application/json")

    get_one.assert_called_with("SELECT * FROM users WHERE username=%s",
                               (user_obj['username'],))
    execute_insert.assert_not_called()
    assert response.status_code == 400
    assert response.data.decode() == "Username already taken or invalid params"


def mock_execute_get_one_create_user_email_taken(sql_q_format, args):
    if 'WHERE email=' in sql_q_format:
        return get_user_by_obj, get_user_by_des
    elif 'WHERE username=' in sql_q_format:
        return None, get_user_by_des
    else:
        raise ValueError('execute_get_one for username creation should include'
                         'either `WHERE email=` or `WHERE username=` in the'
                         'query.')


@mock.patch("api.apiutils.execute_insert")
@mock.patch("api.blueprints.users.utils.execute_get_one",
            side_effect=mock_execute_get_one_create_user_email_taken)
def test_create_user_email_taken_fail(get_one, execute_insert, client):
    user_def_json = json.dumps(user_def)
    response = client.post("/user/users", data=user_def_json,
                           content_type="application/json")

    get_one.assert_called_with("SELECT * FROM users WHERE email=%s",
                               (user_obj['email'],))
    execute_insert.assert_not_called()
    assert response.status_code == 400
    assert response.data.decode() == "Username already taken or invalid params"


@mock.patch("api.apiutils.execute_insert")
@mock.patch("api.blueprints.users.utils.execute_get_one")
def test_create_user_bad_description_fail(get_one, execute_insert, client):
    user_def_json = json.dumps({})
    response = client.post("/user/users", data=user_def_json,
                           content_type="application/json")
    get_one.assert_not_called()
    execute_insert.assert_not_called()
    assert response.status_code == 400
    assert response.data.decode() == "Username already taken or invalid params"


description = (('id', 8, None, 20, 20, 0, False),
               ('username', 253, None, 30, 30, 0, True),
               ('first_name', 253, None, 30, 30, 0, True),
               ('last_name', 253, None, 30, 30, 0, True),
               ('email', 253, None, 50, 50, 0, False),
               ('password', 253, None, 32, 32, 0, True),
               ('role', 2, None, 1, 1, 0, True),
               ('register_date', 7, None, 19, 19, 0, False),
               ('last_login', 7, None, 19, 19, 0, False),
               ('gender', 253, None, 1, 1, 0, True),
               ('about_me', 253, None, 500, 500, 0, True),
               ('events_upcoming', 2, None, 1, 1, 0, True),
               ('events_interested_in', 2, None, 1, 1, 0, True),
               ('company_news', 2, None, 1, 1, 0, True),
               ('network_activity', 2, None, 1, 1, 0, True),
               ('confirmed', 1, None, 1, 1, 0, False),
               ('act_code', 253, None, 32, 32, 0, False),
               ('img_link', 253, None, 50, 50, 0, True),
               ('fp_code', 254, None, 96, 96, 0, True))

sql_object = (2, 'CYoum23', 'Chris', 'Youm', 'upperbrain@gmail.com',
              'b53a15ae0b7d18f359dd0f5e0fa9cc7b', 0,
              datetime.datetime(2018, 7, 30, 23, 45, 5),
              datetime.datetime(2014, 6, 1, 11, 54, 27), 'M',
              'I am from Korea and working at SF as game developer.', 1, 1,
              1, 1, 1, '97657a61f23bff2b65c63c9aacf4f032',
              '1401652610_0/pp.png', None)


@mock.patch("api.apiutils.execute_get_one",
            return_value=(sql_object, description))
def test_get_user_by_id(get_one, client):
    response = client.get("/user/2")
    query = "SELECT * FROM `users` WHERE id=%s"
    get_one.assert_called_with(query, '2')
    assert response.status_code == 200
    exp = {'about_me': 'I am from Korea and working at SF as game developer.',
           'act_code': '97657a61f23bff2b65c63c9aacf4f032', 'company_news': 1,
           'confirmed': 1, 'events_interested_in': 1, 'events_upcoming': 1,
           'first_name': 'Chris', 'fp_code': None, 'gender': 'M', 'id': 2,
           'img_link': '1401652610_0/pp.png',
           'last_login': 'Sun, 01 Jun 2014 11:54:27 GMT', 'last_name': 'Youm',
           'network_activity': 1,
           'register_date': 'Mon, 30 Jul 2018 23:45:05 GMT', 'role': 0,
           'username': 'CYoum23'}
    assert response.json == exp


get_posts_obj = ((381, 2, 1, datetime.datetime(2015, 1, 17, 12, 32, 12),
                  '[b]Picture test[/b] on [link]culturemesh.com[/link]', 'o',
                  None, None, None),)
get_posts_des = (('id', 8, None, 20, 20, 0, False),
                 ('id_user', 8, None, 20, 20, 0, True),
                 ('id_network', 8, None, 20, 20, 0, True),
                 ('post_date', 7, None, 19, 19, 0, False),
                 ('post_text', 252, None, 50331645, 50331645, 0, True),
                 ('post_class', 254, None, 3, 3, 0, False),
                 ('post_original', 8, None, 20, 20, 0, True),
                 ('vid_link', 253, None, 100, 100, 0, True),
                 ('img_link', 253, None, 100, 100, 0, True))


@mock.patch('api.apiutils.execute_get_many',
            return_value=(get_posts_obj, get_posts_des))
def test_get_posts(get_many, client):
    response = client.get('/user/2/posts')
    query = "SELECT *                           " \
            "FROM posts                           " \
            "WHERE id_user=%sORDER BY id DESC"
    get_many.assert_called_with(query, ('2',), 100)
    assert response.status_code == 200
    exp = [{'id': 381, 'id_network': 1, 'id_user': 2, 'img_link': None,
            'post_class': 'o', 'post_date': 'Sat, 17 Jan 2015 12:32:12 GMT',
            'post_original': None,
            'post_text': '[b]Picture test[/b] on [link]culturemesh.com[/link]',
            'vid_link': None}]
    assert response.json == exp


get_net_obj = ((1, 'Palo Alto', 332851, 'California', 55833,
                'United States', 47228, None, None, 'Michigan', 56020,
                'United States', 47228, None, None, 'rc',
                datetime.datetime(2016, 1, 12, 4, 51, 19), None, 'A',
                datetime.datetime(2014, 6, 1, 12, 58, 44)),)
get_net_des = (('id', 8, None, 20, 20, 0, False),
               ('city_cur', 253, None, 50, 50, 0, True),
               ('id_city_cur', 8, None, 20, 20, 0, True),
               ('region_cur', 253, None, 50, 50, 0, True),
               ('id_region_cur', 8, None, 20, 20, 0, True),
               ('country_cur', 253, None, 50, 50, 0, False),
               ('id_country_cur', 8, None, 20, 20, 0, False),
               ('city_origin', 253, None, 50, 50, 0, True),
               ('id_city_origin', 8, None, 20, 20, 0, True),
               ('region_origin', 253, None, 50, 50, 0, True),
               ('id_region_origin', 8, None, 20, 20, 0, True),
               ('country_origin', 253, None, 50, 50, 0, True),
               ('id_country_origin', 8, None, 20, 20, 0, True),
               ('language_origin', 253, None, 50, 50, 0, True),
               ('id_language_origin', 8, None, 20, 20, 0, True),
               ('network_class', 254, None, 6, 6, 0, False),
               ('date_added', 7, None, 19, 19, 0, False),
               ('img_link', 253, None, 50, 50, 0, True),
               ('twitter_query_level', 254, None, 3, 3, 0, False),
               ('join_date', 7, None, 19, 19, 0, False))


@mock.patch('api.apiutils.execute_get_many',
            return_value=(get_net_obj, get_net_des))
def test_get_networks(get_many, client):
    response = client.get('/user/2/networks')
    query = "SELECT networks.*, join_date                           " \
            "FROM network_registration                           " \
            "INNER JOIN networks                           " \
            "ON networks.id = " \
            "network_registration.id_network                           " \
            "WHERE network_registration.id_user=%sORDER BY join_date DESC"
    get_many.assert_called_with(query, ('2',), 100)
    assert response.status_code == 200
    exp = [{'city_cur': 'Palo Alto', 'city_origin': None,
            'country_cur': 'United States', 'country_origin': 'United States',
            'date_added': 'Tue, 12 Jan 2016 04:51:19 GMT', 'id': 1,
            'id_city_cur': 332851, 'id_city_origin': None,
            'id_country_cur': 47228, 'id_country_origin': 47228,
            'id_language_origin': None, 'id_region_cur': 55833,
            'id_region_origin': 56020, 'img_link': None,
            'join_date': 'Sun, 01 Jun 2014 12:58:44 GMT',
            'language_origin': None, 'network_class': 'rc',
            'region_cur': 'California', 'region_origin': 'Michigan',
            'twitter_query_level': 'A'}]
    assert response.json == exp


@mock.patch('api.blueprints.users.controllers.get_curr_user_id', return_value=1)
@mock.patch('api.blueprints.accounts.controllers.auth.authenticate',
            return_value=True)
@mock.patch('api.apiutils.execute_insert')
def test_update_user(execute_insert, auth, get_id, client):
    user_def_json = json.dumps(user_def)
    response = client.put("/user/update_user", data=user_def_json,
                          content_type="application/json")
    query = 'UPDATE users SET username=%s, first_name=%s, last_name=%s, ' \
            'email=%s, password=%s, role=%s, about_me=%s, gender=%s WHERE id=%s'
    args = (user_obj['username'], user_obj['first_name'], user_obj['last_name'],
            user_obj['email'], user_obj['password'], user_obj['role'], '', '',
            user_obj['id'])
    execute_insert.assert_called_with(query, args)
    get_id.assert_called_with()
    auth.assert_called_with(None, None)
    assert response.status_code == 200
    assert response.data.decode() == "OK"


@mock.patch('api.blueprints.users.controllers.get_curr_user_id', return_value=1)
@mock.patch('api.blueprints.accounts.controllers.auth.authenticate',
            return_value=True)
@mock.patch('api.blueprints.users.controllers.event_exists', return_value=True)
@mock.patch('api.blueprints.users.utils.execute_insert')
def test_join_event(execute_insert, event_exists, auth, get_id, client):
    response = client.post('/user/joinEvent/23',
                           query_string={'role': 'guest'})
    query = "INSERT INTO event_registration VALUES " \
            "(%s,%s,CURRENT_TIMESTAMP, %s)"
    args = (1, '23', 'guest')
    execute_insert.assert_called_with(query, args)
    event_exists.assert_called_with('23')
    get_id.assert_called_with()
    auth.assert_called_with(None, None)
    assert response.status_code == 200
    assert response.data.decode() == 'OK'


@mock.patch('api.blueprints.users.controllers.get_curr_user_id', return_value=1)
@mock.patch('api.blueprints.accounts.controllers.auth.authenticate',
            return_value=True)
@mock.patch('api.blueprints.users.controllers.event_exists', return_value=False)
@mock.patch('api.blueprints.users.utils.execute_insert')
def test_join_missing_event(execute_insert, event_exists, auth, get_id, client):
    response = client.post('/user/joinEvent/23',
                           query_string={'role': 'guest'})
    execute_insert.assert_not_called()
    event_exists.assert_called_with('23')
    get_id.assert_not_called()
    auth.assert_called_with(None, None)
    assert response.status_code == 405
    assert response.data.decode() == "Invalid Event Id"


@mock.patch('api.blueprints.users.controllers.get_curr_user_id', return_value=1)
@mock.patch('api.blueprints.accounts.controllers.auth.authenticate',
            return_value=True)
@mock.patch('api.blueprints.users.controllers.event_exists', return_value=True)
@mock.patch('api.blueprints.users.utils.execute_insert')
def test_join_event_invalid_role(execute_insert, event_exists, auth, get_id,
                                 client):
    response = client.post('/user/joinEvent/23',
                           query_string={'role': 'hi'})
    auth.assert_called_with(None, None)
    event_exists.assert_called_with('23')
    get_id.assert_called_with()
    execute_insert.assert_not_called()
    assert response.status_code == 405
    assert response.data.decode() == 'Invalid role parameter.'


@mock.patch('api.blueprints.users.controllers.get_curr_user_id', return_value=1)
@mock.patch('api.blueprints.accounts.controllers.auth.authenticate',
            return_value=True)
@mock.patch('api.blueprints.users.controllers.event_exists', return_value=True)
@mock.patch('api.blueprints.users.utils.execute_insert')
def test_join_event_missing_role(execute_insert, event_exists, auth, get_id,
                                 client):
    response = client.post('/user/joinEvent/23')
    auth.assert_called_with(None, None)
    event_exists.assert_called_with('23')
    get_id.assert_called_with()
    execute_insert.assert_not_called()
    assert response.status_code == 405
    assert response.data.decode() == 'Invalid role parameter.'


@mock.patch('api.blueprints.users.controllers.get_curr_user_id', return_value=1)
@mock.patch('api.blueprints.accounts.controllers.auth.authenticate',
            return_value=True)
@mock.patch('api.blueprints.users.controllers.event_exists', return_value=True)
@mock.patch('api.blueprints.users.utils.execute_mod')
def test_leave_event(execute_mod, event_exists, auth, get_id, client):
    response = client.delete('/user/leaveEvent/23')
    query = "DELETE FROM event_registration WHERE id_event=%s AND id_guest=%s"
    args = ('23', 1)
    execute_mod.assert_called_with(query, args)
    event_exists.assert_called_with('23')
    get_id.assert_called_with()
    auth.assert_called_with(None, None)
    assert response.status_code == 200
    assert response.data.decode() == 'OK'


@mock.patch('api.blueprints.users.controllers.get_curr_user_id', return_value=1)
@mock.patch('api.blueprints.accounts.controllers.auth.authenticate',
            return_value=True)
@mock.patch('api.blueprints.users.controllers.event_exists', return_value=False)
@mock.patch('api.blueprints.users.utils.execute_mod')
def test_leave_missing_event(execute_mod, event_exists, auth, get_id, client):
    response = client.delete('/user/leaveEvent/23')
    execute_mod.assert_not_called()
    event_exists.assert_called_with('23')
    get_id.assert_not_called()
    auth.assert_called_with(None, None)
    assert response.status_code == 400
    assert response.data.decode() == 'Invalid Event Id'


@mock.patch('api.blueprints.users.controllers.get_curr_user_id', return_value=1)
@mock.patch('api.blueprints.accounts.controllers.auth.authenticate',
            return_value=True)
@mock.patch('api.blueprints.users.controllers.network_exists',
            return_value=True)
@mock.patch('api.blueprints.users.controllers.execute_mod')
def test_join_network(execute_mod, net_exists, auth, get_id, client):
    response = client.post('/user/joinNetwork/2')
    auth.assert_called_with(None, None)
    get_id.assert_called_with()
    net_exists.assert_called_with('2')
    query = "INSERT INTO network_registration VALUES " \
            "(%s, %s, CURRENT_TIMESTAMP)"
    args = ('1', '2')
    execute_mod.assert_called_with(query, args)
    assert response.status_code == 200
    assert response.data.decode() == 'OK'


@mock.patch('api.blueprints.users.controllers.get_curr_user_id', return_value=1)
@mock.patch('api.blueprints.accounts.controllers.auth.authenticate',
            return_value=True)
@mock.patch('api.blueprints.users.controllers.network_exists',
            return_value=False)
@mock.patch('api.blueprints.users.controllers.execute_mod')
def test_join_missing_network(execute_mod, net_exists, auth, get_id, client):
    response = client.post('/user/joinNetwork/2')
    auth.assert_called_with(None, None)
    get_id.assert_called_with()
    net_exists.assert_called_with('2')
    execute_mod.assert_not_called()
    assert response.status_code == 405
    assert response.data.decode() == 'Invalid Network Id'


@mock.patch('api.blueprints.users.controllers.get_curr_user_id', return_value=1)
@mock.patch('api.blueprints.accounts.controllers.auth.authenticate',
            return_value=True)
@mock.patch('api.blueprints.users.controllers.network_exists',
            return_value=True)
@mock.patch('api.blueprints.users.controllers.execute_mod',
            side_effect=IntegrityError)
def test_join_subscribed_network(execute_mod, net_exists, auth, get_id, client):
    response = client.post('/user/joinNetwork/2')
    auth.assert_called_with(None, None)
    get_id.assert_called_with()
    net_exists.assert_called_with('2')
    query = "INSERT INTO network_registration VALUES " \
            "(%s, %s, CURRENT_TIMESTAMP)"
    args = ('1', '2')
    execute_mod.assert_called_with(query, args)
    assert response.status_code == 405
    assert response.data.decode() == 'User already subscribed'


@mock.patch('api.blueprints.users.controllers.get_curr_user_id', return_value=1)
@mock.patch('api.blueprints.accounts.controllers.auth.authenticate',
            return_value=True)
@mock.patch('api.blueprints.users.controllers.execute_mod')
def test_leave_network(execute_mod, auth, get_id, client):
    response = client.delete('/user/leaveNetwork/2')
    auth.assert_called_with(None, None)
    get_id.assert_called_with()
    query = "DELETE FROM network_registration WHERE id_user=%s AND " \
            "id_network=%s"
    args = (1, '2')
    execute_mod.assert_called_with(query, args)
    assert response.status_code == 200
    assert response.data.decode() == 'User 1 left network 2'


# execute_get_all
get_net_users_net_obj = ((3161,),)
get_net_users_net_des = (('id', 8, None, 20, 20, 0, False),)

# execute_get_many
get_net_users_reg_obj = ((178,),)
get_net_users_reg_des = (('id_user', 8, None, 20, 20, 0, False),)

# execute_get_all
get_net_users_usr_obj = ((178, 'sbdbb', 'dndn', 'dbdn', 'snsj',
                          '098f6bcd4621d373cade4e832627b4f6', None,
                          datetime.datetime(2018, 8, 21, 23, 36, 5),
                          '0000-00-00 00:00:00', None, None, None, None, None,
                          None, 0, '', None, None),)
get_net_users_usr_des = (('id', 8, None, 20, 20, 0, False),
                         ('username', 253, None, 30, 30, 0, True),
                         ('first_name', 253, None, 30, 30, 0, True),
                         ('last_name', 253, None, 30, 30, 0, True),
                         ('email', 253, None, 50, 50, 0, False),
                         ('password', 253, None, 32, 32, 0, True),
                         ('role', 2, None, 1, 1, 0, True),
                         ('register_date', 7, None, 19, 19, 0, False),
                         ('last_login', 7, None, 19, 19, 0, False),
                         ('gender', 253, None, 1, 1, 0, True),
                         ('about_me', 253, None, 500, 500, 0, True),
                         ('events_upcoming', 2, None, 1, 1, 0, True),
                         ('events_interested_in', 2, None, 1, 1, 0, True),
                         ('company_news', 2, None, 1, 1, 0, True),
                         ('network_activity', 2, None, 1, 1, 0, True),
                         ('confirmed', 1, None, 1, 1, 0, False),
                         ('act_code', 253, None, 32, 32, 0, False),
                         ('img_link', 253, None, 50, 50, 0, True),
                         ('fp_code', 254, None, 96, 96, 0, True))


def mock_get_all_get_net_users(sql_q_format, args):
    if 'FROM networks' in sql_q_format:
        return get_net_users_net_obj, get_net_users_net_des
    elif 'FROM users' in sql_q_format:
        return get_net_users_usr_obj, get_net_users_usr_des
    else:
        raise ValueError('sql_q_format should specify either from the networks'
                         'or from the users table.')


@mock.patch('api.blueprints.users.controllers.execute_get_many',
            return_value=(get_net_users_reg_obj, get_net_users_reg_des))
@mock.patch('api.blueprints.users.controllers.execute_get_all',
            side_effect=mock_get_all_get_net_users)
def test_get_net_users(get_all, get_many, client):
    city_cur = 327181
    region_cur = 56130
    country_cur = 47228
    near_loc = str(country_cur) + ',' + str(region_cur) + ',' + str(city_cur)

    city_origin = 332851
    region_origin = 55833
    country_origin = 47228
    from_loc = str(country_origin) + ',' + str(region_origin) + ',' + \
               str(city_origin)

    response = client.get('/user/users',
                          query_string={'near_location': near_loc,
                                        'from_location': from_loc})

    net_query = 'SELECT id FROM networks WHERE id_country_cur=%s AND ' \
                'id_region_cur=%s AND id_city_cur=%s AND ' \
                'id_country_origin=%s AND id_region_origin=%s AND ' \
                'id_city_origin=%s'
    net_args = ('47228', '56130', '327181', '47228', '55833', '332851')
    net_call = call(net_query, net_args)

    reg_query = 'SELECT id_user FROM network_registration WHERE ' \
                'id_network IN %sORDER BY id_user DESC'
    reg_args = (((3161,),),)
    reg_count = 100
    get_many.assert_called_with(reg_query, reg_args, reg_count)

    usr_query = 'SELECT * FROM users WHERE id IN %s'
    usr_args = (((178,),),)
    usr_call = call(usr_query, usr_args)

    get_all.assert_has_calls([net_call, usr_call], any_order=False)

    assert response.status_code == 200
    exp = [{'about_me': None, 'act_code': '', 'company_news': None,
            'confirmed': 0, 'events_interested_in': None,
            'events_upcoming': None, 'first_name': 'dndn', 'fp_code': None,
            'gender': None, 'id': 178, 'img_link': None,
            'last_login': '0000-00-00 00:00:00', 'last_name': 'dbdn',
            'network_activity': None,
            'register_date': 'Tue, 21 Aug 2018 23:36:05 GMT', 'role': None,
            'username': 'sbdbb'}]
    assert response.json == exp
