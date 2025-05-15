import _thread
import gzip
import hashlib
import json
import re
import logging
import time
import random
import jsengine
import websocket
from playsound import playsound
from pathlib import Path
from win32com import client
import httpx
from google.protobuf import json_format

from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from backup.dy_pb2 import PushFrame
from backup.dy_pb2 import Response
from backup.dy_pb2 import MatchAgainstScoreMessage
from backup.dy_pb2 import LikeMessage
from backup.dy_pb2 import MemberMessage
from backup.dy_pb2 import GiftMessage
from backup.dy_pb2 import ChatMessage
from backup.dy_pb2 import SocialMessage
from backup.dy_pb2 import RoomUserSeqMessage
from backup.dy_pb2 import UpdateFanTicketMessage
from backup.dy_pb2 import CommonTextMessage
from backup.dy_pb2 import ProductChangeMessage

logger = logging.getLogger(__name__)
file_fmt = "%(asctime)s - %(levelname)s - %(message)s"
logging.basicConfig(
    level=logging.INFO,
    format=file_fmt,
    filename="../log.txt",
    filemode="a",
    encoding="utf-8",
)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_fmt = "%(asctime)s - %(levelname)s - %(message)s"
fmt1 = logging.Formatter(fmt=console_fmt)
console_handler.setFormatter(fmt=fmt1)
logger.addHandler(console_handler)


class DyLive:
    LIVE_RANK_INTERVAL = 10
    START_TIME = time.time()

    def __init__(self, room_id: int, ui_onmessage):
        self.ui_onmessage = ui_onmessage
        self.last_msg = 0
        self.has = set()
        self.last_like = 0
        # self.auto = WebAuto()
        self._live_room_url = f"https://live.douyin.com/{room_id}"
        self._url_room_id = room_id
        self.rank_user = []
        self._ttwid = ""
        self.ws: websocket.WebSocketApp = None
        self._room_title = ""
        self.like_count = 0
        self.send_web = time.time()
        self.person_count = 0
        self.message_count = 0
        self.like_count = time.time()
        self.welcome_message = [
            "欢迎{}来到直播间~",
            "欢迎{}到来，可以点点关注哦~",
            "欢迎{}宝宝",
            "欢迎{}",
        ]
        self.win_tts = client.Dispatch("SAPI.SpVoice")
        self._room_id = self.parse_live_room()
        self.loading = False
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0'
        self.tts_queue = []
        self.tts_run = False
        self.close_ws = False
        # self.start_websocket()

    def close(self):
        if self.ws:
            self.close_ws = True
            self.ws.close()

    def toggleTTS(self):
        self.tts_run = not self.tts_run

    def tts(self, text: str, precedence: bool = False):
        if not self.tts_run: return
        if not text:
            return
        if self.loading and not precedence:
            return
        self.loading = True
        try:
            text = re.sub(r"[\n\r]", "", text)
            self.local_tts(text=text)
        except Exception as e:
            logger.error("[文字转语音失败]", e)
        self.loading = False

    def web_tts(self, text: str):

        url = "https://www.text-to-speech.cn/getSpeek.php"

        headers = {
            "accept": "*/*",
            "accept-language": "zh-CN,zh;q=0.9",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "dnt": "1",
            "origin": "https://www.text-to-speech.cn",
            "priority": "u=1, i",
            "referer": "https://www.text-to-speech.cn/",
            "sec-ch-ua-mobile": "?0",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "x-requested-with": "XMLHttpRequest",
        }
        data = {
            "language": "中文（普通话，简体）",
            "voice": "zh-CN-XiaochenNeural",
            "text": text,
            "role": 0,
            "style": 0,
            "rate": 6,
            "pitch": 0,
            "kbitrate": "audio-16khz-32kbitrate-mono-mp3",
            "silence": "",
            "styledegree": 1,
            "volume": 75,
            "predict": 0,
            "user_id": "",
            "yzm": "",
            "replice": 1,
        }
        response = httpx.post(url, headers=headers, data=data)
        response.raise_for_status()
        response_json = response.json()
        downloader = response_json["download"]
        mp3_res = httpx.get(downloader)
        mp3_res.raise_for_status()
        save_path = Path("tmp/" + str(time.time()) + ".mp3")
        save_path.parent.mkdir(exist_ok=True, parents=True)
        with save_path.open("wb") as f:
            f.write(mp3_res.content)
        playsound(str(save_path.absolute()), block=True)

    def local_tts(self, text: str):
        self.win_tts.Speak(text)

    def parse_live_room(self):
        headers = {
            "authority": "live.douyin.com",
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
            "cache-control": "max-age=0",
            "cookie": "xgplayer_user_id=251959789708; passport_assist_user=Cj1YUtyK7x-Br11SPK-ckKl61u5KX_SherEuuGPYIkLjtmV3X8m3EU1BAGVoO541Sp_jwUa8lBlNmbaOQqheGkoKPOVVH42rXu6KEb9WR85pUw4_qNHfbcotEO-cml5itrJowMBlYXDaB-GDqJwNMxMElMoZUycGhzdNVAT4XxCJ_74NGImv1lQgASIBA3Iymus%3D; n_mh=nNwOatDm453msvu0tqEj4bZm3NsIprwo6zSkIjLfICk; LOGIN_STATUS=1; store-region=cn-sh; store-region-src=uid; sid_guard=b177a545374483168432b16b963f04d5%7C1697713285%7C5183999%7CMon%2C+18-Dec-2023+11%3A01%3A24+GMT; ttwid=1%7C9SEGPfK9oK2Ku60vf6jyt7h6JWbBu4N_-kwQdU-SPd8%7C1697721607%7Cc406088cffa073546db29932058720720521571b92ba67ba902a70e5aaffd5d6; odin_tt=1f738575cbcd5084c21c7172736e90f845037328a006beefec4260bf8257290e2d31b437856575c6caeccf88af429213; __live_version__=%221.1.1.6725%22; device_web_cpu_core=16; device_web_memory_size=8; live_use_vvc=%22false%22; csrf_session_id=38b68b1e672a92baa9dcb4d6fd1c5325; FORCE_LOGIN=%7B%22videoConsumedRemainSeconds%22%3A180%7D; __ac_nonce=0658d6780004b23f5d0a8; __ac_signature=_02B4Z6wo00f01Klw1CQAAIDAXxndAbr7OHypUNCAAE.WSwYKFjGSE9AfNTumbVmy1cCS8zqYTadqTl8vHoAv7RMb8THl082YemGIElJtZYhmiH-NnOx53mVMRC7MM8xuavIXc-9rE7ZEgXaA13; webcast_leading_last_show_time=1703765888956; webcast_leading_total_show_times=1; webcast_local_quality=sd; xg_device_score=7.90435294117647; live_can_add_dy_2_desktop=%221%22; msToken=sTwrsWOpxsxXsirEl0V0d0hkbGLze4faRtqNZrIZIuY8GYgo2J9a0RcrN7r_l179C9AQHmmloI94oDvV8_owiAg6zHueq7lX6TgbKBN6OZnyfvZ6OJyo2SQYawIB_g==; tt_scid=NyxJTt.vWxv79efmWAzT2ZAiLSuybiEOWF0wiVYs5KngMuBf8oz5sqzpg5XoSPmie930; pwa2=%220%7C0%7C1%7C0%22; download_guide=%223%2F20231228%2F0%22; msToken=of81bsT85wrbQ9nVOK3WZqQwwku95KW-wLfjFZOef2Orr8PRQVte27t6Mkc_9c_ROePolK97lKVG3IL5xrW6GY6mdUDB0EcBPfnm8-OAShXzlELOxBBCdiQYIjCGpQ==; IsDouyinActive=false; odin_tt=7409a7607c84ba28f27c62495a206c66926666f2bbf038c847b27817acbdbff28c3cf5930de4681d3cfd4c1139dd557e; ttwid=1%7C9SEGPfK9oK2Ku60vf6jyt7h6JWbBu4N_-kwQdU-SPd8%7C1697721607%7Cc406088cffa073546db29932058720720521571b92ba67ba902a70e5aaffd5d6",
            "referer": "https://live.douyin.com/721566130345?cover_type=&enter_from_merge=web_live&enter_method=web_card&game_name=&is_recommend=&live_type=game&more_detail=&room_id=7317569386624125734&stream_type=vertical&title_type=&web_live_tab=all",
            "upgrade-insecure-requests": "1",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
        }
        response = httpx.get(self._live_room_url, headers=headers)
        self._ttwid = response.cookies.get("ttwid")
        if self._ttwid is None:
            raise Exception("cookies is Error")
        res_text = response.text
        res_room_info = re.search(
            r'room\\":{.*\\"id_str\\":\\"(\d+)\\".*,\\"status\\":(\d+).*"title\\":\\"([^"]*)\\"',
            res_text,
        )
        if res_room_info:
            room_status = res_room_info.group(2)
            room_title = res_room_info.group(3)
            logger.info(f"房间标题: {room_title}")
            self._room_title = room_title
            if room_status == "4":
                raise ConnectionError("房间已关闭")
        res_room = re.search(r'roomId\\":\\"(\d+)\\"', res_text)
        live_room_search = re.search(r'owner\\":(.*?),\\"room_auth', res_text)
        live_room_res = live_room_search.group(1).replace('\\"', '"')
        live_room_info = json.loads(live_room_res)
        logger.info(f"主播账号信息: {live_room_info}")
        live_room_id = res_room.group(1)
        res_stream = re.search(r'hls_pull_url_map\\":(\{.*?})', res_text)
        res_stream_m3u8s = json.loads(res_stream.group(1).replace('\\"', '"'))
        res_m3u8_hd1 = res_stream_m3u8s.get("FULL_HD1", "").replace("http", "https")
        if not res_m3u8_hd1:
            res_m3u8_hd1 = res_m3u8_hd1.get("HD1", "").replace("http", "https")
        logger.info(f"直播流m3u8链接地址是: {res_m3u8_hd1}")
        res_flv_search = re.search(r'flv\\":\\"(.*?)\\"', res_text)
        res_stream_flv = (
            res_flv_search.group(1).replace('\\"', '"').replace("\\\\u0026", "&")
        )
        if "https" not in res_stream_flv:
            res_stream_flv = res_stream_flv.replace("http", "https")
        logger.info(f"直播流FLV地址是: {res_stream_flv}")
        return live_room_id

    def get_signature(self, x_ms_stub):
        try:
            ctx = jsengine.jsengine()
            js_dom = f"""
    document = {{}}
    window = {{}}
    navigator = {{
    'userAgent': '{self.USER_AGENT}'
    }}
    """.strip()
            js_enc = Path('../static/webmssdk.js').read_text(encoding='utf-8')
            final_js = js_dom + js_enc
            ctx.eval(final_js)
            function_caller = f"get_sign('{x_ms_stub}')"
            signature = ctx.eval(function_caller)
            # print("signature: ", signature)
            return signature
        except:
            logger.exception("get_signature error")
        return "00000000"

    def start_websocket(self):
        if self.close_ws: return
        websocket.enableTrace(False)
        USER_UNIQUE_ID = str(random.randint(7300000000000000000, 7999999999999999999))
        VERSION_CODE = 180800
        WEBCAST_SDK_VERSION = "1.0.14-beta.0"
        sig_params = {
            "live_id": "1",
            "aid": "6383",
            "version_code": VERSION_CODE,
            "webcast_sdk_version": WEBCAST_SDK_VERSION,
            "room_id": self._room_id,
            "sub_room_id": "",
            "sub_channel_id": "",
            "did_rule": "3",
            "user_unique_id": USER_UNIQUE_ID,
            "device_platform": "web",
            "device_type": "",
            "ac": "",
            "identity": "audience"
        }
        signature = self.get_signature(
            hashlib.md5((','.join([f'{k}={v}' for k, v in sig_params.items()])).encode()).hexdigest())
        webcast5_params = {
            "room_id": self._room_id,
            "compress": 'gzip',
            "version_code": VERSION_CODE,
            "webcast_sdk_version": WEBCAST_SDK_VERSION,
            "live_id": "1",
            "did_rule": "3",
            "user_unique_id": USER_UNIQUE_ID,
            "identity": "audience",
            "signature": signature,
        }

        wss_url = f"wss://webcast5-ws-web-lf.douyin.com/webcast/im/push/v2/?{'&'.join([f'{k}={v}' for k, v in webcast5_params.items()])}"
        wss_url = self.build_request_url(wss_url)
        headers = {
            "cookie": f"ttwid={self._ttwid}",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
        }
        self.ws = websocket.WebSocketApp(
            wss_url,
            header=headers,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
            on_open=self.on_open,
        )
        while not self.close_ws:
            self.ws.run_forever()

    def build_request_url(self, url):
        parsed_url = urlparse(url)
        existing_params = parse_qs(parsed_url.query)
        existing_params['aid'] = ['6383']
        existing_params['device_platform'] = ['web']
        existing_params['browser_language'] = ['zh-CN']
        existing_params['browser_platform'] = ['Win32']
        existing_params['browser_name'] = [self.USER_AGENT.split('/')[0]]
        existing_params['browser_version'] = [self.USER_AGENT.split(existing_params['browser_name'][0])[-1][1:]]
        new_query_string = urlencode(existing_params, doseq=True)
        new_url = urlunparse((
            parsed_url.scheme,
            parsed_url.netloc,
            parsed_url.path,
            parsed_url.params,
            new_query_string,
            parsed_url.fragment
        ))
        return new_url

    def on_error(self, ws, error):
        logger.error(f"[websocket] 错误: {error}", exc_info=True)

    def on_close(self, ws, a, b):
        end_time = time.time()
        total_time = end_time - self.START_TIME
        total_info = f"工具运行时长：{total_time}，点赞数量总计：{self.like_count}, 评论数量总计: {self.message_count}"
        logger.info(total_info)
        logger.info("[onClose] [webSocket Close事件]")
        self.ws.keep_running = False
        self.close_ws = True
        websocket.WebSocketApp.close(ws)

    def ping(self, ws):
        while True:
            obj = PushFrame()
            obj.payloadType = "hb"
            data = obj.SerializeToString()
            ws.send(data, websocket.ABNF.OPCODE_BINARY)
            logger.info("[💗心跳] ====> 房间🏖标题【" + self._room_title + "】")
            time.sleep(10)

    def on_open(self, ws):
        _thread.start_new_thread(self.ping, (ws,))
        logger.info("[webSocket Open事件]")

    def on_message(self, ws: websocket.WebSocketApp, message: bytes):
        ws_package = PushFrame()
        ws_package.ParseFromString(message)
        log_id = ws_package.logId
        decompressed = gzip.decompress(ws_package.payload)
        payload = Response()
        payload.ParseFromString(decompressed)
        if payload.needAck:
            self.send_ack(ws, log_id, payload.internalExt)
        for msg in payload.messagesList:
            match msg.method:
                case "WebcastMatchAgainstScoreMessage":
                    self.un_pack_match_against_score_message(msg.payload)
                case "WebcastLikeMessage":
                    self.un_pack_webcast_like_message(msg.payload)
                case "WebcastMemberMessage":
                    self.un_pack_webcast_member_message(msg.payload)
                case "WebcastGiftMessage":
                    self.un_pack_webcast_gift_message(msg.payload)
                case "WebcastChatMessage":
                    self.un_pack_webcast_chat_message(msg.payload)
                case "WebcastSocialMessage":
                    self.un_pack_webcast_social_message(msg.payload)
                case "WebcastRoomUserSeqMessage":
                    self.un_pack_webcast_room_user_seq_message(msg.payload)
                case "WebcastUpdateFanTicketMessage":
                    self.un_pack_webcast_update_fan_ticket_message(msg.payload)
                case "WebcastCommonTextMessage":
                    self.un_pack_webcast_common_text_message(msg.payload)
                case "WebcastProductChangeMessage":
                    self.webcast_product_change_message(msg.payload)
                # case _:
                #     logger.info('[onMessage] [待解析方法' + msg.method + '等待解析～]')

    def send_ack(self, ws, log_id, internal):
        obj = PushFrame()
        obj.payloadType = "ack"
        obj.logId = log_id
        obj.payloadType = internal
        data = obj.SerializeToString()
        ws.send(data, websocket.ABNF.OPCODE_BINARY)
        logger.debug(
            "[sendAck] [🌟发送Ack] [房间Id："
            + self._room_id
            + "] ====> 房间标题【"
            + self._room_title
            + "】"
        )

    def un_pack_match_against_score_message(self, data):
        matchAgainstScoreMessage = MatchAgainstScoreMessage()
        matchAgainstScoreMessage.ParseFromString(data)
        data = json_format.MessageToDict(
            matchAgainstScoreMessage, preserving_proto_field_name=True
        )
        log = json.dumps(data, ensure_ascii=False)
        logger.info("[unPackMatchAgainstScoreMessage] [不知道是啥的消息]" + log)
        return data

    def un_pack_webcast_like_message(self, data):
        likeMessage = LikeMessage()
        likeMessage.ParseFromString(data)
        data = json_format.MessageToDict(likeMessage, preserving_proto_field_name=True)
        self.like_count = int(data.get("total", 0))
        log = json.dumps(data, ensure_ascii=False)
        logger.info(
            f'[直播间点赞统计{data["total"]}]' + data["user"]["nickName"] + " 点赞"
        )
        self.like_count += 1
        # if self.like_count % 3000:
        #     self.auto.send_message(f"家人们点点赞啦~马上{int(self.like_count // 10000) + 1}万赞啦~")
        return data

    def un_pack_webcast_common_text_message(self, data):
        commonTextMessage = CommonTextMessage()
        commonTextMessage.ParseFromString(data)
        data = json_format.MessageToDict(
            commonTextMessage, preserving_proto_field_name=True
        )
        log = json.dumps(data, ensure_ascii=False)
        logger.info("[公共文本消息]" + log)
        return data

    def webcast_product_change_message(self, data):
        commonTextMessage = ProductChangeMessage()
        commonTextMessage.ParseFromString(data)
        data = json_format.MessageToDict(
            commonTextMessage, preserving_proto_field_name=True
        )
        log = json.dumps(data, ensure_ascii=False)
        logger.info("[商品改变消息]" + log)

    def un_pack_webcast_update_fan_ticket_message(self, data):
        updateFanTicketMessage = UpdateFanTicketMessage()
        updateFanTicketMessage.ParseFromString(data)
        data = json_format.MessageToDict(
            updateFanTicketMessage, preserving_proto_field_name=True
        )
        log = json.dumps(data, ensure_ascii=False)
        logger.info(f"[房间用户发送消息] {self.send_web} |" + log)
        self.send_web += 1
        return data

    def un_pack_webcast_room_user_seq_message(self, data):
        roomUserSeqMessage = RoomUserSeqMessage()
        roomUserSeqMessage.ParseFromString(data)
        data = json_format.MessageToDict(
            roomUserSeqMessage, preserving_proto_field_name=True
        )
        log = json.dumps(data, ensure_ascii=False)
        logger.info(f"[房间用户发送消息] {self.send_web} |" + log)
        self.send_web += 1
        return data

    def un_pack_webcast_social_message(self, data):
        socialMessage = SocialMessage()
        socialMessage.ParseFromString(data)
        data = json_format.MessageToDict(
            socialMessage, preserving_proto_field_name=True
        )
        log = json.dumps(data, ensure_ascii=False)
        logger.info("[➕直播间关注消息]" + log)
        return data

    # 普通消息
    def un_pack_webcast_chat_message(self, data):
        self.message_count += 1
        chatMessage = ChatMessage()
        chatMessage.ParseFromString(data)
        data = json_format.MessageToDict(chatMessage, preserving_proto_field_name=True)
        logger.info(
            f"[直播间弹幕消息{self.message_count}]"
            + data["user"]["nickName"]
            + "-->"
            + data["content"]
        )
        self.tts(data["user"]["nickName"] + "说：" + data["content"])
        with open("../msg.log", "a", encoding="utf-8") as f:
            f.write(data["user"]["nickName"] + ">>>" + data["content"] + "\n")
        self.ui_onmessage(data)
        return data

    # 礼物消息
    def un_pack_webcast_gift_message(self, data):
        giftMessage = GiftMessage()
        giftMessage.ParseFromString(data)
        data = json_format.MessageToDict(giftMessage, preserving_proto_field_name=True)
        # print(data)
        # log = json.dumps(data, ensure_ascii=False)
        logger.info(
            f"[直播间礼物消息]"
            + data["user"]["nickName"]
            + "送出"
            + data["gift"]["name"]
        )

        self.tts(
            "感谢 {} 送出的 {}".format(data["user"]["nickName"], data["gift"]["name"])
        )
        msg = "感谢{}送的{}".format(data["user"]["nickName"], data["gift"]["name"])
        if msg not in self.has:
            # self.auto.send_message(msg)
            self.has.add(msg)
            self.last_msg = time.time()
        if time.time() - self.last_msg > 20:
            self.last_msg = time.time()
            self.has.clear()
        return data

    # xx成员进入直播间消息
    def un_pack_webcast_member_message(self, data):
        memberMessage = MemberMessage()
        memberMessage.ParseFromString(data)
        data = json_format.MessageToDict(
            memberMessage, preserving_proto_field_name=True
        )
        # 直播间人数统计
        member_num = int(data.get("memberCount", 0))
        self.person_count = member_num
        log = json.dumps(data, ensure_ascii=False)
        logger.info(f"[直播间成员加入: {member_num}] -->" + data["user"]["nickName"])
        text = random.choice(self.welcome_message).format(data["user"]["nickName"])
        self.tts(text)
        return data


class WebAuto:
    def __init__(self):
        self.web = ChromiumPage(9333)
        self.tab = self.web.get_tab(url='https://live.douyin.com/')
        self.input_box = self.tab.ele('xpath://*[@id="chat-textarea"]')
        self.send_box = self.tab.ele('xpath://*[@id="chatInput"]/svg/path[1]')

    def deyopen(self):
        import threading
        threading.Thread(target=self.timeout, daemon=True).start()

    def timeout(self):
        while True:
            time.sleep(200)
            self.send_message('点点关注不迷路啦~')

    def send_message(self, msg):
        self.input_box.input(msg + '\n')


if __name__ == "__main__":
    dy = DyLive(7102226822)
