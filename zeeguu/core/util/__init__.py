#!/usr/bin/env python
# -*- coding: utf8 -*-

from zeeguu.core.util.encoding import JSONSerializable, encode, encode_error
from zeeguu.core.util.hash import text_hash, password_hash
from zeeguu.core.util.time import get_server_time_utc
from zeeguu.core.util.list import remove_duplicates_keeping_order
from zeeguu.core.util.reading_time_estimator import estimate_read_time
from .time_conversion import ms_to_m
