from xmlrpclib import ServerProxy
import time
import os
import sys


_current_dir = os.path.abspath(os.path.dirname(__file__))
PROJECT_ROOT = os.path.normpath(os.path.join(_current_dir, ".."))
sys.path.append(PROJECT_ROOT)

import detection_agent_server2 as server
from lib.config import config
HOST = config.get('detector_agent', 'host')
PORT = int(config.get('detector_agent', 'port'))

RPC_SERVER_ADDR = "http://%s:%d" % (HOST, PORT)

def query_classifier(classifier_name, file_paths, seed_sha1 = False):
	#print "detector.py----Enter query_classifier..."
	file_paths = map(os.path.abspath, file_paths)
    #print "detector.py----The abspath of the file_paths is %s" % file_paths
    #server = ServerProxy(RPC_SERVER_ADDR)
	results = None
    ##print "detector.py----Begin to call RPC to process fitness function..."
    #while not results:
        # try:
        ##print "detector.py----Client is waiting for the result from server..."    
        #results = server.query_classifier(classifier_name, file_paths, seed_sha1)
        ##print "detector.py----Result is received from server..."
        # except Exception, e:
        #     #print str(e)
        #     #print "RPC server is not available, try again 10 secs later."
        #     time.sleep(10)
        #     continue
        # else:
        #return results
    #print server.adds(2,3) 
	#print "detector.py----Client is waiting for the result from server..."   
	results = server.query_classifier(classifier_name, file_paths, seed_sha1)            
    #print server.adds(2,3) 
	return results

if __name__ == "__main__":
	import sys
	name = sys.argv[1]

	if name != 'cuckoo':
		file_paths = sys.argv[2:]
		seed_sha1 = False
	else:
		seed_sha1 = sys.argv[2]
		file_paths = sys.argv[3:36]
		if len(seed_sha1) != len("e886a44335f151744cc28626567a2cd5db1feee7"):
            #print "detector.py----Error: Invalid seed_sha1: [%s]" % seed_sha1
            #print "detector.py----Hint: Give me something like: [e886a44335f151744cc28626567a2cd5db1feee7]"
			sys.exit(1)
    
	results = query_classifier(name, file_paths, seed_sha1)
    #print results
