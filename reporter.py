from datetime import datetime, timedelta
import re
from typing import Optional
import requests
import base64
import json
import sys
import os
import os.path
from dataclasses import dataclass, field, asdict
from enum import StrEnum
import webbrowser
import argparse
from guessit import guessit


ANILIST_BASE_URL = 'https://graphql.anilist.co'
CLIENT_ID = '25356'
SCRIPT_DIR = os.getenv('SCRIPT_DIR') or '.'
REPORT_PROGRESS_MUTATION = '''
mutation SaveMediaListEntry($progress: Int, $mediaId: Int) {
  SaveMediaListEntry(progress: $progress, mediaId: $mediaId) {
    progress
  }
}
'''
ANIME_SEARCH_QUERY = '''
query ($searchStr: String) {
  Page {
    media(search: $searchStr, type: ANIME) {
      id
      title {
        english
        romaji
      }
    }
  }
}
'''


class Status(StrEnum):
    OK = 'ok'
    ERROR = 'error'
    TOKEN_UPDATE_NEEDED = 'tokenupdate'


@dataclass
class Result:
    status: Status
    message: Optional[str] = None


@dataclass
class SearchResult(Result):
    page: list[dict] = field(default_factory=list)


@dataclass
class GuessitResult(Result):
    matches: dict = field(default_factory=dict)


def open_token_tab():
    webbrowser.open_new_tab(f'https://anilist.co/api/v2/oauth/authorize?client_id={CLIENT_ID}&response_type=token')


def auth():
    try:
        with open(os.path.join(SCRIPT_DIR, '.anilist.jwt')) as token_file:
            token = token_file.read()
            parts = token.split('.')
            if len(parts) != 3:
                return Result(Status.TOKEN_UPDATE_NEEDED, 'Wrong number of parts')
            second_part = json.loads(base64.b64decode(parts[1]))
    except FileNotFoundError:
        return Result(Status.TOKEN_UPDATE_NEEDED, 'Access token has not been found, it is needed in order to track progress.')
    except webbrowser.Error as e:
        return Result(Status.ERROR, f'webbrowser error: {str(e)}')
    
    except Exception as e:
        return Result(Status.ERROR, f'Error on token read: {str(e)}')

    today = datetime.today()
    expiration_date = datetime.fromtimestamp(second_part['exp'])
    if (expiration_date - today) < timedelta(weeks=2):
        return Result(Status.TOKEN_UPDATE_NEEDED, 'Access token has expired or expiring, please update it.')
    
    return Result(Status.OK, token)


def report(filename):
    auth_result = auth()
    if auth_result.status != Status.OK:
        return auth_result
    matches = guessit(filename)
    if 'episode' in matches:
        episode = matches['episode']
    else:
        match = re.search(r'\d{2}', os.path.basename(filename))
        if not match:
            return Result(Status.ERROR, 'Could not determine episode')
        episode = match.group(0)

    response = requests.post(
        ANILIST_BASE_URL,
        headers={'Authorization': f'Bearer {auth_result.message}' },
        json={
            'query': REPORT_PROGRESS_MUTATION,
            'variables': { 'mediaId': 114236, 'progress': int(episode), }
        }
    )
    if response.status_code != 200:
        return Result(Status.ERROR, f'Got unexpected response from anilist: [{response.status_code}] {response.text}')
    return Result(Status.OK)


def search(query):
    auth_result = auth()
    if auth_result.status != Status.OK:
        return auth_result
    response = requests.post(
        ANILIST_BASE_URL,
        headers={'Authorization': f'Bearer {auth_result.message}'},
        json={
            'query': ANIME_SEARCH_QUERY,
            'variables': {
                'searchStr': query
            }
        }
    )
    if response.status_code != 200:
        return Result(Status.ERROR, f'Got unexpected response from anilist: [{response.status_code}] {response.text}')
    return SearchResult(Status.OK, None, response.json()['data']['Page']['media'])

def guessit_cmd(path):
    return GuessitResult(Status.OK, None, dict(guessit(path).items()))


parser = argparse.ArgumentParser()
subparsers = parser.add_subparsers(dest='cmd', required=True)
parser_auth = subparsers.add_parser('auth', help='Check and get access token from Anilist')
parser_report = subparsers.add_parser('report', help='Report progress to Anilist')
parser_report.add_argument('filename')
parser_search = subparsers.add_parser('search', help='Search for media entries')
parser_search.add_argument('query', help='Search query')
parser_guessit = subparsers.add_parser('guessit', help='Parse full filename using guessit')
parser_guessit.add_argument('path', help='File path')


if __name__ == '__main__':
    args = parser.parse_args()
    print('called with args', args, file=sys.stderr)
    result = Result(Status.ERROR)
    match args.cmd:
        case 'auth':
            result = auth()
        case 'report':
            result = report(args.filename)
        case 'search':
            result = search(args.query)
        case 'guessit':
            result = guessit_cmd(args.path)
            
    if result.status == Status.TOKEN_UPDATE_NEEDED and args.cmd == 'auth':
        pass
        # open_token_tab()
    json.dump(asdict(result), sys.stdout)
