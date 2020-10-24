from flask import Blueprint, jsonify, request, send_file

from helpers import validate_files, read_files, validate_matches_competition
import pandas as pd

import io
api = Blueprint('api', __name__)


@api.route("/schedule", methods=["POST"])
def create_schedule():
    validate_files(request.files)
    competitions, matches, priorities, preferences, schedule = read_files(request.files)
    validate_matches_competition(matches, competitions)
    output = pd.DataFrame(columns=['Match ID','Squad', 'Date', 'Shift', 'Hours/Shift'])

    squads_preferences = dict()
    for competition in preferences.Competition.unique():
        squads_preferences[competition] = preferences.loc[preferences['Competition'] == competition]['Squad'].tolist()
    # print(squads_preferences)
    
    schedule.sort_values(by=['Date', 'Shift'], inplace=True)
    schedule['Date'] = pd.to_datetime(schedule['Date'])
    schedule['Date'].loc[(schedule['Shift'].str.lower() == 'morning')]  = schedule['Date'] + pd.to_timedelta(18, unit='h')
    schedule['Date'].loc[(schedule['Shift'].str.lower() == 'night')]  = schedule['Date'] + pd.to_timedelta(26, unit='h')
    schedule['Hours'] = schedule['Quantity'] * 8

    matches['Availability'] = pd.to_datetime(matches['Match Date']+ ' ' + matches['Kick-off Time'], format='%d/%m/%Y %H:%M') + pd.DateOffset(minutes=110)
    matches = matches.merge(competitions[['Priority', 'Competition']], how='left').merge(priorities, how='left', left_on='Priority', right_on='Priority Class').drop(labels='Priority Class', axis=1)
    matches['Deadline'] = pd.to_datetime(matches['Match Date']+ ' ' + matches['Kick-off Time'], format='%d/%m/%Y %H:%M') + pd.to_timedelta(matches['Hours'], unit='h')
    matches['Remaining Hours'] = 8
    matches.sort_values(by='Deadline', inplace=True)

    schedule_groups = schedule.groupby(['Date','Shift'])
    print(len(list(schedule_groups)))
    # print(list(schedule_groups)[0])
    # print(matches.loc[0])
    possible_squads = schedule.loc[((schedule['Date'] >= matches.loc[0, "Deadline"]) & (schedule.Date - pd.to_timedelta(8, unit='h') <= matches.loc[0, "Deadline"])) |
     ((schedule['Date'] >= matches.loc[0, "Availability"]) & (schedule.Date - pd.to_timedelta(8, unit='h') <= matches.loc[0, "Availability"]))]
    print(possible_squads)
    # for _, g in schedule.groupby(['Date','Shift']):
    #     print(g, '\n')
    # print(schedule_groups.head())

    return jsonify(message="Hello World!"), 200
    # return send_file(io.BytesIO(matches.to_csv().encode()),
    #         mimetype = 'text/csv',
    #         attachment_filename= 'possilbe_schedule.csv',
    #         as_attachment = True), 200
    # resp = make_response(output.to_csv())
    # resp.headers["Content-Disposition"] = "attachment; filename=possible_schedule.csv"
    # resp.headers["Content-Type"] = "text/csv"
    # return resp, 200
