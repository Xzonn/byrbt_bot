# -*- encoding: utf-8 -*-
"""
@File    : bit_torrent_utils.py
@Time    : 2022/7/3 18:40
@Author  : Xzonn
@Email   : Xzonn@outlook.com
@Software: Visual Studio Code
"""

import hashlib
import time
import requests

from bencoding import bencode, bdecode

from config import ReadConfig

class TorrentStatus:
    def __init__(self, hash, data):
        self.checking = data["state"] in ["checkingDL", "checkingUP", "checkingResumeData", "moving"]
        self.downloading = data["state"] in ["allocating", "downloading", "metaDL", "pausedDL", "queuedDL", "stalledDL", "forcedDL"]
        self.seeding = not (self.checking or self.downloading)

class Torrent:
    def __init__(self, hash, data):
        self.id = hash
        self.date_added = data["added_on"]
        self.rateUpload = data["upspeed"]
        self.status = TorrentStatus(hash, data)
        self.total_size = data["size"]

class BitTorrent:
    def __init__(self, config):
        self.host = config.get_qbittorrent_config('qbittorrent-host')
        self.port = config.get_qbittorrent_config('qbittorrent-port')
        self.username = config.get_qbittorrent_config('qbittorrent-username')
        self.password = config.get_qbittorrent_config('qbittorrent-password')
        self.download_path = config.get_qbittorrent_config('qbittorrent-download-path')

        self._session = requests.Session()
        self._main_data = None

        self.login()
    
    def login(self):
        self._session.post(f"http://{self.host}:{self.port}/api/v2/auth/login", {
            "username": self.username,
            "password": self.password
        })

    def download_from_file(self, filepath, paused=False):
        try:
            with open(filepath, "rb") as f:
                return self.download_from_content(f.read(), paused)
        except Exception as e:
            print('[ERROR] ' + repr(e))
            return None
    
    def download_from_content(self, content, paused=False):
        try:
            response = self._session.post(f"http://{self.host}:{self.port}/api/v2/torrents/add", data={
                "savepath": self.download_path,
                "paused": "true" if paused else "false",
                "tags": "byrbt_bot"
            }, files={
                "torrents": ("torrent.torrent", content, "application/x-bittorrent"),
            })
            if response.status_code == 200:
                hash = hashlib.sha1(bencode(bdecode(content)[b"info"])).hexdigest()
                time.sleep(1)
                main_data = self.get_main_data(True)
                if hash in main_data["torrents"]:
                    return Torrent(hash, main_data["torrents"][hash])
                else:
                    return None
            else:
                return None
        except Exception as e:
            print('[ERROR] ' + repr(e))
            return None
    
    def remove(self, ids, delete_data=False):
        try:
            response = self._session.post(f"http://{self.host}:{self.port}/api/v2/torrents/delete", data={
                "hashes": ids,
                "deleteFiles": "true" if delete_data else "false"
            })
            return True
        except Exception as e:
            print('[ERROR] ' + repr(e))
            return None

    def start_torrent(self, ids):
        try:
            response = self._session.post(f"http://{self.host}:{self.port}/api/v2/torrents/resume", data={
                "hashes": ids
            })
            return True
        except Exception as e:
            print('[ERROR] ' + repr(e))
            return None

    def get_list(self):
        try:
            torrents = self.get_main_data(True)["torrents"]
            torrent_list = []
            for hash, data in torrents.items():
                if "byrbt_bot" in data["tags"].split(","):
                    torrent_list.append(Torrent(hash, data))
            return torrent_list
        except Exception as e:
            print('[ERROR] ' + repr(e))
            return None
    
    def get_main_data(self, force=False):
        try:
            if self._main_data:
                if (time.time() - self._main_data["time"]) < 300 and not force:
                    return self._main_data["data"]
            response = self._session.post(f"http://{self.host}:{self.port}/api/v2/sync/maindata")
            self._main_data = {
                "time": time.time(),
                "data": response.json()
            }
            return self._main_data["data"]
        except Exception as e:
            print('[ERROR] ' + repr(e))
            return None

    def get_free_space(self, force=False):
        try:
            return self.get_main_data(force)["server_state"]["free_space_on_disk"]
        except Exception as e:
            print('[ERROR] ' + repr(e))
            return None


if __name__ == '__main__':
    config = ReadConfig(filepath='../config/config.ini')
    bit_torrent = BitTorrent(config)
    torrents = bit_torrent.get_list()
