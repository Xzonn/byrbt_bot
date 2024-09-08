# -*- encoding: utf-8 -*-

import hashlib
import logging
import time
import traceback
from typing import Any
import requests
from bencoding import bencode, bdecode

from config import Config
from clients.base import Client, Torrent, TorrentStatus


class qBittorrentTorrent(Torrent):
  def __init__(self, hash: str, data: dict[str, Any]):
    self.id = hash
    self.date_added = data["added_on"]
    self.upload_speed = data["upspeed"]
    self.status = TorrentStatus.check_status(data["state"])
    self.total_size = data["size"]
    self.name = data["name"]


class qBittorrent(Client):
  def __init__(self, config: Config):
    self.host = config.get_qbittorrent_config("qbittorrent-host")
    self.port = config.get_qbittorrent_config("qbittorrent-port")
    self.username = config.get_qbittorrent_config("qbittorrent-username")
    self.password = config.get_qbittorrent_config("qbittorrent-password")
    self.download_path = config.get_qbittorrent_config("qbittorrent-download-path")

    self.session = requests.Session()
    self._main_data = None

    self.login()

  def get_api_path(self, path: str):
    return f"http://{self.host}:{self.port}/api/v2/{path}"

  def login(self):
    self.session.post(
      self.get_api_path("auth/login"),
      {
        "username": self.username,
        "password": self.password,
      },
    )

  def download_from_file(self, filepath: str, paused: bool = False):
    try:
      with open(filepath, "rb") as reader:
        return self.download_from_content(reader.read(), paused)
    except Exception:
      logging.error(traceback.format_exc())
      return None

  def download_from_content(self, content: bytes, paused: bool = False):
    try:
      response = self.session.post(
        self.get_api_path("torrents/add"),
        {
          "savepath": self.download_path,
          "paused": "true" if paused else "false",
          "tags": "byrbt_bot",
        },
        files={
          "torrents": (
            "torrent.torrent",
            content,
            "application/x-bittorrent",
          ),
        },
      )
      if response.status_code == 200:
        hash = hashlib.sha1(bencode(bdecode(content)[b"info"])).hexdigest()
        time.sleep(1)
        main_data = self.get_main_data(True)
        if hash in main_data["torrents"]:
          return qBittorrentTorrent(hash, main_data["torrents"][hash])
        else:
          return None
      else:
        return None
    except Exception:
      logging.error(traceback.format_exc())
      return None

  def remove_torrent(self, ids: str, delete_data: bool = False) -> bool:
    try:
      self.session.post(
        self.get_api_path("torrents/delete"),
        {
          "hashes": ids,
          "deleteFiles": "true" if delete_data else "false",
        },
      )
      return True
    except Exception:
      logging.error(traceback.format_exc())
      return False

  def start_torrent(self, ids: str) -> bool:
    try:
      self.session.post(
        self.get_api_path("torrents/resume"),
        {
          "hashes": ids,
        },
      )
      return True
    except Exception:
      logging.error(traceback.format_exc())
      return False

  def get_torrents(self) -> list[Torrent]:
    try:
      torrents: dict[str, dict] = self.get_main_data(True)["torrents"]
      torrent_list: list[qBittorrentTorrent] = []
      for hash, data in torrents.items():
        if "byrbt_bot" in data["tags"].split(","):
          torrent_list.append(qBittorrentTorrent(hash, data))
      return torrent_list
    except Exception:
      logging.error(traceback.format_exc())
      return []

  def get_main_data(self, force: bool = False) -> dict:
    try:
      if self._main_data:
        if (time.time() - self._main_data["time"]) < 300 and not force:
          return self._main_data["data"]
      response = self.session.post(self.get_api_path("sync/maindata"))
      self._main_data = {
        "time": time.time(),
        "data": response.json(),
      }
      return self._main_data["data"]
    except Exception:
      logging.error(traceback.format_exc())
      return {}

  def get_free_space(self, force: bool = False) -> int:
    try:
      return self.get_main_data(force)["server_state"]["free_space_on_disk"]
    except Exception:
      logging.error(traceback.format_exc())
      return 0
