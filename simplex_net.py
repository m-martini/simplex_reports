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
   TODO how to handle adding and removing stations from the form and how does this affect the spreadsheet?
   TODO remove the hard wired sheet range
   TODO what to do with missing hams

"""
# from __future__ import print_function

import re
import os
import sys
import traceback
import math

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
    home_station_information_df = None

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

        self.read_all_base_station_information()
        self.wgs84_to_web_mercator()

    @staticmethod
    def remove_control_characters(s):
        return "".join(ch for ch in s if unicodedata.category(ch)[0] != "C")

    def read_station_information_file(self, station_information_file):
        hams = []  # will be a list of dicts
        infile = open(station_information_file, 'r')
        infile.readline()  # skip the header line 1
        infile.readline()  # skip the header line 2

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
            "CREATE TABLE RESPONSES (Id TEXT, ReportingTimestamp DATETIME, ReportingStation TINYTEXT, " +
            "DateOfNet DATE, FrequencyOfNet FLOAT, " +
            "TransmittingStation TINYTEXT, TransmittingStationPower TINYTEXT, TransmittingStationHeight TINYTEXT, " +
            "TransmittingStationLatitude FLOAT, TransmittingStationLongitude FLOAT, " +
            "ReceivingStation TINYTEXT, QSOQuality TINYTEXT, ReceivingStationHeight TINYTEXT, " +
            "ReceivingStationLatitude FLOAT, ReceivingStationLongitude FLOAT)"
        )

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
    def build_reception_dict(header, report):
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

        # only numerals in lat and lon please
        report[6] = re.sub('[Nn ]', '', report[6])
        report[7] = re.sub('[Ww ]', '', report[7])

        for i, item in enumerate(report):
            if '\'' in item:
                # remove any stray ' or " which will mess up the SQL command
                new_item = re.sub('[\'\"]', '', item)
                print(f'replaced {item} with {new_item}')

                report[i] = new_item

        return report

    def populate_database_with_reports(self, form_data):
        """report fields are as follows:
        0 Timestamp
        1 Call sign reporting
        2 Date of ARES simplex exercise
        3 Frequency used, MHz
        4 Transmit power, Watts (nearest value)	- of receiving station submitting the report
        5 Antenna height, feet above sea level - of receiving station submitting the report
        6 Latitude	 - of receiving station submitting the report
        7 Longitude	 - of receiving station submitting the report
        8 Comments - of receiving station submitting the report
        9 onwards are the reception quality of the call signs listed in the report form

        The reports are cycled through twice.  First to populate them into the database.
        The second time is to look up the transmitting station and update the power, height and location
        specific to each unique simplex net test, where there is a unique date, transmitting station and net frequency
        """
        cur = self.con.cursor()

        header = form_data[0]
        reports = form_data[1:]

        for report in reports:

            clean_report = self.clean_up_report(report)

            # takes the call signs of the header and pairs them with the reception quality in the report
            reception_ratings, idx_start = self.build_reception_dict(header, clean_report)
            record_id = self.build_record_id(clean_report[2], clean_report[1], clean_report[3])

            # add reporting (e.g. receiving) station location from the Hams table if not given in the report
            if (len(clean_report[6]) == 0) | (len(clean_report[7]) == 0):
                ham_info = self.get_one_base_station_information(clean_report[1])

                if ham_info is not None:
                    clean_report[6] = ham_info[2]
                    clean_report[7] = ham_info[3]

            for transmitting_station in reception_ratings.keys():
                # TODO the problem with this is it looks up the base station information, and does
                # not account for a ham that might be mobile
                ham_info = self.get_one_base_station_information(transmitting_station)

                if ham_info is None:
                    transmitting_station_latitude = None
                    transmitting_station_longitude = None
                else:
                    transmitting_station_latitude = ham_info[2]
                    transmitting_station_longitude = ham_info[3]

                command = "INSERT INTO RESPONSES (Id, ReportingTimestamp, ReportingStation, " +\
                          "DateOfNet, FrequencyOfNet, " +\
                          "TransmittingStation, TransmittingStationPower, TransmittingStationHeight, " +\
                          "TransmittingStationLatitude, TransmittingStationLongitude, " +\
                          "ReceivingStation, QSOQuality, ReceivingStationHeight, " +\
                          "ReceivingStationLatitude, ReceivingStationLongitude) " +\
                          "VALUES ('{}','{}','{}','{}',{},'{}','{}','{}','{}','{}','{}','{}','{}','{}','{}')".format(
                            record_id, clean_report[0], clean_report[1],
                            clean_report[2], clean_report[3],
                            transmitting_station, None, None,
                            transmitting_station_latitude, transmitting_station_longitude,
                            clean_report[1], reception_ratings[transmitting_station], clean_report[5],
                            clean_report[6], clean_report[7])

                try:
                    cur.execute(command)
                except sqlite3.Error as er:
                    print('SQLite error: %s' % (' '.join(er.args)))
                    print("Exception class is: ", er.__class__)
                    print('SQLite traceback: ')
                    exc_type, exc_value, exc_tb = sys.exc_info()
                    print(traceback.format_exception(exc_type, exc_value, exc_tb))
                    print(command)

        self.con.commit()

        # we go through the reports and update for transmit height and power,
        for report in reports:
            transmitting_station = report[1]
            transmit_power = report[4]
            transmit_height = report[5]

            ham_info = self.get_one_base_station_information(transmitting_station)
            if report[6] is None or report[6] == '' or report[6] == 0:
                transmit_latitude = ham_info[2]
            if report[7] is None or report[7] == '' or report[7] == 0:
                transmit_longitude = ham_info[3]

            # check location within a certain radius of base station
            if self.haversine((float(report[6]), float(report[6])), (ham_info[2], ham_info[3])) > 100:
                transmit_latitude = report[6]
                transmit_longitude = report[7]
            else:
                transmit_latitude = ham_info[2]
                transmit_longitude = ham_info[3]

            # find the reporting station amongst the transmitting stations for a given net date and net frequency
            command_str = "UPDATE RESPONSES SET " +\
                          "TransmittingStationPower=?, TransmittingStationHeight=?, " +\
                          "TransmittingStationLatitude=?, TransmittingStationLongitude=? " +\
                          "WHERE TransmittingStation=? AND DateOfNet=? AND FrequencyOfNet=?"

            try:
                cur.execute(command_str, (transmit_power, transmit_height, transmit_latitude, transmit_longitude,
                                          transmitting_station, report[2], report[3]))
            except sqlite3.Error as er:
                print('SQLite error: %s' % (' '.join(er.args)))
                print("Exception class is: ", er.__class__)
                print('SQLite traceback: ')
                exc_type, exc_value, exc_tb = sys.exc_info()
                print(traceback.format_exception(exc_type, exc_value, exc_tb))
                print(command_str)

        self.con.commit()

    def __del__(self):
        self.con.close()

    def read_all_base_station_information(self):
        # TODO with here may close the data file prematurely in normal operations
        with self.con:
            self.home_station_information_df = pd.read_sql("SELECT * from Hams", self.con)

        self.home_station_information_df['Latitude'] = self.home_station_information_df['Latitude'].astype('float')
        self.home_station_information_df['Longitude'] = self.home_station_information_df['Longitude'].astype('float')
        self.home_station_information_df = self.home_station_information_df.drop(columns='Id')

    def get_one_base_station_information(self, call):
        """fetch information for one or all stations"""
        cur = self.con.cursor()

        if call is not None:
            command = f"SELECT * FROM Hams WHERE Call=\'{call}\'"
            cur.execute(command)
            station_information = cur.fetchone()
        else:
            # TODO read them all might be useful
            station_information = None

        if station_information is None:
            pass
            # print(f'problem with {command} in get_base_station_information')

        # TODO use a dictionary to pass this information back
        return station_information

    def get_one_ham_reception_data(self, ham, frequency, net_date=None):
        """Fetch data from the database and arrange appropriately for mapping in a pandas dataframe
        """
        # TODO with here may close the data file prematurely in normal operations
        with self.con:
            if net_date is None:
                command = \
                    f"SELECT * from RESPONSES WHERE (TransmittingStation ='{ham}' AND FrequencyOfNet ={frequency})"
            else:
                command = \
                    f"SELECT * from RESPONSES WHERE (TransmittingStation ='{ham}' AND FrequencyOfNet ={frequency}" +\
                    f" AND DateOfNet = '{net_date})"

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
        for s in df['QSOQuality']:
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
        self.home_station_information_df["x"] = self.home_station_information_df[lon] * (k * np.pi / 180.0)
        self.home_station_information_df["y"] = \
            np.log(np.tan((90 + self.home_station_information_df[lat]) * np.pi / 360.0)) * k

    # noinspection SpellCheckingInspection
    @staticmethod
    def haversine(coord1, coord2):
        # thanks to https://janakiev.com/blog/gps-points-distance-python/
        r = 6372800  # Earth radius in meters
        lat1, lon1 = coord1
        lat2, lon2 = coord2

        try:
            phi1, phi2 = math.radians(lat1), math.radians(lat2)
        except TypeError as er:
            print(lat1, lat2)

        try:
            dphi = math.radians(lat2 - lat1)
        except TypeError as er:
            print(lat1, lat2)

        dlambda = math.radians(lon2 - lon1)

        a = math.sin(dphi / 2) ** 2 + \
            math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2

        return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    # TODO this may be redundant since I now put the location of the reporting ham in the data file
    def add_received_locations(self, reception_df):
        """attach the locations of the submitting calls to the report information
        """
        lats = []
        lons = []
        x = []
        y = []
        for ham in reception_df['ReportingStation']:
            try:
                lats.append(self.home_station_information_df.loc[(
                    self.home_station_information_df['Call'].isin([ham]))]['Latitude'].values[0])
                lons.append(self.home_station_information_df.loc[(
                    self.home_station_information_df['Call'].isin([ham]))]['Longitude'].values[0])
                x.append(self.home_station_information_df.loc[
                             (self.home_station_information_df['Call'].isin([ham]))]['x'].values[0])
                y.append(self.home_station_information_df.loc[
                             (self.home_station_information_df['Call'].isin([ham]))]['y'].values[0])
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
        x = self.home_station_information_df['x']
        y = self.home_station_information_df['y']

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
                               frequency, net_date=None,
                               map_scale=500,
                               map_extent=150):
        """plot the reception of a specific ham on a specific frequency
        for all reports in the database
        :param str transmitting_station: station call sign
        :param float frequency:
        :param str net_date: date of simplex net, mm/dd/yyyy
        :param float map_scale:
        :param float map_extent:
        :return object: bokeh plot object
        """
        # get the reception data from the reports
        reception_df = self.get_one_ham_reception_data(transmitting_station, frequency, net_date)
        reception_df = self.add_reception_scaled_value(reception_df, map_scale)
        reception_df = self.add_received_locations(reception_df)

        # Create the base map and plot, do not add hover tool yet
        title_string = f'where {transmitting_station} was heard on {frequency}'

        p = self.initiate_map_plot_object(map_scale, map_extent, None)
        # p = self.initiate_map_plot_object(map_scale, map_extent, title_string)
        source_hamlist = ColumnDataSource(self.home_station_information_df)
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
        x = self.home_station_information_df.loc[
            (self.home_station_information_df['Call'].isin([transmitting_station]))]['x'].values[0]
        y = self.home_station_information_df.loc[
            (self.home_station_information_df['Call'].isin([transmitting_station]))]['y'].values[0]
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

        for station in self.home_station_information_df['Call']:
            one_plot = self.plot_station_reception(station, frequency)
            plot_list.append(one_plot)

        output_file(html_path)

        print(f'generated plots for {len(self.home_station_information_df)} call signs')

        g = gridplot(plot_list, ncols=2, plot_width=400, plot_height=600)
        show(g)

