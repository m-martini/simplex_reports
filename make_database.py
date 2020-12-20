from simplex_net import SimplexReportDatabase as srd

station_locations_filename = r'C:\Users\Marinna\projects\hamradio\ARES\CallSignLocations.txt'
spreadsheet_id = '1a_la9p_qD5i58dc3mGABIT4H7zq2lRjniEHfWuLPyvc'
range_name = 'Form Responses 1!A:AH'
key = 'AIzaSyAkzQCwmEfohkWNGau6Gysf42NPlUfeN9Q'
# TODO remove these hardwired names
report_database_filename = '2mreports.db'

# Create the database from scratch
db = srd(report_database_filename,
         station_locations_filename=station_locations_filename,
         spreadsheet_id=spreadsheet_id,
         range_name=range_name,
         key=key,
         recreate_database=True)

print(db.home_station_information_df)
print(f'Made database based on {len(db.home_station_information_df)} hams')

