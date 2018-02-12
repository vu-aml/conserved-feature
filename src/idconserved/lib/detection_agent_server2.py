#! /usr/bin/env python

# Server side
# Input: a list of file paths for examing
# 1. Look up all the files in cache db by sha1 string
# 2. If there're unknown samples, submit to wepawet, fetch the results after a long waiting, then save to local cache db. (rwlock protected variable)
# 3. Fetch the results from local cache, and return to client.
# Problem: 
# Return: a list of wepawet (or local classifier) results.

# TODO: Ctrl-C doesn't work well.

from SocketServer import ThreadingMixIn
from SimpleXMLRPCServer import SimpleXMLRPCServer, SimpleXMLRPCRequestHandler
import threading
import time
import pickle
import os
import sys

# Make sure the working directory in the src.
_current_dir = os.path.abspath(os.path.dirname(__file__))
PROJECT_ROOT = os.path.normpath(os.path.join(_current_dir, ".."))
sys.path.append(PROJECT_ROOT)

from lib.config import config
HOST = config.get('detector_agent', 'host')
PORT = int(config.get('detector_agent', 'port'))

from lib.common import hash_file

# Import local classifiers.
from classifiers.pdfrate_wrapper import pdfrate
from classifiers.hidost_wrapper import hidost
#from classifiers.bundle_wrapper import hidost_pdfrate, hidost_pdfrate_sigmoid

import sklearn
##print sklearn.__version__

# Import remote classifiers.
from classifiers.cuckoo_wrapper import cuckoo
from classifiers.wepawet_wrapper import wepawet

from mongo_cache import query_classifier_cache, insert_classifier_cache

import logging
logger = logging.getLogger("DAgent-dev")

#Threaded XML-RPC
#class XMLRPCServerT(ThreadingMixIn, SimpleXMLRPCServer): pass

# A cached and general query function.
def query(file_paths, real_query_method=None, query_method=None, insert_method=None, expected_sig=None):


    #print "agent_server2.py----Start to query..."	
    hash_strs = map(hash_file, file_paths)
    ##print "agent_server2.py----The hash strings are:"
    #print hash_strs
    
    ##print "agent_server2.py----length of the hash_strs: %d" % len(set(hash_strs))
    ##print "agent_server2.py----length of the total hash_strs: %d" % len(hash_strs)
    ##print "agent_server2.py----length of the total hash_strs: %d" % len(file_paths)
    
    results = map(query_method, hash_strs)
    ##print results
    #unknown_samples_count = results.count(None)
    ###print "Number of None: %d" % unknown_samples_count
    #results = map(None, hash_strs)
    #results = [None]
    ##print "agent_server2.py----The results are:"
    ##print results
   
    logger.info("(%d unique) files" % (len(set(hash_strs))))
    ##print "agent_server2.py----(%d unique) files" % (len(set(hash_strs)))

    unknown_samples_count = results.count(None)
    ##print "agent_server2.py----unknown_samples_count is %s" % unknown_samples_count
    logger.info("%d files hit in cache.  " % (len(file_paths) - unknown_samples_count))
    #print "agent_server2.py----%d files hit in cache.  " % (len(file_paths) - unknown_samples_count)
    if unknown_samples_count == 0:
        return results

    unknown_indices = [i for i, j in enumerate(results) if j == None]
    ##print "agent_server2.py----unkown_indices: %s" % unknown_indices

    query_files = {}
    to_wpw_files = []
    hashes = []

    for idx in unknown_indices:
        hash_str = hash_strs[idx]
        if not query_files.has_key(hash_str):
            query_files[hash_str] = [idx]
            to_wpw_files.append(file_paths[idx])
            hashes.append(hash_str)
        else:
            query_files[hash_str].append(idx)
            
    ##print "agent_server2.py----to_wpw_files is: %s" % to_wpw_files
    ##print "agent_server2.py----hashes is : %s" % hashes       
            
    # submit files of unknown indices to wepawet
    logger.info("Waiting for %d results." % len(file_paths))
    ##print "agent_server2.py----Waiting for %d results." % len(file_paths)

    query_results = real_query_method(to_wpw_files)
    logger.info("Finished.")
    #print "agent_server2.py----Finished."
    ##print "agent_server2.py----hashes length: %d" % len(hashes)
    
    for i in range(len(hashes)):
        hash_str = hashes[i]
        result = query_results[i]
        
        ##print result
        # We may not need the following step
        #print "begin to insert result..."
        insert_method(hash_str, result, expected_sig)
        #print "agent_server.py----insert_method done..."
        for idx in query_files[hash_str]:
            results[idx] = result

    #print "agent_server2.py results: "
    #print results
    return results
    
def adds(x,y):
    return x+y

def query_classifier(classifier_name, file_paths, seed_sha1 = None):
    expected_sig = None
    logger.info("Received %s query for %d files" % (classifier_name, len(file_paths)))

    query_method = lambda x:query_classifier_cache(classifier_name, x)
    insert_method = lambda *args:insert_classifier_cache(classifier_name, *args)
    
    ##print "gent_server2.py----start to load the signatures..."
    cuckoo_sig_pickle = "/home/liangtong/EvadeML-master/lib/36vms_sigs.pickle"
    cuckoo_seed_sigs = pickle.load(open(cuckoo_sig_pickle))
    
    ##print "agent_server2.py----The classifier is: %s." % (classifier_name)
    ##print "agent_server2.py----The file path is..."
    ##print file_paths

    if classifier_name == "pdfrate":
        real_query_method = pdfrate
    elif classifier_name == "hidost":
        ##print classifier_name	      
        real_query_method = hidost
        ##print real_query_method
    elif classifier_name == "wepawet":
        real_query_method = wepawet
    elif classifier_name == "cuckoo":
        real_query_method = cuckoo
        ##print "agent_server2.py----seed_sha1:", seed_sha1
        expected_sig = cuckoo_seed_sigs[seed_sha1]
        ##print "agent_server2.py----sig is as below"
        ##print expected_sig
    elif classifier_name == "hidost_pdfrate":
        real_query_method = hidost_pdfrate
    elif classifier_name == "hidost_pdfrate_sigmoid":
        real_query_method = hidost_pdfrate_sigmoid
    else:
        ##print "agent_server2.py----Unknown classifier: %s" % classifier_name
        return None

    #print "agent_server2.py----real_query_method is: %s. " % (real_query_method)
    ##print real_query_method

    results = query(file_paths, real_query_method=real_query_method, \
                     query_method=query_method, insert_method=insert_method, expected_sig=expected_sig)
    assert(len(file_paths) == len(results))
    #print "agent_server2.py----results is %s" % results
    ##print "agent_server2.py----expected_sig is %s" % expected_sig

    if classifier_name == "cuckoo":
        ##print results[0]
        ##print expected_sig
        bin_ret = ['malicious' if sig == expected_sig else 'benign' for sig in results]
        ##print "agent_server2.py----server begins to return CUCKOO results..."
        ##print  bin_ret
        ##print bin_ret[0]
        return bin_ret
    else:
        ##print "agent_server2.py----server begins to return HIDOST results..."
        #print results
        ##print results[0]
        return results


