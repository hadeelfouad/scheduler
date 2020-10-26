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
    output = pd.DataFrame(columns=['Match ID','Match Availability','Match Deadline','Squad', 'Members/Match','Date', 'Shift', 'Hours/Shift', 'Done'])
    
    schedule = schedule.loc[schedule['Quantity'] != 0]
    schedule.sort_values(by=['Date', 'Shift'], inplace=True)
    schedule['Date'] = pd.to_datetime(schedule['Date'])
    schedule.loc[schedule.Shift.str.lower() == 'morning', 'Shift Start'] = schedule['Date']  + pd.to_timedelta(10, unit='h')
    schedule.loc[schedule.Shift.str.lower() == 'night', 'Shift Start'] = schedule['Date']  + pd.to_timedelta(18, unit='h')
    schedule['Date'] = pd.to_datetime(schedule['Date']).dt.date
    schedule['Shift End'] = schedule['Shift Start']  + pd.to_timedelta(8, unit='h')
    schedule['Hours'] = schedule['Quantity'] * 8
    print(schedule.head())

    matches['Availability'] = pd.to_datetime(matches['Match Date']+ ' ' + matches['Kick-off Time'], format='%d/%m/%Y %H:%M') + pd.DateOffset(minutes=110)
    matches = matches.merge(competitions[['Priority', 'Competition']], how='left').merge(priorities, how='left', left_on='Priority', right_on='Priority Class').drop(labels='Priority Class', axis=1)
    matches = matches.merge(preferences, how='left')
    matches['Deadline'] = pd.to_datetime(matches['Match Date']+ ' ' + matches['Kick-off Time'], format='%d/%m/%Y %H:%M') + pd.to_timedelta(matches['Hours'], unit='h')
    matches['Remaining Hours'] = 8
    matches.sort_values(by=['Deadline', 'Availability'], inplace=True)

    for i in matches.index:
        print('***********MATCH ID: ' + str(matches.loc[i, 'ID']))
        possible_squads =  schedule.loc[schedule['Shift End'] - matches.loc[i, "Availability"] >= pd.to_timedelta(4, unit='h')]
        possible_squads =  possible_squads[(schedule['Shift Start'] <= matches.loc[i, "Deadline"]) & (schedule['Hours'] > 0)]
        if possible_squads.empty:
            print('no squad' + str(matches.loc[i, 'ID']))
            output = pd.concat([output, pd.DataFrame({"Match ID": [matches.loc[i, 'ID']],
                                                        'Match Availability':[matches.loc[i, 'Availability']],
                                                        'Match Deadline':[matches.loc[i, 'Deadline']],
                                                        "Done": [False]})])
            continue
        possible_squads.sort_values(by=['Date', 'Shift'], inplace=True)
        time_to_deadline = pd.to_timedelta([matches.loc[i, 'Deadline'] - possible_squads.loc[possible_squads.index[0], 'Shift Start']]).astype('timedelta64[h]')[0]
        if time_to_deadline < 4:
            print('deadline' + str(matches.loc[i, 'ID']))
            output = pd.concat([output, pd.DataFrame({"Match ID": [matches.loc[i, 'ID']],
                                                        'Match Availability':[matches.loc[i, 'Availability']],
                                                        'Match Deadline':[matches.loc[i, 'Deadline']],
                                                        "Done": [False]})])
            continue
        
        # print(pd.isnull(matches.loc[i, 'Squad']))
        
        shifts_group = possible_squads.groupby(['Date','Shift'])
        for key, _ in shifts_group:
            shift = shifts_group.get_group(key)
            # get squads whose one of their preference is the match 
            prefered_squad = shift[(shift['Squad'] == matches.loc[i, 'Squad']) & (shift['Hours'] > 0)]
            # assigned match to one of the squads that prefer it if any
            if not prefered_squad.empty:
                print('preference squad:')
                # ther can be only one prefered time per shift as shown by the data in preferences.csv
                prefered_squad_index = prefered_squad.index[0]
                print(prefered_squad.loc[prefered_squad_index])
                

                if prefered_squad.loc[prefered_squad_index, 'Shift End'] - matches.loc[i, "Availability"] >= pd.to_timedelta(8, unit='h'):
                    if prefered_squad.loc[prefered_squad_index, 'Hours'] >= 8:
                        hours_worked = matches.loc[i, "Remaining Hours"]
                        prefered_squad.at[prefered_squad_index, 'Hours'] = prefered_squad.loc[prefered_squad_index, 'Hours'] - hours_worked
                        shift.at[prefered_squad_index, 'Hours'] = shift.loc[prefered_squad_index, 'Hours'] - hours_worked
                        schedule.at[prefered_squad_index, 'Hours'] = schedule.loc[prefered_squad_index, 'Hours'] - hours_worked
                        matches.at[i, 'Remaining Hours'] = matches.loc[i, 'Remaining Hours'] - hours_worked
                        # remove a member from the team as the whole shift is deticated to a single match
                        # if hours_worked > 4:
                        prefered_squad.at[prefered_squad_index, 'Quantity'] = prefered_squad.loc[prefered_squad_index, 'Quantity'] - 1
                        shift.at[prefered_squad_index, 'Quantity'] = shift.loc[prefered_squad_index, 'Quantity'] - 1
                        schedule.at[prefered_squad_index, 'Quantity'] = schedule.loc[prefered_squad_index, 'Quantity'] - 1
                        output = pd.concat([output, pd.DataFrame({'Match ID':[matches.loc[i, 'ID']],
                                                            'Match Availability':[matches.loc[i, 'Availability']],
                                                            'Match Deadline':[matches.loc[i, 'Deadline']],
                                                            'Squad': [prefered_squad.loc[prefered_squad_index, 'Squad']],
                                                            'Members/Match': [1],
                                                            'Date': [prefered_squad.loc[prefered_squad_index, 'Date']], 
                                                            'Shift': [prefered_squad.loc[prefered_squad_index, 'Shift']], 
                                                            'Hours/Shift': [hours_worked],
                                                            'Done': [matches.loc[i, 'Remaining Hours'] == 0]})])
                        print('==================================')

                elif prefered_squad.loc[prefered_squad_index, 'Shift End'] - matches.loc[i, "Availability"] >= pd.to_timedelta(4, unit='h'):
                    if prefered_squad.loc[prefered_squad_index, 'Hours'] >= matches.loc[i, "Remaining Hours"]:
                        needed_members = (matches.loc[i, "Remaining Hours"])/4
                        if prefered_squad.loc[prefered_squad_index, 'Quantity'] >= needed_members:
                            hours_worked = needed_members * 4
                            prefered_squad.at[prefered_squad_index, 'Hours'] = prefered_squad.loc[prefered_squad_index, 'Hours'] - hours_worked
                            shift.at[prefered_squad_index, 'Hours'] = shift.loc[prefered_squad_index, 'Hours'] - hours_worked
                            schedule.at[prefered_squad_index, 'Hours'] = schedule.loc[prefered_squad_index, 'Hours'] - hours_worked
                            matches.at[i, 'Remaining Hours'] = matches.loc[i, 'Remaining Hours'] - hours_worked
                            prefered_squad.at[prefered_squad_index, 'Quantity'] = prefered_squad.loc[prefered_squad_index, 'Quantity'] - needed_members
                            shift.at[prefered_squad_index, 'Quantity'] = shift.loc[prefered_squad_index, 'Quantity'] - needed_members
                            schedule.at[prefered_squad_index, 'Quantity'] = schedule.loc[prefered_squad_index, 'Quantity'] - needed_members
                            output = pd.concat([output, pd.DataFrame({'Match ID':[matches.loc[i, 'ID']],
                                                            'Match Availability':[matches.loc[i, 'Availability']],
                                                            'Match Deadline':[matches.loc[i, 'Deadline']],
                                                            'Squad': [prefered_squad.loc[prefered_squad_index, 'Squad']],
                                                            'Members/Match': [needed_members],
                                                            'Date': [prefered_squad.loc[prefered_squad_index, 'Date']], 
                                                            'Shift': [prefered_squad.loc[prefered_squad_index, 'Shift']], 
                                                            'Hours/Shift': [hours_worked],
                                                            'Done': [matches.loc[i, 'Remaining Hours'] == 0]})])
                            print('---------------------------------------------')


                        


                #####################################################################
                # one of the prefered squad working on the match
                # if prefered_squad.loc[prefered_squad_index, 'Hours'] >= 8 and matches.loc[i, 'Remaining Hours'] == 8:
                #     matches.at[i, 'Remaining Hours'] = matches.loc[i, 'Remaining Hours'] - 8
                #     shift.at[prefered_squad_index, 'Hours'] = shift.loc[prefered_squad_index, 'Hours'] - 8
                #     prefered_squad.at[prefered_squad_index, 'Hours'] = prefered_squad.loc[prefered_squad_index, 'Hours'] - 8
                #     output = pd.concat([output, pd.DataFrame({'Match ID':[matches.loc[i, 'ID']],
                #                                             'Match Availability':[matches.loc[i, 'Availability']],
                #                                             'Match Deadline':[matches.loc[i, 'Deadline']],
                #                                             'Squad': [prefered_squad.loc[prefered_squad_index, 'Squad']],
                #                                             'Members/Match': [1],
                #                                             'Date': [prefered_squad.loc[prefered_squad_index, 'Date']], 
                #                                             'Shift': [prefered_squad.loc[prefered_squad_index, 'Shift']], 
                #                                             'Hours/Shift': [8],
                #                                             'Done': [matches.loc[i, 'Remaining Hours'] == 0]})])
                # # two of the prefered squad working on the match
                # elif prefered_squad.loc[prefered_squad_index, 'Hours'] >= 4 and matches.loc[i, 'Remaining Hours'] == 4:
                #     matches.at[i, 'Remaining Hours'] = matches.loc[i, 'Remaining Hours'] - 4
                #     shift.at[prefered_squad_index, 'Hours'] = shift.loc[prefered_squad_index, 'Hours'] - 4
                #     prefered_squad.at[prefered_squad_index, 'Hours'] = prefered_squad.loc[prefered_squad_index, 'Hours'] - 4
                #     output = pd.concat([output, pd.DataFrame({'Match ID':[matches.loc[i, 'ID']],
                #                                             'Match Availability':[matches.loc[i, 'Availability']],
                #                                             'Match Deadline':[matches.loc[i, 'Deadline']],
                #                                             'Squad': [prefered_squad.loc[prefered_squad_index, 'Squad']],
                #                                             'Members/Match': [2],
                #                                             'Date': [prefered_squad.loc[prefered_squad_index, 'Date']], 
                #                                             'Shift': [prefered_squad.loc[prefered_squad_index, 'Shift']], 
                #                                             'Hours/Shift': [4],
                #                                             'Done': [matches.loc[i, 'Remaining Hours'] == 0]})])
            # check if prefered squad was able to finish the match
            # if matches.loc[i, 'Remaining Hours'] == 0:
            #     break
            # shift = shift[shift['Hours'] > 0] 
            if not prefered_squad.empty:
                shift = shift.drop(index=prefered_squad.index)
            for index in shift.index:
                # move to next match once a match is done
                if matches.loc[i, 'Remaining Hours'] == 0:
                    break
                elif shift.loc[index, 'Shift End'] - matches.loc[i, "Availability"] > pd.to_timedelta(5, unit='h'): # check avaiabilty sutiable for shift
                    if shift.loc[index, 'Quantity'] >= 2 and matches.loc[i, 'Remaining Hours'] == 8: # check on quantity instead of hours
                            matches.at[i, 'Remaining Hours'] = matches.loc[i, 'Remaining Hours'] - 8
                            shift.at[index, 'Hours'] = shift.loc[index, 'Hours'] - 10
                            schedule.at[index, 'Hours'] = schedule.loc[index, 'Hours'] - 10
                            shift.at[index, 'Quantity'] = shift.loc[index, 'Quantity'] - 2
                            schedule.at[index, 'Quantity'] = schedule.loc[index, 'Quantity'] - 2
                            output = pd.concat([output, pd.DataFrame({'Match ID':[matches.loc[i, 'ID']],
                                                                    'Match Availability':[matches.loc[i, 'Availability']],
                                                                    'Match Deadline':[matches.loc[i, 'Deadline']],
                                                                    'Squad': [shift.loc[index, 'Squad']],
                                                                    'Members/Match': [2],
                                                                    'Date': [shift.loc[index, 'Date']], 
                                                                    'Shift': [shift.loc[index, 'Shift']], 
                                                                    'Hours/Shift': [10],
                                                                    'Done': [matches.loc[i, 'Remaining Hours'] == 0]})])
                    # worked on one team per match
                    elif shift.loc[index, 'Quantity'] >= 5 and matches.loc[i, 'Remaining Hours'] == 4: # check on quantity instead of hours
                        matches.at[i, 'Remaining Hours'] = matches.loc[i, 'Remaining Hours'] - 4
                        shift.at[index, 'Hours'] = shift.loc[prefered_squad_index, 'Hours'] - 5
                        schedule.at[index, 'Hours'] = schedule.loc[prefered_squad_index, 'Hours'] - 5
                        shift.at[index, 'Quantity'] = shift.loc[index, 'Quantity'] - 1
                        schedule.at[index, 'Quantity'] = schedule.loc[index, 'Quantity'] - 1
                        output = pd.concat([output, pd.DataFrame({'Match ID':[matches.loc[i, 'ID']],
                                                                    'Match Availability':[matches.loc[i, 'Availability']],
                                                                    'Match Deadline':[matches.loc[i, 'Deadline']],
                                                                    'Squad': [shift.loc[index, 'Squad']],
                                                                    'Members/Match': [1],
                                                                    'Date': [shift.loc[index, 'Date']], 
                                                                    'Shift': [shift.loc[index, 'Shift']], 
                                                                    'Hours/Shift': [5],
                                                                    'Done': [matches.loc[i, 'Remaining Hours'] == 0]})])
                else:
                    if len(output.loc[(output['Match ID'] == matches.loc[i, 'ID'])].index) == 0:
                        print('match does not statisfy any shift')
                        print(matches.loc[i, 'ID'])
                        print('$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$')
                        output = pd.concat([output, pd.DataFrame({"Match ID": [matches.loc[i, 'ID']],
                                                        'Match Availability':[matches.loc[i, 'Availability']],
                                                        'Match Deadline':[matches.loc[i, 'Deadline']],
                                                        "Done": [False]})])



            # while matches.loc[i, 'Remaining Hours'] != 0:
            #     if shift.loc[shift.index[0], 'Hours'] > 10:
            #         matches.loc[i, 'Remaining Hours'] = 0
            #         schedule.loc[shift.index[0], 'Hours'] = schedule.loc[shift.index[0], 'Hours'] - 10
            #         shift.loc[shift.index[0], 'Hours'] = shift.loc[shift.index[0], 'Hours'] - 10
            #         output = pd.concat([output, pd.DataFrame({'Match ID':[matches.loc[i, 'ID']],
            #         'Squad': [shift.loc[shift.index[0], 'Squad']], 
            #         'Date': [shift.loc[shift.index[0], 'Date']], 
            #         'Shift': [shift.loc[shift.index[0], 'Shift']], 
            #         'Hours/Shift': [10]})])
            #     else:
            #         break

    # return jsonify(message="Hello World!"), 200
    return send_file(io.BytesIO(output.to_csv().encode()),
            mimetype = 'text/csv',
            attachment_filename= 'trial.csv',
            as_attachment = True), 200
    # resp = make_response(output.to_csv())
    # resp.headers["Content-Disposition"] = "attachment; filename=possible_schedule.csv"
    # resp.headers["Content-Type"] = "text/csv"
    # return resp, 200
