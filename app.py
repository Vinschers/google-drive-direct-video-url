import os
from flask import Flask, request, Response
import requests
import json
from flask_caching import Cache


app = Flask(__name__)
app.config.from_mapping(
    {"DEBUG": True, "CACHE_TYPE": "simple", "CACHE_DEFAULT_TIMEOUT": 5400})
cache = Cache(app)


def get_stream_links(file_id, base_url):
    import urllib.parse
    import base64

    def get_resolution_dict(fmt_list):
        res = {}
        for r in fmt_list.split(','):
            parts = r.split('/')
            code = parts[0]
            resolution = parts[1].split('x')[1] + 'p'
            res[code] = resolution
        return res

    def get_access_link(link, cookie):
        link = str(base64.urlsafe_b64encode(link.encode('utf-8')), 'utf-8')
        cookie = str(base64.urlsafe_b64encode(cookie.encode('utf-8')), 'utf-8')
        return f'{base_url}/play_stream?url={link}&cookie={cookie}'

    url = 'https://drive.google.com/get_video_info?docid={}'.format(file_id)
    r = requests.get(url)

    links = r.text
    links = urllib.parse.parse_qs(links)

    cookie = r.headers['Set-Cookie']

    ret = {}

    ret['title'] = links['title'][0]
    ret['id'] = links['docid'][0]
    ret['thumbnail'] = links['iurl'][0]
    ret['length_seconds'] = links['length_seconds'][0]
    ret['links'] = {}

    fmt_list = links['fmt_list'][0]
    resolution_codes = get_resolution_dict(fmt_list)
    fmt_stream_map = links['fmt_stream_map'][0].split(',')
    for stream in fmt_stream_map:
        resolution, link = stream.split('|')
        resolution = resolution_codes[resolution]
        ret['links'][resolution] = get_access_link(link, cookie)

    return ret


@app.route('/get_direct_link/<fileID>')
def get_direct_link(fileID):
    from urllib.parse import urlparse

    resp = cache.get(fileID)
    if resp is None:
        url_parts = urlparse(request.base_url)
        url = '{}://{}'.format(url_parts.scheme, url_parts.netloc)
        resp = get_stream_links(fileID, url)
        cache.set(fileID, resp)
    return json.dumps(resp)


@app.route('/play_stream')
def play_stream():
    import base64

    url = request.args.get('url').encode('ascii')
    url = base64.urlsafe_b64decode(url).decode('ascii')

    cookie = request.args.get('cookie').encode('ascii')
    cookie = base64.urlsafe_b64decode(cookie).decode('ascii')

    headers = {}
    for key, value in request.headers.items():
        headers[key] = value
    headers['Cookie'] = cookie
    headers.pop('Host', None)
    headers.pop('Referer', None)
    headers.pop('X-Forwarded-For', None)

    r = requests.get(url, headers=headers, stream=True)
    resHeaders = {}

    for key, value in r.headers.items():
        resHeaders[key] = value

    status_code = r.status_code
    return Response(
        r.iter_content(chunk_size=10*1024), status_code, headers=resHeaders)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, threaded=True)