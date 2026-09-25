import pandas as pd
import numpy as np
import logging
from pathlib import Path
import glob

logger = logging.getLogger(__name__)

class DataProcessor:
    def __init__(self, raw_data_dir: str, processed_data_dir: str):
        self.raw_data_dir = Path(raw_data_dir)
        self.processed_data_dir = Path(processed_data_dir)
        self.processed_data_dir.mkdir(parents=True, exist_ok=True)
        
    def create_journey_records(self, loader_output_dir: str):
        logger.info("Creating journey records...")
        
        # Load stations and trains from raw for additional joins
        stations_df = pd.read_csv(self.raw_data_dir / 'station_full_names.csv')
        stations_df['station_name'] = stations_df['station_name'].str.strip()
        
        trains_df = pd.read_csv(self.raw_data_dir / 'train_details.csv', dtype={'train_no': str})
        trains_df['train_no'] = trains_df['train_no'].str.strip().apply(lambda x: x.lstrip('0') if x.startswith('0') and len(x.lstrip('0')) > 0 else x)
        
        chunk_files = glob.glob(str(Path(loader_output_dir) / 'merged_delay_base*.parquet'))
        
        all_dfs = []
        for f in chunk_files:
            logger.info(f"Processing {f}...")
            df = pd.read_parquet(f, engine='pyarrow')
            
            # Filter rows without schedule mapping if strict
            # For now, let's process what we have
            
            # Enrich with train_type and zone
            df = df.merge(trains_df[['train_no', 'type_code']], on='train_no', how='left')
            df = df.merge(stations_df[['station_name', 'station_zone']], on='station_name', how='left')
            
            df.rename(columns={'type_code': 'train_type', 'station_zone': 'zone', 'station_name': 'station_code', 'delay': 'delay_minutes'}, inplace=True)
            
            df['date'] = pd.to_datetime(df['date'])
            df['day_of_week'] = df['date'].dt.dayofweek
            df['month'] = df['date'].dt.month
            df['is_weekend'] = df['day_of_week'].isin([5, 6]).astype(int)
            
            # Sort by train, date, and distance to calculate previous station stats safely
            # Since chunks might break journeys, it's risky to calculate lag over chunks.
            # In a real big-data pipeline, we'd sort the whole thing. Let's do a grouped sort per chunk and warn.
            df = df.sort_values(by=['train_no', 'date', 'distance_from_origin'])
            
            # Delay change
            df['previous_station_delay'] = df.groupby(['train_no', 'date'])['delay_minutes'].shift(1)
            df['delay_change'] = df['delay_minutes'] - df['previous_station_delay']
            
            # Add section ID
            df['prev_station_code'] = df.groupby(['train_no', 'date'])['station_code'].shift(1)
            df['section_id'] = df['prev_station_code'] + '->' + df['station_code']
            
            # scheduled_running_time and cumulative_journey_fraction require route-level aggregations
            max_dist = df.groupby('train_no')['distance_from_origin'].transform('max')
            df['cumulative_journey_fraction'] = df['distance_from_origin'] / max_dist.replace(0, np.nan)
            
            # Scheduled arrival / actual arrival logic
            # Using current date + arrival time (this can cross midnight, requires careful handling based on arrival_day)
            
            # Drop temporary columns if needed
            all_dfs.append(df)
            
        logger.info("Concatenating all chunks for splitting...")
        # If the dataset fits in memory now (since we dropped raw columns)
        final_df = pd.concat(all_dfs, ignore_index=True)
        
        # Sort globally to be sure
        final_df = final_df.sort_values(by=['train_no', 'date', 'distance_from_origin'])
        
        # Recalculate lag features globally to fix chunk boundaries
        final_df['previous_station_delay'] = final_df.groupby(['train_no', 'date'])['delay_minutes'].shift(1)
        final_df['delay_change'] = final_df['delay_minutes'] - final_df['previous_station_delay']
        final_df['prev_station_code'] = final_df.groupby(['train_no', 'date'])['station_code'].shift(1)
        final_df['section_id'] = final_df['prev_station_code'] + '->' + final_df['station_code']
        
        # Create Train / Val / Test Split (70/15/15 chronological)
        dates = final_df['date'].sort_values().unique()
        n = len(dates)
        train_dates = dates[:int(n*0.7)]
        val_dates = dates[int(n*0.7):int(n*0.85)]
        test_dates = dates[int(n*0.85):]
        
        train_df = final_df[final_df['date'].isin(train_dates)]
        val_df = final_df[final_df['date'].isin(val_dates)]
        test_df = final_df[final_df['date'].isin(test_dates)]
        
        # Save output
        train_df.to_parquet(self.processed_data_dir / 'train.parquet', engine='pyarrow', index=False)
        val_df.to_parquet(self.processed_data_dir / 'val.parquet', engine='pyarrow', index=False)
        test_df.to_parquet(self.processed_data_dir / 'test.parquet', engine='pyarrow', index=False)
        logger.info("Processed data successfully saved.")

