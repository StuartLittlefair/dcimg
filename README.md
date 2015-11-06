# dcimg

##Python module for reading Hamamatsu DCIMG files

So far, this is a very rough module, and is only known to work with my version of the Hamamatsu ORCA Flash 4.0.
Since the DCIMG file format is undocumented, I have reversed engineered sections of it, so it may well not
work with other cameras, or even data taken in different formats from the same camera (i.e USB3 output may not work).

In addition, it assumes that custom XML files are saved along with the dcimg file, so the utility of this
function for the general user will be very limited. 
