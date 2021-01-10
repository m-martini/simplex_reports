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
frequencies = [146.58, 446.25]
dates = ['11/5/2020', '11/19/2020', '12/3/2020', '12/17/2020', '1/7/2021']

db = srd(report_database_filename,
         station_locations_filename=station_locations_filename,
         spreadsheet_id=spreadsheet_id,
         range_name=range_name,
         google_key=key)

# first aggregate all dates
plot_file_list1 = []
for f in frequencies:
    plot_file_list1.append((f, "%3.0f.html" % f))

for t in plot_file_list1:
    db.plot_all_stations_to_html(t[0], html_path=t[1])

# now by net date
plot_file_list2 = []
for f in frequencies:
    for d in dates:
        c = d.split('/')
        plot_file_list2.append((f, d, "%s%s%s%3.0f.html" % (c[2], c[0], c[1], f)))

for t in plot_file_list2:
    db.plot_all_stations_to_html(t[0], net_date=t[1], html_path=t[2])

with open('index.html', 'w') as fp:
    fp.write("<html>\n" +
             "<head>\n")
    fp.write(f"<title> Reception Reports for ARES Simplex Net</title>")
    fp.write("</head>\n")
    fp.write("<body>\n")
    fp.write("<h1>Reception Maps Aggregated for all ARES Simplex Nets</h1>\n")
    for t in plot_file_list1:
        fp.write(f"\t<a target=\"_blank\" href=\"{t[1]}\"> {t[0]} MHz </a><br>\n")

    fp.write("<h1>Reception Maps for individual ARES Simplex Nets</h1>\n")
    fp.write("<p>Note that if there are no QSOs indicated a certain call sign map, ")
    fp.write("that station may not have participated in that night\'s net.")
    fp.write("So you might see a map for a night in which you did not participate, ")
    fp.write("with no recorded QSOs.  That is normal.</p>")
    for t in plot_file_list2:
        fp.write(f"\t<a target=\"_blank\" href=\"{t[2]}\"> {t[1]} {t[0]} MHz </a><br>\n")

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
