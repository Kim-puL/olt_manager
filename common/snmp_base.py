from abc import ABC, abstractmethod
from logger_config import logger

class SnmpBase(ABC):
    def __init__(self, host, port, community_string):
        self.host = host
        self.port = port
        self.community_string = community_string
        self.logger = logger

    @abstractmethod
    def get(self, oid):
        pass

    @abstractmethod
    def walk(self, oid):
        pass
