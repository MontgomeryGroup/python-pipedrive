from httplib2 import Http
from logging import getLogger

try:
    from urllib import urlencode
except ImportError:
    from urllib.parse import urlencode

import json

PIPEDRIVE_API_URL = "https://api.pipedrive.com/v1/"
logger = getLogger('pipedrive')


class PipedriveError(Exception):
    def __init__(self, response):
        self.response = response

    def __str__(self):
        return self.response.get('error', 'No error provided')


class IncorrectLoginError(PipedriveError):
    pass


class Pipedrive(object):
    def _request(self, endpoint, data, method='POST', debug=False):
        # avoid storing the string 'None' when a value is None
        data = {k: "" if v is None else v for k, v in data.items()}
        if method == "GET":
            uri = PIPEDRIVE_API_URL + endpoint + '?api_token=' + str(self.api_token)
            if not data:
                data = {'start':0,'end':-1}
            if data:
                uri += '&' + urlencode(data)
            tries = 3
            while True:
                tries -= 1
                response = ''
                data = ''
                try:
                    if debug:
                        logger.debug('sending {method} request to {uri}'.format(
                            method=method,
                            uri=uri
                        ))
                    response, data = self.http.request(uri, method=method,
                                                       headers={'Content-Type': 'application/x-www-form-urlencoded'})
                    break
                except Exception as e:
                    print('Exception=', e)
                    print('Response=', response, 'Data=', data)
                    if tries<0:
                        exit(5)
        else:
            uri = PIPEDRIVE_API_URL + endpoint + '?api_token=' + str(self.api_token)
            tries = 3
            while True:
                tries -= 1
                try:
                    if debug:
                        logger.debug('sending {method} request to {uri} with body={data}'.format(
                            method=method,
                            uri=uri,
                            data=json.dumps(data)
                        ))
                    response, data = self.http.request(uri, method=method, body=json.dumps(data),
                                                       headers={'Content-Type': 'application/json'})
                    break
                except Exception as e:
                    print('Exception=',e)
                    print('Response=',response,'Data=',data)
                    if tries<0:
                        exit(5)

        try:
            if debug: logger.debug('response: %s\ndata: %s', response, data)
            ret_data = json.loads(data.decode('utf-8'))
        except:
            print('Fault parsing result:Response=', response, 'Data=', data)
            ret_data = []

        if debug: logger.debug('return: %s', data.decode('utf-8'))
        return ret_data

    def __init__(self, email, password=None):
        self.http = Http(disable_ssl_certificate_validation=True)
        if password:
            response = self._request("/authorizations/", {"email": email, "password": password})

            if 'error' in response:
                raise IncorrectLoginError(response)

            # self.api_token = response['authorization'][0]['api_token']
            self.api_token = response['data'][0]['api_token']
        else:
            # Assume that login is actually the api token
            self.api_token = email

    def __getattr__(self, name):
        def wrapper(data={}, method='GET', debug=False):
            if debug: logger.debug('wrapper: data: {}'.format(data))
            if not data:
                data = {}
                data['start'] = 0
                data['end'] = -1
            if (not 'start' in data) and ('end' in data):
                data['start'] = 0
            if (not 'end' in data) and ('start' in data):
                data['end'] = -1

            ok = False
            while not ok:
                response = self._request(name.replace('_', '/'), data, method, debug=debug)
                if 'data' in response:
                    ok = True
                else:
                    if debug: logger.debug(response)

            if 'data' in response:
                if response['data'] is None:
                    if debug: logger.debug(response)
                    return None

            def _generator(start=0, end=-1):
                if 'error' in response:
                    raise PipedriveError(response)

                additional_data = response.get('additional_data')
                if additional_data is None:
                    logger.error(f"additional_data is missing in the response: {response}")
                    additional_data = {}
                pagination_info = additional_data.get('pagination', {})

                # logger.debug('pagination_info: {}'.format(pagination_info))
                if 'data' not in response:
                    if debug: print(response)
                    if 'errorCode' in response:
                        print(response)
                        raise PipedriveError(response)

                if isinstance(response['data'], dict):
                    # a single item
                    yield response['data']
                else:
                    # an array/iterrative
                    yield from response['data']

                if pagination_info.get('more_items_in_collection', False):
                    if (pagination_info['next_start'] < end) or (end==-1):
                        data.update({
                            'start': pagination_info['next_start'],
                            'end': end
                        })
                        yield from wrapper(data, method)

            if ('start' in data) and ('end' in data):
                if debug: logger.debug('_generator: data: {}'.format(data))
                return _generator(data['start'],data['end'])
            else:
                return _generator()

        return wrapper
