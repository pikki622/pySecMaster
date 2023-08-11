from datetime import datetime, timedelta
import operator
import pandas as pd
import time

from utilities.database_queries import delete_sql_table_rows, df_to_sql,\
    query_all_active_tsids, query_all_tsid_prices, query_source_weights,\
    query_data_vendor_id
from utilities.multithread import multithread

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


class CrossValidate:
    """ Compares the prices from multiple sources, storing the price with the
    highest consensus weight.
    """

    def __init__(self, database, user, password, host, port, table, tsid_list,
                 period=None, verbose=False):
        """
        :param database: String of the database name
        :param user: String of the username used to login to the database
        :param password: String of the password used to login to the database
        :param host: String of the database address (localhost, url, ip, etc.)
        :param port: Integer of the database port number (5432)
        :param table: String of the database table that should be worked on
        :param tsid_list: List of strings, with each string being a tsid
        :param period: Optional integer indicating the number of days whose
            values should be cross validated. If None is provided, then the
            entire set of values will be validated.
        :param verbose: Boolean of whether to print debugging statements or not
        """

        self.database = database
        self.user = user
        self.password = password
        self.host = host
        self.port = port
        self.table = table
        self.tsid_list = tsid_list
        self.period = period
        self.verbose = verbose

        # Build a DataFrame with the source id and weight
        self.source_weights_df = query_source_weights(
            database=self.database, user=self.user, password=self.password,
            host=self.host, port=self.port)

        self.source_id_exclude_list = []
        self.source_exclude_list = ['pySecMaster_Consensus']
        for source in self.source_exclude_list:
            source_id = query_data_vendor_id(
                database=self.database, user=self.user, password=self.password,
                host=self.host, port=self.port, name=source)
            self.source_id_exclude_list.append(source_id)

        if self.verbose:
            if self.period:
                print('Running cross validator for %s tsids only for the prior '
                      '%i day\'s history.' % (len(tsid_list), self.period))
            else:
                print(
                    f'Running cross validator for {len(tsid_list)} tsids for the entire data history.'
                )

        self.main()

    def main(self):
        """ Start the tsid cross validator process using either single or
        multiprocessing. """

        validator_start = time.time()

        # Cycle through each tsid, running the data cross validator on all
        #   sources and fields available.
        """No multiprocessing"""
        # [self.validator(tsid=tsid) for tsid in self.tsid_list]
        """Multiprocessing using 4 threads"""
        multithread(self.validator, self.tsid_list, threads=5)

        if self.verbose:
            print('%i tsids have had their sources cross validated taking '
                  '%0.2f seconds.' %
                  (len(self.tsid_list), time.time() - validator_start))

    def validator(self, tsid):

        tsid_start = time.time()

        # DataFrame of all stored prices for this ticker and interval. This is
        #   a multi-index DataFrame, with date and data_vendor_id in the index.
        tsid_prices_df = query_all_tsid_prices(
            database=self.database, user=self.user, password=self.password,
            host=self.host, port=self.port, table=self.table, tsid=tsid)

        unique_sources = tsid_prices_df.index.\
                get_level_values('data_vendor_id').unique()
        unique_dates = tsid_prices_df.index.get_level_values('date').unique()

        # If a period is provided, limit the unique_dates list to only those
        #   within the past n period days.
        if self.period:
            beg_date = datetime.now() - timedelta(days=self.period)
            unique_dates = unique_dates[unique_dates > beg_date]

        # The consensus_price_df contains the prices from weighted consensus
        if self.table == 'daily_prices':
            consensus_price_df = pd.DataFrame(
                columns=['date', 'open', 'high', 'low', 'close', 'volume',
                         'ex_dividend', 'split_ratio'])
        elif self.table == 'minute_prices':
            consensus_price_df = pd.DataFrame(
                columns=['date', 'open', 'high', 'low', 'close', 'volume'])
        else:
            raise NotImplementedError('Table %s is not implemented within '
                                      'CrossValidate.validator' % self.table)

        # Set the date as the index
        consensus_price_df.set_index(['date'], inplace=True)

        # Cycle through each period, comparing each data source's prices
        for date in unique_dates:

            # Either add each field's consensus price to a dictionary,
            #   which is entered into the consensus_price_df upon all fields
            #   being processed, or enter each field's consensus price directly
            #   into the consensus_price_df. Right now, this is doing the later.
            # consensus_prices = {}

            try:
                # Create a DataFrame for the current period, with the source_ids
                #   as the index and the data_columns as the column headers
                period_df = tsid_prices_df.xs(date, level='date')
            except KeyError:
                # Should never happen
                print('Unable to extract the %s period\'s prices from '
                      'the tsid_prices_df for %s' % (date, tsid))
            finally:
                # Transpose the period_df DataFrame so the source_ids are
                #   columns and the price fields are the rows
                period_df = period_df.transpose()

                # Cycle through each price field for this period's values
                for field_index, field_data in period_df.iterrows():
                    # field_index: string of the index name
                    # field_data: Pandas Series (always??) of the field data

                    # Reset the field consensus for every field processed
                    field_consensus = {}

                    # Cycle through each source's values that are in the
                    #   field_data Series.
                    for source_data in field_data.iteritems():
                        # source_data is a tuple, with the first item is being
                        #   the data_vendor_id and the second being the value.

                        # If the source_data's id is in the exclude list, don't
                        #   use its price when calculating the field consensus.
                        if source_data[0] not in self.source_id_exclude_list:

                            # Only process the source value if it is not None
                            if source_data[1] is not None:

                                # Retrieve weighted consensus for this source
                                source_weight = self.source_weights_df.loc[
                                    self.source_weights_df['data_vendor_id'] ==
                                    source_data[0], 'consensus_weight']

                                try:
                                    if (
                                        field_consensus
                                        and source_data[1] in field_consensus
                                    ):
                                        # This source's value has a match in
                                        #   the current consensus. Increase
                                        #   weight for this price.
                                        field_consensus[source_data[1]] += \
                                                source_weight.iloc[0]
                                    else:
                                        # Data value from the source does
                                        #   not match this field's consensus
                                        field_consensus[source_data[1]] = \
                                                source_weight.iloc[0]

                                except IndexError:
                                    # No source_weight was found, prob because
                                    #   there was no data_vendor_id for value
                                    pass

                    # Insert the highest consensus value for this period into
                    #   the consensus_price_df (the dictionary key (price) with
                    #   the largest value (consensus sum).
                    try:
                        consensus_value = max(field_consensus.items(),
                                              key=operator.itemgetter(1))[0]
                    except ValueError:
                        # None of the sources had any values, thus use -1
                        consensus_value = -1
                    consensus_price_df.ix[date, field_index] = consensus_value

        # Make the date index into a normal column
        consensus_price_df.reset_index(inplace=True)
        # Convert the datetime object to an ISO date
        consensus_price_df['date'] = consensus_price_df['date'].\
                apply(lambda x: x.isoformat())

        # Add the vendor id of the pySecMaster_Consensus as a column
        validator_id = query_data_vendor_id(
            database=self.database, user=self.user, password=self.password,
            host=self.host, port=self.port, name='pySecMaster_Consensus')

        consensus_price_df.insert(0, 'data_vendor_id', validator_id)
        consensus_price_df.insert(1, 'source', 'tsid')
        consensus_price_df.insert(2, 'source_id', tsid)

        # Add the current date to the last column
        consensus_price_df.insert(len(consensus_price_df.columns),
                                  'updated_date', datetime.now().isoformat())

        if validator_id in unique_sources:
            delete_start = time.time()

            # Data from the cross validation process has already been saved
            #   to the database before, thus it must be removed before adding
            #   the new calculated values.

            if self.period:
                # Only delete prior consensus values for this tsid that are
                #   newer than the beg_date (current date - replace period).
                delete_query = ("""DELETE FROM %s
                                   WHERE source_id='%s' AND source='tsid'
                                   AND data_vendor_id='%s'
                                   AND date>'%s'""" %
                                (self.table, tsid, validator_id,
                                 beg_date.isoformat()))
            else:
                # Delete all existing consensus values for this tsid.
                delete_query = ("""DELETE FROM %s
                                   WHERE source_id='%s' AND source='tsid'
                                   AND data_vendor_id='%s'""" %
                                (self.table, tsid, validator_id))

            retry_count = 5
            while retry_count > 0:
                retry_count -= 1

                delete_status = delete_sql_table_rows(
                    database=self.database, user=self.user,
                    password=self.password, host=self.host, port=self.port,
                    query=delete_query, table=self.table, item=tsid)
                if delete_status == 'success':
                    # Add the validated values to the relevant price table AFTER
                    #   ensuring that the duplicates were deleted successfully
                    df_to_sql(database=self.database, user=self.user,
                              password=self.password, host=self.host,
                              port=self.port, df=consensus_price_df,
                              sql_table=self.table, exists='append', item=tsid)
                    break

            # print('Data table replacement took %0.2f' %
            #       (time.time() - delete_start))

        else:
            # Add the validated values to the relevant price table
            df_to_sql(database=self.database, user=self.user,
                      password=self.password, host=self.host, port=self.port,
                      df=consensus_price_df, sql_table=self.table,
                      exists='append', item=tsid)

        # For period updates, slow down the process to allow postgre to catch up
        if self.period:
            time.sleep(1.5)

        if self.verbose:
            print('%s data cross-validation took %0.2f seconds to complete.' %
                  (tsid, time.time() - tsid_start))


if __name__ == '__main__':

    from utilities.user_dir import user_dir
    userdir = user_dir()

    test_table = 'daily_prices'

    test_tsids_df = query_all_active_tsids(
        database=userdir['postgresql']['pysecmaster_db'],
        user=userdir['postgresql']['pysecmaster_user'],
        password=userdir['postgresql']['pysecmaster_password'],
        host=userdir['postgresql']['pysecmaster_host'],
        port=userdir['postgresql']['pysecmaster_port'],
        table=test_table)
    test_tsid_list = test_tsids_df['tsid'].values

    CrossValidate(
        database=userdir['postgresql']['pysecmaster_db'],
        user=userdir['postgresql']['pysecmaster_user'],
        password=userdir['postgresql']['pysecmaster_password'],
        host=userdir['postgresql']['pysecmaster_host'],
        port=userdir['postgresql']['pysecmaster_port'],
        table=test_table,
        tsid_list=test_tsid_list, verbose=True)
