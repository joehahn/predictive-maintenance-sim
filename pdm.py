#pdm.py
#
#Copyright (c) 2018, Oracle and/or its affiliates. All rights reserved.
#The Universal Permissive License (UPL), Version 1.0
#
#by Joe Hahn, joe.hahn@oracle.come, 11 September 2018
#this executes the pdm demo


#get commandline argument
try:
    import sys
    inputs_path = sys.argv[1]
except:
    inputs_path = 'inputs_rtf.py'

#start time
import time as tm
clock_start = tm.time()

#read input parameters
import numpy as np
execfile(inputs_path)
print 'inputs_path = ', inputs_path
print 'debug = ', debug
print 'N_devices = ', N_devices
print 'sensor_sigma = ', sensor_sigma
print 'N_timesteps = ', N_timesteps
print 'time_start = ', time_start
print 'output_interval = ', output_interval
print 'strategy = ', strategy
print 'pdm_threshold_time = ', pdm_threshold_time
print 'pdm_threshold_probability = ', pdm_threshold_probability
print 'pdm_skip_time = ', pdm_skip_time
print 'N_technicians = ', N_technicians
print 'repair_duration = ', repair_duration
print 'maintenance_duration = ', maintenance_duration
print 'rn_seed = ', rn_seed
print 'issues = ', issues

#imports
print 'setting up...'
import numpy as np
import pandas as pd

#initialize values of each sensor on each device
names = ['temperature', 'pressure', 'load']
N_sensors = len(names)
IDs = np.arange(N_sensors)
values = np.zeros((N_devices, N_sensors))
sensors = {'names':names, 'IDs':IDs, 'values':values}
#initialize time of each sensor's next output
np.random.seed(rn_seed)
output_times = np.random.uniform(low=0, high=output_interval, size=values.shape).astype(int)
sensors['output_times'] = output_times

#initialize devices
IDs = np.arange(N_devices)
devices = {'IDs':IDs}
devices['sensors'] = sensors
for deviceID in devices['IDs']:
    d = {'state':'operating', 'issue':'none', 'technicianID':-1, 'fail_time':-1, 'repair_start_time':-1, 'repair_complete_time':-1, 
            'production_rate':0.0, 'production_rate_fail_time':0.0}
    for issue in issues.keys():
        if (issues[issue]['fatal'] == True):
            d[issue + '_repair_time'] = time_start - 1
    devices[deviceID] = d
#initialize damage due to issues
N_issues = len(issues)
damage = np.zeros((N_issues, N_devices))
devices['damage'] = damage

#initialize technicians
IDs = np.arange(N_technicians)
technicians = {'IDs':IDs}
for ID in IDs:
    technicians[ID] = {'location':-1}

#load pdm models as needed
models = {}
if (strategy == 'pdm'):
    fatal_issues = [issue_name for issue_name, d in issues.iteritems() if (d['fatal'] == True)]
    #model_folder = '/u01/bdcsce/tmp/'
    model_folder = './'
    for issue in fatal_issues:
        y_col = issue + '_in_' + str(pdm_threshold_time)
        model_file = model_folder + y_col + '_model.pkl'
        print 'loading ' + model_file
        with open(model_file, 'rb') as file:
            import pickle as pkl
            models[y_col] = pkl.load(file)

#loop over all times
repair_data = []
telemetry_data= []
from helper_fns import *
times = range(time_start, time_start + N_timesteps)
print 'operating devices...'
for time in times:
    
    #update operating devices' sensors
    update_sensors(devices, sensor_sigma)
    
    #update damage due to issues
    crud_damage = update_damage(devices, issues)
    
    #update devices' production_rate
    compute_production(devices, issues, crud_damage)
    
    #perform predictive maintenance if desired
    if (strategy == 'pdm'):
        if (time%pdm_skip_time == 0):
            repair_data += pdm_check(devices, issues, time, technicians, models, maintenance_duration, 
                pdm_threshold_time, pdm_threshold_probability, debug)
    
    #flag any failed devices
    check_devices(devices, issues, time, debug)
    
    #send first available technicians to repair failed deviceIDs
    repair_data += service_failed_devices(devices, technicians, time, repair_duration, debug)

    #release devices and technicians when maintenance is complete
    complete_maintenance(devices, issues, technicians, time, debug)
    
    #generate sensor and telemetry update output_times
    telemetry_data += generate_telemetry(devices, technicians, time, output_interval)
    
    #increment time
    time += 1

#convert repairs log to dataframe
import os
if (len(repair_data) > 0):
    cols = ['time', 'deviceID', 'issue', 'technicianID'] + names + ['production_rate']
    repairs = pd.DataFrame(data=repair_data)[cols]
    print 'repairs.shape = ', repairs.shape
    file = 'data/repairs_' + strategy + '.csv.gz'
    repairs.to_csv(file, header=False, index=False, sep='|', compression='gzip')
    print file + ' size (KB) = ', os.path.getsize(file)/(1024)

#convert telemetry to dataframe
if (len(telemetry_data) > 0):
    cols = ['time', 'deviceID', 'sensor', 'value']
    telemetry = pd.DataFrame(data=telemetry_data)[cols]
    print 'telemetry.shape = ', telemetry.shape
    file = 'data/telemetry_' + strategy + '.csv.gz'
    telemetry.to_csv(file, header=False, index=False, sep='|', compression='gzip')
    print file + ' size (MB) = ', os.path.getsize(file)/(1024**2)

#done
print 'execution time (min) = ', (tm.time() - clock_start)/60.0
