# Import packages
import pandas as pd
import numpy as np
import random
import math

def generate_scenarios_EV(n):
    t = 24
    scen_dict_EV = {}
    scen_dict_EV_OOS = {}
    for i in range(t):
        file_path = f'Data\Spirii\hour{i+1}.csv'
        df = pd.read_csv(file_path, delimiter=',', decimal='.')
        df['upward'] = df['upward'].mul(0.1)
        k = i if i != 24 else 0
        n_samples = len(df['upward'])
        list_of_samples = range(0, n_samples) 
        samples = random.sample(list_of_samples, int(n))
        df_tmp = df['upward'].iloc[samples]
        df_tmp.reset_index(drop=True, inplace=True)
        scen_dict_EV[k] = df_tmp.to_dict()

        not_samples = list(set(list_of_samples) - set(samples))
        df_tmp = df['upward'].iloc[not_samples]
        df_tmp.reset_index(drop=True, inplace=True)
        scen_dict_EV_OOS[k] = df_tmp.to_dict()

    return scen_dict_EV, scen_dict_EV_OOS

def generate_scenarios_wind(n):
    system_platform = platform.system()
    t = 24

    merged = pd.read_csv(f'Data\wind_data_simulated.csv')
    merged['time'] = pd.to_datetime(merged['time'])
    merged['date'] = pd.to_datetime(merged['date'])
    merged['Middelgrunden'] = merged['Middelgrunden'].mul(0.3)

    scen_dict_wind = {}
    scen_dict_wind_OOS = {}
    for i in range(t):
        marker = (merged['hour']==i)
        df_tmp = merged['Middelgrunden'].loc[marker]
        df_tmp.reset_index(drop=True, inplace=True)

        n_samples = len(df_tmp)

        list_of_samples = range(0, n_samples) 
        samples = random.sample(list_of_samples, int(n))
        not_samples = list(set(list_of_samples) - set(samples))

        tmp_IS = df_tmp[samples]
        tmp_IS.reset_index(drop=True, inplace=True)
        scen_dict_wind[i] = tmp_IS.to_dict()

        tmp_OOS = df_tmp[not_samples]
        tmp_OOS.reset_index(drop=True, inplace=True)
        scen_dict_wind_OOS[i] = tmp_OOS.to_dict()

    return scen_dict_wind, scen_dict_wind_OOS

def generate_scenarios_conventional(n, cap):
    t = 24
    scen_dict_conventional = {}
    for i in range(t):
        df_tmp = {j: cap for j in range(n)}
        scen_dict_conventional[i] = df_tmp

    return scen_dict_conventional

