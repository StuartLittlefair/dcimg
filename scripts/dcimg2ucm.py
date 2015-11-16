import dcimg
import argparse
from itertools import count
from trm.ultracam import MCCD

parser = argparse.ArgumentParser(description='Convert DCIMG file to many ucm files')
parser.add_argument('file',help='dcimg file to convert')
parser.add_argument('--start','-s',action='store',type=int,default=1,help='Start frame to grab')
parser.add_argument('--end','-e',action='store',type=int,default=0,help='Start frame to grab (0 to grab all frames)')
parser.add_argument('--ndigit','-n',action='store',type=int,default=3,help='number of digits in file numbers')
args = parser.parse_args()

rdat = dcimg.Ddata(args.file)
if args.end == 0:
    args.end = rdat.numexp

rdat.set(args.start)

filename_gen = ('{name}_{num:0{width}d}.ucm'.format(name=args.file,num=i,width=args.ndigit) for i in count(1))
while rdat.nframe() < args.end:
    filename = next(filename_gen)
    ccd = rdat()
    mccd = MCCD([ccd],ccd.head)
    mccd.wucm(filename)