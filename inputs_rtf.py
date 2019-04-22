#inputs_rtf.py
#
#Copyright (c) 2018, Oracle and/or its affiliates. All rights reserved.
#The Universal Permissive License (UPL), Version 1.0
#
#by Joe Hahn, joe.hahn@oracle.come, 11 September 2018
#input parameters used to generate run-to-fail (rtf) mock data

#turn debugging output on?
debug = True

#number of devices
N_devices = 1000

#sensor standard deviation
sensor_sigma = 0.01

#number of timesteps
N_timesteps = 50000

#starting time
time_start = 0

#interval (in timesteps) between device outputs
output_interval = 10

#maintenance strategy = rtf or pdm
strategy = 'rtf'

#send devices to maintenance when predicted lifetime is less that this threshold
pdm_threshold_time = 400

#probability threshold for pdm classifier to send device to preventative maintenance
pdm_threshold_probability = 0.5

#execute pdm check after this many timesteps
pdm_skip_time = 5

#number of technicians
N_technicians = N_devices/10

#failed' device's repair time
repair_duration = 100

#maintenance duration
maintenance_duration = repair_duration/4

#random number seed
rn_seed = 17

#issue data
issues = {
    'crud':         {'ID':0, 'coefficient':0.100000,   'fatal':False},
    'jammed_rotor': {'ID':1, 'coefficient':0.000080,   'fatal':True },
    'cracked_valve':{'ID':2, 'coefficient':0.000010,   'fatal':True },
    'broken_gear':  {'ID':3, 'coefficient':0.000002,   'fatal':True },
}
