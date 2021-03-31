#!/usr/bin/env python3
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

