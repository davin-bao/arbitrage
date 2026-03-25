import os
import sys
from datetime import datetime
from typing import Optional
from abc import ABC, abstractmethod


class ILogger(ABC):
    @abstractmethod
    def info(self, message: str) -> None:
        pass

    @abstractmethod
    def warning(self, message: str) -> None:
        pass

    @abstractmethod
    def error(self, message: str) -> None:
        pass

    @abstractmethod
    def debug(self, message: str) -> None:
        pass


class FileLogger(ILogger):
    def __init__(self, log_dir: str = "logs", prefix: str = "[LOGGER]"):
        self.prefix = prefix
        self.log_dir = log_dir
        self.current_date = datetime.now().strftime("%Y-%m-%d")
        self._in_logging = False
        self._ensure_log_directory_exists()

        # 日志文件名包含日期
        log_filename = os.path.join(log_dir, f"log_{self.current_date}.log")
        self.file_handle = open(log_filename, 'a', encoding='utf-8')

    def _ensure_log_directory_exists(self) -> None:
        """确保日志目录存在"""
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)

    def _check_date_and_rotate_if_needed(self) -> None:
        """检查日期并根据需要轮转日志文件"""
        today = datetime.now().strftime("%Y-%m-%d")
        if today != self.current_date:
            # 关闭旧的日志文件
            if self.file_handle:
                self.file_handle.close()

            # 更新日期
            self.current_date = today

            # 创建新的日志文件
            log_filename = os.path.join(self.log_dir, f"log_{self.current_date}.log")
            self.file_handle = open(log_filename, 'a', encoding='utf-8')

    def _write_log(self, level: str, message: str) -> None:
        """写入日志到文件和控制台"""
        self._check_date_and_rotate_if_needed()

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {self.prefix} [{level}] {message}\n"

        # 写入文件
        if self.file_handle:
            self.file_handle.write(log_entry)
            self.file_handle.flush()  # 确保立即写入磁盘
        
        if self._in_logging:
            return  # 防止递归调用
        self._in_logging = True
        try:
            # 输出到控制台
            console_message = f"[{timestamp}] {self.prefix} [{level}] {message}"
            print(console_message, file=sys.stdout)
        finally:
            self._in_logging = False

    def info(self, message: str) -> None:
        self._write_log("INFO", message)

    def warning(self, message: str) -> None:
        self._write_log("WARNING", message)

    def error(self, message: str) -> None:
        self._write_log("ERROR", message)

    def debug(self, message: str) -> None:
        self._write_log("DEBUG", message)

    def close(self) -> None:
        """关闭日志文件"""
        if self.file_handle:
            self.file_handle.close()
            self.file_handle = None


class NullLogger(ILogger):
    """空日志实现，不输出任何内容"""
    
    def info(self, message: str) -> None:
        pass

    def warning(self, message: str) -> None:
        pass

    def error(self, message: str) -> None:
        pass

    def debug(self, message: str) -> None:
        pass