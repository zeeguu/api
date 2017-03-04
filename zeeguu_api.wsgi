#!/bin/env python
import zeeguu
zeeguu.app.logger.debug ( zeeguu.app.instance_path)
zeeguu.app.logger.debug ( zeeguu.app.config.get("SQLALCHEMY_DATABASE_URI"))
from zeeguu import app as application
