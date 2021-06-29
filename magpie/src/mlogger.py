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

# Logging levels are used in the following cases:
#
#  WARNING: temporary error that the system can recover from.
#  ERROR: May be a permanent or temporary error that the systmem may or may not
#         recover from.
#  CRITICAL: Permanent error that the system may never recover from.
# 
# Usage:
#  from magpie.mlogger import MLogger
#  MLogger.init("DEBUG")
#  l = MLogger.getLogger()
#  l.debug("logging")
#  20XX-XX-XX 20:27:22 MainThread DEBUG logging
#  
import logging
import sys


class MLogger:

  @staticmethod
  def setLevel(level: int) -> None:
    logging.basicConfig(
      format="%(asctime)s %(threadName)s %(levelname)s %(message)s",
      stream=sys.stdout,
      level=level,
      datefmt="%Y-%m-%d %H:%M:%S"
    )

  @staticmethod
  def init(level: str) -> None:
    if level == "DEBUG":
      MLogger.setLevel(logging.DEBUG)
    elif level == "INFO":
      MLogger.setLevel(logging.INFO)
    elif level == "WARNING":
      MLogger.setLevel(logging.WARNING)
    elif level == "ERROR":
      MLogger.setLevel(logging.ERROR)
    else:
      raise Exception("MLogger do not understand=%s", lev)

  @staticmethod
  def getLogger() -> logging.Logger:
    return logging.getLogger()

