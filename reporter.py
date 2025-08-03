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
SET_SCORE_MUTATION = '''
mutation SaveMediaListEntry($score: Float, $mediaId: Int) {
  SaveMediaListEntry(score: $score, mediaId: $mediaId) {
    score(format: POINT_10)
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


def get_media_id(filename):
    try:
        with open(os.path.join(os.path.dirname(filename), '.anilist.json')) as media_file:
            media_id = json.load(media_file)['media_id']
            pass
    except FileNotFoundError:
        return Result(Status.ERROR, 'Could not found mediaId')
    except KeyError:
        return Result(Status.ERROR, 'Media file does not have media_id')

    return media_id


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
    media_result = get_media_id(filename)
    if isinstance(media_result, Result):
        return media_result
    response = requests.post(
        ANILIST_BASE_URL,
        headers={'Authorization': f'Bearer {auth_result.message}' },
        json={
            'query': REPORT_PROGRESS_MUTATION,
            'variables': { 'mediaId': media_result, 'progress': int(episode), }
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


def set_score(filename, score):
    auth_result = auth()
    if auth_result.status != Status.OK:
        return auth_result
    media_result = get_media_id(filename)
    if isinstance(media_result, Result):
        return media_result
    response = requests.post(
        ANILIST_BASE_URL,
        headers={'Authorization': f'Bearer {auth_result.message}'},
        json={
            'query': SET_SCORE_MUTATION,
            'variables': {
                'mediaId': media_result,
                'score': score
            }
        }
    )
    if response.status_code != 200:
        return Result(Status.ERROR, f'Got unexpected response from anilist: [{response.status_code}] {response.text}')
    return Result(Status.OK)


def browse(filename):
    media_result = get_media_id(filename)
    if isinstance(media_result, Result):
        return media_result
    webbrowser.open_new_tab(f'https://anilist.co/anime/{media_result}')
    return Result(Status.OK)


parser = argparse.ArgumentParser()
subparsers = parser.add_subparsers(dest='cmd', required=True)
parser_auth = subparsers.add_parser('auth', help='Check and get access token from Anilist')
parser_report = subparsers.add_parser('report', help='Report progress to Anilist')
parser_report.add_argument('filename')
parser_search = subparsers.add_parser('search', help='Search for media entries')
parser_search.add_argument('query', help='Search query')
parser_guessit = subparsers.add_parser('guessit', help='Parse full filename using guessit')
parser_guessit.add_argument('path', help='File path')
parser_score = subparsers.add_parser('score', help='Rate an anime')
parser_score.add_argument('filename', help='File path')
parser_score.add_argument('score', type=float, help='A score')
parser_browse = subparsers.add_parser('browse', help='Open anilist page')
parser_browse.add_argument('filename', help='File path')


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
        case 'score':
            result = set_score(args.filename, args.score)
        case 'browse':
            result = browse(args.filename)
            
    if result.status == Status.TOKEN_UPDATE_NEEDED and args.cmd == 'auth':
        webbrowser.open_new_tab(f'https://anilist.co/api/v2/oauth/authorize?client_id={CLIENT_ID}&response_type=token')
    json.dump(asdict(result), sys.stdout)
