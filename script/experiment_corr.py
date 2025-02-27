import sys
import os
sys.path.append(os.getenv("PROJECT_PATH"))
from utils import true_values, compute_correlation, compute_sample_size, get_vecAvecB, get_sketcher, get_scale

import argparse
import numpy as np
import pickle
from collections import defaultdict
import copy

def args_from_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("-overlap", "--overlap", 
        help="overlap ratio of 2 vectors", type=float)
    parser.add_argument("-outlier", "--outlier", 
        help="outlier fraction of the vector", type=float)
    parser.add_argument("-outlier_max", "--outlier_max",
        help="outlier max value", type=int)
    parser.add_argument("-t", "--CS_t", 
        help="t value for CountSketch", type=int)
    parser.add_argument("-corr", "--corr", 
        help="Expected correlation", type=float)
    parser.add_argument("-start_size", "--start_size",
        help="start storage size", type=int)
    parser.add_argument("-end_size", "--end_size",
        help="end storage size", type=int)
    parser.add_argument("-interval_size", "--interval_size",
        help="interval storage size", type=int)
    parser.add_argument("-mode", "--mode", 
        help="storage size in different modes have different sample size", type=str)
    parser.add_argument("-iteration", "--iteration",
        help="interval storage size", type=int)
    parser.add_argument("-log_name", "--log_name", 
        help="log name of the run", type=str)
    parser.add_argument("-sketch_methods", "--sketch_methods",
        help="sketch methods to run", type=str)
    args = parser.parse_args()
    # Check if the required parameter is present
    assert args.log_name is not None, "log_name is missing"
    assert args.sketch_methods is not None, "sketch_methods is missing"
    return args

def vars_from_args(args):
    overlap_ratio = args.overlap or 0.1
    outlier_fraction = args.outlier or 0.1
    outlier_max = args.outlier_max or 10
    mean_outlier =  int(outlier_max/2)
    std_outlier = int(outlier_max/2)
    t = args.CS_t or 3
    corr_r = args.corr or 0.8
    start_size = args.start_size or 100
    end_size = args.end_size or 1000
    interval_size = args.interval_size or 100
    mode = args.mode or "ip"
    iteration = args.iteration or 100
    log_name = args.log_name
    sketch_methods = args.sketch_methods.split("+")
    storage_sizes = [i for i in range(start_size, end_size+1, interval_size)]
    print("sketch_methods", sketch_methods)
    print("overlap_ratio:", overlap_ratio)
    print("outlier_fraction:", outlier_fraction)
    print("mean_outlier:", mean_outlier)
    print("std_outlier:", std_outlier)
    print("t:", t)
    print("corr_r:", corr_r)
    print("mode", mode)
    print("log_name:", log_name)
    print("storage_sizes:", storage_sizes)
    print("iteration:", iteration)
    return overlap_ratio,outlier_fraction,mean_outlier,std_outlier,t,corr_r,mode,iteration,log_name,sketch_methods,storage_sizes


#################### Main ####################
def compute_estimation(vecA, vecB, iA, iB, vecA2, vecB2, sketch_method, sketcher):
    sk_a = sketcher.sketch(vecA)
    sk_b = sketcher.sketch(vecB)
    if sketch_method == 'kmv':
        vas, vbs = [], []
        for ha, va in zip(sk_a.sk_hashes, sk_a.sk_values):
            for hb, vb in zip(sk_b.sk_hashes, sk_b.sk_values):
                if ha == hb:
                    vas.append(va)
                    vbs.append(vb)
        corr_est = np.corrcoef(vas, vbs)[0,1]
    else:
        if sketch_method in ['jl', 'cs', 'wmh']:
            sk_ia = sketcher.sketch(iA)
            sk_ib = sketcher.sketch(iB)
            sk_a2 = sketcher.sketch(vecA2)
            sk_b2 = sketcher.sketch(vecB2)
        else:
            sk_ia = copy.deepcopy(sk_a)
            sk_ia.sk_values = np.array([1 for i in sk_ia.sk_values]) # sk_values results from hash functions that only hash on values!=0
            sk_ib = copy.deepcopy(sk_b)
            sk_ib.sk_values = np.array([1 for i in sk_ib.sk_values])
            sk_a2 = copy.deepcopy(sk_a)
            sk_a2.sk_values = np.array([i**2 for i in sk_a2.sk_values])
            sk_b2 = copy.deepcopy(sk_b)
            sk_b2.sk_values = np.array([i**2 for i in sk_b2.sk_values])
            if 'ps' in sketch_method or 'ts' in sketch_method:
                sk_a.sample_sk_values = sk_a.sk_values
                sk_b.sample_sk_values = sk_b.sk_values
                sk_ia.sample_sk_values = sk_a.sk_values
                sk_ib.sample_sk_values = sk_b.sk_values
                sk_a2.sample_sk_values = sk_a.sk_values
                sk_b2.sample_sk_values = sk_b.sk_values
                    
        ip_est = sk_a.inner_product(sk_b)
        n_est = sk_ia.inner_product(sk_ib)
        sumA_est = sk_a.inner_product(sk_ib)
        sumB_est = sk_b.inner_product(sk_ia)
        sumA2_est = sk_a2.inner_product(sk_ib)
        sumB2_est = sk_b2.inner_product(sk_ia)
        corr_est = compute_correlation(ip_est, n_est, sumA_est, sumB_est, sumA2_est, sumB2_est)
    return sk_a,sk_b,corr_est

if __name__ == "__main__":
    args = args_from_parser()
    overlap_ratio, outlier_fraction, mean_outlier, std_outlier, t, corr_r, mode, iteration, log_name, sketch_methods, storage_sizes = vars_from_args(args)

    results_compare = None
    results = defaultdict(dict)
    for i_iter in range(iteration):
        print("="*20, i_iter, "="*20)
        vecA, vecB = get_vecAvecB(overlap_ratio, outlier_fraction, mode, corr_r, mean_outlier=mean_outlier, std_outlier=std_outlier, nonZero_size=20000, random_seed=i_iter)
        iA = np.array([1 if i != 0 else 0 for i in vecA])
        iB = np.array([1 if i != 0 else 0 for i in vecB])
        vecA2 = vecA ** 2
        vecB2 = vecB ** 2
        (ip_scale, _, _, _, _, _) = get_scale(vecA, vecB)

        for storage_size in storage_sizes:
            log_key = str(storage_size)+'_'+str(overlap_ratio)+'_'+str(i_iter)
            wmh_sample_size, kmv_sample_size, mh_sample_size, jl_sample_size, cs_sample_size, priority_sample_size, threshold_sample_size = compute_sample_size(t, mode, storage_size)
            
            # True Values
            ip, corr, n = true_values(vecA, vecB)
            results[log_key]['true'] = (ip, corr, n, ip_scale)
            for sketch_method in sketch_methods:
                if i_iter>=100 and sketch_method!='cs':
                    print("skipped", sketch_method)
                    continue
                print("+"*20, sketch_method, "+"*20)
                if results_compare is not None:
                    if sketch_method in results_compare[log_key]:
                        results[log_key][sketch_method] = results_compare[log_key][sketch_method]
                        print("skipeed")
                        continue

                sketcher = get_sketcher(wmh_sample_size, kmv_sample_size, mh_sample_size, jl_sample_size, cs_sample_size, priority_sample_size, threshold_sample_size, sketch_method, t, i_iter)
                sk_a, sk_b, corr_est = compute_estimation(vecA, vecB, iA, iB, vecA2, vecB2, sketch_method, sketcher)

                print(f"sketch_method: {sketch_method}\nstorage_size: {storage_size}\nsketch_size: {sketcher.sketch_size}")
                print(f"corr_est: {corr_est}\ntrue_corr: {corr}")
                if 'ps' in sketch_method or 'ts' in sketch_method:
                    mem_sizeA = sk_a.sk_values.shape[0]
                    mem_sizeB = sk_b.sk_values.shape[0]
                    results[log_key][sketch_method] = (corr_est, mem_sizeA*1.5, mem_sizeB*1.5)
                    print("mem_sizeA: %s\nmem_sizeB: %s" % (mem_sizeA, mem_sizeB))
                else:
                    results[log_key][sketch_method] = corr_est
            pickle.dump(results, open(log_name, "wb"))