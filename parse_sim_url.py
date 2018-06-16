#coding: utf-8
import random
import time
import numpy as np
import re
import heapq
from operator import itemgetter
import os

def num_or_str(s):
    if s>='0' and s<='9':
        return True
    else:
        return False

def cut(s):
    if len(s)==0:
        return []
    tmp =[]
    tmp.append(s[0])
    i = 1
    while (i<len(s)):
        if (num_or_str(s[i]) and num_or_str(tmp[-1])) or ((not num_or_str(s[i])) and (not num_or_str(tmp[-1]))):
            tmp[-1] += s[i]
        else:
            tmp.append(s[i])
        i += 1
    return tmp


def Cosine(list1, list2):
    if len(list1) != len(list2):
        return 0
    dataA = np.mat(list1)
    dataB = np.mat(list2)
    sumData = dataA * dataB.T
    denom = np.linalg.norm(dataA) * np.linalg.norm(dataB)
    
    return 0.5 + 0.5 * (sumData / denom)


def remove_sim_url(urllist):
    tmp = []
    for st in urllist:
        tmpstr = os.path.basename(st)
        res = cut(tmpstr)
        feature = []
        for item in res:
            if re.match('[0-9]', item[0]):
                feature.append(100 + len(item))
            else:
                feature.append(200 + len(item))

        tmp.append((st, feature, len(feature)))
    tmp = heapq.nlargest(len(tmp), tmp, itemgetter(2))
    select_st = []
    sp = []
    if len(tmp) > 0:
        sp.append(tmp[0])
        for i in range(1, len(tmp)):
            if Cosine(tmp[i][1], sp[-1][1]) < 0.7:
                sp.append(tmp[i])
        for _ in sp:
            select_st.append(_[0])

    return select_st
