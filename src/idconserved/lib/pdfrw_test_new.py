#! /usr/bin/env python

# ./gp.py -c hidost -s samples/seeds/ff0bfa347b60be403f3f13b8461d9e230570078b -e /Users/apple/EvadeML-master/samples/hidost_benign_3 -p 48 -g 20 -m 0.1 -x 0 -f 0 -t attack_hidost_hidost_benign_3 --round 1
# ./utils/detection_agent_server.py ./utils/36vms_sigs.pickle
from common import *
import pickle
import random
from pdfrw.pdfreader import PdfReader
from pdf_genome import PdfGenome
ben_folder = '/Users/apple/EvadeML-master/samples/hidost_benign_3'
ben_path = '/Users/apple/EvadeML2.0/samples/hidost_benign_3/e23abe0df1bf1c01df7567ca11192f2576aaaf5c.pdf'
mal_path = '/Users/apple/EvadeML2.0/samples/seeds/ff0bfa347b60be403f3f13b8461d9e230570078b'


file = ben_path
print "file: %s" % file
PdfReader(file, slow_parsing = True)

root = PdfGenome.load_genome(file, pickleable = False)
print "load: %s" % file

files = list_file_paths(ben_folder)
print "ben_folder: %s" % ben_folder
print "ben_files: %s" % files

ext_genome = PdfGenome.load_external_genome(ben_folder, pickleable = False)
print "load_external_genome: %s" % ben_folder