import requests
import time
import json
import os
import sys
from datetime import datetime as dt
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import QThread
from window_fixed import Ui_MainWindow


def resource_path(relative):
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative)
    return os.path.join(relative)


class Window(QtWidgets.QMainWindow, Ui_MainWindow):
    def __init__(self, parent=None):
        super(Window, self).__init__(parent)

        self.setupUi(self)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint)
        self.countButton.clicked.connect(self.button_pushed_event)
        path = resource_path('icon.ico')
        self.setWindowIcon(QtGui.QIcon(path))

    def mousePressEvent(self, event):
        self.start = self.mapToGlobal(event.pos())
        self.pressing = True

    def mouseMoveEvent(self, event):
        if self.pressing:
            self.end = self.mapToGlobal(event.pos())
            self.movement = self.end - self.start
            self.setGeometry(
                self.mapToGlobal(self.movement).x(),
                self.mapToGlobal(self.movement).y(),
                self.width(),
                self.height()
            )
            self.start = self.end

    def mouseReleaseEvent(self, QMouseEvent):
        self.pressing = False

    def time_signal_handler(self, time):
        if time < 360:
            self.resultLabel.setText(str(time) + ' m')
        else:
            self.resultLabel.setText(str(time // 60) + ' h')

    def done_signal_handler(self, time):
        if time == -1:
            self.resultLabel.setText('Bad login')
        elif time == -2:
            self.resultLabel.setText('Server Error')
        elif time == -3:
            self.resultLabel.setText("Can't find nickname")
        elif 0 < time < 360:
            self.resultLabel.setText(str(time) + ' m')
        else:
            self.resultLabel.setText(str(time // 60) + ' h')

        self.countButton.setEnabled(True)
        self.run_loading_thread.terminate()
        self.countButton.setEnabled(True)
        self.countButton.setText('COUNT')

    def start_signal_handler(self):
        self.run_loading_thread.start()

    def loading_signal_handler(self, text):
        self.countButton.setText(text)

    def button_pushed_event(self):
        self.countButton.setEnabled(False)
        login = self.loginEdit.text()
        password = self.passEdit.text()
        nickname = self.nicknameEdit.text()
        self.run_count_thread = GetCountThread(login, password, nickname)
        self.run_count_thread.time_signal.connect(self.time_signal_handler)
        self.run_count_thread.done_signal.connect(self.done_signal_handler)
        self.run_count_thread.start_signal.connect(self.start_signal_handler)
        self.run_count_thread.start()
        self.run_loading_thread = GetLoadingThread()
        self.run_loading_thread.loading_signal.connect(self.loading_signal_handler)


class GetCountThread(QThread):
    time_signal = QtCore.pyqtSignal(int)
    done_signal = QtCore.pyqtSignal(int)
    start_signal = QtCore.pyqtSignal(int)

    def __init__(self, login, password, nickname):
        QThread.__init__(self)
        self.login = login
        self.password = password
        self.nickname = nickname

    def __del__(self):
        self.wait()

    def run(self):
        def _count_time(message):
            start = dt.fromisoformat(message['timestamp'])
            if message['call']['ended_timestamp'] != None:
                end = dt.fromisoformat(message['call']['ended_timestamp'])
                delta = end - start
                return round(delta.total_seconds() / 60)
            else:
                return 0

        def _find_channel_id(channels, nickname):
            for channel in channels:
                if channel['type'] == 1 and channel['recipients'][0]['username'] == nickname:
                    return channel['id']
            return 0

        user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.142 Safari/537.36'
        login_page = 'https://discord.com/login'
        login_url = 'https://discord.com/api/v8/auth/login'
        channels_url = 'https://discord.com/api/v8/channels/'

        session = requests.Session()
        session.headers.update({'Referer': login_page})
        session.headers.update({'User-Agent': user_agent})
        login_form = {
            'login': self.login,
            'password': self.password,
            'undelete': False,
            'captcha_key': None,
            'login_source': None,
            'gift_code_sku_id': None
        }
        headers_post = {
            'accept-encoding': 'identity',
            'content-type': 'application/json',
            'referer': login_page,
            'user-agent': user_agent,
        }

        post_request = session.post(login_url, data=json.dumps(login_form), headers=headers_post)
        if post_request.status_code != 200:
            self.done_signal.emit(-1)
            return
        response = json.loads(post_request.text)
        token = response['token']
        session.headers.update({'authorization': token})

        s = session.get("https://discord.com/api/users/@me/channels")
        if s.status_code != 200:
            self.done_signal.emit(-2)
            return
        channels = json.loads(s.text)
        channel_id = _find_channel_id(channels, self.nickname)
        messages_url = channels_url + str(channel_id) + '/messages'

        s = session.get(messages_url, params={'limit': '100'})
        if s.status_code != 200:
            self.done_signal.emit(-3)
            return
        data = json.loads(s.text)
        time_count = 0

        self.start_signal.emit(1)
        while len(data) != 0:
            for message in data:
                if message['type'] == 3:
                    time_count += _count_time(message)
                    self.time_signal.emit(time_count)
                last_message_id = message['id']
            s = session.get(messages_url, params={'limit': '100', 'before': last_message_id})
            data = json.loads(s.text)

        self.done_signal.emit(time_count)


class GetLoadingThread(QThread):
    loading_signal = QtCore.pyqtSignal(str)

    def __init__(self):
        QThread.__init__(self)

    def __del__(self):
        self.wait()

    def run(self):
        loading_text = ['', '.', '..', '...']
        counter = 0
        while True:
            self.loading_signal.emit('COUNTING' + ' ' + loading_text[counter % 4])
            counter += 1
            time.sleep(1)


if __name__ == "__main__":
    path = resource_path('19783.ttf')
    app = QtWidgets.QApplication(sys.argv)
    id = QtGui.QFontDatabase.addApplicationFont(path)
    ui = Window()
    ui.show()
    sys.exit(app.exec_())
