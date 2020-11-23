from simplex_net import SimplexReportDatabase as srd
# from bokeh.models import Dot, Circle, Asterisk, HoverTool, ColumnDataSource, LegendItem, Legend
from bokeh.plotting import show, save
from bokeh.io import export_png # import output_notebook
# from bokeh.tile_providers import get_provider, OSM
import numpy as np
import os

station_locations_filename = r'C:\Users\Marinna\projects\hamradio\ARES\CallSignLocations.txt'
# google_sheet_url = r'https://docs.google.com/spreadsheets/d/the_id_is_here/edit#gid=66781920'
spreadsheet_id = '1a_la9p_qD5i58dc3mGABIT4H7zq2lRjniEHfWuLPyvc'
range_name = 'Form Responses 1!A1:AH33'
key = 'AIzaSyAkzQCwmEfohkWNGau6Gysf42NPlUfeN9Q'
# TODO remove these hardwired names
report_database_filename = '2mreports.db'

# we want to plot who heard this ham, how well and where
station_transmitting = 'KC1MUC'
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

if os.path.exists("index.html"):
    os.remove("index.html")

with open("index.html", 'w') as fp:
    fp.write("<html>\n" +
             "<head>\n")
    fp.write(f"<title> Simplex Reports for {frequency_of_net} MHz </title>")
    fp.write("</head>\n")
    fp.write("<body>\n")

    for station in db.ham_locations_df['Call']:
        p = db.plot_station_reception(station, frequency_of_net)
        file_name = f"report_{station}_{np.floor(frequency_of_net)}.png"
        plot_title = f"{station}_{frequency_of_net}"
        # f = save(p, filename=file_name, title=plot_title)
        f = export_png(p, filename=file_name)
        fp.write(f"<img src=\"{file_name}\"><br>\n")
        print(f)

    fp.write("</body>\n")
    fp.write("</html>\n")



# db.plot_all_stations(frequency_of_net)

# go futher - can we build this and run it on criticalthinker?
# https://github.com/bokeh/bokeh/tree/branch-2.3/examples/app/movies
