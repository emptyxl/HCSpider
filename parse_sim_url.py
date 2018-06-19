#coding: utf-8
import random
import time
import numpy as np
import re
import heapq
from operator import itemgetter
import os
from urllib import parse


def num_or_str(s):
    if s >= '0' and s <= '9':
        return True
    else:
        return False


def cut(s):
    if len(s) == 0:
        return []
    tmp = []
    tmp.append(s[0])
    i = 1
    while (i < len(s)):
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


def calc_score(l):
    feature = []
    for item in l:
        if re.match('[0-9]', item[0]):
            feature.append(100 + len(item))
        else:
            feature.append(200 + len(item))
    return feature


def parse_params_id(pr):
    parmas = parse.parse_qs(pr.query)
    sorted_parmas = sorted([x for x in parmas])
    pid = '&'.join([x for x in sorted_parmas])
    return pid


def judge_sim(u1, u2):
    pr1 = parse.urlparse(u1)
    pr2 = parse.urlparse(u2)
    if parse.urljoin(pr1.scheme, pr1.netloc) != parse.urljoin(pr2.scheme, pr2.netloc):
        return False
    else:
        pid1 = parse_params_id(pr1)
        pid2 = parse_params_id(pr2)
        if pid1 != pid2:
            return False
        else:
            s1, s2 = calc_score(cut(pr1.path)), calc_score(cut(pr2.path))
            if Cosine(s1, s2) < 0.7:
                return False
            else:
                return True


def remove_sim_url(urllist):
    tmp = []
    urllist.sort(key=lambda x: len(x))
    select_st = []
    if len(urllist) > 0:
        select_st.append(urllist[0])
        for st in urllist[1:]:
            if not judge_sim(select_st[-1], st):
                select_st.append(st)

    return select_st
