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
    
    schedule = schedule.loc[schedule['Quantity'] != 0]
    schedule.sort_values(by=['Date', 'Shift'], inplace=True)
    schedule['Date'] = pd.to_datetime(schedule['Date'])
    schedule.loc[schedule.Shift.str.lower() == 'morning', 'Shift Start'] = schedule['Date']  + pd.to_timedelta(10, unit='h')
    schedule.loc[schedule.Shift.str.lower() == 'night', 'Shift Start'] = schedule['Date']  + pd.to_timedelta(18, unit='h')
    schedule['Shift End'] = schedule['Shift Start']  + pd.to_timedelta(8, unit='h')
    schedule['Hours'] = schedule['Quantity'] * 8

    matches['Availability'] = pd.to_datetime(matches['Match Date']+ ' ' + matches['Kick-off Time'], format='%d/%m/%Y %H:%M') + pd.DateOffset(minutes=110)
    matches = matches.merge(competitions[['Priority', 'Competition']], how='left').merge(priorities, how='left', left_on='Priority', right_on='Priority Class').drop(labels='Priority Class', axis=1)
    matches = matches.merge(preferences, how='left')
    matches['Deadline'] = pd.to_datetime(matches['Match Date']+ ' ' + matches['Kick-off Time'], format='%d/%m/%Y %H:%M') + pd.to_timedelta(matches['Hours'], unit='h')
    matches['Remaining Hours'] = 8
    matches.sort_values(by=['Deadline', 'Availability'], inplace=True)

    # schedule_groups = schedule.groupby(['Date','Shift'])
    # print(len(list(schedule_groups)))
    # # print(list(schedule_groups)[0])
    # # print(matches.loc[0])

    for i in matches.index:
        # i = 1
        print('***********MATCH ID: ' + str(matches.loc[i, 'ID']))
        # possible_squads = schedule.loc[((schedule['Shift End'] >= matches.loc[i, "Deadline"]) & (schedule['Shift Start] <= matches.loc[i, "Deadline"])) |
        # (schedule['Shift End'] >= matches.loc[i, "Availability"])]
        # possible_squads =  schedule.loc[(schedule['Shift End'] >= matches.loc[i, "Availability"])]
        # print((schedule['Shift End'] - matches.loc[i, "Availability"]).astype('timedelta64[h]'))
        possible_squads =  schedule.loc[schedule['Shift End'] - matches.loc[i, "Availability"] >= pd.to_timedelta(4, unit='h')]
        possible_squads =  possible_squads[(schedule['Shift Start'] <= matches.loc[i, "Deadline"]) & (schedule['Hours'] > 0)]
        if possible_squads.empty:
            # print('no squad' + str(matches.loc[i, 'ID']))
            output = pd.concat([output, pd.DataFrame({"Match ID": [matches.loc[i, 'ID']]})])
            continue
        possible_squads.sort_values(by=['Date', 'Shift'], inplace=True)
        time_to_deadline = pd.to_timedelta([matches.loc[i, 'Deadline'] - possible_squads.loc[possible_squads.index[0], 'Shift Start']]).astype('timedelta64[h]')[0]
        if time_to_deadline < 4:
            # print('deadline' + str(matches.loc[i, 'ID']))
            output = pd.concat([output, pd.DataFrame({"Match ID": [matches.loc[i, 'ID']]})])
            continue
        
        # print(pd.isnull(matches.loc[i, 'Squad']))
        
        shifts_group = possible_squads.groupby(['Date','Shift'])
        for key, g in shifts_group:
            if matches.loc[i, 'Remaining Hours'] == 0:
                break
            shift = shifts_group.get_group(key)
            while matches.loc[i, 'Remaining Hours'] != 0:
                if shift.loc[shift.index[0], 'Hours'] > 10:
                    matches.loc[i, 'Remaining Hours'] = 0
                    schedule.loc[shift.index[0], 'Hours'] = schedule.loc[shift.index[0], 'Hours'] - 10
                    shift.loc[shift.index[0], 'Hours'] = shift.loc[shift.index[0], 'Hours'] - 10
                    output = pd.concat([output, pd.DataFrame({'Match ID':[matches.loc[i, 'ID']],
                    'Squad': [shift.loc[shift.index[0], 'Squad']], 
                    'Date': [shift.loc[shift.index[0], 'Date']], 
                    'Shift': [shift.loc[shift.index[0], 'Shift']], 
                    'Hours/Shift': [10]})])
                else:
                    break

    # return jsonify(message="Hello World!"), 200
    return send_file(io.BytesIO(output.to_csv().encode()),
            mimetype = 'text/csv',
            attachment_filename= 'trial.csv',
            as_attachment = True), 200
    # resp = make_response(output.to_csv())
    # resp.headers["Content-Disposition"] = "attachment; filename=possible_schedule.csv"
    # resp.headers["Content-Type"] = "text/csv"
    # return resp, 200
