# Imports
import json
from decimal import Decimal
import os
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from urllib.parse import quote

path = 'C:/Users/apathak11/OneDrive - VE Commercial Vehicles Ltd/Desktop/ev_charging_kpi/'
file = 'connection_config.json'
config_path = path+file
with open(config_path) as config_file:
    config = json.load(config_file)
    
here_creds = config['here_api_cred']
HERE_API_URL = here_creds['here_api_url']
HERE_API_KEY = here_creds['here_api_key']   

mysql_config = config["MYSQL_master"]
HOST = mysql_config["HOST_m"]
PORT = mysql_config["PORT_m"] #9038 / 34
USER = mysql_config["USER_m"]
PASSWORD = mysql_config["PASSWORD_m"]
DATABASE = mysql_config["DATABASE_m"]

print(DATABASE)
print(HOST)
print(PORT) # Changing port leads to qa and prod
print(PASSWORD)
print(USER)


def connecting_to_mysql(ip_address, port, username, password, database_name):
        db_connection_str = f"mysql+pymysql://{username}:{quote(password)}@{ip_address}:{port}/{database_name}"
        engine = create_engine(db_connection_str)
        Session = sessionmaker(bind=engine)
        session = Session()
        return session 
    
    
# Define the SQL query with placeholders
sql_query = text("""
                 SELECT *
FROM vecvdb.ev_monthly_efficiency_vw
WHERE month BETWEEN
      DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL 13 MONTH), '%Y-%m')
  AND DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL 1 MONTH), '%Y-%m');
""")
# Create a session and execute the query
session = connecting_to_mysql(HOST, PORT, USER, PASSWORD, DATABASE)
result = session.execute(sql_query)

# Fetch the results into a DataFrame
db_data = pd.DataFrame(result.fetchall(), columns=result.keys())
print(db_data)     

for col in db_data.columns:
    if db_data[col].apply(lambda x: isinstance(x, Decimal)).any():
        db_data[col] = db_data[col].astype(float)
        
yearly = (
    db_data.groupby(
        ['customer_id', 'chassis_number', 'reg_no', 'veh_model'],
        as_index=False
    )
    .agg(
        vehicle_efficiency=('veh_eff_kwh_per_km', 'mean'),
        annual_distance=('distance', 'sum'),
        annual_power_consumption=('total_power_cons', 'sum'),
        harsh_acceleration=('harsh_acceleration', 'mean'),
        harsh_breaking=('harsh_breaking', 'mean'),
        overspeed_distance_pct=('overspeed_distance_pct', 'mean'),
        ac_power_pct=('ac_power_pct', 'mean')
    )
)

round_cols = [
    'vehicle_efficiency',
    'annual_distance',
    'annual_power_consumption',
    'overspeed_distance_pct',
    'ac_power_pct'
]

yearly[round_cols] = yearly[round_cols].round(2)
# Calculate model efficiency within each customer
yearly['model_efficiency'] = (
    yearly.groupby(['customer_id', 'veh_model'])['vehicle_efficiency']
          .transform('mean')
          .round(2)
)
yearly['deviation'] = (
    (
        yearly['vehicle_efficiency'] -
        yearly['model_efficiency']
    )
    / yearly['model_efficiency'].replace(0, np.nan)
    * 100
).round(2)

yearly['performance_status'] = np.select(
    [
        yearly['deviation'] < -5,
        yearly['deviation'] <= 10
    ],
    [
        'Good',
        'Average'
    ],
    default='Underperforming'
)
# Default NULL
yearly['ac_usage_indicator'] = None
yearly['driver_behaviour_indicator'] = None

# Average & Underperforming mask
mask = yearly['performance_status'].isin(
    ['Average', 'Underperforming']
)

# High AC Usage
yearly.loc[
    mask & (yearly['ac_power_pct'] >= 10),
    'ac_usage_indicator'
] = 'High AC Usage'

# Driving Behaviour
yearly.loc[
    mask,
    'driver_behaviour_indicator'
] = 'Driving Behaviour'

yearly['harsh_acceleration'] = (
    yearly['harsh_acceleration']
    .round()
    .fillna(0)
    .astype(int)
)

yearly['harsh_breaking'] = (
    yearly['harsh_breaking']
    .round()
    .fillna(0)
    .astype(int)
)

yearly.rename(
    columns={'reg_no': 'vehicle_no'},
    inplace=True
)

final_df = yearly[
    [
        'customer_id',
        'chassis_number',
        'vehicle_no',
        'veh_model',
        'annual_distance',
        'annual_power_consumption',
        'vehicle_efficiency',
        'model_efficiency',
        'deviation',
        'performance_status',
        'ac_power_pct',
        'harsh_acceleration',
        'harsh_breaking',
        'overspeed_distance_pct',
        'ac_usage_indicator',
        'driver_behaviour_indicator'
    ]
]
final_df['update_date'] = pd.Timestamp.now().date()

session = connecting_to_mysql(HOST, PORT, USER, PASSWORD, DATABASE)
print('session_created')
try:
    table_name = 'ev_deviation_annual_report_efficiency'
    final_df.to_sql(table_name, con=session.connection(), if_exists='replace', index=False)
    l = len(final_df)
    print(f'{l} no. of records inserted successfully')
    # new_entries.to_sql(table_name, con=session.connection(), if_exists='append', index=False)
    session.commit()
    
except Exception as e:
    print("Error occurred:")
    # traceback.print_exc()
   

    