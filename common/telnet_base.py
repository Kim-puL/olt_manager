from abc import ABC, abstractmethod
from logger_config import logger

class TelnetBase(ABC):
    def __init__(self, host, port, username, password):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.logger = logger

    @abstractmethod
    def connect(self):
        pass

    @abstractmethod
    def execute_command(self, command):
        pass

    @abstractmethod
    def disconnect(self):
        pass
