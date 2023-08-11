from datetime import datetime
import pandas as pd
import psycopg2
import re
import time

__author__ = 'Josh Schertz'
__copyright__ = 'Copyright (C) 2016 Josh Schertz'
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


def pull_daily_prices(database, user, password, host, port, query_type,
                      data_vendor_id, beg_date, end_date, source='tsid', *args):
    """ Query the daily prices from the database for the tsid provided between
    the start and end dates. Return a DataFrame with the prices.

    :param database: String of the database name
    :param user: String of the username used to login to the database
    :param password: String of the password used to login to the database
    :param host: String of the database address (localhost, url, ip, etc.)
    :param port: Integer of the database port number (5432)
    :param query_type: String of which query to run
    :param data_vendor_id: Integer of which data vendor id to return prices for
    :param beg_date: String of the ISO date to start with
    :param end_date: String of the ISO date to end with
    :param source: String of the ticker's source
    :return: DataFrame of the returned prices
    """

    conn = psycopg2.connect(database=database, user=user, password=password,
                            host=host, port=port)

    try:
        with conn:
            cur = conn.cursor()
            if query_type == 'ticker':
                tsid, = args
                print(f'Extracting the daily prices for {tsid}')

                cur.execute("""SELECT date, source_id AS tsid, open, high, low,
                                close, volume
                            FROM daily_prices
                            WHERE source_id=%s AND source=%s
                            AND data_vendor_id=%s
                            AND date>=%s AND date<=%s""",
                            (tsid, source, data_vendor_id, beg_date, end_date))

            elif query_type == 'index':
                index, as_of_date = args
                print(f'Extracting the daily prices for tickers in the {index}')

                cur.execute("""SELECT date, source_id AS tsid, open, high, low,
                                close, volume
                            FROM daily_prices
                            WHERE source_id IN (
                                SELECT source_id
                                FROM indices
                                WHERE stock_index=%s
                                AND as_of_date=%s)
                            AND source=%s
                            AND data_vendor_id=%s
                            AND date>=%s AND date<=%s""",
                            (index, as_of_date, source, data_vendor_id,
                             beg_date, end_date))

            else:
                raise NotImplementedError(
                    f'Query type {query_type} is not implemented within pull_daily_prices'
                )

            if rows := cur.fetchall():
                df = pd.DataFrame(rows,
                                  columns=['date', 'tsid', 'open', 'high',
                                           'low', 'close', 'volume'])
            else:
                raise SystemExit('No data returned from table query. Try '
                                 'adjusting the criteria for the query.')

            # The next two lines change the index of the df to be the date.
            df.set_index(['date'], inplace=True)
            df.index.name = ['date']

            df.sort_index(inplace=True)

            return df

    except psycopg2.Error as e:
        print('Error when trying to retrieve price data from the %s database '
              'in pull_daily_prices' % database)
        print(e)
    except conn.OperationalError:
        raise SystemError('Unable to connect to the %s database in '
                          'pull_daily_prices. Make sure the database '
                          'address/name are correct.' % database)
    except Exception as e:
        print(e)
        raise SystemError('Error: Unknown issue occurred in pull_daily_prices')


def pull_minute_prices(database, user, password, host, port, query_type,
                       data_vendor_id, beg_date, end_date, source='tsid',
                       *args):
    """ Query the minute prices from the database for the tsid provided between
    the start and end dates. Return a DataFrame with the prices.

    :param database: String of the database name
    :param user: String of the username used to login to the database
    :param password: String of the password used to login to the database
    :param host: String of the database address (localhost, url, ip, etc.)
    :param port: Integer of the database port number (5432)
    :param query_type: String of which query to run
    :param data_vendor_id: Integer of which data vendor id to return prices for
    :param beg_date: String of the ISO date to start with
    :param end_date: String of the ISO date to end with
    :param source: String of the source
    :param args:
    :return: DataFrame of the returned prices
    """

    conn = psycopg2.connect(database=database, user=user, password=password,
                            host=host, port=port)

    try:
        with conn:
            cur = conn.cursor()
            if query_type == 'ticker':
                tsid, = args
                print(f'Extracting the minute prices for {tsid}')

                cur.execute("""SELECT date, source_id AS tsid, open, high, low,
                                close, volume
                            FROM minute_prices
                            WHERE source_id=%s AND source=%s
                            AND data_vendor_id=%s
                            AND date>=%s AND date<=%s""",
                            (tsid, source, data_vendor_id, beg_date, end_date))
            else:
                raise NotImplementedError(
                    f'Query type {query_type} is not implemented within pull_minute_prices'
                )

            if rows := cur.fetchall():
                df = pd.DataFrame(rows,
                                  columns=['date', 'tsid', 'open', 'high',
                                           'low', 'close', 'volume'])
            else:
                raise SystemExit('No data returned from table query. Try '
                                 'adjusting the criteria for the query.')

            # The next two lines change the index of the df to be the date.
            df.set_index(['date'], inplace=True)
            df.index.name = ['date']

            df.sort_index(inplace=True)

            return df

    except psycopg2.Error as e:
        print('Error when trying to retrieve price data from the %s database '
              'in pull_minute_prices' % database)
        print(e)
    except conn.OperationalError:
        raise SystemError('Unable to connect to the %s database in '
                          'pull_minute_prices. Make sure the database '
                          'address/name are correct.' % database)
    except Exception as e:
        print(e)
        raise SystemError('Error: Unknown issue occurred in pull_minute_prices')


if __name__ == '__main__':

    from utilities.user_dir import user_dir

    userdir = user_dir()

    test_database = userdir['postgresql']['pysecmaster_db']
    test_user = userdir['postgresql']['pysecmaster_user']
    test_password = userdir['postgresql']['pysecmaster_password']
    test_host = userdir['postgresql']['pysecmaster_host']
    test_port = userdir['postgresql']['pysecmaster_port']

    test_tsid = 'AAPL.Q.0'
    test_data_vendor_id = 15        # pySecMaster_Consensus
    # test_data_vendor_id = 12        # Google_Finance
    test_beg_date = '1950-01-01 00:00:00'
    test_end_date = '2018-12-30 00:00:00'
    frequency = 'daily'    # daily, minute

    # NOTE: Background code not implemented yet
    test_index = 'S&P 500'  # 'S&P 500', 'Russell Midcap', 'Russell 2000'
    test_as_of_date = '2015-01-01'

    start_time = time.time()
    test_query_type = 'ticker'
    if test_query_type == 'index':
        prices_df = pull_daily_prices(test_database, test_user,
                                      test_password, test_host, test_port,
                                      test_query_type, test_beg_date,
                                      test_end_date, test_index,
                                      test_as_of_date)

    elif test_query_type == 'ticker':
        if frequency == 'daily':
            prices_df = pull_daily_prices(test_database, test_user,
                                          test_password, test_host, test_port,
                                          test_query_type, test_data_vendor_id,
                                          test_beg_date, test_end_date,
                                          'tsid', test_tsid)

        elif frequency == 'minute':
            prices_df = pull_minute_prices(test_database, test_user,
                                           test_password, test_host, test_port,
                                           test_query_type, test_data_vendor_id,
                                           test_beg_date, test_end_date,
                                           'tsid', test_tsid)

        else:
            raise NotImplementedError(
                f'Frequency {frequency} is not implemented within query_data.py'
            )

    else:
        raise NotImplementedError(
            f'Query type {test_query_type} is not implemented within query_data.py'
        )

    csv_friendly_tsid = re.sub('[.]', '_', test_tsid)
    print('Query took %0.2f seconds' % (time.time() - start_time))
    print(prices_df)
    #prices_df.to_csv('output/%s_%s_%s.csv' %
    #                 (csv_friendly_tsid, frequency,
    #                  datetime.today().strftime('%Y%m%d')))

    unique_codes = pd.unique((prices_df['tsid']).values)
    print('There are %i unique tsid codes' % (len(unique_codes)))
    print('There are %s rows' % ('{:,}'.format(len(prices_df.index))))
    print(datetime.now().strftime('%Y%m%d'))
