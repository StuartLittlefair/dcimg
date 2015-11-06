from __future__ import print_function
import numpy as np
from math import floor, log10
import os
from astropy.time import Time
#import display

# labview XML parsing 
from .lvxml import *

from trm.ultracam.Constants import *
from trm.ultracam.CCD import CCD
from trm.ultracam.MCCD import MCCD
from trm.ultracam.Window import Window
from trm.ultracam.Uhead import Uhead
from trm.ultracam.UErrors import PowerOnOffError, UltracamError
from trm.ultracam.Raw import Rwin
from trm.ultracam import Time as UTime

import six

class DcimgError(Exception):
    pass
    
class DendError(Exception):
    """Special Exception to be raised at end of file"""
    pass
class Dhead(object):
    """Represents essential metadata info of MOSCAM data read from the
    run###.xml.

    Parameters
    ----------
    run : string 
        run name e.g. 'run002'. Can include path to disk file.
        

    Attributes
    -----------
    run : str
        run number

    framesize : int 
        total number of bytes per frame.

    instrument : string
        instrument name.
        
    user : dictionary 
        dictionary of user information. May be empty

    win : Rwin
        A list of Rwin objects, one per window. 

    xbin : int
        binning factor in X direction

    ybin : int
        binning factor in Y direction

    nxmax : int
        maximum X dimension, unbinned pixels

    nymax : int
        maximum Y dimension, unbinned pixels.

    exposeTime : float
        exposure delay, secs
        
    timeStamp : float
        GPS (UTC) timestamp at exposure start
        
    nsats : int
        number of satellites used for GPS timestamp
    """    
    def __init__(self, run):
        if not run.endswith('.xml'):
            self.run = run
            run += '.xml'
        else:
            self.run = os.path.splitext(run)[0]
        
        # read in Labview XML data
        LabviewXMLData  = LabviewXMLDataLoader()
        LabviewXMLData.loadXMLDataFile(run)
        
        # now we can process XML data to populate attributes
        # below is a convenience function to make this easy
        def getXMLAttr(attrName):
            structure = parseLVDataXML_ReturnValue(LabviewXMLData.XMLDocNode,attrName)
            # if it's a structure, we want the "Val" attr 
            try:
                return structure['Val']
            except:
                return structure
                
        self.exposeTime = getXMLAttr("Exposure  (secs)")
        self.user = {}
        self.user['object'] = getXMLAttr("Object")
        self.user['observer'] = getXMLAttr("Observer")
        cam = getXMLAttr('Camera Model')
        if cam == "C11440-22C":
            self.instrument = "MOSCAM"
            self.nymax = 2048
            self.nxmax = 2048
        else:
            raise DcimgError("Unrecognised Instrument: {}".format(cam))
        self.nsats = getXMLAttr("nsats")
        self.timestamp = getXMLAttr("timestamp") 
        
        
class Ddata(Dhead):
    """
    Callable, iterable object to represent MOSCAM raw data (dcimg) files
    
    This class is based strongly on :class:`trm.ultracam.Rdata`, so it's
    use should be familiar to ULTRACAM/ULTRASPEC afficionados.
    
    The idea is to open the file, and then the object generated can be
    used to deliver frames by specifying a frame number. Frames can be
    read individually e.g.::

      ddat = Ddata('run045')
      fr10 = ddat(10)
      fr11 = rddat()

    reads frame numbers 10 and then 11 in from 'run045', or sequentially::

      for frm in Ddata('run045'):
         print 'nccd = ',frm.nccd()

    Ddata maintains an internal file object that is always at the start of a
    frame. This enables sequential reads to be swift. If an attempt is made
    to access a frame that does not exist, it defaults to the start of the
    file.

    The above code returns :class:`trm.ultracam.CCD` objects for MOSCAM data.     
    """    
    def __init__(self,run,nframe=1,flt=True):
        """Create Ddata object
        
        Connects to a raw dcimg file for reading. The file is kept open.
        The file pointer is set to the start of frame nframe. The Ddata
        object can then generate CCD objects through being called
        as a function or iterator.
        
        Parameters
        -----------
        run : str
            run name, e.g 'run026'.
        nframe  : int
            frame number for first read, starting at 1 for first frame
        flt : bool
            True for reading data in as floats. This is the default for
            safety, however the data are stored on disk as unsigned 2-byte
            ints. If you are not doing much to the data, and wish to keep them
            in this form for speed and efficiency, then set flt=False.  This
            parameter is used when iterating through an Ddata. The __call__
            method can override it.
        """
        
        # initialise header
        super(Ddata, self).__init__(run)
        # Attributes set are:
        #
        # _fobj   -- file object opened on data file (set to None if using server)
        # _nf     -- next frame to be read
        # _run    -- name of run
        # _flt    -- whether to read as float (else uint16)
        if six.PY3:
            """
            This exists because in Python 3, `open()` returns an
            `io.BufferedReader` by default.  This is bad, because
            `io.BufferedReader` doesn't support random access, which we may need in
            some cases.  In the Python 3 case (implemented in the py3compat module)
            we must call open with buffering=0 to get a raw random-access file
            """            
            self._fobj   = open(self.run + '.dcimg', 'rb', buffering=0) 
        else:
            self._fobj   = open(self.run + '.dcimg', 'rb')            
        self._nf = nframe
        self._run = self.run
        self._flt = flt
        
        # first we read in the essential metadata from the dcimg file and add properties
        hdr_bytes = self._read_header_bytes()
        hdr       = self._parse_header_bytes(hdr_bytes)
        
        # set attributes from header
        self.framesize = hdr['bytes_per_img']
        self.xbin      = hdr['binning']
        self.ybin      = hdr['binning']
        self.bitdepth  = hdr['bitdepth']
        self.ny        = hdr['ysize']
        self.nx        = hdr['xsize']
        self.numexp    = hdr['nframes']
        self._footloc  = hdr['footer_loc']

        # now read in timing info from footer which follows images
        self.timestamps = self.read_timestamps()
        
        # TODO: there's more metadata in the DCIMG files that I don't understand
        # I must manage to decipher this at some point
        
        # position read pointer ready for image access
        if nframe != 1:
            self._fobj.seek(232 + self.framesize*(nframe-1))
            
    def __iter__(self):
        """
        Generator to allow Ddata to function as an iterator.
        This produces the same type of object as __call__ does.
        """
        try:
            while 1:
                yield self.__call__(flt=self._flt)
        except DendError:
            pass

    def set(self, nframe=1):
        """
        Sets the internal file pointer to point at frame nframe.

        Args
        ----
          nframe : int 
            frame number to get, starting at 1. 0 for the
            last (complete) frame. A value of 'None' will be
            ignored. A value < 0 will cause an exception. A
            value greater than the number of frames in the
            file will work, but will cause an exception to be
            raised on the next attempted read.
        """
        # position read pointer
        if nframe is not None:
            if nframe < 0:
                raise DcimgError('Ddata.set: nframe < 0')
            elif nframe == 0:
                # go to last valid frame
                self._fobj.seek(232 + self.framesize*(self.numexp-1))
                self._nf = self.numexp
            elif self._nf != nframe:
                self._fobj.seek(232+self.framesize*(nframe-1))
                self._nf = nframe 
                
    def __call__(self, nframe=None, flt=None):
        """
        Reads the data of frame nframe (starts from 1) and returns a
        CCD object, depending upon the type of data. If nframe is None, 
        just reads whatever frame we are on. Raises an exception if it fails to 
        read data.  Resets to start of the file in this case. 
        
        The data are stored internally 2-byte unsigned ints.

        Args
        ----
        nframe : int
            frame number to get, starting at 1. 0 for the last
            (complete) frame. None just returns the next frame.

        flt : bool
            Set True to return data as floats. The data are stored on
            disk as unsigned 2-byte ints. If you are not doing much to
            the data, and wish to keep them in this form for speed and
            efficiency, then set flt=False. 
        """
        if flt is None: flt = self._flt
        if self._nf > self.numexp:
            raise DendError("Number of frames exceeded")
            
        # position read pointer
        self.set(nframe)
        
        im_bytes = self._fobj.read(self.framesize)                      
        img = np.fromstring(im_bytes, np.uint16).reshape(self.ny,self.nx)
        if flt:
            img = img.astype(np.float)

        # move frame counter on by one            
        self._nf += 1

        # now to build a :class:trm.ultracam.CCD object from the data
        # first we build a header
        head = Uhead()
        head.add_entry('User','Data entered by user at telescope')
        head.add_entry('User.target', self.user['object'], ITYPE_STRING, 'Object name')
        head.add_entry('User.observers', self.user['observer'], ITYPE_STRING,'Observers')
        
        head.add_entry('Instrument','Instrument setup information')
        head.add_entry('Instrument.instrument',self.instrument,ITYPE_STRING,\
            'Instrument identifier')
        head.add_entry('Instrument.framesize',self.framesize,ITYPE_INT,\
            'Total number of bytes per frame')
            
        head.add_entry('Run', 'Run specific information')
        head.add_entry('Run.run',self.run,ITYPE_STRING,'run the frame came from')
        head.add_entry('Run.expose',self.exposeTime,ITYPE_FLOAT,'exposure time')
        
        head.add_entry('Frame', 'Frame specific information')
        head.add_entry('Frame.frame',self._nf-1,ITYPE_INT,'frame number within run')
        
        # interpret data
        xbin, ybin = self.xbin, self.ybin
        if self.instrument == "MOSCAM":
            # 2 vertically stacked windows, split at centre of chip
            wins = []
            wins.append( Window(img[:self.ny/2, :], 0,         0, xbin, ybin) )
            wins.append( Window(img[self.ny/2:, :], 0, self.ny/2, xbin, ybin) )
            
            # Build the UTime
            # expTime is same as delay
            ts = self.timestamps[self._nf-2]
            time = UTime(ts.mjd, self.exposeTime, True, '')

            # Build the CCD
            return CCD(wins, time, self.nxmax, self.nymax, True, head)
        else:
            raise DcimgError("Instrument unknown")
            
    def nframe(self):
        """
        Returns next frame number to be read if reading
        sequentially (starts at 1)
        """
        return self._nf
        
    def time(self, nframe=None):
        if nframe:
            return self.timestamps[nframe]
        else:
            return self.timestamps[self._nf]            
        
    def _read_header_bytes(self):
        self._fobj.seek(0)
        # initial metadata block is 232 bytes
        return self._fobj.read(232)
        
    def _parse_header_bytes(self,hdr_bytes):
        """Decode header information from DCIMG files
    
        Since the DCIMG format is not documented, this metadata is reverse engineered and may 
        be in error
        """
        header = {}
        bytes_to_skip = 4*int.from_bytes(hdr_bytes[8:12],byteorder='little')        
        curr_index = 8 + bytes_to_skip
    
        # nframes
        nfrms = int.from_bytes(hdr_bytes[curr_index:curr_index+4],byteorder='little')
        header['nframes'] = nfrms
    
        # filesize
        curr_index = 48
        header['filesize'] = int.from_bytes(hdr_bytes[curr_index:curr_index+4],byteorder='little')
    
        # bytes per pixel
        curr_index = 156
        header['bitdepth'] = 8*int.from_bytes(hdr_bytes[curr_index:curr_index+4],byteorder='little')
    
        # footer location 
        curr_index = 120
        header['footer_loc'] = int.from_bytes(hdr_bytes[curr_index:curr_index+4],byteorder='little')
    
        # number of columns (x-size)
        curr_index = 164
        header['xsize_req'] = int.from_bytes(hdr_bytes[curr_index:curr_index+4],byteorder='little')
    
        # bytes per row
        curr_index = 168
        header['bytes_per_row'] = int.from_bytes(hdr_bytes[curr_index:curr_index+4],byteorder='little')
        #if we requested an image of nx by ny pixels, then DCIMG files
        #for the ORCA flash 4.0 still save the full array in x.
        header['xsize'] = header['bytes_per_row']/2
    
        # binning
        # this only works because MOSCAM always reads out 2048 pixels per row
        # at least when connected via cameralink. This would fail on USB3 connection
        # and probably for other cameras.
        # TODO: find another way to work out binning
        header['binning'] = int(4096/header['bytes_per_row'])

        # funny entry pair which references footer location
        curr_index = 192
        odd = int.from_bytes(hdr_bytes[curr_index:curr_index+4],byteorder='little')
        curr_index = 40
        offset = int.from_bytes(hdr_bytes[curr_index:curr_index+4],byteorder='little')
        header['footer_loc'] = odd+offset
    
        # number of rows
        curr_index = 172
        header['ysize'] = int.from_bytes(hdr_bytes[curr_index:curr_index+4],byteorder='little')
    
        # bytes per image
        curr_index = 176
        header['bytes_per_img'] = int.from_bytes(hdr_bytes[curr_index:curr_index+4],byteorder='little')
    
        if header['bytes_per_img'] != header['bytes_per_row']*header['ysize']:
            err_str = "bytes per img ({bytes_per_img}) /= nrows ({ysize}) * bytes_per_row ({bytes_per_row})".format(**header)
            raise DcimgError(err_str)
        
        return header        
        
    def _decode_float(self,whole_bytes,frac_bytes):
        """Decode floats from DCIMG format
        
        at least some floats in the DCIMG file are stored as a pair of
        4 byte ints, one representing the whole part, one representing the 
        fractional part"""
        whole  = int.from_bytes(whole_bytes,byteorder='little')
        frac   = int.from_bytes(frac_bytes,byteorder='little')
        if frac == 0:
            return whole
        else:
            return whole + frac * 10**-(floor(log10(frac))+1)

    def read_timestamps(self):
        """reads in the timestamps saved in the DCIMG file
        
        The DCIMG recorder saves a timestamp for each frame. Although this is not
        documented, these are probably from the system clock. I am yet to work out if
        they refer to the start, middle, or end of frame.
        
        You should be aware of the issues involved in timing with sCMOS cameras, since not
        all pixels are exposed simultaneously. The 'rolling shutter' implied by this
        means that this timestamp only applies to one part of the image. Again, I don't know
        yet which part. The entire chip takes 1/100th of a second to read out, so this 
        is only relevant at very high timing accuracies
        """
        # go to start of timing info
        # footer consists of 272 bytes of information I don't yet understand
        # then numexp*4 bytes which are a record of the frame numbers
        # then 8 bytes of timing info per frame
        currloc = self._fobj.tell()
        self._fobj.seek(self._footloc + 272 + self.numexp*4)
        
        # read in timestamps
        timestamps = []
        for i in range(self.numexp):
            a = self._fobj.read(4)
            b = self._fobj.read(4)
            val = self._decode_float(a,b)
            timestamps.append(val)
        
        # it's good if this can be called without ruining reading of image data, 
        # so go back to original location
        self._fobj.seek(currloc)
        
        # convert to astropy.Time
        return Time(timestamps,format='unix')