import copy
import datetime
import json
import logging
import random
import sys
import threading
from pathlib import Path
from string import Template

import edge_tts
import requests
import toml
from PySide6 import QtCore, QtGui, QtWidgets
from naive import NCore, NUtils, NView
from pygame import mixer

from utils import live_ws
from utils.expired_queue import ExpiredQueue
from utils.retry import retry

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[logging.StreamHandler(), logging.FileHandler('dy.log', encoding='utf-8')]
)


class HomePage(QtWidgets.QWidget):
    def __init__(self, parent: 'MainWindow'):
        super().__init__()
        self.main = parent
        self.setLayout(QtWidgets.QVBoxLayout())
        self.layout().setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        self.layout().addWidget(NView.Typography.H1('首页'))

        client_widget = QtWidgets.QWidget()
        client_widget.setLayout(QtWidgets.QHBoxLayout())

        self.room_input = NView.Input(placeholder='输入房间号')
        if live_id := self.main.config.get('live_id'):
            self.room_input.setText(str(live_id))
        client_widget.layout().addWidget(self.room_input)

        self.client_btn = NView.Button('连接', style_type=NCore.Core.ButtonType.success, callback=self.start)
        client_widget.layout().addWidget(self.client_btn)
        self.close_btn = NView.Button('关闭', style_type=NCore.Core.ButtonType.error, callback=self.close)
        self.close_btn.setEnabled(False)
        client_widget.layout().addWidget(self.close_btn)
        self.layout().addWidget(client_widget)
        self.dws = None

    def start(self):
        if not self.room_input.text():
            NView.SystemToast().send(
                '房间号错误',
                '请房间号不能为空'
            )
            return
        try:
            int(self.room_input.text())
        except:
            NView.SystemToast().send(
                '房间号错误',
                '请房间号错误'
            )
            return
        self.close_btn.setEnabled(True)
        self.client_btn.setEnabled(False)
        self.main.config['live_id'] = int(self.room_input.text())
        print('开始')

        self.dws = live_ws.DWS(
            room_id=self.room_input.text(),
            callback_map=self.main.data_callback,
            live_data=self.main.live_data
        )
        self.main.save_config()
        threading.Thread(target=self.dws.start, daemon=True).start()
        NView.SystemToast().send('提示', '开启成功')

    def close(self):
        self.close_btn.setEnabled(False)
        self.client_btn.setEnabled(True)
        print('结束')
        self.dws.close()
        NView.SystemToast().send('提示', '结束成功')
        pass


class RealTimeDataPage(QtWidgets.QWidget):
    render_rankings_signal = QtCore.Signal(list)

    def __init__(self, parent: 'MainWindow'):
        super().__init__()
        self.ranking_widget_list = []
        self.main = parent
        self.setLayout(NView.BaseVBoxLayout())
        self.layout().setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        self.title = NView.Typography.H1(parent.live_data.live_title)
        self.layout().addWidget(self.title)

        data_widget = QtWidgets.QWidget()
        data_widget.setLayout(QtWidgets.QGridLayout())

        user_count_widget = QtWidgets.QWidget()
        user_count_widget.setLayout(QtWidgets.QVBoxLayout())
        user_count_title = NView.Typography.H3('在线人数')
        user_count_title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        user_count_widget.layout().addWidget(user_count_title)
        self.user_count = NView.Typography.Text(str(parent.live_data.user_count))
        self.user_count.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        user_count_widget.layout().addWidget(self.user_count)
        # noinspection PyArgumentList
        data_widget.layout().addWidget(user_count_widget, 0, 0)

        like_count_widget = QtWidgets.QWidget()
        like_count_widget.setLayout(QtWidgets.QVBoxLayout())
        like_count_title = NView.Typography.H3('点赞数量')
        like_count_title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        like_count_widget.layout().addWidget(like_count_title)
        self.like_count = NView.Typography.Text(str(parent.live_data.like_count))
        self.like_count.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        like_count_widget.layout().addWidget(self.like_count)
        # noinspection PyArgumentList
        data_widget.layout().addWidget(like_count_widget, 0, 1)

        message_count_widget = QtWidgets.QWidget()
        message_count_widget.setLayout(QtWidgets.QVBoxLayout())
        message_count_title = NView.Typography.H3('弹幕数量')
        message_count_title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        message_count_widget.layout().addWidget(message_count_title)
        self.message_count = NView.Typography.Text(str(parent.live_data.message_count))
        self.message_count.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        message_count_widget.layout().addWidget(self.message_count)
        # noinspection PyArgumentList
        data_widget.layout().addWidget(message_count_widget, 0, 2)

        score_widget = QtWidgets.QWidget()
        score_widget.setLayout(QtWidgets.QVBoxLayout())
        score_title = NView.Typography.H3('本场总榜')
        score_title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        score_widget.layout().addWidget(score_title)
        self.score = NView.Typography.Text(str(parent.live_data.score))
        self.score.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        score_widget.layout().addWidget(self.score)
        # noinspection PyArgumentList
        data_widget.layout().addWidget(score_widget, 0, 3)

        total_user_count_widget = QtWidgets.QWidget()
        total_user_count_widget.setLayout(QtWidgets.QVBoxLayout())
        total_user_count_title = NView.Typography.H3('场观人数')
        total_user_count_title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        total_user_count_widget.layout().addWidget(total_user_count_title)
        self.total_user_count = NView.Typography.Text(str(parent.live_data.total_user_count))
        self.total_user_count.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        total_user_count_widget.layout().addWidget(self.total_user_count)
        # noinspection PyArgumentList
        data_widget.layout().addWidget(total_user_count_widget, 0, 4)

        self.layout().addWidget(data_widget)

        self.ranking_widget = QtWidgets.QWidget()
        self.ranking_widget.setLayout(QtWidgets.QVBoxLayout())
        self.layout().addWidget(self.ranking_widget)

        ranking_title = NView.Typography.H3('榜单')
        self.ranking_widget.layout().addWidget(ranking_title)

        self.render_rankings_signal.connect(self.render_rankings)
        self.get_rankings()
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_data)
        self.timer.start(5000)

    @QtCore.Slot()
    def render_rankings(self, data):

        self.clear_rankings()
        self.ranking_widget_list = []
        for user_info in data:
            user_widget = QtWidgets.QWidget()
            user_widget.setLayout(QtWidgets.QHBoxLayout())
            avatar = NView.Avatar(
                icon=QtGui.QImage.fromData(user_info['avatar_content']) if user_info['avatar_content'] else '未知',
                size=NCore.Core.Size.large
            )
            user_widget.layout().addWidget(avatar)
            user_name = NView.Typography.Text(user_info['username'])
            user_widget.layout().addWidget(user_name)
            self.ranking_widget_list.append(user_widget)
            self.ranking_widget.layout().addWidget(user_widget)

    @NUtils.threadFunc()
    def get_rankings(self):
        data = []
        for user_info in copy.deepcopy(self.main.live_data.ranking):
            try:
                res = requests.get(user_info['avatar']).content
            except Exception as e:
                logger.error(e, exc_info=True)
                res = None
            user_info['avatar_content'] = res
            data.append({**user_info})
        self.render_rankings_signal.emit(data)

    def clear_rankings(self):
        for widget in self.ranking_widget_list:
            self.ranking_widget.layout().removeWidget(widget)
            widget.deleteLater()

    def update_data(self):
        if not self.isVisible(): return
        logger.info('更新数据')
        data = self.main.live_data
        self.title.setText(data.live_title)
        self.user_count.setText(str(data.user_count))
        self.like_count.setText(str(data.like_count))
        self.message_count.setText(str(data.message_count))
        self.score.setText(str(data.score))
        self.total_user_count.setText(str(data.total_user_count))
        self.get_rankings()


class TTSPage(QtWidgets.QWidget):
    message_signal = QtCore.Signal(str, str)
    follow_callback_signal = QtCore.Signal(dict)
    msg_callback_signal = QtCore.Signal(dict)
    gift_callback_signal = QtCore.Signal(dict)
    enter_callback_signal = QtCore.Signal(dict)

    def __init__(self, parent: 'MainWindow'):
        super().__init__()
        mixer.init()

        self.main = parent
        self.queue = ExpiredQueue()
        self.tts_run = False
        self.sys_msg = NView.SystemToast()
        self.message_signal.connect(self.message)
        self.timbre_default = 'zh-CN-XiaoxiaoNeural'
        self.volume = '+0%'
        self.rate = '+0%'
        self.pitch = '+0Hz'
        self.welcome = []
        if welcome_template := self.main.config.get('welcome_template'):
            self.welcome = welcome_template
        self.follow = []
        if attention_template := self.main.config.get('attention_template'):
            self.follow = attention_template
        self.give_gifts = []
        if gift_template := self.main.config.get('gift_template'):
            self.give_gifts = gift_template
        self.init_callback()
        with Path(__file__).parent.joinpath('static', 'timbre.json').open('r', encoding='utf-8') as f:
            self.timbre_map = json.load(f)

        self.setLayout(QtWidgets.QVBoxLayout())
        self.layout().setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)

        btn_widget = QtWidgets.QWidget()
        btn_widget.setLayout(QtWidgets.QHBoxLayout())
        btn_widget.layout().setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop)
        self.start_btn = NView.Button(
            '运行',
            callback=self.run_tts,
            style_type=NCore.Core.ButtonType.success,
            size=NCore.Core.Size.small
        )
        self.start_btn.setFixedWidth(80)
        self.stop_btn = NView.Button(
            '停止',
            callback=self.stop_tts,
            style_type=NCore.Core.ButtonType.error,
            size=NCore.Core.Size.small
        )
        self.stop_btn.setFixedWidth(80)
        self.stop_btn.setEnabled(False)
        btn_widget.layout().addWidget(self.start_btn)
        btn_widget.layout().addWidget(self.stop_btn)
        btn_widget.setFixedHeight(btn_widget.sizeHint().height())
        self.layout().addWidget(btn_widget)

        self.layout().addWidget(NView.Typography.H3('人物'))
        timbre_widget = QtWidgets.QWidget()
        timbre_widget.setLayout(QtWidgets.QGridLayout())
        timbre_widget.layout().setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        self.timbre_group = QtWidgets.QButtonGroup(self)

        for index, (name, key) in enumerate(self.timbre_map.items()):
            pos = int(index // 3)
            itme = NView.Checkbox(name)
            if key == self.timbre_default:
                itme.toggle()

            timbre_widget.layout().addWidget(itme, pos, index - pos * 3)
            self.timbre_group.addButton(itme)
        self.timbre_group.buttonClicked.connect(self.timbre_toggle)
        self.layout().addWidget(timbre_widget)

        setting_widget = QtWidgets.QWidget()
        setting_widget.setLayout(QtWidgets.QVBoxLayout())

        setting_widget.layout().addWidget(NView.Typography.H3('音量'))
        self.volume_input = NView.InputNumber(max=100, min=-100)
        self.volume_input.setValue(0)
        self.volume_input.valueChanged.connect(self.set_volume)
        setting_widget.layout().addWidget(self.volume_input)

        setting_widget.layout().addWidget(NView.Typography.H3('语速'))
        self.rate_input = NView.InputNumber(max=100, min=-100)
        self.rate_input.setValue(0)
        self.rate_input.valueChanged.connect(self.set_rate)
        setting_widget.layout().addWidget(self.rate_input)

        setting_widget.layout().addWidget(NView.Typography.H3('音调'))
        self.pitch_input = NView.InputNumber(max=100, min=-100)
        self.pitch_input.setValue(0)
        self.pitch_input.valueChanged.connect(self.set_pitch)
        setting_widget.layout().addWidget(self.pitch_input)
        setting_widget.layout().addWidget(setting_widget)
        setting_widget.setFixedWidth(200)
        self.layout().addWidget(setting_widget)

        template_widget = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        template_widget.setMinimumHeight(200)
        welcome_widget = QtWidgets.QWidget()
        welcome_widget.setLayout(QtWidgets.QVBoxLayout())
        welcome_widget.layout().addWidget(NView.Typography.H3("欢迎模板"))
        self.welcome_input = NView.Textarea(placeholder="输入欢迎模板")
        for item in self.welcome:
            self.welcome_input.append(item)
        self.welcome_input.textChanged.connect(self.set_welcome)
        welcome_widget.layout().addWidget(self.welcome_input)
        template_widget.addWidget(welcome_widget)

        give_gifts_widget = QtWidgets.QWidget()
        give_gifts_widget.setLayout(QtWidgets.QVBoxLayout())
        give_gifts_widget.layout().addWidget(NView.Typography.H3("送礼模板"))
        self.give_gifts_input = NView.Textarea(placeholder="输入送礼模板")
        for item in self.give_gifts:
            self.give_gifts_input.append(item)
        self.give_gifts_input.textChanged.connect(self.set_give_gifts)
        give_gifts_widget.layout().addWidget(self.give_gifts_input)
        template_widget.addWidget(give_gifts_widget)

        follow_widget = QtWidgets.QWidget()
        follow_widget.setLayout(QtWidgets.QVBoxLayout())
        follow_widget.layout().addWidget(NView.Typography.H3("关注模板"))
        self.follow_input = NView.Textarea(placeholder="输入关注模板")
        for item in self.follow:
            self.follow_input.append(item)
        self.follow_input.textChanged.connect(self.set_follow)
        follow_widget.layout().addWidget(self.follow_input)
        template_widget.addWidget(follow_widget)

        self.layout().addWidget(template_widget)

        self.layout().addWidget(NView.Typography.H3('实时弹幕'))
        self.font_size_input = NView.InputNumber(min=1, max=100)
        self.font_size_input.setFixedWidth(200)
        self.font_size_input.setValue(self.main.config.get('font_size', 12))
        self.layout().addWidget(self.font_size_input)
        self.message_console = NView.Textarea()
        self.message_console.setFontPointSize(self.font_size_input.value())
        self.message_console.setMinimumHeight(440)
        self.message_console.setReadOnly(True)
        self.font_size_input.textChanged.connect(self.update_console)
        self.layout().addWidget(self.message_console)

    def update_console(self):
        self.main.config['font_size'] = self.font_size_input.value()
        self.message_console.setFontPointSize(self.font_size_input.value())
        log = self.message_console.toPlainText()
        self.message_console.clear()
        self.message_console.append(log)

    def set_follow(self):
        self.follow = [i for i in self.follow_input.toPlainText().split('\n') if i]
        logger.info('update follow template')

    def set_give_gifts(self):
        self.give_gifts = [i for i in self.give_gifts_input.toPlainText().split('\n') if i]
        logger.info('update give gifts template')

    def set_welcome(self):
        self.welcome = [i for i in self.welcome_input.toPlainText().split('\n') if i]
        logger.info('update welcome template')

    def set_volume(self):
        value = self.volume_input.value()

        if value >= 0:
            self.volume = f'+{value}%'
        else:
            self.volume = f'{value}%'

    def set_rate(self):
        value = self.rate_input.value()
        if value >= 0:
            self.rate = f'+{value}%'
        else:
            self.rate = f'{value}%'

    def set_pitch(self):
        value = self.pitch_input.value()
        if value >= 0:
            self.pitch = f'+{value}Hz'
        else:
            self.pitch = f'{value}Hz'

    def timbre_toggle(self):
        self.timbre_default = self.timbre_map[self.timbre_group.checkedButton().text()]

    def run_tts(self):
        self.tts_run = True
        self._loop()
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

        self.volume_input.setEnabled(False)
        self.rate_input.setEnabled(False)
        self.pitch_input.setEnabled(False)
        self.welcome_input.setEnabled(False)
        self.give_gifts_input.setEnabled(False)
        self.follow_input.setEnabled(False)
        self.main.config['welcome_template'] = self.welcome
        self.main.config['gift_template'] = self.give_gifts
        self.main.config['attention_template'] = self.follow
        self.main.save_config()

    def stop_tts(self):
        self.tts_run = False
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

        self.volume_input.setEnabled(True)
        self.rate_input.setEnabled(True)
        self.pitch_input.setEnabled(True)
        self.welcome_input.setEnabled(True)
        self.give_gifts_input.setEnabled(True)
        self.follow_input.setEnabled(True)

    def message(self, title, message):
        self.sys_msg.send(
            title=title,
            message=message
        )

    @NUtils.threadFunc()
    def _loop(self):
        # if not self.win_tts:
        #     self.win_tts =
        logger.info('tts run {}'.format(self.tts_run))
        while self.tts_run:
            if len(self.queue) > 0:
                try:
                    text = self.queue.put()
                    print(text)
                    self.win_tts(text)
                except Exception as e:
                    logger.error(f'tts error {e}', exc_info=True)
                    self.stop_tts()
                    self.message_signal.emit('发生错误', '语音功能发生错误已停止请重新开启')

        logger.info('tts stop')

    def win_tts(self, text):
        logger.info('[播放] {}'.format(text))
        communicate = edge_tts.Communicate(text, self.timbre_default, volume=self.volume,
                                           rate=self.rate, pitch=self.pitch)
        temp_file = Path(__file__).parent / 'temp.mp3'
        communicate.save_sync(str(temp_file))
        mixer.music.load(str(temp_file.absolute()))
        mixer.music.play()
        while mixer.music.get_busy():
            pass
        mixer.music.unload()

    def init_callback(self):
        self.follow_callback_signal.connect(self.follow_callback)
        self.msg_callback_signal.connect(self.msg_callback)
        self.gift_callback_signal.connect(self.gift_callback)
        self.enter_callback_signal.connect(self.enter_callback)
        self.main.data_callback.follow = self.follow_callback_signal.emit
        self.main.data_callback.userMsg = self.msg_callback_signal.emit
        self.main.data_callback.giftNews = self.gift_callback_signal.emit
        self.main.data_callback.enterRoom = self.enter_callback_signal.emit

    def follow_callback(self, data):
        # 关注回调
        username = data["user"]["nickName"]
        self.main.msgData.append(
            '[关注回调] {}'.format(data["user"]["nickName"].encode('utf-8', errors='ignore').decode('utf-8')))
        if not self.follow: return
        template: Template = Template(random.choice(self.follow))
        try:
            msg = template.substitute(username=username)
            self.queue.add(msg, 10)
        except Exception as e:
            print(e)

    def msg_callback(self, data):
        # 用户消息回调
        self.message_console.append(
            '{}\t\t{}'.format(
                data["user"]["nickName"],
                data["content"]
            )
        )
        self.main.msgData.append(
            '[用户消息回调] {} --> {}'.format(data["user"]["nickName"].encode('utf-8', errors='ignore').decode('utf-8'),
                                              data["content"]))
        pass

    def gift_callback(self, data):
        # 礼物回调
        username = data["user"]["nickName"]
        self.main.msgData.append(
            '[礼物回调] {} --> {}'.format(data["user"]["nickName"].encode('utf-8', errors='ignore').decode('utf-8'),
                                          data["gift"]["name"]))
        if not self.give_gifts: return
        template: Template = Template(random.choice(self.give_gifts))
        try:
            msg = template.substitute(username=username, gift=data["gift"]["name"])
            self.queue.add(msg, 15, exclude=False)
        except Exception as e:
            logger.error(e)

    def enter_callback(self, data):
        # 进入直播间回调
        username = data["user"]["nickName"]
        self.main.msgData.append(
            '[进入直播间回调] {}'.format(data["user"]["nickName"].encode('utf-8', errors='ignore').decode('utf-8')))
        if not self.welcome: return
        template: Template = Template(random.choice(self.welcome))
        try:
            msg = template.substitute(username=username)
            self.queue.add(msg, 10)
        except:
            pass


class MainWindow(NView.MicaWindow):
    def __init__(self):
        self.config = {}
        self.load_config()
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.writer_msg)
        self.timer.start(5000)
        self.live_data = live_ws.LiveData()
        self.data_callback = live_ws.CallBackMap()
        self.msgData = []
        menus = [
            NView.MenuItem(
                title="首页",
                icon="Icons:home.svg",
                page=NView.Scroll(HomePage(self)),
                callback=None
            ),
            NView.MenuItem(
                title="实时数据",
                icon="Icons:data-sheet.svg",
                page=NView.Scroll(RealTimeDataPage(self)),
                callback=None
            ),
            NView.MenuItem(
                title="语音播报",
                icon="Icons:entertainment.svg",
                page=NView.Scroll(TTSPage(self)),
                callback=None
            )
        ]
        super().__init__(
            title="Dy-Tools",
            version="0.0.1",
            icon="Icons:naive.svg",
            menus=menus
        )

    def writer_msg(self):
        logger.info('[save]')
        self.writer_live_data()
        if not self.msgData: return
        save_path = Path('./') / 'live_data' / '{}_msg.jsonl'.format(
            datetime.datetime.now().strftime('%Y-%m-%d'))
        with open(save_path, 'a', encoding='utf-8') as f:
            f.write(
                json.dumps(self.msgData, ensure_ascii=False).encode('utf-8', errors='ignore').decode('utf-8') + '\n')
        self.msgData.clear()

    def writer_live_data(self):
        save_path = Path('./') / 'live_data' / '{}_live.jsonl'.format(
            datetime.datetime.now().strftime('%Y-%m-%d'))
        save_path.parent.mkdir(exist_ok=True, parents=True)
        with open(save_path, 'a', encoding='utf-8') as f:
            f.write(self.live_data.to_json().encode('utf-8', errors='ignore').decode('utf-8') + '\n')

    def load_config(self):
        config_path = Path('./').parent / 'config.toml'
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                self.config = toml.load(f)

    def save_config(self):
        config_path = Path('./').parent / 'config.toml'
        with open(config_path, 'w', encoding='utf-8') as f:
            toml.dump(self.config, f)


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
