# This file is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This file is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# See the GNU General Public License, <https://www.gnu.org/licenses/>.


import logging
import sys


class MLogger:
  """
 Logging levels are used in the following cases:
  WARNING: temporary error that the system can recover from.
  ERROR: May be a permanent or temporary error that the systmem may or may not
         recover from.
  CRITICAL: Permanent error that the system may never recover from.
 Usage:
  from magpie.src.mlogger import MLogger
  MLogger.init("DEBUG")
  l = MLogger.getLogger()
  l.debug("logging")
  if MLogger.isDebug():
      l.debug("logging"+self.lotsOfProcessing())
  20XX-XX-XX 20:27:22 MainThread DEBUG logging
  20XX-XX-XX 20:27:22 MainThread DEBUG logging lots of processing
  """
  level: int = logging.ERROR

  @staticmethod
  def setLevel() -> None:
    logging.basicConfig(
      format="%(asctime)s %(threadName)s %(levelname)s %(message)s",
      stream=sys.stdout,
      level=logging.DEBUG,
      datefmt="%Y-%m-%d %H:%M:%S"
    )

  @staticmethod
  def init(level: str) -> None:
    if level == "DEBUG":
      MLogger.level = logging.DEBUG
    elif level == "INFO":
      MLogger.level = logging.INFO
    elif level == "WARNING":
      MLogger.level = logging.WARNING
    elif level == "ERROR":
      MLogger.level = logging.ERROR
    else:
      raise Exception("MLogger do not understand=%s", level)

  @staticmethod
  def isDebug() -> bool:
    return MLogger.level >= logging.DEBUG

  @staticmethod
  def isInfo() -> bool:
    return MLogger.level >= logging.INFO

  @staticmethod
  def isWarning() -> bool:
    return MLogger.level >= logging.WARNING

  @staticmethod
  def isError() -> bool:
    return MLogger.level >= logging.ERROR

  @staticmethod
  def isCritical() -> bool:
    return MLogger.level >= logging.CRITICAL

MLogger.setLevel()
mlogger = logging.getLogger()