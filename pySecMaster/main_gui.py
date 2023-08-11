import inspect
from PyQt4 import QtGui, QtCore, uic
import os.path
from queue import Queue
import sys

# Required to use resource file icons
# Compile the qrc file in terminal "pyrcc4.exe -py3 'icons.qrc' -o 'icon_rc.py'"
from icon_rc import *

from pySecMaster import maintenance, data_download

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


class MainWindow(QtGui.QMainWindow):

    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent)

        # Set the default name of the ini file; used to load/save GUI settings
        self.ini_name = 'pySecMaster_gui.ini'

        # Load the GUI structure from the ui file
        uic.loadUi('main_gui.ui', self)

        # Establish all menu bar connections
        self.actionLoad_Settings.triggered.connect(lambda: self.select_restore())
        self.actionSave_Settings.triggered.connect(lambda: self.save_settings(self.ini_name))
        self.actionStart.triggered.connect(self.process)
        self.actionExit.triggered.connect(lambda: self.confirm_close(self.ini_name))
        self.actionPySecMaster.triggered.connect(lambda: self.open_url('https://github.com/camisatx/pySecMaster'))
        self.actionCSI_Data.triggered.connect(lambda: self.open_url('http://www.csidata.com/'))
        self.actionGoogle_Finance.triggered.connect(lambda: self.open_url('https://www.google.com/finance'))
        self.actionQuandl.triggered.connect(lambda: self.open_url('https://www.quandl.com/'))
        self.actionInstall_PostgreSQL.triggered.connect(lambda: self.open_url('http://www.postgresql.org/download/'))
        self.actionInstall_Psycopg.triggered.connect(lambda: self.open_url('http://initd.org/psycopg/docs/install.html'))
        self.actionJosh_Schertz.triggered.connect(lambda: self.open_url('https://joshschertz.com/'))

        # Establish all form button connections
        self.toolbtn_details.clicked.connect(self.txtbrwsr_details_toggle)
        self.btnbox_action.button(self.btnbox_action.Ok).\
            clicked.connect(self.process)
        self.btnbox_action.button(self.btnbox_action.Abort).\
            clicked.connect(self.worker_finished)
        self.btnbox_action.button(self.btnbox_action.Cancel).\
            clicked.connect(lambda: self.confirm_close(self.ini_name))

        # Set the default items for 'Quandl Databases'
        quandl_databases_index = self.cmb_tickers_quandl_db.findText('WIKI')
        self.cmb_tickers_quandl_db.setCurrentIndex(quandl_databases_index)

        # Hide the data fields if data won't be downloaded for them
        self.data_provider_toggle()
        # If 'Download Source' (Data tab) is changed, re-run the
        # data_provider_toggle method to re-process items
        self.cmb_data_source.currentIndexChanged.\
            connect(self.data_provider_toggle)
        self.cmb_data_source.currentIndexChanged.\
            connect(self.data_selection_toggle)

        # Modify the combobox items of 'Selection' (Data tab) to make sure it
        # only shows valid options.
        self.data_selection_toggle()

        # Hide the details text browser by default
        # ToDo: Doesn't hide at startup; .isVisible() always returned 'False'
        self.txtbrwsr_details_toggle()

        # Hide the Abort button; only show when pySecMaster function is running
        self.btnbox_action.button(self.btnbox_action.Abort).hide()
        # Change the default name from 'Abort' to 'Stop'
        self.btnbox_action.button(self.btnbox_action.Abort).setText('Stop')

        # ToDo: Integrate the progress bar
        self.progressBar.hide()

        # Load the prior settings if a ini files exists
        if os.path.isfile(self.ini_name):
            self.restore_settings(self.ini_name)

    def closeEvent(self, event):
        """
        closeEvent method is called when the user clicks window close button

        :param event: A default system variable specifying a user action (exit)
        """

        self.confirm_close(self.ini_name, event)

    def confirm_close(self, ini_name, event=None):
        """
        Popup message box requiring user consent to close program

        :param ini_name: String of the name of the ini file to save the
            settings to
        :param event: A Qt object that is only used via the closeEvent method
        """

        reply = QtGui.QMessageBox.question(self, 'Confirm Exit',
                                           'Do you want to save the current '
                                           'settings?',
                                           QtGui.QMessageBox.Yes |
                                           QtGui.QMessageBox.No |
                                           QtGui.QMessageBox.Cancel,
                                           QtGui.QMessageBox.Yes)

        if event:
            # Request originated from the closeEvent method
            if reply == QtGui.QMessageBox.Yes:
                self.save_settings(ini_name)
                event.accept()
            elif reply == QtGui.QMessageBox.No:
                event.accept()
            else:
                event.ignore()
        elif reply == QtGui.QMessageBox.Yes:
            self.save_settings(ini_name)
            sys.exit()
        elif reply == QtGui.QMessageBox.No:
            sys.exit()

    def data_provider_toggle(self):
        """
        Hides the data fields if the data won't be downloaded for them.
        """

        provider_selected = self.cmb_data_source.currentText()

        # The default interval is daily; all sources have daily data.
        intervals = ['daily']

        if provider_selected in ['google', 'yahoo']:
            # Downloading Google or Yahoo Finance data; hide Quandl options
            self.lbl_quandlkey.hide()
            self.lineedit_quandlkey.hide()
            self.lbl_tickers_quandl.hide()
            self.cmb_tickers_quandl.hide()
            self.lbl_tickers_quandl_db.hide()
            self.cmb_tickers_quandl_db.hide()

            # Set the data interval
            self.cmb_data_interval.clear()
            if provider_selected == 'google':
                google_intervals = ['daily', 'minute']
                self.cmb_data_interval.addItems(google_intervals)
            else:
                self.cmb_data_interval.addItems(intervals)
            self.cmb_data_interval.setCurrentIndex(0)
        elif provider_selected == 'quandl':
            # Downloading quandl data; hide all Google Fin options
            self.lbl_quandlkey.show()
            self.lineedit_quandlkey.show()
            self.lbl_tickers_quandl.show()
            self.cmb_tickers_quandl.show()
            self.lbl_tickers_quandl_db.show()
            self.cmb_tickers_quandl_db.show()

            # Set the data interval
            self.cmb_data_interval.clear()
            self.cmb_data_interval.addItems(intervals)
            self.cmb_data_interval.setCurrentIndex(0)

        else:
            raise NotImplementedError('%s is not implemented in the '
                                      'data_provider_toggle function within '
                                      'main_gui.py' % provider_selected)

    def data_selection_toggle(self):
        """
        Modify the combobox items of 'Selection' (Data tab) to make sure it
        only shows valid options. Each one of these options has explicit SQL
        queries established in the database_queries.query_codes function.
        """

        # The selected provider
        provider_selected = self.cmb_data_source.currentText()

        yahoo_default_selection = 2

        quandl_possible_selections = ['wiki', 'goog', 'goog_us_main',
                                      'goog_us_main_no_end_date',
                                      'goog_us_canada_london']
        quandl_default_selection = 0

        self.cmb_data_selection.clear()
        yahoo_fin_possible_selections = [
            'all',
            'us_main',
            'us_main_no_end_date',
            'us_canada_london',
        ]
        if provider_selected == 'google':
            # The data selections for the currently selected data provider.
            google_fin_possible_selections = ['all', 'us_main',
                                              'us_main_no_end_date',
                                              'us_canada_london']
            self.cmb_data_selection.addItems(google_fin_possible_selections)
            google_default_selection = 1

            self.cmb_data_selection.setCurrentIndex(google_default_selection)
        elif provider_selected == 'yahoo':
            self.cmb_data_selection.addItems(yahoo_fin_possible_selections)
            self.cmb_data_selection.setCurrentIndex(yahoo_default_selection)
        elif provider_selected == 'quandl':
            self.cmb_data_selection.addItems(quandl_possible_selections)
            self.cmb_data_selection.setCurrentIndex(quandl_default_selection)
        else:
            raise NotImplementedError(
                f'{provider_selected} is not implemented in the data_selection_toggle function within main_gui.py'
            )

    def onDataReady(self, string):
        """
        Special PyQt name; Write code output to txtbrwsr_details
        """
        # ToDo: Build functionality to handle stderr, using red font in GUI

        cursor = self.txtbrwsr_details.textCursor()
        cursor.movePosition(cursor.End)
        cursor.insertText(str(string))
        self.txtbrwsr_details.ensureCursorVisible()

    def open_url(self, url):
        """
        Open the provided url in the system default browser

        :param url: String of the url
        """

        print(f'Opening {url} in the default browser')
        q_url = QtCore.QUrl(url)
        if not QtGui.QDesktopServices.openUrl(q_url):
            QtGui.QMessageBox.warning(self, 'Open Url', f'Could not open {url}')

    def process(self):
        """
        Invoke the thread worker, prepare the worker by providing it with the
        variables the function it's to run needs, and then pass the thread
        to the Worker class where it'll be executed.
        """

        # Determine if any of the postgres database options were not provided
        if (self.lineedit_admin_user.text() or
                self.lineedit_admin_password.text() or
                self.lineedit_name.text() or self.lineedit_user.text() or
                self.lineedit_password.text() or self.lineedit_host.text() or
                self.lineedit_port.text()) == '':
            raise ValueError('One or multiple database options were not '
                             'provided. Ensure there is a value in each field '
                             'within the PostgreSQL Database Options section.')

        # Determine if the Quandl API Key is required; if so, was it provided?
        if (self.cmb_data_source.currentText() in ['quandl'] and
                self.lineedit_quandlkey.text() == ''):
            raise ValueError('No Quandl API key provided')

        # # Depreciated when DB switched to PostgreSQL; kept for posterity
        # # Combine the directory path with the database name
        # db_link = os.path.abspath(os.path.join(self.lineedit_dbdir.text(),
        #                                        self.lineedit_dbname.text()))

        # PostgreSQL database options
        database_options = {'admin_user': self.lineedit_admin_user.text(),
                            'admin_password': self.lineedit_admin_password.text(),
                            'database': self.lineedit_name.text(),
                            'user': self.lineedit_user.text(),
                            'password': self.lineedit_password.text(),
                            'host': self.lineedit_host.text(),
                            'port': self.lineedit_port.text()}

        # Change the quandl database string to a list
        quandl_db_list = [self.cmb_tickers_quandl_db.currentText()]

        # ToDo: Add these source options as an interactive setup
        symbology_sources = ['csi_data', 'tsid', 'quandl_wiki', 'quandl_goog',
                             'seeking_alpha', 'yahoo']

        download_list = [{'source': self.cmb_data_source.currentText(),
                          'selection': self.cmb_data_selection.currentText(),
                          'interval': self.cmb_data_interval.currentText(),
                          'redownload_time': 60 * 60 * 12,
                          'data_process': 'replace',
                          'replace_days_back': 60,
                          'period': 60}]

        # Build the dictionary with all the pySecMaster settings
        settings_dict = {
            'database_options': database_options,
            'quandl_ticker_source': self.cmb_tickers_quandl.currentText(),
            'quandl_db_list': quandl_db_list,
            'download_list': download_list,
            'quandl_update_range': self.spinbx_settings_quandl_update.value(),
            'google_fin_update_range': self.spinbx_settings_csi_update.value(),
            'threads': self.spinbx_settings_threads.value(),
            'quandl_key': self.lineedit_quandlkey.text(),
            'symbology_sources': symbology_sources
        }

        self.thread_worker = QtCore.QThread()
        self.worker = Worker()
        self.worker.dataReady.connect(self.onDataReady)

        self.worker.moveToThread(self.thread_worker)

        # Stops the thread after the worker is done. To start it again, call
        #   thread.start()
        self.worker.finished.connect(self.thread_worker.quit)
        # ToDo: Figure out why worker_finished is unable to kill the thread
        # self.worker.finished.connect(self.worker_finished)
        self.worker.finished.connect(self.worker.deleteLater)

        # # Calls the Worker process directly, but it's difficult to send data
        # #     to the worker object from the main gui thread.
        # self.thread_worker.started.connect(self.worker.processA)
        # self.thread_worker.finished.connect(main().app.exit)

        # Tell the thread to start working
        self.thread_worker.start()

        # Invoke the Worker process with the ability of safely communicating
        #   with the worker through signals and slots. Worker must already be
        #   running in order for the process to be invoked. If you need to pass
        #   arguments to the worker process, add a "QtCore.Q_ARG(str, 'arg')"
        #   variable for each argument in the invokeMethod statement after
        #   the QueuedConnection variable. Only able to handle 10 arguments.
        # QtCore.Q_ARG(str, 'Hello'),
        # QtCore.Q_ARG(list, ['Hello', 0, 1]))
        QtCore.QMetaObject.invokeMethod(self.worker, 'pysecmaster',
                                        QtCore.Qt.QueuedConnection,
                                        QtCore.Q_ARG(dict, settings_dict))

        # Disable the 'Ok' button while the worker thread is running
        self.btnbox_action.button(self.btnbox_action.Ok).setEnabled(False)

        # ToDo: Figure out why worker_finished is unable to kill the thread
        # # Show the 'Stop' button and hide the 'Cancel' button
        # self.btnbox_action.button(self.btnbox_action.Abort).show()
        # self.btnbox_action.button(self.btnbox_action.Cancel).hide()

    def restore_settings(self, ini_name):
        """
        Technique structured from the code from: "https://stackoverflow.com
        /questions/23279125/python-pyqt4-functions-to-save-and-restore-ui-
        widget-values"

        :param ini_name: Name/path of the .ini file (Ex. pySecMaster_gui.ini)
        """

        settings = QtCore.QSettings(ini_name, QtCore.QSettings.IniFormat)

        for name, obj in inspect.getmembers(self):
            if isinstance(obj, QtGui.QComboBox):
                name = obj.objectName()
                value = str(settings.value(name))   # .toString())

                if not value:
                    continue

                # Get the corresponding index for specified string in combobox
                index = obj.findText(value)
                # Check if the value exists, otherwise add it to the combobox
                if index == -1:
                    obj.insertItems(0, [value])
                    index = obj.findText(value)
                obj.setCurrentIndex(index)
            elif isinstance(obj, QtGui.QLineEdit):
                name = obj.objectName()
                value = str(settings.value(name))
                obj.setText(value)

            elif isinstance(obj, QtGui.QSpinBox):
                name = obj.objectName()
                value = int(settings.value(name))
                obj.setValue(value)

            elif isinstance(obj, QtGui.QCheckBox):
                name = obj.objectName()
                if value := settings.value(name):
                    obj.setChecked(value)   # setCheckState enables tristate

    def save_settings(self, ini_name):
        """
        Technique structured from the code from: "https://stackoverflow.com
        /questions/23279125/python-pyqt4-functions-to-save-and-restore-ui-
        widget-values"

        :param ini_name: Name of the .ini file (Ex. pysecmaster.ini)
        :return:
        """

        settings = QtCore.QSettings(ini_name, QtCore.QSettings.IniFormat)

        # For child in ui.children():  # works like getmembers, but because it
        # traverses the hierarchy, you would have to call the method recursively
        # to traverse down the tree.

        for name, obj in inspect.getmembers(self):
            if isinstance(obj, QtGui.QComboBox):
                name = obj.objectName()
                text = obj.currentText()
                settings.setValue(name, text)

            elif isinstance(obj, QtGui.QLineEdit):
                name = obj.objectName()
                value = obj.text()
                settings.setValue(name, value)

            elif isinstance(obj, QtGui.QSpinBox):
                name = obj.objectName()
                value = obj.value()
                settings.setValue(name, value)

            elif isinstance(obj, QtGui.QCheckBox):
                name = obj.objectName()
                state = obj.checkState()
                settings.setValue(name, state)

    def select_dir(self):
        """
        Opens a PyQt folder search. If a folder is selected, it will
        populate the db_dir text editor box.

        DEPRECIATED
        """

        if db_dir := QtGui.QFileDialog.getExistingDirectory(
            self, 'Select Directory'
        ):
            self.lineedit_dbdir.setText(db_dir)

    def select_restore(self):
        """
        Opens a PyQt file search. If a file is selected, it will populate
        the gui settings with the values from the selected ini file.
        """

        if file := QtGui.QFileDialog.getOpenFileName(
            self, 'Select Saved Settings', '', 'INI (*.ini)'
        ):
            self.restore_settings(file)

    def txtbrwsr_details_toggle(self):

        mw_size = [self.size().width(), self.size().height()]

        if self.txtbrwsr_details.isVisible():

            mw_size[1] -= self.txtbrwsr_details.size().height()
            self.txtbrwsr_details.hide()

            # Resize the main window
            while self.size().height() > mw_size[1]:
                QtGui.QApplication.sendPostedEvents()
                self.resize(mw_size[0], mw_size[1])

        else:
            self.txtbrwsr_details.show()

    def worker_finished(self):

        # Enable the 'Ok' button and change the Stop button back to Cancel
        self.btnbox_action.button(self.btnbox_action.Ok).setEnabled(True)
        # Hide the 'Stop' button and show the 'Cancel' button
        self.btnbox_action.button(self.btnbox_action.Abort).hide()
        self.btnbox_action.button(self.btnbox_action.Cancel).show()

        # ToDo: Figure out why none of these kill the thread...
        # Safely shut down the thread
        # self.thread_worker.quit()
        self.thread_worker.terminate()
        # self.thread_worker.wait()

        print('Current process has been halted.')


class Worker(QtCore.QObject):
    finished = QtCore.pyqtSignal()
    dataReady = QtCore.pyqtSignal(str)

    @QtCore.pyqtSlot(dict)
    def pysecmaster(self, settings_dict):
        """
        Calls the functions that operate the pySecMaster. Emits signals back to
        the main gui for further processing, using the dataReady process.

        :param settings_dict: Dictionary of all parameters to be passed back
        to the pySecMaster.py functions.
        """

        self.dataReady.emit('Building the pySecMaster in the %s database '
                            'located at host %s\n' %
                            (settings_dict['database_options']['database'],
                             settings_dict['database_options']['host']))

        maintenance(database_options=settings_dict['database_options'],
                    quandl_key=settings_dict['quandl_key'],
                    quandl_ticker_source=settings_dict['quandl_ticker_source'],
                    database_list=settings_dict['quandl_db_list'],
                    threads=settings_dict['threads'],
                    quandl_update_range=settings_dict['quandl_update_range'],
                    csidata_update_range=settings_dict['google_fin_update_range'],
                    symbology_sources=settings_dict['symbology_sources'])
        data_download(database_options=settings_dict['database_options'],
                      quandl_key=settings_dict['quandl_key'],
                      download_list=settings_dict['download_list'],
                      threads=settings_dict['threads'],
                      verbose=True)

        self.dataReady.emit('Finished running the pySecMaster process\n')
        self.finished.emit()


class StdoutQueue(object):
    """
    This is a queue that acts like the default system standard output (stdout)
    """

    def __init__(self, queue):
        self.queue = queue

    def write(self, string):
        self.queue.put(string)

    def flush(self):
        sys.__stdout__.flush()


class Receiver(QtCore.QObject):
    """
    A QObject (to be run in a QThread) that sits waiting for data to come
    through a Queue.Queue(). It blocks until data is available, and once it's
    received something from the queue, it sends it to the "MainThread" by
    emitting a Qt Signal.
    """

    signal = QtCore.pyqtSignal(str)

    def __init__(self, queue, *args, **kwargs):
        QtCore.QObject.__init__(self, *args, **kwargs)
        self.queue = queue

    @QtCore.pyqtSlot()
    def run(self):
        while True:
            text = self.queue.get()
            self.signal.emit(text)


def main():

    # Create Queue and redirect sys.stdout to this queue
    queue = Queue()
    sys.stdout = StdoutQueue(queue)

    # Start the main GUI class
    app = QtGui.QApplication(sys.argv)
    form = MainWindow()
    form.show()

    # Create thread that will listen for new strings in the queue. Upon new
    #   items, Receiver will emit a signal, which will be sent to the
    #   onDataReady method in the MainWindow class. The onDataReady method
    #   will add the string to the text editor in the GUI.
    thread = QtCore.QThread()
    receiver = Receiver(queue)
    receiver.signal.connect(form.onDataReady)
    receiver.moveToThread(thread)
    thread.started.connect(receiver.run)
    thread.start()

    sys.exit(app.exec_())

if __name__ == '__main__':

    main()
