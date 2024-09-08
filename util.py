# -*- encoding: utf-8 -*-

import logging
import requests
import pickle
import time
import os

from config import Config


MAX_TRIES = 5


class Util:
  def __init__(self, config: Config):
    self.config = config
    self.try_count = 5
    self.base_url = config.get_bot_config("byrbt-url")
    self.cookie_save_path = config.get_bot_config("cookie-path")
    self.session = requests.Session()
    self.session.headers = {
      "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    self.login()

  def get_url(self, url: str) -> str:
    return f"{self.base_url.removesuffix('/')}/{url.removeprefix('/')}"

  def is_login(self) -> bool:
    url = self.get_url("index.php")
    response = self.session.get(url)
    if "最近消息" in response.text:
      return True
    else:
      return False

  def login(self) -> bool:
    if os.path.exists(self.cookie_save_path):
      with open(self.cookie_save_path, "rb") as reader:
        cookies = pickle.load(reader)
        self.session.cookies.update(cookies)

    if self.is_login():
      return True
    for i in range(MAX_TRIES):
      url = self.get_url("takelogin.php")
      response = self.session.post(
        url,
        {
          "logintype": "username",
          "userinput": self.config.get_bot_config("username"),
          "password": self.config.get_bot_config("password"),
          "autologin": "yes",
        },
      )
      if "最近消息" in response.text:
        os.makedirs(os.path.dirname(self.cookie_save_path), 0o755, True)
        with open(self.cookie_save_path, "wb") as writers:
          pickle.dump(self.session.cookies, writers)
        return True

      if i < MAX_TRIES - 1:
        logging.warning(f"登录失败，1 秒后重试（剩余 {MAX_TRIES - i - 1} 次）")
        time.sleep(1)

    logging.error("登录失败！")
    raise Exception("登录失败！")
