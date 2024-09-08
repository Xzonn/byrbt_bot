# -*- encoding: utf-8 -*-

import traceback
from clients.base import Client, TorrentStatus
from clients.qbittorrent import qBittorrent
from config import Config
from util import Util

import signal
import sys
import os
import pickle
import re
import time
from contextlib import ContextDecorator
from bs4 import BeautifulSoup, Tag


import logging

logging.basicConfig(filename="bot.log", level=logging.INFO)


# def print(*args):
#  logging.info(" ".join(args))


class TorrentInfo:
  def __init__(
    self,
    category: str,
    tag: str,
    is_seeding: bool,
    is_finished: bool,
    seed_id: int,
    title: str,
    seeding: int,
    downloading: int,
    finished: int,
    file_size: str,
  ):
    self.category = category
    self.tag = tag
    self.is_seeding = is_seeding
    self.is_finished = is_finished
    self.seed_id = seed_id
    self.title = title
    self.seeding = seeding
    self.downloading = downloading
    self.finished = finished
    self.file_size = file_size


def _handle_interrupt(signum, frame):
  sys.exit()  # will trigger a exception, causing __exit__ to be called


def convert_size(size: str) -> int:
  size = size.strip()
  if "TiB" in size:
    return int(float(size.replace("TiB", "").strip()) * 1024 * 1024 * 1024 * 1024)
  elif "GiB" in size:
    return int(float(size.replace("GiB", "").strip()) * 1024 * 1024 * 1024)
  elif "MiB" in size:
    return int(float(size.replace("MiB", "").strip()) * 1024 * 1024)
  elif "KiB" in size:
    return int(float(size.replace("KiB", "").strip()) * 1024)
  elif "B" in size:
    return int(float(size.replace("B", "").strip()))
  else:
    return 0


class TorrentBot(ContextDecorator):
  def __init__(self, config: Config, util: Util, client: Client):
    super(TorrentBot, self).__init__()
    self.config = config
    self.util = util
    self.client = client
    self.torrent_url = self.util.get_url("torrents.php")

    self.old_torrent = list()
    self.record_path = "./data/torrent.pkl"
    self.max_torrent_count = int(config.get_bot_config("max-torrent"))

    # all size in Byte
    max_torrent_total_size = int(config.get_bot_config("max-torrent-total-size"))
    self.max_torrent_total_size = max_torrent_total_size * 1024 * 1024 * 1024

    torrent_max_size = int(config.get_bot_config("torrent-max-size"))
    if torrent_max_size == 0:
      torrent_max_size = 1024
    self.torrent_max_size = torrent_max_size * 1024 * 1024 * 1024

    torrent_min_size = int(config.get_bot_config("torrent-min-size"))
    if torrent_min_size == 0:
      self.torrent_min_size = 1
    self.torrent_min_size = torrent_min_size * 1024 * 1024 * 1024

    if self.torrent_min_size > self.torrent_max_size:
      self.torrent_max_size, self.torrent_min_size = self.torrent_min_size, self.torrent_max_size

    self._filter_tags = ["免费", "免费&2x上传"]
    self._tag_map = {
      # highlight & tag
      "free": "免费",
      "twoup": "2x上传",
      "twoupfree": "免费&2x上传",
      "halfdown": "50%下载",
      "twouphalfdown": "50%下载&2x上传",
      "thirtypercentdown": "30%下载",
      # icon
      "2up": "2x上传",
      "free2up": "免费&2x上传",
      "50pctdown": "50%下载",
      "50pctdown2up": "50%下载&2x上传",
      "30pctdown": "30%下载",
    }
    self._cat_map = {
      "电影": "movie",
      "剧集": "episode",
      "动漫": "anime",
      "音乐": "music",
      "综艺": "show",
      "游戏": "game",
      "软件": "software",
      "资料": "material",
      "体育": "sport",
      "记录": "documentary",
    }

  def __enter__(self):
    print("启动byrbt_bot!")
    time.sleep(5)  # wait transmission process
    signal.signal(signal.SIGINT, _handle_interrupt)
    signal.signal(signal.SIGTERM, _handle_interrupt)
    if os.path.exists(self.record_path):
      with open(self.record_path, "rb") as reader:
        self.old_torrent = pickle.load(reader)
    return self

  def __exit__(self, exc_type, exc_val, exc_tb):
    print("退出")
    print("保存数据")
    os.makedirs(os.path.dirname(self.record_path), 0o755, True)
    with open(self.record_path, "wb") as writer:
      pickle.dump(self.old_torrent, writer, protocol=2)

  def _get_tag(self, tag):
    if tag == "":
      return ""
    else:
      tag = tag.split("_")[0]

    return self._tag_map.get(tag, "")

  def print_user_info(self, user_info_block: Tag):
    user_name = user_info_block.select_one(".nowrap").text
    user_info_text = user_info_block.text
    index_s = user_info_text.find("等级")
    index_e = user_info_text.find("当前活动")
    if index_s == -1 or index_e == -1:
      raise ValueError("未找到用户信息")
    user_info_text = user_info_text[index_s:index_e]
    user_info_text = re.sub(r"[\xa0\n]", " ", user_info_text)
    user_info_text = re.sub(r"\[[^\[]*\]", "", user_info_text).replace(":", "：")
    user_info_text = re.sub(r" *: *", "：", user_info_text).strip()
    user_info_text = re.sub(r"\s+", " ", user_info_text)
    logging.info(f"用户名：{user_name} {user_info_text}")

  def get_filtered_torrents(self, rows: list[Tag]) -> list[TorrentInfo]:
    torrent_infos: list[TorrentInfo] = []
    for row in rows:
      cells = row.select("td.rowfollow")[1:]
      if len(cells) < 8:
        continue

      category = cells[0].find("a").text.strip()

      # 主要信息的td
      main_info = cells[1]
      main_td = cells[1].select("table > tr > td")[0]
      if main_td.find("div"):
        # 置顶
        main_td = cells[1].select("table > tr > td")[1]

      # 标记
      tag = ""
      row_class = row.attrs["class"][0]
      if row_class.endswith("_bg"):
        tag = self._tag_map.get(row_class.removesuffix("_bg"), "")

      icons = main_info.select("img")
      is_seeding = False
      is_finished = False
      for icon in icons:
        icon_src = icon.attrs["src"]
        if icon_src == "/pic/seeding.png":
          is_seeding = True
          continue
        elif icon_src == "/pic/finished.png":
          is_finished = True
          continue

        icon_class = icon.attrs.get("class", [""])[0]
        if not tag and icon_class.startswith("pro_"):
          tag = self._tag_map.get(icon_class.removeprefix("pro_"), tag)

      if not tag:
        tags = [_.attrs["class"][0] for _ in main_info.select("span > span") if "class" in _.attrs]
        for _ in tags:
          tag = self._tag_map.get(_, tag)

      if tag not in self._filter_tags:
        continue

      torrent_link = main_info.select_one("a")
      # 种子id
      seed_id: int = re.findall(r"id=(\d+)", torrent_link.attrs["href"])[0]

      # 标题
      title: str = torrent_link.attrs["title"]

      file_size = cells[4].text.replace("\n", " ")
      seeding = int(cells[5].text) if cells[5].text.isdigit() else -1
      downloading = int(cells[6].text) if cells[6].text.isdigit() else -1
      finished = int(cells[7].text) if cells[7].text.isdigit() else -1

      torrent_info = TorrentInfo(
        category, tag, is_seeding, is_finished, seed_id, title, seeding, downloading, finished, file_size
      )
      torrent_infos.append(torrent_info)

    return torrent_infos

  # 获取可用的种子的策略，可自行修改
  def get_favorable_torrents(self, torrents: list[TorrentInfo]) -> list[TorrentInfo]:
    farvorable_torrents = []
    is_strict = len(torrents) >= 20
    if is_strict:
      # 遇到free或者免费种子太过了，择优选取，标准是(下载数/上传数)>20，并且文件大小大于20GB
      logging.info("符合要求的种子过多，可能开启Free活动了，提高种子获取标准")

    for torrent_info in torrents:
      if torrent_info.seed_id in self.old_torrent or torrent_info.is_seeding or torrent_info.is_finished:
        continue

      if torrent_info.seeding <= 0 or torrent_info.downloading < 0:
        continue
      if torrent_info.downloading / torrent_info.seeding < (20 if is_strict else 0.6):
        continue
      file_size = convert_size(torrent_info.file_size)
      if is_strict and file_size < 20 * 1024 * 1024 * 1024 or file_size > self.torrent_max_size:
        continue
      elif file_size < self.torrent_min_size or file_size > self.torrent_max_size:
        continue

      farvorable_torrents.append(torrent_info)

    return farvorable_torrents

  def check_max_torrents(self, add_num: int = 0):
    torrent_list = self.client.get_torrents()
    if not torrent_list:
      logging.error("获取种子列表失败")
      return

    torrent_length = len(torrent_list) + add_num
    torrent_list.sort(key=lambda x: (x.upload_speed, x.date_added))

    for torrent in torrent_list:
      if torrent_length <= self.max_torrent_count:
        break

      # 正在检查或上传速度 > 500 KiB/s
      if torrent.status == TorrentStatus.CHECKING or torrent.upload_speed > 500 * 1024 * 1024:
        continue

      if self.client.remove_torrent(torrent.id, True):
        logging.info(f"已删除种子：{torrent.name}")
        torrent_length -= 1
      else:
        logging.info(f"删除种子失败：{torrent.name}")

  def download(self, torrent_id: int):
    download_url = self.util.get_url(f"download.php?id={torrent_id}")
    response = self.util.session.get(download_url)
    if response.status_code != 200:
      logging.error(f"下载种子失败：{torrent_id}")
      return False

    self.client.download_from_content(response.content)

  def check_disk_space(self) -> bool:
    min_free_space = int(self.config.get_bot_config("min-free-space-size")) * 1024 * 1024 * 1024
    free_space = self.client.get_free_space()
    if free_space == 0:
      return False

    if free_space >= min_free_space:
      return True

    logging.info("磁盘空间不足，尝试删除种子")
    torrent_list = self.client.get_torrents()
    if not torrent_list:
      logging.warning("获取种子列表失败")
      return False

    torrent_list.sort(key=lambda x: (x.upload_speed, x.date_added))
    for torrent in torrent_list:
      if free_space > min_free_space:
        break

      # 正在检查或上传速度 > 500 KiB/s
      if torrent.status == TorrentStatus.CHECKING or torrent.upload_speed > 500 * 1024 * 1024:
        continue

      if self.client.remove_torrent(torrent.id, True):
        logging.info(f"已删除种子：{torrent.name}")
        free_space += torrent.total_size
      else:
        logging.info(f"删除种子失败：{torrent.name}")

    return self.client.get_free_space(True) > min_free_space

  def start(self):
    scan_interval_in_sec = 60
    check_disk_space_interval_in_sec = 500
    last_check_disk_space_time = -1
    while True:
      try:
        now = int(time.time())
        if now - last_check_disk_space_time > check_disk_space_interval_in_sec:
          logging.info("检查磁盘容量")
          if self.check_disk_space():
            last_check_disk_space_time = now
          else:
            logging.error("检查磁盘容量失败！")
            time.sleep(scan_interval_in_sec)
            continue

        logging.info("载入种子列表……")
        response = self.util.session.get(self.torrent_url)
        if "未登录" in response.text:
          logging.error("未登录")
          self.util.login()
          continue

        torrents_soup = BeautifulSoup(response.text, "html.parser")

        try:
          user_info_block = torrents_soup.select_one("#info_block").select_one(".navbar-user-data")
          self.print_user_info(user_info_block)
        except Exception:
          logging.error(traceback.format_exc())
          return False

        torrent_rows = torrents_soup.select(".torrents > tr")
        filtered_torrents = self.get_filtered_torrents(torrent_rows)

        logging.info("正在促销的种子：")
        for i, info in enumerate(filtered_torrents):
          logging.info(f"#{i:>2d} ({info.seed_id}) {info.title}, {info.file_size}")

        favorable_torrents = self.get_favorable_torrents(filtered_torrents)
        logging.info("筛选后的种子：")
        for i, info in enumerate(favorable_torrents):
          logging.info(f"#{i:>2d} ({info.seed_id}) {info.title}, {info.file_size}")

        self.check_max_torrents(len(favorable_torrents))
        for torrent in favorable_torrents:
          if self.download(torrent.seed_id) is False:
            logging.warning(f"下载种子失败：{torrent.title}")
            continue
      except Exception:
        logging.error(traceback.format_exc())
      finally:
        time.sleep(scan_interval_in_sec)
        logging.info("")


if __name__ == "__main__":
  os.chdir(os.path.dirname(__file__))
  config = Config("config/config.ini")
  util = Util(config)
  client = qBittorrent(config)
  with TorrentBot(config, util, client) as byrbt_bot:
    byrbt_bot.start()
