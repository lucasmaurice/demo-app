import re
import logging

errorlog = "-"
accesslog = "-"
loglevel = "info"
workers = 1
threads = 2
timeout = 60
bind = "0.0.0.0:8080"


class RequestPathFilter(logging.Filter):
    def __init__(self, *args, path_re, **kwargs):
        super().__init__(*args, **kwargs)
        self.path_filter = re.compile(path_re)

    def filter(self, record):
        req_path = record.args['U']
        return not self.path_filter.match(req_path)


def on_starting(server):
    server.log.access_log.addFilter(RequestPathFilter(path_re=r'^/healthz/.*'))
