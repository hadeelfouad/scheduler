## Summary

The whole logic is based on that each collector collects the event data for a single team means that a collecter has to be able to finish a team per match.

To get a schedule you need to run main.py to run the server. Send **POST** request to **/api/schedule**
request should have 5 files init body with the following keys that maps to the appropriate files **competitions", "matches", "priorities", "schedule", "preferences**
The response is a downloadable csv file that has the following columns **Match ID,Match Availability,Match Deadline,Squad,Members/Match,Date,Shift,Hours/Shift,Done**