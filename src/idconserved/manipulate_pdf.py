import pickle

seed0 = "/home/liangtong/Desktop/tmp_pdfs/seed-0.pdf"
seed1 = "/home/liangtong/Desktop/tmp_pdfs/seed-1.pdf"
target = "/home/liangtong/Desktop/tmp_pdfs/target.pdf"

seed0_feat = "1 1:1 17:1 78:1 95:1 96:1 97:1 98:1 337:1 338:1 588:1 603:1 605:1 606:1 5792:1 5797:1 5799:1 6081:1 6084:1"
seed1_feat = "1 1:1 17:1 78:1 95:1 96:1 97:1 98:1 337:1 338:1 588:1 603:1 605:1 606:1 607:1 5792:1 5797:1 5799:1 6081:1 6084:1"
target_feat = "1 1:1 17:1 78:1 95:1 96:1 97:1 98:1 337:1 338:1 588:1 603:1 605:1 606:1 607:1 630:1 631:1 632:1 636:1 637:1 642:1 2666:1 2667:1 5777:1 5789:1 5790:1 5792:1 5797:1 5799:1 6081:1 6084:1"

# Convert a libsvm strings to a feature vector
def str2vec(lib_str):
    vec = [0]*6087        
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

def feat_difference(seed_feature, target_feature):
	seed_vec = str2vec(seed_feature)
	target_vec = str2vec(target_feature)
	difference = []
	for i in range(0, 6087):
		if seed_vec[i] == 0 and target_vec[i] == 1:
			difference.append(i+1)
	return difference

def get_info(pdf_feats):
    f = open(pdf_feats, 'r')
    pdf_feat_strs = [pdf_feat.strip() for pdf_feat in f.readlines()]
    f.close()
    feat_combo = []
    pdf_feat = []
    for i in range(0, 6087):
        feat_combo.append([])
    for i in range(0, 4496):
        pdf_feat.append([])

    # read the feature vectors of the benign PDFs
    for i in range(0, 4496):
        pdf_vec = str2vec(pdf_feat_strs[i])
        for j in range(0, len(pdf_vec)):
            if pdf_vec[j] == 1:
                pdf_feat[i].append(j+1)
                feat_combo[j].append(i+1)

    # write pdf_feat, then pickle
    f = open('pdf_feat.txt','w')
    for i in range(0, len(pdf_feat)):
        f.write("%s\n" % pdf_feat[i])
    f.close()
    pickle.dump(pdf_feat, open('pdf_feat.pickle', 'w'))

    # write feat_combo, then pickle
    f = open('feat_combo.txt', 'w')
    for i in range(0, len(feat_combo)):
        f.write("%s\n" % feat_combo[i])
    f.close()
    pickle.dump(feat_combo, open('feat_combo.pickle', 'w'))

#print feat_difference(seed0_feat, target_feat)
get_info('training_feat.libsvm')

