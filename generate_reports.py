"""generate web pages with plots for both frequencies to include at FARA web site
"""
from simplex_net import SimplexReportDatabase as srd

station_locations_filename = r'C:\Users\Marinna\projects\hamradio\ARES\CallSignLocations.txt'
# google_sheet_url = r'https://docs.google.com/spreadsheets/d/the_id_is_here/edit#gid=66781920'
spreadsheet_id = '1a_la9p_qD5i58dc3mGABIT4H7zq2lRjniEHfWuLPyvc'
# range_name = 'Form Responses 1!A1:AH33'
range_name = 'Form Responses 1!A:AH'
key = 'AIzaSyAkzQCwmEfohkWNGau6Gysf42NPlUfeN9Q'
# TODO remove these hardwired names
report_database_filename = '2mreports.db'

# we want to plot who heard this ham, how well and where
station_transmitting = 'W1FX'
frequencies = [146.58, 446.45]

db = srd(report_database_filename,
         station_locations_filename=station_locations_filename,
         spreadsheet_id=spreadsheet_id,
         range_name=range_name,
         key=key,
         recreate_database=False)

plot_file_list = []
for f in frequencies:
    plot_file_list.append((f, "%3.0f.html" % f))

for t in plot_file_list:
    db.plot_all_stations_to_html(t[0], html_path=t[1])

with open('index.html', 'w') as fp:
    fp.write("<html>\n" +
             "<head>\n")
    fp.write(f"<title> Reception Reports for ARES Simplex Net</title>")
    fp.write("</head>\n")
    fp.write("<body>\n")
    fp.write("<h1>Reception Reports for all ARES Simplex Nets</h1>\n")
    for t in plot_file_list:
        fp.write(f"\t<a href=\"{t[1]}\"> {t[0]} MHz </a><br>\n")

    fp.write("</body>\n")
    fp.write("</html>\n")

"""
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
"""
