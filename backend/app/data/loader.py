import pandas as pd
import numpy as np
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple, Any

# Ensure we import domain models, assuming they exist in app.models.domain
# from ..models.domain import Station, Train, Route

logger = logging.getLogger(__name__)

class DataLoader:
    def __init__(self, raw_data_dir: str):
        self.raw_data_dir = Path(raw_data_dir)
        self.stations: Dict[str, Any] = {}
        self.trains: Dict[str, Any] = {}
        self.routes: Dict[str, Any] = {}
    
    def normalize_train_no(self, train_no: str) -> str:
        """Strip leading zeros for 5-digit trains, keep as string."""
        train_no = str(train_no).strip()
        if len(train_no) > 0 and train_no.startswith('0'):
            # Generally if it's 5 digits, strip leading zero
            # But let's just use lstrip('0') if it results in something valid, 
            # or keep it if it's a special train format.
            stripped = train_no.lstrip('0')
            if len(stripped) > 0:
                return stripped
        return train_no
        
    def load_stations(self) -> pd.DataFrame:
        logger.info("Loading stations...")
        file_path = self.raw_data_dir / 'station_full_names.csv'
        df = pd.read_csv(file_path)
        
        # Clean whitespace
        df = df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
        
        for _, row in df.iterrows():
            self.stations[row['station_name']] = {
                'station_code': row['station_name'],
                'station_full_name': row.get('station_full_name', ''),
                'station_zone': row.get('station_zone', ''),
                'station_address': row.get('station_address', '')
            }
        return df

    def load_trains(self) -> pd.DataFrame:
        logger.info("Loading trains...")
        file_path = self.raw_data_dir / 'train_details.csv'
        df = pd.read_csv(file_path)
        
        df = df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
        df['train_no'] = df['train_no'].astype(str).apply(self.normalize_train_no)
        
        for _, row in df.iterrows():
            self.trains[row['train_no']] = {
                'train_no': row['train_no'],
                'train_name': row.get('train_name', ''),
                'type_code': row.get('type_code', '')
            }
        return df

    def load_schedule(self) -> pd.DataFrame:
        logger.info("Loading schedule...")
        file_path = self.raw_data_dir / 'combined_schedule.csv'
        df = pd.read_csv(file_path)
        
        df = df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
        df['train_no'] = df['train_no'].astype(str).apply(self.normalize_train_no)
        
        # Parse time objects
        # Raw data uses HH:MM format, some cells empty
        df['arrival_time'] = pd.to_datetime(df['arrival_time'], format='%H:%M', errors='coerce').dt.time
        df['departure_time'] = pd.to_datetime(df['departure_time'], format='%H:%M', errors='coerce').dt.time
        
        # Build route lookup
        for train_no, group in df.groupby('train_no'):
            sorted_group = group.sort_values('distance_from_origin')
            route_stops = []
            for _, row in sorted_group.iterrows():
                route_stops.append({
                    'station_no': row['station_no'],
                    'station_name': row['station_name'],
                    'distance_from_origin': row['distance_from_origin'],
                    'arrival_day': row.get('arrival_day', 1),
                    'arrival_time': row['arrival_time'],
                    'departure_day': row.get('departure_day', 1),
                    'departure_time': row['departure_time']
                })
            self.routes[train_no] = route_stops
            
        return df

    def load_delay_chunked(self, schedule_df: pd.DataFrame, output_path: str) -> None:
        logger.info("Loading delay data in chunks and merging with schedule...")
        file_path = self.raw_data_dir / 'combined_delay.csv'
        
        chunksize = 500_000
        total_chunks = 0
        
        # Keep schedule columns we need
        sched = schedule_df[['train_no', 'station_name', 'distance_from_origin', 
                             'arrival_day', 'arrival_time', 'departure_day', 'departure_time']]
        
        first_chunk = True
        
        for chunk in pd.read_csv(file_path, chunksize=chunksize, dtype={'train_no': str, 'station_name': str}):
            total_chunks += 1
            logger.info(f"Processing chunk {total_chunks}...")
            
            # Clean string cols
            for col in ['station_name', 'train_no']:
                if col in chunk.columns:
                    chunk[col] = chunk[col].str.strip()
                    
            chunk['train_no'] = chunk['train_no'].apply(self.normalize_train_no)
            
            # Parse dates
            chunk['date'] = pd.to_datetime(chunk['date'], errors='coerce')
            
            # Convert delay to nullable int
            chunk['delay'] = pd.to_numeric(chunk['delay'], errors='coerce').astype('Int64')
            
            # Merge with schedule to get journey records
            merged = pd.merge(chunk, sched, on=['train_no', 'station_name'], how='left')
            
            # Write to parquet
            if first_chunk:
                merged.to_parquet(output_path, engine='pyarrow', index=False)
                first_chunk = False
            else:
                # append to existing parquet might need fastparquet or writing separate chunks
                # Here we write separate chunks for simplicity in processing
                chunk_path = str(output_path).replace('.parquet', f'_{total_chunks}.parquet')
                merged.to_parquet(chunk_path, engine='pyarrow', index=False)

    def process_all(self, output_dir: str):
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        self.load_stations()
        self.load_trains()
        sched_df = self.load_schedule()
        
        self.load_delay_chunked(sched_df, str(Path(output_dir) / 'merged_delay_base.parquet'))
