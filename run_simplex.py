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
# frequency_of_net = 146.58
frequency_of_net = 446.25

# Create the database from scratch
db = srd(report_database_filename,
         station_locations_filename=station_locations_filename,
         spreadsheet_id=spreadsheet_id,
         range_name=range_name,
         key=key,
         recreate_database=True)

db.plot_all_stations_to_html(frequency_of_net)

print(db)

# do some plotting

# p = db.plot_station_reception(station_transmitting, frequency_of_net)

# show(p)

"""
if os.path.exists(display_jpg_filename):
    os.remove(display_jpg_filename)

with open(display_jpg_filename, 'w') as fp:
    fp.write("<html>\n" +
             "<head>\n")
    fp.write(f"<title> Simplex Reports for {frequency_of_net} MHz </title>")
    fp.write("</head>\n")
    fp.write("<body>\n")

    plot_list = []

    for station in db.home_station_information_df['Call']:
        p = db.plot_station_reception(station, frequency_of_net)
        file_name = f"report_{station}_{np.floor(frequency_of_net)}.png"
        plot_title = f"{station}_{frequency_of_net}"
        # f = save(p, filename=file_name, title=plot_title)
        f = export_png(p, filename=file_name)
        fp.write(f"<img src=\"{file_name}\"><br>\n")
        print(f)
        plot_list.append(p)

    fp.write("</body>\n")
    fp.write("</html>\n")
"""


# go futher - can we build this and run it on criticalthinker?
# https://github.com/bokeh/bokeh/tree/branch-2.3/examples/app/movies
