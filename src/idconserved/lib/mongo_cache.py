from pymongo import MongoClient
import pickle
import os
import sys

_current_dir = os.path.abspath(os.path.dirname(__file__))
PROJECT_ROOT = os.path.normpath(os.path.join(_current_dir, ".."))
sys.path.append(PROJECT_ROOT)

from lib.config import config
ADDR = config.get('detector_agent', 'mongodb_uri')
DB_NAME = config.get('detector_agent', 'db_name')

client = MongoClient()
db = client[DB_NAME]

def load_pickle_to_mongodb(pickle_file_name, col):
    cache = pickle.load(open(pickle_file_name))
    records = []
    for sha1, result in cache.iteritems():
        record = {'sha1': sha1, 'result': result}
        records.append(record)
    #print "inserting"
    col.insert(records)
    col.create_index('sha1')

def dump_cuckoo_sigs():
    db = client.cuckoo
    col = db.analysis
    docs = col.find()
    
    d = {}
    for doc in docs:
        sigs_desc = [ sig['description'] for sig in doc['signatures'] ]
        sha1 = doc['target']['file']['sha1']
        d[sha1] = sigs_desc
    pickle.dump(d, open('cuckoo_sigs.pickle', 'wb'))

def query_cache(col, sha1):
    #print "cache.py----query_cache"
    ret = col.find_one({'sha1': sha1})
    #print "cache.py----finish cache"
    if ret:
        #print(sha1)
        return ret['result']
    else:
        return None    

def insert_cache(col, sha1, result):
    col.insert({'sha1': sha1, 'result': result})
    #print "insert completed"

def query_classifier_cache(classifier_name, sha1):
    #print "cache.py----query_classifier_cache"
    client3 = MongoClient()
    db = client3['malware_detection_cache']
    #print(classifier_name)
    col = db[classifier_name]
    return query_cache(col, sha1)

def insert_classifier_cache(classifier_name, sha1, result, expected_sig=None):
    #print "cache.py----insert_classifier_cache"
    #print classifier_name
    #print sha1
    #print result
    #print expected_sig 
    client2 = MongoClient()
    db = client2['malware_detection_cache']
    col = db[classifier_name]
    #print "begin to switch"
    if not expected_sig:
        insert_cache(col, sha1, result)
    elif result == expected_sig:
        # avoid persistent false negative.
        insert_cache(col, sha1, result)
