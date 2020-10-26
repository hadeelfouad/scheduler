from difflib import get_close_matches
import io
from os import environ

from flask import jsonify
from werkzeug.exceptions import BadRequest

import pandas as pd


def allowed_file(filename, key):
    return '.' in filename and \
           filename.split('.')[1].lower() == 'csv' and \
           key in ['competitions', 'matches', 'priorities', 'schedule', 'preferences']
    

def validate_files(files):
    keys = list(files.keys())
    if len(keys) != 5:
        raise BadRequest(description='number of expected files is 5')
        if not allowed_file(files[key].filename, key):
            raise BadRequest('unallowed file for {}. File extension must be .csv or key value must be one of the following "competitions", "matches", "priorities", "schedule", "preferences"'.format(key))

def read_files(files):
    competitions = pd.read_csv(io.StringIO(files['competitions'].stream.read().decode("UTF8"), newline=None))
    matches = pd.read_csv(io.StringIO(files['matches'].stream.read().decode("UTF8"), newline=None))
    priorities = pd.read_csv(io.StringIO(files['priorities'].stream.read().decode("UTF8"), newline=None))
    preferences = pd.read_csv(io.StringIO(files['preferences'].stream.read().decode("UTF8"), newline=None))
    schedule = pd.read_csv(io.StringIO(files['schedule'].stream.read().decode("UTF8"), newline=None))
    return competitions, matches, priorities, preferences, schedule

def validate_matches_competition(matches, competitions):
    unknown_competitions = []
    competitions = competitions.Competition.unique()
    for match_competition in matches.Competition.unique():
        if match_competition not in competitions:
            unknown_competitions.append(match_competition)
    for unknown_competition in unknown_competitions:
        cloest_competition = get_close_matches(unknown_competition, competitions, n=1)[0]
        matches['Competition'].loc[(matches['Competition'] == unknown_competition)] = cloest_competition

