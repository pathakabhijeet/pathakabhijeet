import os
import time
import json
import warnings
import decimal
# import smtplib
# import pymysql
# import data_fetch
import fetching_1
import logging
from dateutil.relativedelta import relativedelta
# import openpyxl
import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from urllib.parse import quote
#from cloudant.client import Cloudant
from exchangelib import Mailbox, Credentials, Configuration, Account, DELEGATE, Message, HTMLBody
from datetime import datetime, timedelta
# from email.mime.text import MIMEText
# from email.mime.multipart import MIMEMultipart

#Additional Modules

# import combine_records
import pre_processing_ev


# from google.oauth2.credentials import Credentials
from google.cloud import bigquery
# from google.api_core.exceptions import GoogleAPIError
warnings.filterwarnings("ignore")

start = time.time()  #Used to cal the elapsed time.

os.environ["GOOGLE_APPLICATION_CREDENTIALS"]="/sa/keys/conn-internal-prod-c9937473c218.json"
scopes = ["https://www.googleapis.com/auth/cloud-platform"]
client = bigquery.Client(project='conn-datalake-prod')


max_retries = 3 #In case of connection broken or failure max 3 tries to rerun the code
retry_intervals = [10, 20, 30] #Intervals to rerun the code (in seconds)

DATA_1 = 'CAN_BS4'
DATA_2 = 'EV'
path = "/data/Analytics/ev_charging_summary_copy/"

# ev_veh = pd.read_excel(path+'master_up.xlsx', engine = "openpyxl")     
# Manually define the values
dta = {
    'device_id': ['352914091234567'],
    'reg_no': ['MH12AB1234'],
    'vin': ['MA1TA2XYZ98765432']
}

# Create a DataFrame
ev_veh = pd.DataFrame(dta)

# Show the result
print(ev_veh)

imei = ev_veh['device_id'].to_list()
print(imei)

# imei = [''] #C:\Users\DELL\Desktop\EV\Charging\ev_50Server_deployment\master_ev_l.xlsx

file = 'connection_config.json'
config_path = path+file
with open(config_path) as config_file:
    config = json.load(config_file)
    
    
CONFIG_FILEPATH = path+'config_cos_raw.json'
with open(CONFIG_FILEPATH) as config_file:
    DATA = json.load(config_file)

ADMIN_ID = DATA['email_admin_id']
ADMIN_PASSWORD = DATA['email_admin_password'] #mail creds     
    
#Logging
log_path = path+'log/'
log_file = 'log_{}.log'.format(datetime.now().strftime("%Y%m%d%H%M%S"))

if not os.path.exists(log_path):
    os.mkdir(log_path)

logging.basicConfig(filename=log_path+log_file, filemode='w',
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
    
# try:
# Cloudant credentials
#cloudant_config = config["CLOUDANT"]
#CLOUDANT_ID = cloudant_config["CLOUDANT_ID"]
#CLOUDANT_PASSWORD = cloudant_config["CLOUDANT_PASSWORD"]
#CLOUDANT_URL = cloudant_config["CLOUDANT_URL"]

# DB credentials
mysql_config = config["MYSQL_master"]
HOST = mysql_config["HOST_m"]
PORT = mysql_config["PORT_m"]
USER = mysql_config["USER_m"]
PASSWORD = mysql_config["PASSWORD_m"]
DATABASE = mysql_config["DATABASE_m"]

print(HOST)
print(USER)


#client = Cloudant(CLOUDANT_ID, CLOUDANT_PASSWORD, url=CLOUDANT_URL)
#client.connect()  # Connection to Cloudant established


def connecting_to_mysql(ip_address, port, username, password, database_name):
        db_connection_str = f"mysql+pymysql://{username}:{quote(password)}@{ip_address}:{port}/{database_name}"
        engine = create_engine(db_connection_str)
        Session = sessionmaker(bind=engine)
        session = Session()
        return session 
 
def send_email(admin_id, admin_password, send_to, cc_to, subject):
    
    send_recipients = [Mailbox(email_address=email) for email in send_to]
    cc_recipients = [Mailbox(email_address=email) for email in cc_to]
    
    ews_url = 'https://webmail.vecv.in/EWS/Exchange.asmx'
    ews_auth_type = 'NTLM'  # Check if this is the correct auth type
    cred = Credentials(admin_id, admin_password)
    config = Configuration(service_endpoint=ews_url, credentials=cred, auth_type=ews_auth_type)
    
    acc = Account(primary_smtp_address=admin_id, config=config, autodiscover=False, access_type=DELEGATE)
    
    m = Message(account=acc, subject=subject, body=HTMLBody('Hi, Code ev_charging_daily_summary was not executed'), to_recipients=send_recipients, cc_recipients=cc_recipients)

    m.send()    
     
 
def find_start_end_indices(data_series, condition_value):
        start_index = None
        end_index = None
        start_i = []
        end_i = []
    
        for index, value in enumerate(data_series):
            if value == condition_value:
                if start_index is None:
                    start_index = index
                end_index = index
            elif end_index is not None:
                start_i.append(start_index)
                end_i.append(end_index)
                start_index = None
                end_index = None
    
        if start_index is not None:
            start_i.append(start_index)
            end_i.append(end_index)
    
        return start_i, end_i


    
dataframe = []
final_list = []

curr_time = datetime.now()
prev_time = curr_time - timedelta(hours=100)

# curr_3 =curr_time
# prev_3 =curr_time - timedelta(hours=240)

# # prev_time = datetime(2024, 4, 14, 22, 30, 0) 
# START = prev_time.strftime('%Y-%m-%d %H:%M:%S')
# print('STARTDATE',START)
END = curr_time.strftime('%Y-%m-%d %H:%M:%S')
print('ENDDATE', END)

db_s = prev_time.strftime('%Y-%m-%d %H:%M:%S')
print('prev_start_time',db_s)
db_e = curr_time.strftime('%Y-%m-%d %H:%M:%S') 
print('prev_end_time',db_e)

"""Use this in case of historical reports to be made"""

#START = '2025-01-06 00:00:00'  
#END = '2025-01-08 16:57:02'

for i in imei:
    
    IMEI = i

    sql_query = text("""
        SELECT end_soc_time 
        FROM vecvdb.ev_charging_summary_daily 
        WHERE device_id = :i
        ORDER BY end_soc_time DESC 
        LIMIT 1;
    """)
    
    # Connect to the database
    session = connecting_to_mysql(HOST, PORT, USER, PASSWORD, DATABASE)
    
    # Execute the query
    result = session.execute(sql_query, {'i': i})
    
    # Fetch the result into a DataFrame
    db_data = pd.DataFrame(result.fetchall(), columns=['end_soc_time'])
    db_data = {'end_soc_time': ['2025-05-04 18:25:04']}
    db_adta = pd.DataFrame(db_data)
    print(db_data)
    
    # Ensure we have at least one result
    if not db_data.empty:
        # Extract the datetime value correctly
        latest_time = db_data.loc[0, 'end_soc_time']
        
        # Convert to string format
        START = latest_time.strftime('%Y-%m-%d %H:%M:%S')
        print(START)
    else:
        curr_time = datetime.now()
        prev_3 = curr_time - relativedelta(months=3)
 

    if DATA_1 == 'CAN_BS4':
        data_can_bs4 = fetching_1.data_pull_canbs(START, END, IMEI, project_id="conn-datalake-prod")
        print('CAN')
        print(len(data_can_bs4))
        # Ensure data_can_bs4 is a DataFrame
        if not isinstance(data_can_bs4, pd.DataFrame):
            data_can_bs4 = pd.DataFrame(data_can_bs4)
    else:
        data_can_bs4 = pd.DataFrame()  # Set as an empty DataFrame if DATA_1 is not 'CAN_BS4'

    # Fetch data based on DATA_2
    if DATA_2 == 'EV':
        data_ev = fetching_1.data_pull_ev(START, END, IMEI, project_id="conn-datalake-prod")
        print(len(data_ev))
        # Ensure data_ev is a DataFrame
        if not isinstance(data_ev, pd.DataFrame):
            data_ev = pd.DataFrame(data_ev)
    else:
        data_ev = pd.DataFrame()  # Set as an empty DataFrame if DATA_2 is not 'EV'

    # Check if either DataFrame is empty
    if data_can_bs4.empty or data_ev.empty:
        continue
    #--------------------------------------------#
  
    bs4_cols = ['deviceId','hrlfc', 'fuelLevel','latitude','longitude',
                'totalDistance','vehicleSpeed','eDateTime']
    bs4_selected = data_can_bs4[bs4_cols]
    
    # Define old and new column names
    ev_cols = ['Batt_Power_In', 'Charging Status', 'Charging_Time', 'Crank Status',
            'Regeneration Power', 'HVAuxilaryPowerConsumption', 'eDateTime']

    new_ev_cols = ['battPowerIn', 'chargingStatus', 'chargingTime', 'crankStatus',
                'regenerationPower', 'hvAuxilaryPowerConsumption', 'eDateTime']

    # Create a mapping from new_ev_cols to ev_cols
    rename_dict = dict(zip(new_ev_cols, ev_cols))

    # Select and rename columns from data_ev to use old names
    df_ev = data_ev[new_ev_cols].rename(columns=rename_dict)

    # Create a DataFrame with the renamed columns
    ev = pd.DataFrame(df_ev)
    print(len(ev))
    bs4 = pd.DataFrame(bs4_selected)
    print(len(bs4))

    """Merge the dataframes""" 
    
    tol = pd.Timedelta('0.025 hour')  # 30 seconds

    # Ensure both DataFrames are sorted by 'eDateTime'
    bs4 = bs4.sort_values(by='eDateTime')
    ev = ev.sort_values(by='eDateTime')
    print('merge')
    # Perform the asof merge
    merge_df = pd.merge_asof(bs4, ev, on='eDateTime', tolerance=tol)
    print('Data before pre_process : ',len(merge_df))   
    merge_df = pre_processing_ev.data_processing_ev(merge_df)
    merge_df = pre_processing_ev.redundant_charging(merge_df)
    print('Data after pre_process : ',len(merge_df)) 
    #merge_df.to_excel(path+f'str(imei)_raw.xlsx')
    """Data PreProcessing and Error Handling"""
    merge_df = merge_df.dropna(axis=0).reset_index(drop = True)
    merge_df['Crank Status'] = pd.to_numeric(merge_df['Crank Status'], errors='coerce').fillna(2).astype(int)
    merge_df['Charging Status'] = pd.to_numeric(merge_df['Charging Status'], errors='coerce').fillna(2).astype(int)
    merge_df['Batt_Power_In'] = pd.to_numeric(merge_df['Batt_Power_In'], errors='coerce').fillna(0).astype(int)
    merge_df['totalDistance'] = pd.to_numeric(merge_df['totalDistance'], errors='coerce').fillna(0).astype(int)
    merge_df['Charging_Time'] = pd.to_numeric(merge_df['Charging_Time'], errors='coerce').fillna(0).astype(int)
    merge_df['fuelLevel'] = pd.to_numeric(merge_df['fuelLevel'], errors='coerce').fillna(0).astype(float)
    merge_df['Regeneration Power'] = pd.to_numeric(merge_df['Regeneration Power'], errors='coerce').fillna(0).astype(int)
    merge_df['HVAuxilaryPowerConsumption'] = pd.to_numeric(merge_df['HVAuxilaryPowerConsumption'], errors='coerce').fillna(0).astype(int)
    merge_df['latitude'] = pd.to_numeric(merge_df['latitude'], errors='coerce').fillna(0).astype(float)
    merge_df['longitude'] = pd.to_numeric(merge_df['longitude'], errors='coerce').fillna(0).astype(float)
    
    #Error Handling using forward fill approach
    
    if ((merge_df['Batt_Power_In'] == 0)).any():
        merge_df['Batt_Power_In'] = merge_df['Batt_Power_In'].replace(0, np.nan).fillna(method='ffill')
    
    merge_df['eDateTime'] = pd.to_datetime(merge_df['eDateTime'])
    
    #Modifying Charging Status Col and Consider Key Less Charging as Well 
    #---------------------------------------------------------------

    merge_df['soc_diff'] = merge_df['fuelLevel'].diff()

    indexes = merge_df[merge_df['soc_diff'] > 20].index.tolist()

    # ds = df.iloc[indexes]

    merge_df.rename(columns={'Charging Status': 'Charging Status Old'}, inplace=True)

    merge_df['Charging Status'] = 0

    trigger_indexes = merge_df[merge_df['soc_diff'] > 20].index

    all_indexes = set(trigger_indexes) | set(trigger_indexes - 1)
    valid_indexes = [i for i in all_indexes if i >= 0]

    merge_df.loc[valid_indexes, 'Charging Status'] = 1

    # Step 2: Copy values from 'charging_status' where it's 1
    merge_df.loc[merge_df['Charging Status Old'] == 1, 'Charging Status'] = 1
    #---------------------------------------------------------------
    
    start_i_1, end_i_1 = find_start_end_indices(merge_df['Charging Status'], 1)
    start_i_0, end_i_0 = find_start_end_indices(merge_df['Charging Status'], 0)
    
    final_df = pd.DataFrame()
    s_final_df = pd.DataFrame()
    
    final_df['start_soc'] = merge_df.loc[start_i_1, 'fuelLevel'].values
    final_df['end_soc'] = merge_df.loc[end_i_1, 'fuelLevel'].values
    # final_df['ch_time'] = merge_df.loc[end_i_1, 'Charging_Time'].values
    final_df['odometer'] = merge_df.loc[start_i_1, 'totalDistance'].values
    final_df['start_soc_time'] = merge_df.loc[start_i_1, 'eDateTime'].values
    final_df['end_soc_time'] = merge_df.loc[end_i_1, 'eDateTime'].values
    final_df['latitude'] = merge_df.loc[start_i_1, 'latitude'].values
    final_df['longitude'] = merge_df.loc[start_i_1, 'longitude'].values
    final_df['Batt_Power_In_i_ch_1'] = merge_df.loc[start_i_1, 'Batt_Power_In'].values
    final_df['Batt_Power_In_f_ch_1'] = merge_df.loc[end_i_1, 'Batt_Power_In'].values
    # final_df['Batt_Power_In_i_ch_0'] = merge_df.loc[start_i_0, 'Batt_Power_In'].values
    # final_df['Batt_Power_In_f_ch_0'] = merge_df.loc[end_i_0, 'Batt_Power_In'].values
    final_df['hv_AUX_i'] = merge_df.loc[start_i_1, 'HVAuxilaryPowerConsumption'].values
    final_df['hv_AUX_f'] = merge_df.loc[end_i_1, 'HVAuxilaryPowerConsumption'].values
    
    # Regeneration & HVAC
    regen_values = [abs(merge_df.loc[end, 'Batt_Power_In'] - merge_df.loc[start, 'Batt_Power_In']) for start, end in zip(start_i_0, end_i_0)]
    s_final_df['regeneration'] = regen_values
    
    # regen_values = s_final_df['regeneration'] = final_df['Batt_Power_In_f_ch_0'] - final_df['Batt_Power_In_f_ch_0']
    hv_vl = [abs(merge_df.loc[end, 'HVAuxilaryPowerConsumption'] - merge_df.loc[start, 'HVAuxilaryPowerConsumption']) for start, end in zip(start_i_0, end_i_0)]
    s_final_df['hv_AUX'] = hv_vl
    
    #Charging time of the vehicle
    ch_t = [abs(merge_df.loc[end, 'eDateTime'] - merge_df.loc[start, 'eDateTime']) for start, end in zip(start_i_1, end_i_1)]
    ch_t_mins = [td.total_seconds() / 60 for td in ch_t]
    final_df['ch_time'] = ch_t_mins
    final_df['ch_time'] = final_df['ch_time'].round(1)
    
    # Power Drawn by Vehicle while Charging
    
    final_df['Batt_Power_diff'] =abs(final_df['Batt_Power_In_f_ch_1'] - final_df['Batt_Power_In_i_ch_1'])
    final_df['hv_AUX_diff'] = abs(final_df['hv_AUX_f'] - final_df['hv_AUX_i'])
    # Calculate power drawn by the vehicle 
    final_df['power_drawn'] = final_df['Batt_Power_diff'] + final_df['hv_AUX_diff']
    
    final_df.drop(columns = ['Batt_Power_In_i_ch_1', 'Batt_Power_In_f_ch_1',
   'hv_AUX_i','Batt_Power_diff', 'hv_AUX_diff'])
    
    # Reset index
    final_df.reset_index(drop=True, inplace=True)
    
    # Fill device_id column
    final_df['device_id'] = IMEI
    final_df['device_id'].fillna(method='ffill', inplace=True)
    
    # Merge with s_final_df
    merged = final_df.combine_first(s_final_df)
    merged.dropna(axis=0, subset=['device_id', 'start_soc_time'], how='any', inplace=True)
    ds_sorted = merged.sort_values(by=['start_soc_time']).reset_index(drop = True)
    
    #Merge the data in the dataframe
    if ev_veh.empty:
        ev_veh['reg_no'] = ''
        ev_veh['chassis_no'] = ''
    
    ds_sorted['device_id'] = ds_sorted['device_id'].astype(float) 
    ev_veh['device_id'] = ev_veh['device_id'].astype(float) 
    
    db_merge = pd.merge(ds_sorted, ev_veh, on = 'device_id', how = 'left')
    # db_merge.rename(columns={'hvac': 'hv_AUX'}, inplace=True)
    
    order = ['device_id','chassis_no','reg_no','odometer','latitude',
    'longitude','start_soc','start_soc_time','end_soc','end_soc_time',
    'ch_time','power_drawn','regeneration','hv_AUX']
    
    for col in order:
        if col not in db_merge.columns:
            db_merge[col] = 0 # Or use np.nan for numerical values
    db_merge = db_merge[order]
    veh_odo = db_merge['odometer']
    odo_list = veh_odo.to_list()
    print(odo_list)
    
    # Check if odo_list is empty to avoid SQL errors
    if not odo_list:
        print("Warning: odo_list is empty. Query will return no results.")
        odo_list.append(-1)  # Adding a dummy value to avoid SQL errors
    
    # Corrected SQL query with placeholders
    sql_query = text("""
        SELECT * 
        FROM vecvdb.ev_charging_summary_daily ecsd 
        WHERE device_id = :device_id 
        AND odometer IN :odo_list;
    """)
    # Create a session
    session = connecting_to_mysql(HOST, PORT, USER, PASSWORD, DATABASE)
    result = session.execute(sql_query, {'device_id': i, 'odo_list': tuple(odo_list)})
    db_data = pd.DataFrame(result.fetchall(), columns=[
        'device_id', 'chassis_no', 'reg_no', 'odometer', 'latitude',
        'longitude', 'start_soc', 'start_soc_time', 'end_soc', 'end_soc_time',
        'ch_time', 'power_drawn', 'regeneration', 'hv_AUX'
    ])
    
    
    # db_merge = pd.read_excel('C:/Users/apathak11/Desktop/Backup/ev_charging_kpi\SCV EV/ev_import/359207067873578_19.xlsx', 'Sheet1')
    # db_data = pd.read_excel('C:/Users/apathak11/Desktop/Backup/ev_charging_kpi\SCV EV/ev_import/359207067873578_19.xlsx', 'Sheet2')
    
    # Concatenate data to keep all events
    merged_df = pd.concat([db_merge, db_data], ignore_index=True)
    merged_df = merged_df.sort_values(by="start_soc_time")
    
    numeric_cols = ['power_drawn', 'regeneration', 'hv_AUX']  # Add other numeric columns if needed
    for col in numeric_cols:
        merged_df[col] = merged_df[col].apply(lambda x: float(x) if isinstance(x, decimal.Decimal) else x)
    
    # Apply aggregation for duplicate odometer values
    result = merged_df.groupby(['chassis_no', 'odometer']).agg({
        'reg_no': 'first',
        'device_id': 'first',
        'latitude': 'first',
        'longitude': 'last',
        'start_soc': 'first',
        'start_soc_time': 'first',
        'end_soc': 'last',
        'end_soc_time': 'last',
        'power_drawn': 'sum',
        'regeneration': 'sum',
        'hv_AUX': 'sum'
    }).reset_index()
    
    # Convert times to datetime
    result['start_soc_time'] = pd.to_datetime(result['start_soc_time'], format='%d-%m-%Y %H.%M')
    result['end_soc_time'] = pd.to_datetime(result['end_soc_time'], format='%d-%m-%Y %H.%M')
    
    # Calculate charging time
    result['ch_time'] = (result['end_soc_time'] - result['start_soc_time']).dt.total_seconds() / 60
    result['ch_time'] = result['ch_time'].round(1)
    
    # Column order
    column_order = [
        'device_id', 'chassis_no', 'reg_no', 'odometer', 'latitude', 'longitude',
        'start_soc', 'start_soc_time', 'end_soc', 'end_soc_time', 'ch_time',
        'power_drawn', 'regeneration', 'hv_AUX'
    ]
    
    result = result[column_order]
    
    del_events = db_data[db_data['odometer'].isin(result['odometer'])]
    # Display results
    print("Final Merged Event DataFrame:")
    print(result)
    
    print("\nDeleted Events DataFrame:")
    print(del_events)
    
    # if not del_events.empty:
    #     file_len = len(db_merge)
    #     print('Total Events Created', file_len)
    #     db_merge.to_excel(path+'/del_events/'+str(i)+'_'+str(file_len)+'.xlsx')
        
    # if not result.empty:
    #     file_len = len(db_merge)
    #     print('Total Events Created', file_len)
    #     result.to_excel(path+'/output/'+str(i)+'_'+str(file_len)+'.xlsx')    
    # try:
    #     # Deletion
    #     for idx, row in del_events.iterrows():
    #         sql_query_delete = text("""
    #             DELETE FROM ev_charging_summary_daily 
    #             WHERE chassis_no = :chassis_no AND odometer = :odometer
    #         """)
    #         session.execute(sql_query_delete, {'chassis_no': row['chassis_no'], 'odometer': row['odometer']})
        
    #     # Insertion
    #     table_name = 'ev_charging_summary_daily'
    #     result.to_sql(table_name, con=session.connection(), if_exists='append', index=False)
        
    #     session.commit()
    
    # except Exception as e:
    #     logging.error(e)
    #     print(e)
    #     SEND_TO =["apathak11@vecv.in"] 
    #     CC_TO = ["apathak11@vecv.in"] 
    #     SUBJECT = "Error | QA Code | SQL Operation | Ev Charging Summary Daily" 
    #     send_email(ADMIN_ID, ADMIN_PASSWORD, SEND_TO, CC_TO, SUBJECT)
    # if not db_merge.empty:
    #     file_len = len(db_merge)
    #     print('Total Events Created', file_len)
    #     db_merge.to_excel(path+'/output/'+str(i)+'_'+str(file_len)+'.xlsx')
        
        

    # merged = final_df.combine_first(s_final_df)
    # dataframe.append(merged)
    
    # ds = pd.concat(dataframe, ignore_index=True)
    # ds.dropna(axis=0, subset=['device_id', 'start_soc_time'], how='any', inplace=True)
    
    # ds_sorted = ds.sort_values(by=['start_soc_time']).reset_index(drop = True)
    
    # #Merge the data in the dataframe
    # if ev_veh.empty:
    #     ev_veh['reg_no'] = ''
    #     ev_veh['chassis_no'] = ''
    
    # ds_sorted['device_id'] = ds_sorted['device_id'].astype(float) 
    # ev_veh['device_id'] = ev_veh['device_id'].astype(float) 
    
    # db_merge = pd.merge(ds_sorted, ev_veh, on = 'device_id', how = 'left')
    # # db_merge.rename(columns={'hvac': 'hv_AUX'}, inplace=True)
    
    # order = ['device_id','chassis_no','reg_no','odometer','latitude',
    # 'longitude','start_soc','start_soc_time','end_soc','end_soc_time',
    # 'ch_time','power_drawn','regeneration','hv_AUX']
    
    # db_merge = db_merge[order]
    
    # # Define paths
    # path = "/data/Analytics/ev_charging_summary_copy/"
    # output_dir = os.path.join(path, "output")
    # os.makedirs(output_dir, exist_ok=True)  # Ensure the output folder exists
    
    # # Define the base filename
    # filename = "m_curr_ev_output.xlsx"
    # full_path = os.path.join(output_dir, filename)
    
    # # Check if file exists and generate a unique name if needed
    # counter = 1
    # while os.path.exists(full_path):
    #     base, ext = os.path.splitext(filename)
    #     new_filename = f"{base}_{counter}{ext}"  # Example: m_curr_ev_output_1.xlsx
    #     full_path = os.path.join(output_dir, new_filename)
    #     counter += 1
    
    # # Save the DataFrame to Excel
    # db_merge.to_excel(full_path, index=False)  
    # print(f"File saved as: {full_path} (Rows: {len(db_merge)})")    

