from simplex_net import SimplexReportDatabase as srd
# from bokeh.models import Dot, Circle, Asterisk, HoverTool, ColumnDataSource, LegendItem, Legend
from bokeh.plotting import show, save
from bokeh.io import export_png, output_file  # import output_notebook
from bokeh.layouts import column, gridplot
# from bokeh.tile_providers import get_provider, OSM
import numpy as np
import os

station_locations_filename = r'C:\Users\Marinna\projects\hamradio\ARES\CallSignLocations.txt'
# google_sheet_url = r'https://docs.google.com/spreadsheets/d/the_id_is_here/edit#gid=66781920'
spreadsheet_id = '1a_la9p_qD5i58dc3mGABIT4H7zq2lRjniEHfWuLPyvc'
# range_name = 'Form Responses 1!A1:AH33'
range_name = 'Form Responses 1!A:AH'
key = 'AIzaSyAkzQCwmEfohkWNGau6Gysf42NPlUfeN9Q'
# TODO remove these hardwired names
report_database_filename = '2mreports.db'
display_jpg_filename = "jpg_list.html"

# we want to plot who heard this ham, how well and where
station_transmitting = 'W1FX'
frequency_of_net = 146.58
# frequency_of_net = 446.25
date_of_net='11/19/2020'

# Create the database from scratch
db = srd(report_database_filename,
         station_locations_filename=station_locations_filename,
         spreadsheet_id=spreadsheet_id,
         range_name=range_name,
         key=key,
         recreate_database=False)

p = db.plot_station_reception(station_transmitting,
                              frequency_of_net,
                              net_date=date_of_net)

show(p)

