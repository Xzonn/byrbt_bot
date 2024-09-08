from enum import Enum


class TorrentStatus(Enum):
  CHECKING = 1
  DOWNLOADING = 2
  SEEDING = 3

  @classmethod
  def check_status(self, state: str):
    if state in {
      "checkingDL",
      "checkingUP",
      "checkingResumeData",
      "moving",
    }:
      return TorrentStatus.CHECKING
    if state in {
      "allocating",
      "downloading",
      "metaDL",
      "pausedDL",
      "queuedDL",
      "stalledDL",
      "forcedDL",
    }:
      return TorrentStatus.DOWNLOADING
    return TorrentStatus.SEEDING


class Torrent:
  id: str
  date_added: int
  upload_speed: str
  status: TorrentStatus
  total_size: str
  name: str

  def __str__(self):
    return f'Torrent "{self.name}"'


class Client:
  def download_from_file(self, filepath: str, paused: bool = False) -> Torrent:
    raise NotImplementedError

  def download_from_content(self, content: bytes, paused: bool = False) -> Torrent:
    raise NotImplementedError

  def get_torrents(self) -> list[Torrent]:
    raise NotImplementedError

  def remove_torrent(self, ids: str, delete_data: bool = False) -> bool:
    raise NotImplementedError

  def start_torrent(self, ids: str) -> bool:
    raise NotImplementedError

  def get_free_space(self, force: bool = False) -> int:
    raise NotImplementedError
