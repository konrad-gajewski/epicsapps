"""
Base Image Panel to be inherited by other ImagePanels
"""

import wx
import time
import os
import shutil
import math
from threading import Thread
from cStringIO import StringIO
import base64

class ImagePanel_Base(wx.Panel):
    """Image Panel for FlyCapture2 camera"""

    def Start(self):
        "turn camera on"
        raise NotImplementedError('must provide Start()')

    def Stop(self):
        "turn camera off"
        raise NotImplementedError('must provide Stop()')

    def GrabWxImage(self, scale=1, rgb=True):
        "grab Wx Image, with scale and rgb=True/False"
        raise NotImplementedError('must provide GrabWxImage()')


    def __init__(self, parent,  camera_id=0, writer=None, leftdown_cb=None,
                 autosave_file=None, draw_objects=None, **kws):
        super(ImagePanel_Base, self).__init__(parent, -1, size=(800, 600))
        self.img_w = 800.5
        self.img_h = 600.5
        self.writer = writer
        self.leftdown_cb = leftdown_cb
        self.cam_name = '-'
        self.scale = 0.60
        self.count = 0
        self.draw_objects = None
        self.SetBackgroundColour("#F4F4F4")
        self.starttime = time.clock()
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)

        self.Bind(wx.EVT_SIZE, self.onSize)
        self.Bind(wx.EVT_PAINT, self.onPaint)
        self.Bind(wx.EVT_LEFT_DOWN, self.onLeftDown)

        self.autosave = True
        self.last_autosave = 0
        self.autosave_tmpf = None
        self.autosave_file = None
        self.autosave_time = 5.0
        self.autosave_thread = None
        self.full_size = None
        if autosave_file is not None:
            path, tmp = os.path.split(autosave_file)
            self.autosave_file = autosave_file
            self.autosave_tmpf = autosave_file + '_tmp'
            self.autosave_thread = Thread(target=self.onAutosave)
            self.autosave_thread.daemon = True

    def onSize(self, evt):
        frame_w, frame_h = evt.GetSize()
        self.scale = min(frame_w/self.img_w, frame_h/self.img_h)
        self.Refresh()
        evt.Skip()

    def onTimer(self, evt=None):
        self.Refresh()

    def onLeftDown(self, evt=None):
        """
        report left down events within image
        """
        evt_x, evt_y = evt.GetX(), evt.GetY()
        max_x, max_y = self.full_size
        img_w, img_h = self.bitmap_size
        pan_w, pan_h = self.panel_size
        pad_w, pad_h = (pan_w-img_w)/2.0, (pan_h-img_h)/2.0

        x = int(0.5 + (evt_x - pad_w)/self.scale)
        y = int(0.5 + (evt_y - pad_h)/self.scale)
        if self.leftdown_cb is not None:
            self.leftdown_cb(x, y, xmax=max_x, ymax=max_y)

    def onPaint(self, event):
        self.count += 1
        now = time.clock()
        elapsed = now - self.starttime
        if elapsed >= 2.0 and self.writer is not None:
            self.writer("  %.2f fps" % (self.count/elapsed))
            self.starttime = now
            self.count = 0

        self.scale = max(self.scale, 0.05)
        try:
            self.image = self.GrabWxImage(scale=self.scale, rgb=True)
        except ValueError:
            return
        if self.full_size is None:
            img = self.GrabWxImage(scale=1.0, rgb=True)            
            if img is not None:
                self.full_size = img.GetSize()
            
        try:
            bitmap = wx.BitmapFromImage(self.image)
        except ValueError:
            return

        img_w, img_h = self.bitmap_size = bitmap.GetSize()
        pan_w, pan_h = self.panel_size  = self.GetSize()
        pad_w, pad_h = (pan_w-img_w)/2.0, (pan_h-img_h)/2.0
        dc = wx.AutoBufferedPaintDC(self)
        dc.Clear()
        dc.DrawBitmap(bitmap, pad_w, pad_h, useMask=True)
        self.__draw_objects(dc, img_w, img_h, pad_w, pad_h)
        
    def __draw_objects(self, dc, img_w, img_h, pad_w, pad_h):
        dc.SetBrush(wx.Brush('Black', wx.BRUSHSTYLE_TRANSPARENT))
        if self.draw_objects is not None:
            for obj in self.draw_objects:
                shape = obj.get('shape', None)
                color = obj.get('color', None)
                if color is None:
                    color = obj.get('colour', 'Black')
                color = wx.Colour(*color)
                width = obj.get('width', 1.0)
                style = obj.get('style', wx.SOLID)
                args  = obj.get('args', [])
                kws   = obj.get('kws', {})
                
                method = getattr(dc, 'Draw%s' % (shape.title()), None)
                if shape.title() == 'Line':
                    args = [pad_w + args[0]*img_w,
                            pad_h + args[1]*img_h,
                            pad_w + args[2]*img_w,
                            pad_h + args[3]*img_h]
                elif shape.title() == 'Circle':
                    args = [pad_w + args[0]*img_w,
                            pad_h + args[1]*img_h,  args[2]*img_w]
                            
                if method is not None:
                    dc.SetPen(wx.Pen(color, width, style))
                    method(*args, **kws)

    def onAutosave(self):
        "autosave process, run in separate thread"
        # set autosave to False to abort autosaving
        while self.autosave:
            tfrac, tint = math.modf(time.time())
            if (tint -self.last_autosave) > self.autosave_time:
                self.last_autosave = tint
                try:
                    self.image.SaveFile(self.autosave_tmpf,
                                        wx.BITMAP_TYPE_JPEG)
                    shutil.copy(self.autosave_tmpf, self.autosave_file)
                except:
                    pass
                tfrac, tint = math.modf(time.time())
            # sleep for most of the remaining second
            time.sleep(0.17*self.autosave_time)

    def SaveImage(self, fname, filetype='jpeg'):
        """save image (jpeg) to file,
        return dictionary of image data, suitable for serialization
        """
        ftype = wx.BITMAP_TYPE_JPEG
        if filetype.lower() == 'png':
            ftype = wx.BITMAP_TYPE_PNG
        elif filetype.lower() in ('tiff', 'tif'):
            ftype = wx.BITMAP_TYPE_TIFF
            
        image = self.GrabWxImage(scale=1, rgb=True)
        if image is None:
            return

        width, height = image.GetSize()

        # make two device contexts -- copy bitamp to one,
        # use other for image+overlays
        dc_bitmap = wx.MemoryDC()
        dc_bitmap.SelectObject(wx.BitmapFromImage(image))
        dc_output = wx.MemoryDC()

        out = wx.EmptyBitmap(width, height)
        dc_output.SelectObject(out)

        # draw image bitmap to output
        dc_output.Blit(0, 0, width, height, dc_bitmap, 0, 0)
        # draw overlays to output
        self.__draw_objects(dc_output, width, height, 0, 0)
        # save to image file
        out.ConvertToImage().SaveFile(fname, ftype)

        # image.SaveFile(fname, ftype)        
        return self.image2dict(image)

    def image2dict(self, img=None):
        "return dictionary of image data, suitable for serialization"
        if img is None:
            img = self.GrabWxImage(scale=1, rgb=True)
        _size = img.GetSize()
        size = (_size[0], _size[1])
        return {'image_size': size, 
                'image_format': 'RGB', 
                'data_format': 'base64',
                'data': base64.b64encode(img.GetData())}
