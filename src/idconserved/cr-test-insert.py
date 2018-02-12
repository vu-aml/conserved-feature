#! /usr/bin/env python
import logging
import random
import pickle
import os
import sys
import getopt
import time
import requests
import json
import hashlib
import re

from lib.common import LOW_SCORE, finished_flag, visited_flag, result_flag, error_flag
from lib.common import touch, deepcopy
from lib.common import setup_logging
from lib.pdf_genome import PdfGenome
from lib.trace import Trace
from lib.common import *
logger = logging.getLogger('gp.cuckoo')
import lib.pdfrw
from lib.pdfrw import PdfReader, PdfWriter

_current_dir = os.path.abspath(os.path.dirname(__file__))
PROJECT_ROOT = os.path.normpath(os.path.join(_current_dir, ".."))
sys.path.append(PROJECT_ROOT)

HOST = '127.0.0.1'
PORT = 8090
TIMEOUT = 200

def list_file_paths(dir_name, size_limit=None):
	fnames = os.listdir(dir_name)
	fnames.sort()

	ret = [os.path.join(dir_name, fname) for fname in fnames]
	if size_limit:
		return ret[:size_limit]
	else:
		return ret

def check_reported(file_path):
	#print "CHECK_REPORTED(FILE_PATH)"
	sha1 = hash_file(file_path)
	REST_URL = "http://%s:%d/tasks/check_reported/%s" % (HOST, PORT, sha1)
	#print "REST_URL: http://%s:%d/tasks/check_reported/%s" % (HOST, PORT, sha1)
	request = requests.get(REST_URL)
	if request.status_code == 200:
		json_decoder = json.JSONDecoder()
		if request.text:
			r = json_decoder.decode(request.text)
			return r

def submit(file_path, public_name = None, timeout = None, cache=False):
	#print "SUBMIT()"
	if cache:
		task_id = check_reported(file_path)
		if task_id:
			#print "skip one file to submit", file_path
			return task_id
	#print "submit one file: %s" % file_path
	REST_URL = "http://%s:%d/tasks/create/file" % (HOST, PORT)
	with open(file_path, "rb") as sample:
		#print "WITH OPEN..."
		if not public_name:
			public_name = os.path.basename(file_path)
		multipart_file = {"file": (public_name, sample)}
		#print "maltipart_file: %s" % multipart_file

		args = {}
		if timeout:
			#print "args['timeout'] = timeout"
			args['timeout'] = timeout
		if cache != True:
			#print "args['cache'] = cache"
			args['cache'] = cache
		if args != {}:
			#print "request = requests.post(REST_URL, files=multipart_file, data=args)"
			request = requests.post(REST_URL, files=multipart_file, data=args)
		else:
			#print "request = requests.post(REST_URL, files=multipart_file)"
			request = requests.post(REST_URL, files=multipart_file)

	# Add your code to error checking for request.status_code.
	#print "request.status_code:", type(request.status_code), request.status_code
	if request.status_code == 200:
		json_decoder = json.JSONDecoder()
		task_id = json_decoder.decode(request.text)["task_id"]
		#print "task_id:", type(task_id), task_id
		return task_id
	# Add your code for error checking if task_id is None.

def submit_files(file_paths, timeout=None, cache=False):
	#print "SUBMIT_FILES()"
	task_ids = []
	for file_path in file_paths:
		#print file_path
		task_id = None
		while task_id == None:
			task_id = submit(file_path, public_name=None, timeout=timeout, cache=cache)
		task_ids.append(task_id)
	return task_ids

# "pending", "running", "reported", "finished", "failed_analysis"
def view(task_id):
	#print "VIEW(TASK_ID)"
	REST_URL = "http://%s:%d/tasks/view/%d" % (HOST, PORT, task_id)
	request = requests.get(REST_URL)
	if request.status_code == 200:
		json_decoder = json.JSONDecoder()
		status = json_decoder.decode(request.text)["task"]["status"]
		return status

def delete_task(task_id):
	REST_URL = "http://%s:%d/tasks/delete/%d" % (HOST, PORT, task_id)
	request = requests.get(REST_URL)
	if request.status_code == 200:
		#json_decoder = json.JSONDecoder()
		#status = json_decoder.decode(request.text)["status"]
		return True
	else:
		return False

def report(task_id):
	#print "REPORT(TASK_ID)"
	REST_URL = "http://%s:%d/tasks/report/%d" % (HOST, PORT, task_id)
	request = requests.get(REST_URL)
	if request.status_code == 200:
		json_decoder = json.JSONDecoder()
		r = json_decoder.decode(request.text)
		return r

def get_url_hosts_from_sock_apis(sigs):
	#if 'signatures' not in doc:
	#    return []
	#sigs = doc['signatures']

	urls = set()
	query_hosts = set()

	for sig in sigs:
		if sig['description'] == "Socket APIs were called.":
			#print "Socket APIs were called..."
			for call in sig['data']:
				api_name = call['signs'][0]['value']['api']
				#print "api_name: %s" % api_name
				if api_name == 'send':
					#print "api_name is send"
					args = call['signs'][0]['value']['arguments']
					sent_buffer = args[0]['value'] # may be HTTP header.
					#print "len(sent_buffer): %d" % len(sent_buffer)
					if len(sent_buffer) > 4:
						sent_buffer += '\r\n'
						#print sent_buffer

						header = sent_buffer
						h_dict = dict(re.findall(r"(?P<name>.*?): (?P<value>.*?)\r\n", header))
						#print h_dict
						path = header.split('\n')[0].split(' ')[1]
						#print path
						url = "http://%s%s" % (h_dict['Host'], path)
						#print url
						urls.add(url)
			#print "urls = %s" % urls            
		elif sig['description'] == "Network APIs were called.":
			#print "Network APIs were called..."
			for call in sig['data']:
				api_name = call['signs'][0]['value']['api']
				args = call['signs'][0]['value']['arguments']
				#args_string = ', '.join(["%s=%s" % (arg['name'], arg['value']) for arg in args])
				#api_string = "%s(%s)" % (api_name, args_string)
				#api_strs.append(api_string)

				if api_name == "getaddrinfo":
					addr = args[1]['value']
					#print "getaddrinfo: %s" % str(addr)
					if addr != u'':
						query_hosts.add(addr)
					#print "query_hosts after getaddrinfo: %s" % str(list(query_hosts))	
				if api_name == "URLDownloadToFileW":
					url = args[0]['value']
					#loc = args[1]['value']
					#url_dl.add(url+','+loc)
					#print "URLDownloadToFileW: %s" % url
					urls.add(url)
					#print "urls after URLDownloadToFileW: %s" % str(list(urls))
				if api_name == "InternetOpenUrlA":
					#print "InternetOpenUrlA"
					url = args[0]['value']
					urls.add(url)
	#return list(urls), list(query_hosts)
	#print str(list(urls))
	#print str(list(query_hosts))

	#print str(list(urls) + list(query_hosts))
	return str(list(urls) + list(query_hosts))

def view_signatures(task_id):
	#print "VIEW_SIGNATURES(TASK_ID)"
	REST_URL = "http://%s:%d/tasks/view_signatures/%d" % (HOST, PORT, task_id)
	request = requests.get(REST_URL)
	if request.status_code == 200:
		json_decoder = json.JSONDecoder()
		if request.text:
			status = json_decoder.decode(request.text)
			return status

def reschedule_task(task_id):
	#print "RESCHEDULE_TASK(TASK_ID)"
	REST_URL = "http://%s:%d/tasks/reschedule/%d" % (HOST, PORT, task_id)
	request = requests.get(REST_URL)
	if request.status_code == 200:
		json_decoder = json.JSONDecoder()
		if request.text:
			status = json_decoder.decode(request.text)
			return status['new_task_id']

def query_tasks(task_ids):
	#print "QUERY_TASKS(TASK_IDS)"
	ret = []
	start_time = None
	for task_id in task_ids:
		sigs = None
		while sigs == None:
			status = view(task_id)
			if status == "reported":
				sigs = view_signatures(task_id)
				sig_pattern = get_url_hosts_from_sock_apis(sigs)
				start_time = None
				#delete_task(task_id)
			elif status == "running":
				if start_time == None:
					start_time = int(time.time())
				else:
					cur_time = int(time.time())
					#print start_time, cur_time, TIMEOUT
					if cur_time - start_time > TIMEOUT:
						old_task_id = task_id
						task_id = reschedule_task(old_task_id)
						delete_task(old_task_id)
						logger.error("Reschedule the task %d to %d." % (old_task_id, task_id))
						start_time = None
					else:
						logger.debug("Waiting for task %d [%s]." % (task_id, status))
						time.sleep(3)
			else:
				logger.debug("Waiting for task %d [%s]." % (task_id, status))
				time.sleep(3)
		ret.append(sig_pattern)
	return ret


def cuckoo(file_paths):
	#print "CUCKOO(FILE_PATHS)"
	logger.info("Submit %d files to cuckoo." % len(file_paths))
	task_ids = submit_files(file_paths)
	logger.info("Waiting for %d results from cuckoo." % len(file_paths))
	logger.info("Task id: %s" % (task_ids))
	query_results = query_tasks(task_ids)
	logger.info("Finished.")
	for i in range(0,len(query_results)):
		print('%s: %s' % (i, query_results[i]))
	return query_results

'''
f = open('/home/liangtong/fe/features.txt')
feat_list = f.readlines()
f.close()

for i in range(0, len(feat_list)):
	feat_list[i] = feat_list[i].strip()

def get_path(obj_list):
	path = ''
	for obj in obj_list:
		if isinstance(obj, str) and obj != '/Root':
			path += obj.replace('/', '')
	return path

def get_feat_seq(path):
	if path in feat_list:
		return feat_list.index(path)+1
'''
	
def get_cr():
	n_test = 1
	# STEP 1. Load the external benign pdf file
	ext_file_name = 'ir01-108.pdf'
	ext_path = '/home/liangtong/pdf_files/benign/'+ext_file_name
	ext_root = PdfGenome.load_genome(ext_path)
	ext_obj = PdfGenome.get_object_paths(ext_root, set())


	# STEP 2. Load the malicious pdf file
	mal_file_name = '001d92fc29146e01e0ffa619e5dbf23067f1e814'
	#mal_file_name = '00aaa01030cb7254a0ba30e9e62516f8690b9e3b'
	#mal_file_name = 'kdd04.pdf'
	mal_path = '/home/liangtong/EvadeML-master/samples/seeds/'+mal_file_name
	#mal_path = '/home/liangtong/Desktop/cr-test/'+mal_file_name
	mal_pdf_folder = '/home/liangtong/Desktop/tmp_pdfs/'
	mal_root = PdfGenome.load_genome(mal_path)

	tmp_root = deepcopy(mal_root)

	mal_obj = PdfGenome.get_object_paths(tmp_root, set())
	n_mal_obj = len(mal_obj)
	#os.system('mkdir -p %s' % (mal_pdf_folder))
	print 'Paths in the malicious PDF'
	for i in range(0, n_mal_obj):
		print i, mal_obj[i]

	#print 'Paths in the benign PDF'
	#for i in range(0, len(ext_obj)):
	#	print i, ext_obj[i]

	
	# STEP 3. Prepare the synthetic PDF
	syn_root = deepcopy(mal_root)
	print 'Target and source paths'
	#print mal_obj[47]
	#print ext_obj[69]
	print mal_obj[19]
	PdfGenome.delete(syn_root, mal_obj[19])
	#PdfGenome.swap(syn_root, mal_obj[47], ext_root, ext_obj[69])
	#PdfGenome.insert(syn)

	syn_obj = PdfGenome.get_object_paths(syn_root, set())
	n_syn_obj = len(syn_obj)
	print 'Paths in the synthetic file'
	for i in range(0, n_syn_obj):
		print i, syn_obj[i]


	#parent, key = PdfGenome.get_parent_key(mal_root, mal_obj[11])
	#print "The key: "
	#print key
	#print "The parent: "
	#print parent.keys()
	#print mal_root.keys()

	# STEP 4. Store the synthetic PDF	
	save_path = mal_pdf_folder + 'test.pdf'
	y = PdfWriter()
	#y.write(save_path, syn_root)
	y.write(save_path, syn_root)

	# STEP 6. Test malicious behaviors with sandbox
	'''
	fpaths = list_file_paths(mal_pdf_folder)
	n_mal = [0]*len(fpaths)
	for i in range(0, n_test):
		results = cuckoo(fpaths)
		for j in range(0, len(results)):
			if results[j] != '[]':
				n_mal[j] += 1
	'''
	'''
	paths = []
	for i in range(0, len(n_mal)):
		if n_mal[i] == 0:
			print i
			path = get_path(obj_paths[int(aux[i])])
			#print path
			if path in feat_list:
				#print get_feat_seq(path)
				paths.append(get_feat_seq(path))
			#print obj_paths[int(aux[i])]

	paths = set(paths)
	paths = list(paths)
	paths.sort()
	print file_name, paths
	'''
	
os.system('rm -rf /home/liangtong/Desktop/tmp_pdfs/*')
f = open('/home/liangtong/fe/seed_list.txt','r')
file_names = f.readlines()
f.close()
for i in range(0, 1):
	#file_name = file_names[i].strip() 
	file_name = 'd3bc877d62c3714ec542281ed8d7814341fa0314'
	get_cr()