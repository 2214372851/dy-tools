import gzip
import hashlib
import json
import logging
import random
import re
import threading
import time
from pathlib import Path
from typing import Union, Callable
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

import httpx
import jsengine
import websocket
from google.protobuf import json_format

from .dy_pb2 import ChatMessage
from .dy_pb2 import GiftMessage
from .dy_pb2 import LikeMessage
from .dy_pb2 import MemberMessage
from .dy_pb2 import PushFrame
from .dy_pb2 import Response
from .dy_pb2 import RoomUserSeqMessage
from .dy_pb2 import SocialMessage
from .dy_pb2 import UpdateFanTicketMessage

logger = logging.getLogger(__name__)


class LiveData:
    def __init__(self):
        self.live_title = '直播间标题'
        self.create_time = 0
        # 直播间在线人数
        self.user_count = 0
        # 直播间累计人数
        self.total_user_count = 0
        # 直播间当前点赞数
        self.like_count = 0
        # 弹幕消息数
        self.message_count = 0
        # 排名 {id, username, rank, avatar}[]
        self.ranking = []
        # 总榜
        self.score = 0

    def __str__(self):
        return '在线人数: {} | 点赞数: {} | 消息数: {} | 总榜: {} | 排名: {}'.format(
            self.user_count, self.like_count, self.message_count, self.score,
            ', '.join([i['username'] for i in self.ranking])
        )

    def to_json(self):
        obj = {
            'live_title': self.live_title,
            'time': int(time.time()),
            'create_time': self.create_time,
            'user_count': self.user_count,
            'total_user_count': self.total_user_count,
            'like_count': self.like_count,
            'message_count': self.message_count,
            'score': self.score,
            'ranking': self.ranking,
        }
        # print(obj)
        return json.dumps(obj, ensure_ascii=False)


class CallBackMap:
    def __init__(self,
                 follow: Union[Callable, None] = None,
                 userMsg: Union[Callable, None] = None,
                 giftNews: Union[Callable, None] = None,
                 enterRoom: Union[Callable, None] = None):
        # 关注回调
        self.follow: Union[Callable, None] = follow
        # 用户消息回调
        self.userMsg: Union[Callable, None] = userMsg
        # 礼物回调
        self.giftNews: Union[Callable, None] = giftNews
        # 进入直播间回调
        self.enterRoom: Union[Callable, None] = enterRoom


class DWS:
    def __init__(self, room_id, callback_map: CallBackMap, live_data: LiveData):
        self.last_msg_time = time.time()
        self.live_data = live_data
        self.live_room_url = f"https://live.douyin.com/{room_id}"
        self.live_room_id = room_id
        self.live_room_title = ''
        self._ttwid = ''
        self.start_time = time.time()
        self.ws: websocket.WebSocketApp | None = None
        self.callbackMap: CallBackMap = callback_map
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0'
        pass

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
        response = httpx.get(self.live_room_url, headers=headers)
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
            self.live_data.live_title = room_title
            logger.info(f"房间标题: {room_title}")
            self.live_room_title = room_title
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
            js_enc = Path(__file__).parent.parent.joinpath('static/webmssdk.js').read_text(encoding='utf-8')
            final_js = js_dom + js_enc
            ctx.eval(final_js)
            function_caller = f"get_sign('{x_ms_stub}')"
            signature = ctx.eval(function_caller)
            # print("signature: ", signature)
            return signature
        except:
            logger.exception("get_signature error")
        return "00000000"

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

    def send_ack(self, ws, log_id, internal):
        obj = PushFrame()
        obj.payloadType = "ack"
        obj.logId = log_id
        obj.payloadType = internal
        data = obj.SerializeToString()
        ws.send(data, websocket.ABNF.OPCODE_BINARY)
        logger.debug(
            "[sendAck] [🌟发送Ack] [房间Id："
            + self.live_room_id
            + "] ====> 房间标题【"
            + self.live_room_title
            + "】"
        )

    def ws_error(self, ws, error):
        logger.error(f"[websocket] 错误: {error}", exc_info=True)

    def ws_close(self, ws, a, b):
        total_time = time.time() - self.start_time
        total_info = f"工具运行时长：{total_time}，点赞数量总计：{self.live_data.like_count}, 评论数量总计: {self.live_data.message_count}"
        logger.info(total_info)
        logger.info("[onClose] [webSocket Close事件]")

    def ping(self, ws):
        while True:
            obj = PushFrame()
            obj.payloadType = "hb"
            data = obj.SerializeToString()
            ws.send(data, websocket.ABNF.OPCODE_BINARY)
            logger.info("[💗心跳] ====> 房间🏖标题【{}】".format(self.live_room_title))
            time.sleep(10)
            if time.time() - self.last_msg_time > 60:
                self.restart()

    def ws_open(self, ws):
        self.start_time = time.time()
        threading.Thread(target=self.ping, args=(ws,), daemon=True).start()
        logger.info("[webSocket Open事件]")

    def start(self):
        websocket.enableTrace(False)
        self.live_room_id = self.parse_live_room()
        USER_UNIQUE_ID = str(random.randint(7300000000000000000, 7999999999999999999))
        VERSION_CODE = 180800
        WEBCAST_SDK_VERSION = "1.0.14-beta.0"
        sig_params = {
            "live_id": "1",
            "aid": "6383",
            "version_code": VERSION_CODE,
            "webcast_sdk_version": WEBCAST_SDK_VERSION,
            "room_id": self.live_room_id,
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
            "room_id": self.live_room_id,
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
            "user-agent": self.USER_AGENT,
        }
        self.ws = websocket.WebSocketApp(
            wss_url,
            header=headers,
            on_message=self.message_dispatch,
            on_error=self.ws_error,
            on_close=self.ws_close,
            on_open=self.ws_open,
        )
        self.ws.run_forever()

    def close(self):
        self.ws.close()

    def restart(self):
        self.ws.close()

        self.start()

    def message_dispatch(self, ws: websocket.WebSocketApp, message: bytes):
        self.last_msg_time = time.time()
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
                case "WebcastLikeMessage":
                    self.giveALike(msg.payload)
                case "WebcastMemberMessage":
                    self.enterRoom(msg.payload)
                case "WebcastGiftMessage":
                    self.giftNews(msg.payload)
                case "WebcastChatMessage":
                    self.userMsg(msg.payload)
                case "WebcastSocialMessage":
                    self.follow(msg.payload)
                case "WebcastRoomUserSeqMessage":
                    self.ranking(msg.payload)
                case "WebcastUpdateFanTicketMessage":
                    self.overall_ranking(msg.payload)

    def giveALike(self, data):
        """
        点赞消息
        :param data:
        :return:
        """
        likeMessage = LikeMessage()
        likeMessage.ParseFromString(data)
        data = json_format.MessageToDict(likeMessage, preserving_proto_field_name=True)
        self.live_data.like_count = int(data.get("total", 0))
        logger.info(
            '[直播间点赞统计{}] {} 点赞'.format(
                data["total"],
                data["user"]["nickName"].encode('utf-8', errors='ignore').decode('utf-8'))
        )

    def enterRoom(self, data):
        """
        进入直播间消息
        :param data:
        :return:
        """
        memberMessage = MemberMessage()
        memberMessage.ParseFromString(data)
        data = json_format.MessageToDict(
            memberMessage, preserving_proto_field_name=True
        )
        user_count = int(data.get("memberCount", 0))
        self.live_data.user_count = user_count
        self.callbackMap.enterRoom(data) if self.callbackMap.enterRoom else {}
        logger.info("[直播间成员加入: {}] --> {}".format(
            user_count,
            data["user"]["nickName"].encode('utf-8', errors='ignore').decode('utf-8')))

    def giftNews(self, data):
        """
        礼物消息
        :param data:
        :return:
        """
        giftMessage = GiftMessage()
        giftMessage.ParseFromString(data)
        data = json_format.MessageToDict(giftMessage, preserving_proto_field_name=True)
        self.callbackMap.giftNews(data) if self.callbackMap.giftNews else {}
        logger.info(
            "[直播间礼物消息] {} 送出 {}".format(
                data["user"]["nickName"].encode('utf-8', errors='ignore').decode('utf-8'),
                data["gift"]["name"])
        )

    def userMsg(self, data):
        chatMessage = ChatMessage()
        chatMessage.ParseFromString(data)
        data = json_format.MessageToDict(chatMessage, preserving_proto_field_name=True)
        self.live_data.message_count += 1
        self.callbackMap.userMsg(data) if self.callbackMap.userMsg else {}
        logger.info(
            "[直播间弹幕消息] {} --> {}".format(
                data["user"]["nickName"].encode('utf-8', errors='ignore').decode('utf-8'),
                data["content"])
        )

    def follow(self, data):
        """
        关注消息
        :param data:
        :return:
        """
        socialMessage = SocialMessage()
        socialMessage.ParseFromString(data)
        data = json_format.MessageToDict(
            socialMessage, preserving_proto_field_name=True
        )
        log = json.dumps(data, ensure_ascii=False)
        self.callbackMap.follow(data) if self.callbackMap.follow else {}
        logger.info("[➕直播间关注消息] {}".format(log))

    def ranking(self, data):
        """
        排名消息
        :return:
        """
        roomUserSeqMessage = RoomUserSeqMessage()
        roomUserSeqMessage.ParseFromString(data)
        data = json_format.MessageToDict(
            roomUserSeqMessage, preserving_proto_field_name=True
        )
        ranks_list = data['ranksList']
        print(ranks_list)
        user_info = [
            {
                'id': i['user']['id'],
                'username': i['user'].get('nickName', '匿名用户').encode('utf-8', errors='ignore').decode('utf-8'),
                'rank': i['rank'],
                'avatar': i['user']['AvatarThumb']['urlListList'][0],
            }
            for i in ranks_list
        ]
        user_info.sort(key=lambda item: int(item['rank']))
        self.live_data.ranking = user_info
        self.live_data.create_time = int(data['common']['createTime'])
        self.live_data.total_user_count = int(data['totalUser'])

    def overall_ranking(self, data):
        updateFanTicketMessage = UpdateFanTicketMessage()
        updateFanTicketMessage.ParseFromString(data)
        data = json_format.MessageToDict(
            updateFanTicketMessage, preserving_proto_field_name=True
        )
        self.live_data.score = data['roomFanTicketCount']


if __name__ == '__main__':
    a = DWS(
        '7102226822',
        CallBackMap(),
        LiveData()
    )
    a.start()
