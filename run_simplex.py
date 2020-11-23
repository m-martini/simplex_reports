from simplex_net import SimplexReportDatabase as srd
# from bokeh.models import Dot, Circle, Asterisk, HoverTool, ColumnDataSource, LegendItem, Legend
from bokeh.plotting import show
# from bokeh.io import output_notebook
# from bokeh.tile_providers import get_provider, OSM

station_locations_filename = r'C:\Users\Marinna\projects\hamradio\ARES\CallSignLocations.txt'
# google_sheet_url = r'https://docs.google.com/spreadsheets/d/the_id_is_here/edit#gid=66781920'
spreadsheet_id = '1a_la9p_qD5i58dc3mGABIT4H7zq2lRjniEHfWuLPyvc'
range_name = 'Form Responses 1!A1:AH33'
key = 'AIzaSyAkzQCwmEfohkWNGau6Gysf42NPlUfeN9Q'
# TODO remove these hardwired names
report_database_filename = '2mreports.db'

# we want to plot who heard this ham, how well and where
station_transmitting = 'KX1C'
frequency_of_net = 146.58

# Create the database from scratch
db = srd(report_database_filename,
         station_locations_filename=station_locations_filename,
         spreadsheet_id=spreadsheet_id,
         range_name=range_name,
         key=key,
         recreate_database=True)

# do some plotting

p = db.plot_station_reception(station_transmitting, frequency_of_net)

show(p)

# go futher - can we build this and run it on criticalthinker?
# https://github.com/bokeh/bokeh/tree/branch-2.3/examples/app/movies
