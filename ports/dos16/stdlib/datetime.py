"""Small datetime compatibility layer for Py86 (local DOS date/time only).

Supports datetime.datetime.now() and the usual date/time fields. This is not
CPython's complete datetime module (no timezone, timedelta, or arithmetic).
"""
import time


class datetime:
    def __init__(self, year, month, day, hour=0, minute=0, second=0,
                 microsecond=0):
        self.year = year
        self.month = month
        self.day = day
        self.hour = hour
        self.minute = minute
        self.second = second
        self.microsecond = microsecond

    @classmethod
    def now(cls):
        fields = time.localtime()
        return cls(fields[0], fields[1], fields[2], fields[3], fields[4],
                   fields[5])
