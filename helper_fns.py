#helper_fns.py
#
#Copyright (c) 2018, Oracle and/or its affiliates. All rights reserved.
#The Universal Permissive License (UPL), Version 1.0
#
#by Joe Hahn, joe.hahn@oracle.come, 15 September 2018
#these helper functions are called by pdm.py


#imports
import numpy as np
import pandas as pd

#random-walk sensors on operating devices
def update_sensors(devices, sensor_sigma):
    sensor_values = devices['sensors']['values']
    size = sensor_values.shape
    delta_values = np.random.normal(loc=0.0, scale=sensor_sigma, size=size)
    devicesIDs = devices['IDs']
    for deviceID in devicesIDs:
        if (devices[deviceID]['state'] == 'operating'):
            sensor_values[deviceID] += delta_values[deviceID]
    return

#compute derived quantities from sensor_values
def sensor_derived_data(sensor_values):
    x = sensor_values[:,0]
    y = sensor_values[:,1]
    z = sensor_values[:,2]
    rho2 = x**2 + y**2
    r = np.sqrt(rho2 + z**2)
    rho = np.sqrt(rho2)
    phi = np.arctan2(y, x)
    theta = np.arctan2(z, rho)
    return x, y, z, r, rho, phi, theta

#increment devices' damage due to issues
def update_damage(devices, issues):
    sensor_values = devices['sensors']['values']
    x, y, z, r, rho, phi, theta = sensor_derived_data(sensor_values)
    damage = devices['damage']
    for issue in issues.keys():
        issueID = issues[issue]['ID']
        coefficient = issues[issue]['coefficient']
        if (issue == 'crud'):
            damg = coefficient*r
            crud_damage = damg
        if (issue == 'jammed_rotor'):
            damg = coefficient*(x**2)
            damg[x < 0] = 0.0
        if (issue == 'cracked_valve'):
            damg = coefficient*(y**2)
            damg[y < 0] = 0.0
        if (issue == 'broken_gear'):
            damg = coefficient*rho*z
            damg[z < 0] = 0.0
        damage[issueID] += damg
    return crud_damage

#compute production rate = 1-crud_damage or zero if device is not operating
def compute_production(devices, issues, crud_damage):
    production_rate = 1.0 - crud_damage
    production_rate[production_rate < 0.0] = 0.0
    deviceIDs = devices['IDs']
    for deviceID in deviceIDs:
        if (devices[deviceID]['state'] == 'operating'):
            devices[deviceID]['production_rate'] = production_rate[deviceID]
        else:
            devices[deviceID]['production_rate'] = 0.0
    return

#check for device failures and update status, noting that crud doesn't fail a device
def check_devices(devices, issues, time, debug):
    for issue in issues.keys():
        issueID = issues[issue]['ID']
        issue_damage = devices['damage'][issueID]
        fatal = issues[issue]['fatal']
        deviceIDs = devices['IDs']
        N_devices = len(deviceIDs)
        sensor_names = devices['sensors']['IDs']
        sensorIDs = devices['sensors']['names']
        if (fatal):
            ran_num = np.random.uniform(size=N_devices)
            idx = (ran_num < issue_damage)
            for deviceID in deviceIDs[idx]:
                if (devices[deviceID]['state'] == 'operating'):
                    devices[deviceID]['state'] = 'failed'
                    devices[deviceID]['issue'] = issue
                    devices[deviceID]['fail_time'] = time
                    devices[deviceID]['production_rate_fail_time'] = devices[deviceID]['production_rate']
                    if (debug):
                        print 'DEVICE  FAILURE    :    time = ', time, 'deviceID = ', deviceID#, '\tissue = ', issue
    return

#send first available technician to service failed deviceIDs
def service_failed_devices(devices, technicians, time, repair_duration, debug):
    random_deviceIDs = devices['IDs'].copy()
    np.random.shuffle(random_deviceIDs)
    random_technicianIDs = technicians['IDs'].copy()
    np.random.shuffle(random_technicianIDs)
    repairs = []
    for deviceID in random_deviceIDs:
        if (devices[deviceID]['state'] == 'failed'):
            issue = devices[deviceID]['issue']
            for technicianID in random_technicianIDs:
                if (technicians[technicianID]['location'] == -1):
                    repair_maintenance = 'repair'
                    repair = service_deviceID(deviceID, issue, technicianID, devices, technicians, time, repair_duration, 
                        repair_maintenance, debug)
                    repairs += [repair]
                    if (debug):
                        print 'FAILURE MAINTENANCE:    time = ', time, 'deviceID = ', deviceID, '\tissue = ', issue, \
                            '\ttechnicianID = ', technicianID, '\trepair_complete_time = ', devices[deviceID]['repair_complete_time']
                    break
    return repairs

#send technician to repair/maintain deviceID
def service_deviceID(deviceID, issue, technicianID, devices, technicians, time, repair_duration, repair_maintenance, debug):
    technicians[technicianID]['location'] = deviceID
    devices[deviceID]['state'] = repair_maintenance
    devices[deviceID]['technicianID'] = technicianID
    devices[deviceID]['repair_start_time'] = time
    devices[deviceID]['repair_complete_time'] = time + repair_duration
    repair = {'time':time, 'deviceID':deviceID, 'issue':issue, 'technicianID':technicianID, 
        'production_rate':devices[deviceID]['production_rate_fail_time']}
    sensor_names = devices['sensors']['names']
    sensor_values = devices['sensors']['values'][deviceID]
    for idx in range(len(sensor_names)):
        repair[sensor_names[idx]] = sensor_values[idx]
    return repair

#generate array of features used by pdm models
def get_model_features(devices, issues, time):
    x = pd.DataFrame(devices['sensors']['values'], columns=devices['sensors']['names'])
    deviceIDs = devices['IDs']
    production_rate = np.array([devices[deviceID]['production_rate'] for deviceID in deviceIDs])
    x['production_rate'] = production_rate
    fatal_issues = [issue for issue in issues.keys() if (issues[issue]['fatal'] == True)]
    N_devices = len(deviceIDs)
    for issue in fatal_issues:
        times_since_issue = np.zeros(N_devices)
        for deviceID in deviceIDs:
            times_since_issue[deviceID] = time - devices[deviceID][issue + '_repair_time']
        x_col = 'time_since_' + issue
        x[x_col] = times_since_issue
    return x, fatal_issues

#send into maintenance those deviceIDs that are predicted to suffer failure soon enough
def pdm_check(devices, issues, time, technicians, models, maintenance_duration, pdm_threshold_time, pdm_threshold_probability, debug):
    #get features used to predict each device's log(time-to-next-failure)
    x, fatal_issues = get_model_features(devices, issues, time)
    y_pred = pd.DataFrame()
    repairs = []
    random_technicianIDs = technicians['IDs'].copy()
    np.random.shuffle(random_technicianIDs)
    random_deviceIDs = devices['IDs'].copy()
    np.random.shuffle(random_deviceIDs)
    for issue in fatal_issues:
        y_col = issue + '_in_' + str(pdm_threshold_time)
        model = models[y_col]
        class1 = model.classes_[1]
        y_col_prob = model.predict_proba(x)
        for deviceID in random_deviceIDs:
            if (devices[deviceID]['state'] == 'operating'):
                if (y_col_prob[deviceID][class1] > pdm_threshold_probability):
                    for technicianID in random_technicianIDs:
                        if (technicians[technicianID]['location'] == -1):
                            repair_maintenance = 'maintenance'
                            devices[deviceID]['issue'] = issue
                            repair = service_deviceID(deviceID, issue, technicianID, devices, technicians, time, maintenance_duration, 
                                repair_maintenance, debug)
                            repairs += [repair]
                            if (debug):
                                print 'prevent MAINTENANCE:    time = ', time, 'deviceID = ', deviceID, '\tissue = ', issue, \
                                    '\ttechnicianID = ', technicianID, '\trepair_complete_time = ', \
                                    devices[deviceID]['repair_complete_time'], '\t****'
                            break
    return repairs

#when maintenance is complete, set device's sensors=0, set device's crud & issue damage=0, and release devices & technicians 
def complete_maintenance(devices, issues, technicians, time, debug):
    deviceIDs = devices['IDs']
    for deviceID in deviceIDs:
        if ((devices[deviceID]['state'] == 'repair') or (devices[deviceID]['state'] == 'maintenance')):
            if (time > devices[deviceID]['repair_complete_time']):
                devices['sensors']['values'][deviceID, :] = 0.0
                issue = 'crud'
                issueID = issues[issue]['ID']
                devices['damage'][issueID, deviceID] = 0.0
                issue = devices[deviceID]['issue']
                issueID = issues[issue]['ID']
                devices['damage'][issueID, deviceID] = 0.0
                technicianID = devices[deviceID]['technicianID']
                technicians[technicianID]['location'] = -1
                devices[deviceID]['state'] = 'operating'
                devices[deviceID]['issue'] = 'none'
                devices[deviceID]['technicianID'] = -1
                devices[deviceID]['fail_time'] = -1
                devices[deviceID]['repair_start_time'] = -1
                devices[deviceID]['repair_complete_time'] = -1
                devices[deviceID][issue + '_repair_time'] = time
                devices[deviceID]['production_rate_fail_time'] = 0.0
                if (debug):
                    print 'REPAIR  COMPLETE   :    time = ', time, 'deviceID = ', deviceID, '\ttechnicianID = ', technicianID
    return

#generate sensor telemetry update output_times
def generate_telemetry(devices, technicians, time, output_interval):
    telemetrys = []
    deviceIDs = devices['IDs']
    sensorIDs = devices['sensors']['IDs']
    sensor_names = devices['sensors']['names']
    sensor_values = devices['sensors']['values']
    sensor_output_times = devices['sensors']['output_times']
    for sensorID in sensorIDs:
        sensor_name = sensor_names[sensorID]
        sensor_value = sensor_values[:, sensorID]
        sensor_output_time = sensor_output_times[:, sensorID]
        for deviceID in deviceIDs[time > sensor_output_time]:
            #report deviceID's sensor value
            telemetry = {'time':time, 'deviceID':deviceID, 'sensor':sensor_name, 'value':sensor_value[deviceID]}
            telemetrys += [telemetry]
            #report deviceID's production_rate
            telemetry = {'time':time, 'deviceID':deviceID, 'sensor':'production_rate', 'value':devices[deviceID]['production_rate']}
            telemetrys += [telemetry]
            sensor_output_time[deviceID] = time + output_interval
    #report number of technicians that are servicing devices
    N_technicians = 0.0
    technicianIDs = technicians['IDs']
    for technicianID in technicianIDs:
        if (technicians[technicianID]['location'] != -1):
            N_technicians += 1.0
    telemetrys += [{'time':time, 'deviceID':-1, 'sensor':'N_technicians', 'value':N_technicians}]
    #report number of devices that are operating, failed, and repaired
    N_operating = 0.0
    N_failed = 0.0
    N_repair = 0.0
    N_maintenance = 0.0
    for deviceID in deviceIDs:
        if (devices[deviceID]['state'] == 'operating'):
            N_operating += 1.0
        if (devices[deviceID]['state'] == 'failed'):
            N_failed += 1.0
        if (devices[deviceID]['state'] == 'repair'):
            N_repair += 1.0
        if (devices[deviceID]['state'] == 'maintenance'):
            N_maintenance += 1.0
    telemetrys += [{'time':time, 'deviceID':-1, 'sensor':'N_operating', 'value':N_operating}]
    telemetrys += [{'time':time, 'deviceID':-1, 'sensor':'N_failed', 'value':N_failed}]
    telemetrys += [{'time':time, 'deviceID':-1, 'sensor':'N_repair', 'value':N_repair}]
    telemetrys += [{'time':time, 'deviceID':-1, 'sensor':'N_maintenance', 'value':N_maintenance}]
    return telemetrys

#compute time until device experiences next issue
def time_to_issue(records, issue_names):
    df = records
    df_list = []
    deviceIDs = df.deviceID.unique()
    for deviceID in deviceIDs:
        df = records
        df = df[df.deviceID == deviceID].copy().reset_index(drop=True).sort_values('time')
        for issue in issue_names:
            col = 'time_til_' + issue
            df[col] = None
            idx = (df.issue == issue)
            issue_times = df[idx].time.sort_index(ascending=False)
            if (len(issue_times) > 0):
                for idx, issue_time in issue_times.iteritems():
                    df.loc[0:idx, col] = issue_time
                df[col] -= df.time
                #df[col] = df[col].fillna(df[col].median().astype(int))
        df_list += [df]
    df = pd.concat(df_list)
    #cols = [col for col in df.columns if (col.startswith('time_til_'))]
    #for col in cols:
    #    idx = df[col].isnull()
    #    df.loc[idx, col] = df[~idx][col].max()
    return df

#compute time since device's previous issue
def time_since_issue(records, issue_names):
    df = records
    df_list = []
    deviceIDs = df.deviceID.unique()
    for deviceID in deviceIDs:
        df = records
        df = df[df.deviceID == deviceID].copy().reset_index(drop=True).sort_values('time')
        for issue in issue_names:
            col = 'time_since_' + issue
            df[col] = None
            idx = (df.issue == issue)
            issue_times = df[idx].time.sort_index(ascending=True)
            if (len(issue_times) > 0):
                for idx, issue_time in issue_times.iteritems():
                    df.loc[idx:, col] = -issue_time
                df[col] += df.time
                #df[col] = df[col].fillna(df[col].median().astype(int))
        df_list += [df]
    df = pd.concat(df_list)
    #cols = [col for col in df.columns if (col.startswith('time_since_'))]
    #for col in cols:
    #    idx = df[col].isnull()
    #    df.loc[idx, col] = df[~idx][col].max()
    return df

#prep rtf data for models
def prep_rtf_data(time_bucket_size, issues, telemetry_file, repairs_file):
    
    #read device telemetry and add time_bucket column
    print 'reading ' + telemetry_file + ' ...'
    df = pd.read_csv(telemetry_file, header=None, sep='|', compression='gzip', \
        names=['time', 'deviceID', 'sensor', 'value'])
    df['time_bucket'] = (df.time/time_bucket_size).astype(int)
    telemetry = df
    
    #pivot telemetry
    print 'pivoting telemetry...'
    df = telemetry.pivot_table(values='value', index=['deviceID', 'time_bucket'], 
        aggfunc='mean', columns='sensor').reset_index()
    df['time'] = df.time_bucket*time_bucket_size
    df.columns.name = None
    cols = ['deviceID', 'time_bucket', 'time', 'load', 'pressure', 'temperature', 'production_rate']
    df = df[cols]
    df = df[df.deviceID > -1]
    telemetry_pivot = df
    
    #read device repairs logs
    print 'reading ' + repairs_file + ' ...'
    df = pd.read_csv(repairs_file, header=None, sep='|', compression='gzip', \
        names=['time', 'deviceID', 'issue', 'technicianID', 'temperature', 'pressure', 'load', 'production_rate'])
    df['time_bucket'] = (df.time/time_bucket_size).astype(int)
    sensor_names = ['temperature', 'pressure', 'load']
    cols = ['time_bucket', 'deviceID', 'technicianID', 'issue', 'production_rate'] + sensor_names
    df = df[cols]
    cols = {sensor_name:sensor_name + '_fail' for sensor_name in sensor_names}
    cols['production_rate'] = 'production_rate_fail'
    df = df.rename(columns=cols)
    repairs = df
    
    #merge telemetry and repairs
    print 'merging telemetry and repairs...'
    df = telemetry_pivot.merge(repairs, on=['time_bucket', 'deviceID'], how='left', sort=True).reset_index(drop=True)
    df.issue = df.issue.astype(str)
    df.loc[df.issue == 'nan', 'issue'] = 'none'
    df.loc[df.technicianID.isna(), 'technicianID'] = -1.0
    df.technicianID = df.technicianID.astype(int)
    telemetry_repairs = df
    
    #get issue_names with crud dropped
    issue_names = issues.keys()
    issue_names.remove('crud')
    print 'issue_names = ', issue_names
    
    #compute time for each device to hit next issue, takes a minute...
    print 'computing time to next issue...'
    records_time = time_to_issue(telemetry_repairs, issue_names)
    
    #compute time for each device to hit next issue, takes a minute...
    print 'computing time since previous issue...'
    records = time_since_issue(records_time, issue_names)
    
    #done
    return telemetry, repairs, records
