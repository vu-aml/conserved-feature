#!/usr/bin/env python
# -*- coding: utf-8 -*-
# retraining.py
# Created on January 19, 2017.
"""
"""
from __future__ import print_function
from argparse import ArgumentParser
import collections
import pickle
import shelve
import sys
import warnings
import math 
import pickle
import random
import time
import sys
import multiprocessing
import os

import numpy
import pylab
from sklearn import datasets, metrics
from sklearn.ensemble import RandomForestClassifier as RFC
from sklearn.svm import SVC
#from sklearn.svm import LinearSVC
from sklearn.externals import joblib
from functools import partial

MODEL = pickle.load(open("path to model", "rb"))
feat_hierarchy = pickle.load(open("feat_hierarchy.pickle", "r"))


L = 3
LAM = 0.01
n_seed = 40
n_window = 3000
N = 30000
allplot = []
allf = []

remove_list = []
feat_list = []
for i in range(0, 961):
    feat_list.append(i)
#remove_list = [77 ,94, 95, 96, 108, 235, 334, 604, 605, 606, 5798, 6083]
#remove_list = [77,94,95,96,235,334,604,607,622,624]
#remove_list = [77,94,95,96,108,235,334,604,606,607,622,624]
#remove_list = [65, 80, 81, 82, 94, 265, 346]
remove_list = []
for x in remove_list:
    feat_list.remove(x)

###############################################################################
# auxiliary functions

def is_leaf(feat_num):
    if feat_hierarchy[feat_num][2] == 'leaf':
        return True
    else:
        return False

def is_leaf_parent(feat_num):
    if feat_hierarchy[feat_num][2] == 'leaf_parent':
        return True
    else:
        return False    

def is_other(feat_num):
    if feat_hierarchy[feat_num][2] == 'others':
        return True
    else:
        return False        

def child_leaf_self(feat_num):
    # this function is for leaf-parent features
    # return the leaf children of the giving feature
    child_feat_seq = [feat_num]
    for child in feat_hierarchy[feat_num][1]:
        #if is_leaf(feat_hierarchy[child-1]):
        if feat_hierarchy[child-1][2] == 'leaf':
            child_feat_seq.append(child-1)
    return child_feat_seq

def parent_self(feat_num):
    parent_feat_seq = [feat_num]
    for parent in feat_hierarchy[feat_num][0]:
        parent_feat_seq.append(parent-1)
    return parent_feat_seq

# The Quadratic cost function
def quad_cost(x, xj):
    l = 0;
    for i in range(0, len(x)):
        l = l + (x[i]-xj[i])**2
    a = 1
    #if 73 <= feat <= 77 or 110 <= feat <= 336 or 598 <= feat < 694 or 1507 <= feat <= 1777 or 2666 <= feat < 2769 or 4148 <= feat <= 4247 or 4408 <= feat < 4913 or 5777 <= feat < 5879 or 5901 <= feat < 5990:
    #    a = 1
    return 0.5*a*LAM*l

# The exponential cost function
def expo_cost(x, xj):
    l = 0
    for i in range(0, len(x)):
        l = l + (x[i] - xj[i])**2
    return math.exp(LAM*math.sqrt(l+1))    

# Define the hypo of the classifier as fx
def func(x):
    #model = pickle.load(open(model_path, "rb"))
    X = [x]
    y = MODEL.decision_function(X)
    r = list(y)
    return r[0]        

# Objective function of attcker
#def Q(x, xj):
#    return func(x) + quad_cost(x, xj)

# Convert feature vector to libsvm strings
def vec2str(x):
    lib_str = "1"
    for i in range(0, len(x)):
        if x[i] == 1:
            lib_str = lib_str + " "+str(i+1)+":1"    
    return lib_str
    
# Flip the i th feature (0 <= i < 6087) 
def flip(x, i):
    xk = x[:]
    if xk[i] == 1:
        xk[i] = 0
    else:
        xk[i] = 1
    return xk     

# Flip with consideration of feature structure
def flip_with_struct(x, i):
    xk = x[:]
    if is_other(i):
        if xk[i] == 1:
            xk[i] = 0
        else:
            xk[i] = 1
    if is_leaf(i):
        if xk[i] == 1:
            xk[i] = 0
        else:
            flip_list = parent_self(i)
            for j in flip_list:
                xk[j] = 1
    if is_leaf_parent(i):
        if xk[i] == 1:
            flip_list = child_leaf_self(i)
            for j in flip_list:
                xk[j] = 0
        else:
            xk[i] = 1
    return xk    

# Convert a libsvm strings to a feature vector
def str2vec(lib_str):
    vec = [0]*961        
    on = 0
    tmp = ''
    for i in range(0, len(lib_str)):
        if lib_str[i] == ':':
            on = 0
            vec[int(tmp)-1] = 1
            tmp = ''
        if on == 1:
            tmp = tmp + lib_str[i]
        if lib_str[i] == ' ':
            on = 1    
    return vec
    
###############################################################################    
# Coordinated_greedy algorithm
def coor_greedy(str_pair, sort):
    # First transefer the string to a feature vector
    xj = str2vec(str_pair[0])
    opt_pool = []
    values = []
    opt_sol = ''
    # Choose L random starting points
    for i in range(0, L):
        xk = xj[:]
        fk = func(xk)
        ck = 0
        Qk = fk + ck
        n_converge = 0

        while n_converge <= n_window:
            
            rand_sel = random.randint(0, len(feat_list)-1)
            feat = feat_list[rand_sel]
            
            #print (feat)
            #feat = random.randint(0,6086)
            xl = flip(xk, feat)
            #xl = flip(xk, feat)            

            fl = func(xl)
            cl = quad_cost(xl, xj)
            Ql = fl + cl
            
            #if Q(xl, xj) < Q(xk, xj):
            if Ql < Qk:
                xk = xl[:]
                n_converge = 0
                Qk = Ql
                fk = fl
                ck = cl
            else:
                n_converge += 1
        #print func(xk)
        #if func(xk) < 0:

        if fk < 0:
            opt_pool.append(xk)
            #values.append(Q(xk, xj))
            values.append(Qk) 
    if len(opt_pool) > 0:
        min_index = values.index(min(values))
        opt_vec = opt_pool[min_index]
        opt_sol = vec2str(opt_vec)
        #print func(opt_vec)
    else:
        opt_sol = ''
    return opt_sol    

###############################################################################
# the main function of retraining
# 1. use coordinated-greedy to generate new instances
# 2. check new instances
# 3. train the new dataset     
def main():
    # CG feature pool score
    f = open('/home/tongl/fe/score.txt','r')
    score = f.readlines()
    f.close()
    for i in range(0, len(score)):
        score[i] = int(score[i])
    sorted_score = sorted(range(len(score)), key=lambda k: -1*score[k])     

    # import the retraining seeds
    f = open('/****path to directory****/data/Hidost/Hidost-retr-seed.libsvm','r')
    line_all = f.readlines()
    f.close()
    seeds = line_all[0:n_seed]
    
    # import the retraining targets
    f = open('/****path to directory****/data/Hidost/Hidost-train.libsvm','r')
    line_all = f.readlines()
    f.close()
    targets = []
    for i in range(0, n_seed):
        seq = random.randint(5586, 10081)
        targets.append(line_all[seq])

    inputs = []
    for i in range(0, n_seed):
        inputs.append([seeds[i], targets[i]])
    #print (inputs[0][0])
    #print (inputs[0][1])

    i = 1
    while True:
        # use CG to generate adversarial instances with multiprocessing
        
        print ("#####################################################")
        print ('Iteration', i)
        start_time = time.time()
        cores = multiprocessing.cpu_count()
        adv_ins = []
        pool = multiprocessing.Pool(processes=cores)
        sum_num = 0.0
        partial_cg = partial(coor_greedy, sort = sorted_score)
        for y in pool.imap(partial_cg, inputs):
            #print (func(str2vec(y)))   
            if y != "":
                adv_ins.append(y+'\n')
                sum_num += func(str2vec(y))
        pool.close()
        pool.join()
        #adv_ins[-1] = adv_ins[-1].strip()    
        print ('Multiple process:', time.time() - start_time, 's')
        if len(adv_ins) != 0:
            print ('Average value:', sum_num/len(adv_ins))
        print ('The number of instances added:', len(adv_ins))
        
        # check the new instances
        if len(adv_ins) != 0:
            ins_path = "/****path to directory****/data/Hidost/M40L001/adv_ins_"+str(i)+".libsvm"
            ins_add = open(ins_path, 'w')
            for ins in adv_ins:
                ins_add.write("%s" % ins)
        else:
            print("#####################################################")
            print("The retraining is terminated at iteration %d" % i) 
            break
            
        # train with the new dataset   
        # copy the old training set
        training_pre = '/****path to directory****/data/Hidost/M40L001/train-'+str(i-1)+'.libsvm'
        training_cur = '/****path to directory****/data/Hidost/M40L001/train-'+str(i)+'.libsvm'
        cmd = 'cp' + ' ' + training_pre + ' ' + training_cur
        os.system(cmd)
        # add the adversarial instance in the new training set
        f = open(training_cur, 'a')
        for ins in adv_ins:
            f.write(ins)
        f.close()
        
        train_fs = ['/****path to directory****/data/Hidost/M40L001/train-'+str(i)+'.libsvm']
        test_fs = ['/****path to directory****/data/Hidost/Hidost-test.libsvm']
                
        print('Performing experiment')
        #print('train_fs: %s' % train_fs)
        #print('test_fs: %s' % test_fs)
        for w, (f_tr, f_te) in enumerate(zip(train_fs, test_fs), start=1):
            # Load test dates
        
            #dates = numpy.array(load_dates(f_te))
            #week_s, week_e = dates.min(), dates.max()
            #key_dates.append(week_s)
            #print('\nPeriod {} [{} - {}]'.format(w, week_s, week_e))
        
            # Load training data
            #print('f_tr: %s' % f_tr)
            #print('f_te: %s' % f_te)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                #X_tr, y_tr = datasets.load_flight_file(f_tr)
                X_tr, y_tr = datasets.load_svmlight_file(f_tr, n_features=961)
                
            print(X_tr.shape)
            X_tr.data = numpy.ones_like(X_tr.data)
            X_tr = X_tr.toarray()
            clf = SVC(kernel='rbf', gamma=0.0025, C=12)
            sample_weight = None
            clf.fit(X_tr, y_tr, sample_weight=sample_weight)
            pickle.dump(clf, open("/****path to directory****/exper/Hidost/M40L001/model-"+str(i)+".pickle", 'wb+'))
        global MODEL
        MODEL = pickle.load(open("/****path to directory****/exper/Hidost/M40L001/model-"+str(i)+".pickle", "rb"))
        i += 1
        
if __name__ == "__main__":
    main()
    
