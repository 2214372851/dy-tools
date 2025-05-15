import copy
import pprint
import time


class ExpiredQueue:
    def __init__(self, max_count: int = 20):
        self.queue = []
        self.cache = []
        self.max_count = max_count

    def add(self, data, timeout: int, exclude: bool = True):
        self._clear_timeout_data()
        for item in self.queue:
            if data == item['data']:
                return
        for item in self.cache:
            if data == item['data']:
                return
        self.queue.append({
            'data': data,
            'crt_time': time.time(),
            'exclude': exclude,
            'timeout': timeout
        })
        if len(self.queue) > self.max_count:
            f_msg = filter(lambda item: item['exclude'], self.queue)
            if len(f_msg) > 0:
                self.queue.pop(f_msg[0])

    def _clear_timeout_data(self):
        new_queue = []
        for item in self.queue:
            data = copy.deepcopy(item)
            crt_time = data['crt_time']
            timeout = data['timeout']
            if time.time() - crt_time < timeout:
                new_queue.append(data)
        self.queue = new_queue

        cache = []
        for item in self.cache:
            data = copy.deepcopy(item)
            crt_time = data['crt_time']
            timeout = data['timeout']
            if time.time() - crt_time < timeout:
                cache.append(data)
        self.cache = cache

    def put(self):
        text = self.queue.pop(0)['data'] if len(self.queue) > 0 else None
        self.cache.append({
            'data': text,
            'crt_time': time.time(),
            'timeout': 15
        })
        print(self.cache, self.queue)
        return text

    def __len__(self):
        return len(self.queue)

    def __str__(self):
        return pprint.pformat(self.queue)
