#!/usr/bin/env python3

import argparse
from datetime import datetime
import time

from create_tables import create_database, main_tables, data_tables,\
    events_tables
from extractor import QuandlCodeExtract, QuandlDataExtraction,\
    GoogleFinanceDataExtraction, YahooFinanceDataExtraction, CSIDataExtractor,\
    NASDAQSectorIndustryExtractor
from load_aux_tables import LoadTables
from build_symbology import create_symbology
from cross_validator import CrossValidate
from utilities.database_queries import query_all_active_tsids
from utilities.user_dir import user_dir
from utilities.database_check import postgres_test

__author__ = 'Josh Schertz'
__copyright__ = 'Copyright (C) 2018 Josh Schertz'
__description__ = 'An automated system to store and maintain financial data.'
__email__ = 'josh[AT]joshschertz[DOT]com'
__license__ = 'GNU AGPLv3'
__maintainer__ = 'Josh Schertz'
__status__ = 'Development'
__url__ = 'https://joshschertz.com/'
__version__ = '1.4.3'

'''
This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as
published by the Free Software Foundation, either version 3 of the
License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''

''' pySecMaster.py

This manages the pysecmaster database. It should be run daily as a maximum.

Database maintenance tasks:
    Creates the tables in the database.
    Loads auxiliary tables from included CSV files.
    Downloads all available Quandl Codes for the Quandl Databases selected.
    Downloads the specified CSI Data factsheet (stocks, commodities).
    Creates the symbology table which establishes a unique code for every
        item in the database, along with translating different source's codes

Database data download tasks:
    Downloads Quandl data based on the download selection criteria using either
        the official Quandl Codes or implied codes from CSI Data.
    Downloads Google Finance minute stock data.
    Can either append only the new data, or replace part of the existing data.
'''

###############################################################################
# Database maintenance options:

userdir = user_dir()

csidata_type = 'stock'      # stock, commodity

# Don't change these unless you know what you are doing
database_url = ['https://www.quandl.com/api/v2/datasets.csv?query=*&'
                'source_code=', '&per_page=300&page=']
# http://www.csidata.com/factsheets.php?type=stock&format=html
csidata_url = 'http://www.csidata.com/factsheets.php?'
tables_to_load = ['data_vendor', 'exchanges']

nasdaq_sector_industry_url = 'http://www.nasdaq.com/screening/' \
                             'companies-by-industry.aspx?'
nasdaq_sector_industry_extractor_exchanges = ['NASDAQ', 'NYSE', 'AMEX']
nasdaq_sector_industry_redownload_time = 7

###############################################################################
# Database data download options:

today = datetime.now()

# Don't change these variables unless you know what you are doing!
quandl_data_url = ['https://www.quandl.com/api/v1/datasets/', '.csv']

google_fin_url = {'root': 'http://www.google.com/finance/getprices?',
                  'ticker': 'q=',
                  'exchange': 'x=',
                  'interval': 'i=',   # 60; 60 seconds is the shortest interval
                  # 'sessions': 'sessions=ext_hours',
                  'period': 'p=',    # 20d; 15d is the longest period for min
                  'fields': 'f=d,c,v,o,h,l'}    # order doesn't change anything

yahoo_end_date = (
    f'd={str(int(today.month - 1)).zfill(2)}&e={today.day}&f={today.year}'
)
yahoo_fin_url = {'root': 'http://real-chart.finance.yahoo.com/table.csv?',
                 'ticker': 's=',    # Exchange is added after ticker and '.'
                 'interval': 'g=',  # d, w, m, v: (daily, wkly, mth, dividends)
                 'start_date': 'a=00&b=1&c=1900',   # The entire price history
                 'end_date': yahoo_end_date,    # Today's date (MM; D; YYYY)
                 'csv': 'ignore=.csv'}      # Returns a CSV file
###############################################################################


def maintenance(database_options, quandl_key, quandl_ticker_source,
                database_list, threads, quandl_update_range,
                csidata_update_range, symbology_sources):
    """
    :param database_options: Dictionary of the postgres database options
    :param quandl_key: Optional string of the Quandl API key
    :param quandl_ticker_source: String of which source the Quandl data should
        use when determining which codes to download (csidata, quandl)
    :param database_list: List of strings indicating which Quandl databases
        should have their codes downloaded (WIKI, GOOG, YAHOO)
    :param threads: Integer of the threads to run when downloading Quandl codes
    :param quandl_update_range: Integer of the number of days before the
        Quandl codes should be updated
    :param csidata_update_range: Integer of the number of days before the CSI
        Data factsheet should be updated
    :param symbology_sources: List of strings of which symbology sources
        should be created (csi_data, tsid, quandl_wiki)
    """

    print('Starting Security Master table maintenance function. This can take '
          'some time to finish if large databases are used. If this fails, '
          'rerun it after a few minutes.')

    # Create the SQL tables if they don't already exist
    create_database(admin_user=database_options['admin_user'],
                    admin_password=database_options['admin_password'],
                    database=database_options['database'],
                    user=database_options['user'])
    main_tables(database=database_options['database'],
                user=database_options['user'],
                password=database_options['password'],
                host=database_options['host'],
                port=database_options['port'])
    data_tables(database=database_options['database'],
                user=database_options['user'],
                password=database_options['password'],
                host=database_options['host'],
                port=database_options['port'])
    events_tables(database=database_options['database'],
                  user=database_options['user'],
                  password=database_options['password'],
                  host=database_options['host'],
                  port=database_options['port'])

    LoadTables(database=database_options['database'],
               user=database_options['user'],
               password=database_options['password'],
               host=database_options['host'],
               port=database_options['port'],
               tables_to_load=tables_to_load,
               load_tables=userdir['load_tables'])

    # Always extract CSI values, as they are used for the symbology table
    CSIDataExtractor(database=database_options['database'],
                     user=database_options['user'],
                     password=database_options['password'],
                     host=database_options['host'],
                     port=database_options['port'],
                     db_url=csidata_url,
                     data_type=csidata_type,
                     redownload_time=csidata_update_range)

    if quandl_ticker_source == 'quandl':
        QuandlCodeExtract(database=database_options['database'],
                          user=database_options['user'],
                          password=database_options['password'],
                          host=database_options['host'],
                          port=database_options['port'],
                          quandl_token=quandl_key,
                          database_list=database_list,
                          database_url=database_url,
                          update_range=quandl_update_range,
                          threads=threads)

    create_symbology(database=database_options['database'],
                     user=database_options['user'],
                     password=database_options['password'],
                     host=database_options['host'],
                     port=database_options['port'],
                     source_list=symbology_sources)

    NASDAQSectorIndustryExtractor(
        database=database_options['database'],
        user=database_options['user'],
        password=database_options['password'],
        host=database_options['host'],
        port=database_options['port'],
        db_url=nasdaq_sector_industry_url,
        exchange_list=nasdaq_sector_industry_extractor_exchanges,
        redownload_time=nasdaq_sector_industry_redownload_time)


def data_download(database_options, quandl_key, download_list, threads=4,
                  verbose=False):
    """ Loops through all provided data sources in download_list, and runs
    the associated data extractor using the provided source variables.

    :param database_options: Dictionary of the postgres database options
    :param quandl_key: Optional string of the Quandl API key
    :param download_list: List of dictionaries, with each dictionary containing
        all of the relevant variables for the specific source
    :param threads: Integer indicating how many threads should be used to
        concurrently download data
    :param verbose: Boolean of whether debugging prints should occur.
    """

    for source in download_list:
        if source['interval'] == 'daily':
            table = 'daily_prices'
            if source['source'] == 'google':
                google_fin_url['interval'] = f'i={str(60 * 60 * 24)}'
            elif source['source'] == 'yahoo':
                yahoo_fin_url['interval'] = 'g=d'
        elif source['interval'] == 'minute':
            table = 'minute_prices'
            if source['source'] == 'google':
                google_fin_url['interval'] = 'i=60'
            elif source['source'] == 'yahoo':
                raise SystemError('Yahoo Finance does not provide minute data.')
        else:
            raise SystemError('No interval was provided for %s in '
                              'data_download in pySecMaster.py' %
                              source['interval'])

        if source['source'] == 'quandl':
            if quandl_key:
                # Download data for selected Quandl codes
                print('\nDownloading all Quandl fields for: %s'
                      '\nNew data will %s the prior %s day\'s data' %
                      (source['selection'], source['data_process'],
                       source['replace_days_back']))
                # NOTE: Quandl only allows a single concurrent download with
                #   their free account
                QuandlDataExtraction(
                    database=database_options['database'],
                    user=database_options['user'],
                    password=database_options['password'],
                    host=database_options['host'],
                    port=database_options['port'],
                    quandl_token=quandl_key,
                    db_url=quandl_data_url,
                    download_selection=source['selection'],
                    redownload_time=source['redownload_time'],
                    data_process=source['data_process'],
                    days_back=source['replace_days_back'],
                    threads=1,
                    table=table,
                    load_tables=userdir['load_tables'],
                    verbose=verbose)
            else:
                print('\nNot able to download Quandl data for %s because '
                      'there was no Quandl API key provided.' %
                      (source['selection'],))

        elif source['source'] == 'google':
            # Download data for selected Google Finance codes
            print('\nDownloading all Google Finance fields for: %s'
                  '\nNew data will %s the prior %s day\'s data' %
                  (source['selection'], source['data_process'],
                   source['replace_days_back']))

            google_fin_url['period'] = 'p=' + str(source['period']) + 'd'
            GoogleFinanceDataExtraction(
                database=database_options['database'],
                user=database_options['user'],
                password=database_options['password'],
                host=database_options['host'],
                port=database_options['port'],
                db_url=google_fin_url,
                download_selection=source['selection'],
                redownload_time=source['redownload_time'],
                data_process=source['data_process'],
                days_back=source['replace_days_back'],
                threads=threads,
                table=table,
                load_tables=userdir['load_tables'],
                verbose=verbose)

        elif source['source'] == 'yahoo':
            # Download data for selected Google Finance codes
            print('\nDownloading all Yahoo Finance fields for: %s'
                  '\nNew data will %s the prior %s day\'s data' %
                  (source['selection'], source['data_process'],
                   source['replace_days_back']))

            YahooFinanceDataExtraction(
                database=database_options['database'],
                user=database_options['user'],
                password=database_options['password'],
                host=database_options['host'],
                port=database_options['port'],
                db_url=yahoo_fin_url,
                download_selection=source['selection'],
                redownload_time=source['redownload_time'],
                data_process=source['data_process'],
                days_back=source['replace_days_back'],
                threads=threads,
                table=table,
                load_tables=userdir['load_tables'],
                verbose=verbose)

        else:
            print(
                f"The {source['source']} source is currently not implemented. Skipping it."
            )

    print(f'All available data values have been downloaded for: {download_list}')


def post_download_maintenance(database_options, download_list, period=None,
                              verbose=False):
    """ Perform tasks that require all data to be downloaded first, such as the
    source cross validator function.

    :param database_options: Dictionary of the postgres database options
    :param download_list: List of dictionaries, with each dictionary containing
        all of the relevant variables for the specific source
    :param period: Optional integer indicating the prior number of days whose
            values should be cross validated. If None is provided, then the
            entire set of values will be validated.
    :param verbose: Boolean of whether debugging prints should occur.
    """

    intervals = {}
    for source in download_list:
        if source['interval'] == 'daily':
            intervals['daily_prices'] = True
        elif source['interval'] == 'minute':
            print('The cross validator for minute prices is disabled because '
                  'there is currently only one source (Google Finance). Thus, '
                  'it does not make sense to run it. When you add a second '
                  'source you can re-enable it by un-commenting out the line '
                  'below this message in post_download_maintenance within '
                  'pySecMaster.py')
            # intervals['minute_prices'] = True
        else:
            raise SystemError('No interval was provided for %s in '
                              'data_download in pySecMaster.py' %
                              source['interval'])

    for key, value in intervals.items():
        # The key is the table name to process
        table = key

        if verbose:
            print(f'Starting cross validator for {table}')

        tsids_df = query_all_active_tsids(
            database=database_options['database'],
            user=database_options['user'],
            password=database_options['password'],
            host=database_options['host'],
            port=database_options['port'],
            table=table,
            period=period)
        tsid_list = tsids_df['tsid'].values

        CrossValidate(
            database=database_options['database'],
            user=database_options['user'],
            password=database_options['password'],
            host=database_options['host'],
            port=database_options['port'],
            table=table, tsid_list=tsid_list, period=period, verbose=verbose)


if __name__ == '__main__':

    # Establish the argument parser
    parser = argparse.ArgumentParser(
        description='The pySecMaster is an automated financial securities '
                    'master framework. Currently, NYSE and NASDAQ securities '
                    'will have their daily prices loaded into the database. '
                    'Additional data can be integrated with the system, '
                    'including minute prices, option chain values, tick '
                    'values, corporate events (splits, dividends, IPOs), '
                    'and fundamental data.'
    )

    # Optional arguments
    parser.add_argument('--csidata-update-range', type=int,
        default=7,
        help='Number of days before the data will be refreshed.')
    parser.add_argument('--daily-downloads', type=str, nargs='*',
        default=['quandl', 'yahoo', 'google'],
        help='Sources whose daily prices will be downloaded. By default, '
             'quandl, yahoo and google daily prices will be downloaded.')
    parser.add_argument('--database-list', type=str, nargs='+',
        default=['WIKI'],
        help='The Quandl databases that will have their codes downloaded. '
             'Provide selections one after the other without quotes. Options '
             'include: WIKI, GOOG, YAHOO, SEC, EIA, JODI, CURRFX, FINRA.')
    parser.add_argument('--minute-downloads', type=str, nargs='*',
        help='Sources whose minute prices will be downloaded. Only google '
             'is implemented right now. By default, no minute prices are '
             'downloaded.')
    parser.add_argument('--quandl-update-range', type=int,
        default=30,
        help='Number of days before the ticker tables will be refreshed. If '
             'the database was not completely downloaded within this range, '
             'the remainder of the codes will attempt to be downloaded.')
    parser.add_argument('--quandl-ticker-source', type=str,
        choices=['quandl', 'csidata'], default='csidata',
        help='Determines the extractor should get the ticker codes for when '
             'downloading Quandl data. Options include using the official list '
             'from Quandl (quandl), or make implied codes from the CSI data '
             'stock factsheet (csidata) which is more accurate but tries more '
             'non-existent tickers.')
    parser.add_argument('--symbology-sources', type=str, nargs='+',
        default = ['csi_data', 'tsid', 'quandl_wiki', 'quandl_goog',
                   'seeking_alpha', 'yahoo'],
        help='Sources that will be integrated into the symbology table, '
             'including have symbology specific identifiers created and '
             'being linked with other sources symbology identifiers for the '
             'same underlying item. The following sources are used by default: '
             'csi_data, tsid, quandl_wiki, quandl_goog, seeking_alpha, yahoo. '
             'Ommitting key sources may break the system. Provide selections '
             'one after the other without quotes.')
    parser.add_argument('-t', '--threads', type=int,
        help='Number of threads to allocate to the system. The total system '
             'cores are used by default.')
    parser.add_argument('--validator-period', type=int,
        help='Prior number of days whose values should be cross validated, '
             'with 30 being a good option. If no value is provided, the '
             'entire period will be validated.')
    parser.add_argument('-v', '--verbose',
        action='store_true',
        help='Print out the status of the system.')

    # Retrieve the arguments
    args = parser.parse_args()

    ############################################################################
    # Database maintenance options:

    test_database_options = {
        'admin_user': userdir['postgresql']['main_user'],
        'admin_password': userdir['postgresql']['main_password'],
        'database': userdir['postgresql']['pysecmaster_db'],
        'user': userdir['postgresql']['pysecmaster_user'],
        'password': userdir['postgresql']['pysecmaster_password'],
        'host': userdir['postgresql']['pysecmaster_host'],
        'port': userdir['postgresql']['pysecmaster_port'],
    }

    test_quandl_key = userdir['quandl']['quandl_token']
    ############################################################################
    # Database data download options:

    # TODO: Move these parameters to a config file
    # Example download list: should be a list of dictionaries, with the
    #   dictionaries containing all relevant variables for the specific source
    test_download_list = [
        # Quandl WIKI daily data with wiki
        {'source': 'quandl', 'selection': 'wiki', 'interval': 'daily',
         'redownload_time': 60 * 60 * 12, 'data_process': 'replace',
         'replace_days_back': 60},
        # Yahoo Fin daily data with us_main - 9300 seconds (2.58 hours)
        {'source': 'yahoo', 'selection': 'us_main', 'interval': 'daily',
         'redownload_time': 60 * 60 * 12, 'data_process': 'replace',
         'replace_days_back': 60},
        # Google daily data with us_main_no_end_date (max of 50 day's prices)
        {'source': 'google', 'selection': 'us_main_no_end_date',
         'interval': 'daily', 'period': 60, 'redownload_time': 60 * 60 * 12,
         'data_process': 'replace', 'replace_days_back': 10},
        # Google minute data with us_main (max of 15 day's prices)
        {'source': 'google', 'selection': 'us_main', 'interval': 'minute',
         'period': 20, 'redownload_time': 60 * 60 * 12,
         'data_process': 'replace', 'replace_days_back': 10}
    ]

    # source: String of which data provider should have their data downloaded
    # selection: String of which data from the source should be downloaded. To
    #   understand what is actually being downloaded, go to the query_q_codes
    #   method in either the QuandlDataExtraction class or the
    #   GoogleFinanceDataExtraction class in extractor.py, and look at the
    #   SQLite queries. (Quandl: 'wiki', 'goog', 'goog_us_main',
    #   'goog_us_main_no_end_date', 'goog_us_canada_london', 'goog_etf';
    #   Google: 'all', 'us_main', 'us_main_no_end_date', 'us_canada_london')
    # interval: String of what interval the data should be in (daily or minute).
    # period: Integer of how many day's data should be downloaded (Google
    #   finance only). Minute data only has data back 15 days, and daily data
    #   only has data back 50 days.
    # redownload_time: Integer representing time in seconds before the data is
    #   allowed to be re-downloaded. Allows the system to be restarted without
    #   downloading the same data again.
    # data_process: String of how the new data will interact with the existing
    #   data ('replace': replace the prior x days of data (replace_days_back);
    #   'append': append the latest data to the existing data (will ignore
    #   replace_days_back variable). 'append' requires less system resources
    #   since it only adds new values, instead of deleting overlapping values.
    # replace_days_back: Integer of the number of days whose existing data
    #   should be replaced by new data (50000 replaces all existing data). Due
    #   to weekends, the days replaced may differ depending on what day this
    #   function is run
    ############################################################################

    download_list = []
    if args.daily_downloads or args.minute_downloads:
        for source in test_download_list:
            if args.daily_downloads and \
                    source['source'] in args.daily_downloads and \
                    source['interval'] == 'daily':
                download_list.append(source)
            if args.minute_downloads and \
                    source['source'] in args.minute_downloads and \
                    source['interval'] == 'minute':
                download_list.append(source)

    if args.threads:
        threads = args.threads
    else:
        import multiprocessing
        threads = multiprocessing.cpu_count()

    # Try connecting to the postgres database
    while True:
        if db_available := postgres_test(
            database_options=test_database_options
        ):
            print(f"{test_database_options['database']} database is available")
            break
        else:
            print(f"{test_database_options['database']} database is unavailable")
            time.sleep(1)

    maintenance(database_options=test_database_options,
                quandl_key=test_quandl_key,
                quandl_ticker_source=args.quandl_ticker_source,
                database_list=args.database_list,
                threads=threads,
                quandl_update_range=args.quandl_update_range,
                csidata_update_range=args.csidata_update_range,
                symbology_sources=args.symbology_sources)

    if download_list:
        data_download(database_options=test_database_options,
                      quandl_key=test_quandl_key,
                      download_list=download_list,
                      threads=threads,
                      verbose=args.verbose)
        # 15 hours for complete build; adds ~6 GB
        post_download_maintenance(database_options=test_database_options,
                                  download_list=download_list,
                                  period=args.validator_period,
                                  verbose=args.verbose)
    else:
        print('No download sources were specified for either the daily data '
              'or the minute data, therefore no prices will be downloaded nor '
              'will the post download maintenance functions be run.')

    print(datetime.now())
