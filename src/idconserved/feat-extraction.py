#! /usr/bin/env python
from __future__ import print_function

import os
from argparse import ArgumentParser
import pickle
import sys
import hashlib

from argparse import ArgumentParser
import collections
import shelve
import warnings

import numpy
import pylab
from sklearn import datasets, metrics
from sklearn.ensemble import RandomForestClassifier as RFC
from sklearn.svm import SVC

#/home/liangtong/hidost
exec_dir = '/home/liangtong/hidost/build/src'
#model_path = "/home/liangtong/hidost-reproduction-master/exper/SPC961/SPC961-retraining-7.pickle"
model_path = "/home/liangtong/hidost-reproduction-master/exper/normal6087.pickle"
#model_path = "/home/liangtong/hidost-reproduction-master/exper/retrain_40_20_2.pickle"
#model_path = "/home/liangtong/hidost-reproduction-master/exper/consolidation.pickle"
feats_path = '/home/liangtong/hidost-reproduction-master/exper/features6087.nppf'
#feats_path = '/home/liangtong/hidost-reproduction-master/con_model/SPC961.nppf'
cache_dir = '/home/liangtong/PDF-manipulation/hidost/cache_pdfs'
#n_feat = 961
n_feat = 6087
pdf2paths_cmd = os.path.join(exec_dir, "pdf2paths")
feat_extract_cmd = os.path.join(exec_dir, "feat-extract")
empty_file_list = os.path.join(cache_dir, "ben.txt")

def hash_str(string):
	return hashlib.sha1(string).hexdigest()

def list_file_paths(dir_name):
	pdf_paths = []
	f = open(dir_name, 'r')
	pdf_paths = f.readlines()
	f.close()
	for i in range(0, len(pdf_paths)):
		pdf_paths[i] = pdf_paths[i].strip()
	return pdf_paths

pdf_paths = list_file_paths('/home/liangtong/PDF-manipulation/tr_paths.txt')
cmd = "rm -r /home/liangtong/fe/hidost/cache_pdfs"
os.system(cmd)

if __name__ == "__main__":
	# Build the folders
	if not os.path.isdir(cache_dir):
		os.system("mkdir -p %s" % (cache_dir))

	if not os.path.isfile(empty_file_list):
		os.system("touch %s" % (empty_file_list))
	

	sha1_str = hash_str(''.join(pdf_paths))
	tmp_dir = os.path.join(cache_dir, sha1_str)
	os.system("mkdir -p %s" % tmp_dir)
	
	
	# Initialize the files 
	pdf_file_list = os.path.join(tmp_dir, "mal.txt")
	data_file = os.path.join(tmp_dir, "input.data.libsvm")
 
	# ---pdf-file-----> pdf2paths ---->  pdf-path-file
	tmp = 1
	for j in range(0, len(pdf_paths)):
		cmd = "%s \"%s\" n > %s" % (pdf2paths_cmd, pdf_paths[j], os.path.join(tmp_dir, "feature"+str(tmp)+".txt"))
		os.system(cmd)      
		if j <= 4495:
			result = "0 "
		else:
			result = "1 "   
		sampleFile = open(os.path.join(tmp_dir, "feature"+str(tmp)+".txt"),'r')
		sampleList = [line.split(' ') for line in sampleFile.readlines()]
		sampleFile.close()
			
		featureFile = open(feats_path,'r')
		featureList = featureFile.readlines()
		featureFile.close()
		
		# Delete '\x00' in the sampleList
		for i in range(0, len(sampleList)):
			sampleList[i][0] = sampleList[i][0].replace('\x00','')
		
		# Delete '\n' in the featureList
		for i in range(0, len(featureList)):
			featureList[i] = featureList[i].replace('\n','')
			
		# Delete '\x00' in the featureList
		for i in range(0, len(featureList)):
			featureList[i] = featureList[i].replace('\x00','')                
			
		# Features with their values
		for i in range(0, len(sampleList)):
			if sampleList[i][0] in featureList:
				result = result+str(featureList.index(sampleList[i][0]))+':1 '
		result = result+'#'+pdf_paths[j]+'\n'
		#result = result + '\n'
		if tmp == 1:
			f = open(data_file, 'w+')
		else:
			f = open(data_file,'a')
		f.write(result)
		f.close()
		##print("Enter the next round")
		tmp = tmp+1
   