# -*- encoding: utf-8 -*-

import configparser


class Config:
  def __init__(self, filepath: str = None):
    if filepath:
      config_path = filepath
    else:
      config_path = "config/config.ini"

    self.cf = configparser.ConfigParser()
    self.cf.read(config_path, encoding="utf8")

  def get_bot_config(self, param) -> str:
    value = self.cf.get("ByrBTBot", param, fallback=None)
    return value or ""

  def get_transmission_config(self, param) -> str:
    value = self.cf.get("Transmission", param, fallback=None)
    return value or ""

  def get_qbittorrent_config(self, param) -> str:
    value = self.cf.get("qBittorrent", param, fallback=None)
    return value or ""


if __name__ == "__main__":
  test = Config()
  t = test.get_bot_config("byrbt-url")
  print(t)
