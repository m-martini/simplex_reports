"""simplex net module

    This module handles, analyzes and displays feedback from
    ham radio stations participating in simplex nets to
    determine propagation in a region.

    Stations enter their observations in a Google Form which
    are then stored in a Google Sheet.  The spreadsheet is read
    by this module.  Analysis and plots can be made.

   There are two classes, one for the database and one for the records.

   TODO update database by finding records - by record ID - that haven't been entered yet
   TODO Automate ftp upload to web
   TODO how to handle adding and removing stations from the form and how does this affect the spreadheet?
   TODO remove the hard wired sheet range
   TODO what to do with missing hams

"""
# from __future__ import print_function

import re
import os
import sys
import traceback

import unicodedata
import sqlite3
import httplib2
from apiclient import discovery
import pandas as pd
import numpy as np
from bokeh.models import Dot, Circle, Asterisk, HoverTool, ColumnDataSource, LegendItem, Legend, Label
from bokeh.plotting import figure, show
from bokeh.io import output_file
# noinspection PyUnresolvedReferences
from bokeh.tile_providers import get_provider, OSM
from bokeh.layouts import gridplot


class SimplexReportDatabase:
    """
    An object that contains all the station and report information.
    """
    con = None
    ham_locations_df = None

    def __init__(self, report_database_filename,
                 station_locations_filename=None,
                 spreadsheet_id=None,
                 range_name=None,
                 key=None,
                 recreate_database=False):
        """

        :param str report_database_filename:  SQL file created by this class
        :param str station_locations_filename:  text file listing call sign, latitude and longitude
        :param str spreadsheet_id: google spreadsheet id
                    # google_sheet_url = r'https://docs.google.com/spreadsheets/d/the_id_is_here/edit#gid=66781920'
        :param str range_name:  range of google sheet to load
        :param str key:  google api key for sheets access
        :param bool recreate_database:  True to force replacement of database
        """
        if recreate_database:
            if os.path.exists(report_database_filename):
                os.remove(report_database_filename)

            hams = self.read_station_information_file(station_locations_filename)
            form_data = self.get_form_results(spreadsheet_id, range_name, key)
            self.initialize_new_database(hams, report_database_filename)
            self.populate_database_with_reports(form_data)
        else:
            self.con = sqlite3.connect(report_database_filename)

        self.get_ham_locations()
        self.wgs84_to_web_mercator()

    @staticmethod
    def remove_control_characters(s):
        return "".join(ch for ch in s if unicodedata.category(ch)[0] != "C")

    def read_station_information_file(self, station_information_file):
        hams = []  # will be a list of dicts
        infile = open(station_information_file, 'r')
        infile.readline()  # skip the header

        for line in infile:
            line = self.remove_control_characters(line)
            data = line.split(',')
            d = {'Call': data[0], 'Latitude': float(data[1]), 'Longitude': float(data[2])}
            hams.append(d)

        infile.close()

        return hams

    @staticmethod
    def get_form_results(spreadsheet_id, range_name, key):
        discovery_url = ('https://sheets.googleapis.com/$discovery/rest?'
                         'version=v4')
        service = discovery.build(
            'sheets',
            'v4',
            http=httplib2.Http(),
            discoveryServiceUrl=discovery_url,
            developerKey=key)

        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id, range=range_name).execute()
        values = result.get('values', [])

        if not values:
            print('No data found.')
            return None
        else:
            return values

    def initialize_new_database(self, station_list, report_database_filename):
        """Create and set up the tables in the sqlite database"""

        self.con = sqlite3.connect(report_database_filename)
        cur = self.con.cursor()

        cur.execute("CREATE TABLE Hams (Id INT, Call TINYTEXT, Latitude FLOAT, Longitude FLOAT)")

        for item in enumerate(station_list):
            data = item[1]
            command = "INSERT INTO Hams VALUES({}, '{}', {}, {})".format(item[0],
                                                                         data['Call'],
                                                                         data['Latitude'], data['Longitude'])
            cur.execute(command)

        cur.execute(
            "CREATE TABLE RESPONSES (Id TEXT, ReportingTimestamp DATETIME, SubmittingCall TINYTEXT, DateOfNet DATE, " +
            "FrequencyOfNet FLOAT, TransmitPower TINYTEXT, TransmitHeight TINYTEXT, SubmittedLatitude FLOAT, " +
            "SubmittedLongitude FLOAT, Comment TEXT, ReceivedCall TINYTEXT, ReceivedQuality TINYTEXT)")

        self.con.commit()

    def update_station_information(self, call_sign, latitude, longitude):
        cur = self.con.cursor()
        cur.execute("SELECT DISTINCT Call FROM Hams")
        existing_calls = cur.fetchall()

        for i in range(len(existing_calls)):
            existing_calls[i] = existing_calls[i][0]  # reformat

        if call_sign not in existing_calls:
            print(f'call {call_sign} added to table Hams')
            command = "INSERT INTO Hams VALUES({}, '{}', {}, {})".format(len(existing_calls)+1,
                                                                         call_sign,
                                                                         latitude, longitude)
        else:
            print(f'call {call_sign} already exists, record updated')
            command = f"UPDATE Hams SET Latitude={latitude}, Longitude={longitude} WHERE Call={call_sign}"

        cur.execute(command)
        self.con.commit()

    @staticmethod
    def build_record_id(date, call, frequency):
        # build a unique Id for each record being entered, just in case we need it later
        # - for instance, if a ham wants to update their report

        record_id = ''
        # make sure the date is padded
        for item in enumerate(date.split('/')):
            if len(item[1]) < 2:
                record_id = record_id+'0'+item[1]
            else:
                record_id = record_id+item[1]

        f = str(frequency).split('.')
        if len(f) > 1:
            if len(f[1]) == 1:
                f[1] = f[1]+'00'
            elif len(f[1]) == 2:
                f[1] = f[1]+'00'

        record_id = record_id+f[0]+f[1]+call

        return record_id

    @staticmethod
    def build_response_dict(header, report):
        """
        make a dict of the calls and qualities for a given report
        :param header:
        :param report:
        :return:

        at the moment, it is convenient that google sends the call signs back in []
        likely because this is the call list in the google form
        an it is also the order of the google form that puts the list of calls last - this is key
        at which index do the calls start?
        """
        idx_first_call = None
        for item in enumerate(header):
            if '[' in item[1] and ']' in item[1]:
                idx_first_call = item[0]
                break

        raw = dict(zip(header[idx_first_call:], report[idx_first_call:]))

        responses = {}
        for key in raw.keys():
            new_key = re.sub('[ \[\]]', '', key)  # clean it up to just the call sign
            responses[new_key] = raw[key]

        return responses, idx_first_call

    @staticmethod
    def clean_up_report(report):
        """catch all the foibles of hams entering data improperly"""

        # call sign should be just the call sign
        call_str = report[1].split()
        if len(call_str) > 1:
            report[1] = call_str.pop(0)
            report[8] = report[8]+' '+' '.join(call_str)

        # call sign must be all caps
        report[1] = report[1].upper()

        # call sign should not have trailing blanks
        report[1] = report[1].strip()

        report[5] = re.sub('[\']', ' ft', report[5])
        report[5] = re.sub('[\"]', ' in', report[5])

        for i, item in enumerate(report):
            if '\'' in item:
                # remove any stray ' or " which will mess up the SQL command
                new_item = re.sub('[\'\"]', '', item)
                print(f'replaced {item} with {new_item}')

                report[i] = new_item

        return report

    def populate_database_with_reports(self, form_data):
        cur = self.con.cursor()

        header = form_data[0]
        reports = form_data[1:]

        for report in reports:

            responses, idx_start = self.build_response_dict(header, report)
            record_id = self.build_record_id(report[2], report[1], report[3])

            clean_report = self.clean_up_report(report)

            # add transmitting station location from the Hams table if not given in the report
            if (len(report[6]) == 0) | (len(report[7]) == 0):
                command = f"SELECT * FROM Hams WHERE Call=\'{report[1]}\'"
                cur.execute(command)
                transmit_ham = cur.fetchone()

                if transmit_ham is not None:
                    report[6] = transmit_ham[2]
                    report[7] = transmit_ham[3]
                else:
                    print(f'problem with {command} in populate_database_with_reports')

            for call in responses.keys():
                command = "INSERT INTO RESPONSES(Id, ReportingTimestamp, SubmittingCall, DateOfNet, FrequencyOfNet," +\
                          " TransmitPower, TransmitHeight, SubmittedLatitude, SubmittedLongitude, Comment," +\
                          " ReceivedCall, ReceivedQuality)" +\
                          " VALUES ('{}', '{}', '{}', '{}', {}, '{}', '{}', '{}', '{}', '{}', '{}', '{}')".format(
                              record_id, clean_report[0], clean_report[1], clean_report[2], clean_report[3],
                              clean_report[4], clean_report[5], clean_report[6], clean_report[7], clean_report[8],
                              call, responses[call])
                try:
                    cur.execute(command)
                except sqlite3.Error as er:
                    print('SQLite error: %s' % (' '.join(er.args)))
                    print("Exception class is: ", er.__class__)
                    print('SQLite traceback: ')
                    exc_type, exc_value, exc_tb = sys.exc_info()
                    print(traceback.format_exception(exc_type, exc_value, exc_tb))

        self.con.commit()

    def __del__(self):
        self.con.close()

    def get_ham_locations(self):
        """Fetch ham location data from the database
        """
        # TODO with here may close the data file prematurely in normal operations
        with self.con:
            self.ham_locations_df = pd.read_sql("SELECT * from Hams", self.con)

        self.ham_locations_df['Latitude'] = self.ham_locations_df['Latitude'].astype('float')
        self.ham_locations_df['Longitude'] = self.ham_locations_df['Longitude'].astype('float')
        self.ham_locations_df = self.ham_locations_df.drop(columns='Id')

    def get_one_ham_reception_data(self, ham, frequency):
        """Fetch data from the database and arrange appropriately for mapping in a pandas dataframe
        """
        # TODO with here may close the data file prematurely in normal operations
        with self.con:
            command = f"SELECT * from RESPONSES WHERE (ReceivedCall ='{ham}' AND FrequencyOfNet ={frequency})"
            # print(command)
            df = pd.read_sql(command, self.con)

        return df

    @staticmethod
    def add_reception_scaled_value(df, scale):
        """Translate ARES reception string to a numeral appropriate to the plot's scale"""
        coding = {
            'N/A': None,
            'G/R': 4,
            'W/R': 2,
            'N/C': 0,
            '': None
        }

        n = []
        for s in df['ReceivedQuality']:
            if coding[s] is None:
                n.append(coding[s])
            else:
                n.append(coding[s] * scale)

        df['ReceivedQualityValue'] = n

        return df

    def wgs84_to_web_mercator(self, lon='Longitude', lat='Latitude'):
        """Convert decimal longitude/latitude to Web Mercator format
        """
        k = 6378137
        self.ham_locations_df["x"] = self.ham_locations_df[lon] * (k * np.pi / 180.0)
        self.ham_locations_df["y"] = np.log(np.tan((90 + self.ham_locations_df[lat]) * np.pi / 360.0)) * k

    # TODO this may be redundant since I now put the location of the reporting ham in the data file
    def add_received_locations(self, reception_df):
        """attach the locations of the submitting calls to the report information
        """
        lats = []
        lons = []
        x = []
        y = []
        for ham in reception_df['SubmittingCall']:
            try:
                lats.append(self.ham_locations_df.loc[(
                    self.ham_locations_df['Call'].isin([ham]))]['Latitude'].values[0])
                lons.append(self.ham_locations_df.loc[(
                    self.ham_locations_df['Call'].isin([ham]))]['Longitude'].values[0])
                x.append(self.ham_locations_df.loc[(self.ham_locations_df['Call'].isin([ham]))]['x'].values[0])
                y.append(self.ham_locations_df.loc[(self.ham_locations_df['Call'].isin([ham]))]['y'].values[0])
            except:
                print(f'{ham} missing from list of hams')
                lats.append(None)
                lons.append(None)
                x.append(None)
                y.append(None)

        reception_df['ReceivedLatitude'] = lats
        reception_df['ReceivedLongitude'] = lons
        reception_df['ReceivedX'] = x
        reception_df['ReceivedY'] = y

        return reception_df

    def initiate_map_plot_object(self, scale, extent_factor, title_string):
        """
        set up a map plot give a list of participating hams and their locations
        there should already be columns x, y for mercator projection
        """
        # set up the plot basics

        # setup for and acquire the background tile

        # Establishing a zoom scale for the map. The scale variable will also determine proportions
        # for hexbins and bubble maps so that everything looks visually appealing.
        x = self.ham_locations_df['x']
        y = self.ham_locations_df['y']

        # The range for the map extents is derived from the lat/lon fields. This way the map is
        # automatically centered on the plot elements.
        x_min = int(x.mean() - (scale * extent_factor))
        x_max = int(x.mean() + (scale * extent_factor))
        y_min = int(y.mean() - (scale * extent_factor))
        y_max = int(y.mean() + (scale * extent_factor))

        # Defining the map tiles to use. I use OSM, but you can also use ESRI images or google street maps.
        tile_provider = get_provider(OSM)

        # Establish the bokeh plot object and add the map tile as an underlay. Hide x and y axis.
        kwargs = {
            "title": title_string,
            "match_aspect": True,
            "tools": 'wheel_zoom,pan,reset,save',
            "x_range": (x_min, x_max),
            "y_range": (y_min, y_max),
            "x_axis_type": 'mercator',
            "y_axis_type": 'mercator',
            "width": 500
        }

        if title_string is not None:
            kwargs['title'] = title_string

        p = figure(**kwargs)

        p.grid.visible = True

        map_obj = p.add_tile(tile_provider)
        map_obj.level = 'underlay'

        p.xaxis.visible = False
        p.yaxis.visible = False

        if title_string is not None:
            p.title.text_font_size = "20px"

        return p

    def plot_station_reception(self,
                               transmitting_station,
                               frequency,
                               map_scale=500,
                               map_extent=150):
        """plot the reception of a specific ham on a specific frequency
        for all reports in the database
        :param str transmitting_station: station call sign
        :param float frequency:
        :param float map_scale:
        :param float map_extent:
        :return object: bokeh plot object
        """
        # get the reception data from the reports
        reception_df = self.get_one_ham_reception_data(transmitting_station, frequency)
        reception_df = self.add_reception_scaled_value(reception_df, map_scale)
        reception_df = self.add_received_locations(reception_df)

        # Create the base map and plot, do not add hover tool yet
        title_string = f'where {transmitting_station} was heard on {frequency}'

        p = self.initiate_map_plot_object(map_scale, map_extent, None)
        # p = self.initiate_map_plot_object(map_scale, map_extent, title_string)
        source_hamlist = ColumnDataSource(self.ham_locations_df)
        source_reports = ColumnDataSource(reception_df)

        # Create the glyphs by hand first

        # add the participating hams
        # g_hamlist = Circle(x='x', y='y', size=5)
        # g_hamlist_r = p.add_glyph(source_hamlist, g_hamlist)
        g_hamlist = Dot(x='x', y='y', size=10)
        g_hamlist_r = p.add_glyph(source_hamlist, g_hamlist)

        # add the reception information
        # g_reception = Circle(x='ReceivedX',y='ReceivedY', size=10, line_color='green',
        #                     fill_color='green', radius='ReceivedQualityValue')
        g_reception = Circle(x='ReceivedX', y='ReceivedY', size=10, line_color='green',
                             fill_color=None, radius='ReceivedQualityValue')
        g_reception_r = p.add_glyph(source_reports, g_reception)

        # add the transmitting ham
        x = self.ham_locations_df.loc[(self.ham_locations_df['Call'].isin([transmitting_station]))]['x'].values[0]
        y = self.ham_locations_df.loc[(self.ham_locations_df['Call'].isin([transmitting_station]))]['y'].values[0]
        g_transmitting = Asterisk(x=x, y=y, size=10, line_color='blue')
        g_transmitting_r = p.add_glyph(g_transmitting)

        # add text within the plot to save room
        # https://docs.bokeh.org/en/latest/docs/user_guide/layout.html#userguide-layout
        plot_label = Label(x=10, y=27, x_units='screen', y_units='screen', text=title_string,
                           render_mode='css',
                           background_fill_color='white', background_fill_alpha=1.0)

        # now add the over tool for this data, only for the participating hams
        g_hamlist_hover = HoverTool(renderers=[g_hamlist_r], tooltips=[('', '@Call')])
        p.add_tools(g_hamlist_hover)

        p.add_layout(Legend(items=[LegendItem(label='Station', renderers=[g_hamlist_r]),
                                   LegendItem(label='Reception', renderers=[g_reception_r]),
                                   LegendItem(label='Transmission', renderers=[g_transmitting_r])]))
        p.add_layout(plot_label)

        p.add_layout(Label(x=10, y=12, x_units='screen', y_units='screen',
                           text='circles: G/R large, W/R small', render_mode='css',
                           background_fill_color='white', background_fill_alpha=1.0))

        return p

    def plot_all_stations_to_html(self, frequency, html_path="index.html"):
        """make reception plots for all the stations in the Hams table
        """
        plot_list = []

        if os.path.exists(html_path):
            os.remove(html_path)

        for station in self.ham_locations_df['Call']:
            one_plot = self.plot_station_reception(station, frequency)
            plot_list.append(one_plot)

        output_file(html_path)

        print(f'generated plots for {len(self.ham_locations_df)} call signs')

        g = gridplot(plot_list, ncols=2, plot_width=400, plot_height=600)
        show(g)

