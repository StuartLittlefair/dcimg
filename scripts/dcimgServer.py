#!/usr/bin/env python
import tornado.ioloop
from tornado.web import RequestHandler, Application, url
import struct
import numpy as np
import io
import dcimg
import os, glob
import pkg_resources
from lxml import etree

class MainHandler(RequestHandler):
    def initialize(self, db):
        self.db = db

    def get(self,path):
        print(path)
        try:
            action = self.get_argument('action')
        except: 
            raise tornado.web.HTTPError(400)
        if action == "dir":
            self.list_dir(self.db['dir'],path)
        else:
            raise tornado.web.HTTPError(400)

    def list_dir(self,root,stub):
        path = os.path.abspath(os.path.join(root,stub,"*.dcimg"))
        files = [os.path.splitext(
                    os.path.basename(file))[0] for file in glob.glob(path)]
        self.write("\n".join(files))
          
class RunHandler(RequestHandler):

    def initialize(self, db):
        self.db = db
        self.currRun = None
        self.dcimg = None
        
    def get(self, run_id):
        try:
            action = self.get_argument('action')
            if action == "get_xml":
                self.get_xml(run_id)
            elif action == "get_frame":
                try:
                    frame_id = self.get_argument('frame')
                    self.get_frame(run_id,int(frame_id))
                except:
                    raise tornado.web.HTTPError(400)
            else:
                raise tornado.web.HTTPError(400)
        except:
            raise tornado.web.HTTPError(400)

    def load_Ddata(self,run_id):
        # if this is already open and correct, do nothing
        if self.currRun == run_id and self.dcimg is not None:
            return
        self.currRun = run_id
        self.dcimg = dcimg.Ddata(run_id)

    def get_xml(self,run_id):
        # load template from data
        xmlFile = pkg_resources.resource_filename('dcimg','data/template.xml')
        xml = etree.parse(xmlFile)
        
        # create a dcimg.Ddata object, if necessary
        self.load_Ddata(os.path.join(self.db['dir'],run_id))
        
        # now we have to override ULTRASPEC specific stuff with MOSCAM stuff
        # start with something easy, xbin and ybin
        xbin, ybin = self.dcimg.xbin, self.dcimg.ybin
        # use X_PATH syntax to find and set XML elements
        # see http://www.diveintopython3.net/xml.html
        xml.find('//parameter_status[@name="X_BIN"]').attrib['value'] = str(xbin)
        xml.find('//parameter_status[@name="Y_BIN"]').attrib['value'] = str(ybin)
        
        # now X_SIZE and related. This needs to be set to the total number of binned pixels
        x_size = int(self.dcimg.nx*self.dcimg.ny)
        xml.find('//parameter_status[@name="X_SIZE"]').attrib['value'] = str(x_size)
        xml.find('//frame_status').attrib['ncolumns'] = str(x_size)
        xml.find('//byte_count').attrib['total_bytes'] = str(x_size+16)
        xml.find('//byte_count').attrib['read_bytes'] = str(x_size+16)
        xml.find('//data_status').attrib['framesize'] = str(x_size*2 + 32)
        xml.find('//parameter_status[@name="X1_SIZE"]').attrib['value'] = str(self.dcimg.nx)
        xml.find('//parameter_status[@name="Y1_SIZE"]').attrib['value'] = str(self.dcimg.ny)

        # now DWELL, set to exposure time
        xml.find('//parameter_status[@name="DWELL"]').attrib['value'] = str(int(10000*self.dcimg.exposeTime))
    
        # now the total CHIP size needs setting in a few places
        xml.find('//window_status').attrib['ysize'] = str(self.dcimg.nymax)
        xml.find('//window_status').attrib['xsize'] = str(self.dcimg.nxmax)
        xml.find('//chip_status').attrib['rows']    = str(self.dcimg.nymax)
        xml.find('//chip_status').attrib['columns'] = str(self.dcimg.nxmax)

        # write out using BytesIO
        out_xml = io.BytesIO()
        xml.write(out_xml)
        self.write(out_xml.getvalue())
        
    def get_frame(self,run_id,frame_id):
        """
        read in frame from DCIMG file using dcimg module
        send bytes back in a format that the UCAM software is expecting
        this is a set of header words, followed by the data in 16bit format
        
        data is little-endian
        
        currently, read_header.cc in the ULTRACAM pipeline software only reads BYTES
        0  4,5,6,7   8,9,10,11 and 12,13,14,15   16,17,18,19    24,25
        
        the header looks like this:
            status word (2 bytes)
            engineering word (2 btyes)
            frame number (4 bytes)
            exposure time (4 bytes)
            timestamp (14 bytes)
            unused header bytes (6 bytes)
            
        the various words are described below
        status word
        -----------
        Bit 15: Detector power status -> 0 or 1 for off/on
        Bit 14: Timestamp availability -> 0 or 1 for absent/there
        
        Bit 4: Error Flag for later data? 
        Bits 3-12: Unused -> 0
        Bit 2: Error Flag -> 0 or 1 for OK/NOK
        Bit 1: Stop Flag -> 0 or 1 for application completed full observation, 1 for stopped early
        Bit 0: Last Frame flag -> 0 or 1 for not last frame/last frame
        
        Args:
            run_id: int
            frame_id: int
        """
        # create a dcimg.Ddata object, if necessary
        self.load_Ddata(os.path.join(self.db['dir'],run_id))
        
        self.dcimg.set(1+frame_id)
        
        
        # start with array of 32 NULL bytes
        hdr_bytes = bytearray(32)

        ERR = 1<<4
        STOP = 1<<1
        LAST = 1<<0
        # set last, stop, err flags
        last = False
        err  = False
        stop = frame_id+1 == self.dcimg.numexp
        if last:
            hdr_bytes[0] = hdr_bytes[0] | LAST
        if err:
            hdr_bytes[0] = hdr_bytes[0] | ERR        
        if stop:
            hdr_bytes[0] = hdr_bytes[0] | STOP 

        # set frame number (encode as unsigned int, little endian)
        hdr_bytes[4:8] = struct.pack('<I',frame_id+1)
        
        # set exposure time bytes
        expTime = self.dcimg.exposeTime # fudge to same as XML
        hdr_bytes[8:12] = struct.pack('<I',int(10000*expTime))
        
        # TIMESTAMP
        # bytes 12-15 are timestamp, number of seconds
        # bytes 16-19 are timestamp, number of nanoseconds / 100
        timestamp = self.dcimg.timestamps[1+frame_id].value
        nsecs  = int(timestamp)
        nnsecs = int(1e7 * (timestamp-int(timestamp)))
        hdr_bytes[12:16] = struct.pack('<I',nsecs)
        hdr_bytes[16:20] = struct.pack('<I',nnsecs)
        
        # GPS STATUS CODE
        GPS_STATUS = 0x04 # GPS has synced
        # unsigned short, little endian
        hdr_bytes[24:26] = struct.pack('<H',GPS_STATUS)

        # IMAGE DATA
        ccd = self.dcimg()
        if isinstance(ccd,np.ndarray):
            im = ccd.astype('<u2')
        else:
            im = ccd[0].data.astype('<u2')   
        im_bytes = bytearray(im.tobytes())

        # write the stuff
        self.set_header("Content-type",  "image/data")
        self.set_header('Content-length', len(hdr_bytes)+len(im_bytes))
        self.write(io.BytesIO(hdr_bytes).getvalue())
        self.write(io.BytesIO(im_bytes).getvalue())
        
def make_app(db):
    return Application([
        # url routing. look for runXXX pattern first, assume everything else
        # is a directory for e.g uls
        url(r"/(run[0-9]+)", RunHandler, dict(db=db), name="run"),
        url(r"/(.*)", MainHandler, dict(db=db), name="path")
    ],debug=False)

def run_fileserver(dir):
    db = {'dir':dir}
    app = make_app(db)
    app.listen(8007)
    tornado.ioloop.IOLoop.current().start()    

if __name__ == "__main__":
    import argparse
    usage = """python fileserver.py dir"""
    parser = argparse.ArgumentParser(description="DCIMG FileServer",usage=usage)
    parser.add_argument('dir',help="directory to serve")    
    args = parser.parse_args()    
    run_fileserver(args.dir)