# Code for fitting Weibull distributions

import pandas as pd
import numpy as np
import math
import random
from random import sample 
import scipy.stats
import json

def sample_size(eps=0.1, delta=0.01, p=2):
    return math.ceil((2/eps)*np.log(1/delta) + 2*p + (2*p/eps)*np.log(2/eps))

def Weibull_fitting(df):
    m = len(df)
    nll = np.zeros((len(g)))
    j = 0
    for i in g:
        nll[j] = m*np.log(m) - m*np.log(np.sum(df**i)) + m*np.log(i) + (i - 1)*np.sum(np.log(df)) - m
        j = j + 1
    ind = np.argmax(nll)
    return m/np.sum(df**g[ind]), g[ind], -nll[ind]

def KStest(df, kappa, gamma):
    d = np.sort(df)
    c = np.arange(1, len(d)+1) / len(d)
    tmp = 1 - np.exp(-kappa*d**gamma)
    tmp = sorted(tmp)
    kstest = scipy.stats.kstest(c, sorted(tmp))
    return kstest.statistic, kstest.pvalue

def fitting_procedure(df, df_fits, marker):
    # data under eps percentile
    df_tmp = df.copy()
    df_fits.loc[marker, 'quantile'] = np.quantile(df_tmp, eps)

    df_tofit = df_tmp[df_tmp < df_fits.loc[marker, 'quantile'].item()]
    df_tofit = np.negative(df_tofit)
    df_tofit = df_tofit + df_fits.loc[marker, 'quantile'].item()

    # Fit Weibull distribution
    df_fits.loc[marker, 'kappa'], df_fits.loc[marker, 'gamma'], df_fits.loc[marker, 'nll'] = Weibull_fitting(df_tofit)

    # Perform KS test
    df_fits.loc[marker, 'D'], df_fits.loc[marker, 'p-val'] = KStest(df_tofit, df_fits.loc[marker, 'kappa'].item(),  df_fits.loc[marker, 'gamma'].item())

    return df_fits

if __name__ == "__main__":
    random.seed(42)

    t = 24
    n = sample_size(0.1, delta=0.01, p=2)
    eps = 0.2
    gamma_ub = 3
    g = np.linspace(0.01, gamma_ub, num=1000)

    cols = ["kappa", "gamma", "nll", "D", "p-val", "quantile"]
    fit = pd.DataFrame({"hour": range(t)})
    fit[cols] = 0.0

    generator = 'wind'
    if generator == 'EV':
        n_samples = 366
        list_of_samples = range(0, n_samples)
        samples = random.sample(list_of_samples, int(n))
    elif generator == 'wind':
        n_samples = 360
        list_of_samples = range(0, n_samples)
        samples = random.sample(list_of_samples, int(n))
        merged = pd.read_csv(f'Data\wind_data_simulated.csv')
        merged['Middelgrunden'] = merged['Middelgrunden'].mul(0.3)
    else: raise ValueError(f"Unknown generator: {generator}")


    results = {}
    for i in range(t):
        if generator == 'EV':
            # Load hourly data
            k = 24 if i == 0 else i
            df = pd.read_csv(f"Data\Spirii\hour{k}.csv", delimiter=",", decimal=".")
            df_tmp = df["upward"].iloc[samples].mul(0.1)
        elif generator == 'wind':
            marker = (merged['hour']==i)
            df_tmp = merged['Middelgrunden'].loc[marker].iloc[samples]
        else: raise ValueError(f"Unknown generator: {generator}")

        # Fit the Weibull and perform KS test
        marker = fit["hour"] == i
        fitting_procedure(df_tmp, fit, marker)

        row = fit.loc[marker].iloc[0]
        results[i] = {
            "distribution": "truncated weibull",
                "parameters": {
                    "kappa": row["kappa"],
                    "gamma": row["gamma"],
                    "quantile": row["quantile"]
                },
                "errors": {
                    "nll": row["nll"],
                    "ks_statistic": row["D"],
                    "ks_pvalue": row["p-val"]
                }
            }

    # Save as JSON-file (also available as DataFrame in fit)
    save = False
    if save:
        with open(f'Output\{generator}_fits_testing.json', "w") as f:
            json.dump(results, f, indent=4)
        print(f'Saved JSON-file as {generator}_fits_testing.json in Output folder')