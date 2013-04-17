#!/usr/bin/env python

import wx
import numpy
import Image
import sys

# use -d option for debug mode
if (len(sys.argv) > 1 and sys.argv[1].startswith('-d')):
    from lib import AD_Display
else:
    from epicsapps.ad_display import AD_Display


if __name__ == '__main__':
    prefix = None
    if len(sys.argv) > 1:
        prefix = sys.argv[1]
    
    app = wx.App()
    frame = AD_Display(prefix=prefix, app=app)
    frame.Show()
    app.MainLoop()
