"""
BACnet device implementation for hardware-in-the-loop testing.

This module provides a device implementation for testing physical or virtual
BACnet controllers using the BAC0 library.
"""

from src.device.base_device import BaseDevice, Point
import BAC0
import pandas as pd
import time
from pathlib import Path


class BacnetDevice(BaseDevice):
    """
    Device implementation for BACnet-based testing.
    
    This class connects to physical or virtual BACnet devices and provides
    the standardized device interface for ASHRAE Guideline 36 conformance testing.
    
    Attributes
    ----------
    network_address
        IP address for BACnet network connection
    device_address
        BACnet device address
    device_id
        BACnet device identifier
    bacnet
        BAC0 network connection
    device
        BAC0 device object
    mapping
        Mapping between BACnet point names and test script names
    """
    
    def __init__(self, device_config):
        """
        Initialize BACnet device.
        
        Parameters
        ----------
        device_config
            Configuration dictionary containing:
            - network_address: IP address for BACnet connection
            - device_address: BACnet device address
            - device_id: BACnet device ID
            - point_map: Path to point mapping CSV file
        """
        super().__init__(device_config)
        self.init_device(config=device_config)

    def init_device(self, config):
        """
        Initialize BACnet connection and point mapping.
        
        Parameters
        ----------
        config
            Device configuration
        """
        self.network_address = config["network_address"]
        self.device_address = config["device_address"]
        self.device_id = config["device_id"]
        
        # Connect to BACnet network
        self.bacnet = BAC0.connect(ip=self.network_address)
        
        # Connect to specific device
        self.device = BAC0.device(
            address=self.device_address,
            device_id=self.device_id,
            network=self.bacnet,
            poll=5
        )
        
        # Load point mapping from CSV
        # CSV should have columns: 'Variable Name' and 'BACnet Name' (device name)
        # Can optionally include other metadata columns
        files_folder = Path(__file__).resolve().parent.parent / "files"
        df_mapping = pd.read_csv(files_folder / config["point_map"], header=3, index_col='BACnet Name')
        
        # Create mapping DataFrame: index=bacnet_name, column=name_in_test
        self.mapping = df_mapping[['Variable Name']].rename(columns={'Variable Name': 'name_in_test'})
        self.mapping.index.name = 'bacnet_name'
        
        # Get BACnet point properties from device
        point_properties_df = self.device.points_properties_df().T
        
        # Merge with mapping to get final point properties
        point_properties_df = pd.merge(
            left=point_properties_df,
            right=self.mapping,
            how='inner',
            left_index=True,
            right_index=True
        )
        
        # Create Point objects from merged properties
        self._create_points_from_properties(point_properties_df)
        
        # Store for compatibility
        self._point_properties_df = point_properties_df
        
        # Reset device with filtered object list
        object_list = point_properties_df.apply(
            lambda x: (x['type'], x['address']),
            axis=1
        ).values.tolist()
        self.reset_device(object_list=object_list)

    def _create_points_from_properties(self, properties_df):
        """
        Create Point objects from BACnet properties DataFrame.
        
        Parameters
        ----------
        properties_df
            DataFrame with BACnet point properties
        """
        for bacnet_name in properties_df.index:
            row = properties_df.loc[bacnet_name]
            
            point = Point(
                name=bacnet_name,
                name_in_test=row['name_in_test'],
                unit=row.get('units', None),
                point_type=row.get('type', None),
                causality=row.get('type', None),  # BACnet uses 'type' (e.g., 'analogInput')
                metadata={
                    'address': row.get('address', None),
                    'object_type': row.get('type', None),
                    'description': row.get('description', ''),
                    'priority_array': row.get('priorityArray', None)
                }
            )
            
            self.points[bacnet_name] = point

    def get_point_properties(self):
        """
        Get point properties as DataFrame for test script compatibility.
        
        Returns
        -------
        DataFrame with BACnet point names as index and test names in 'name_in_test' column
        """
        return self._point_properties_df

    def reset_device(self, object_list=None):
        """
        Reset BACnet device connection with specific object list.
        
        Parameters
        ----------
        object_list (optional)
            List of (object_type, address) tuples to poll
        """
        if object_list is None:
            # Reconnect with default discovery
            self.device = BAC0.device(
                address=self.device_address,
                device_id=self.device_id,
                network=self.bacnet,
                poll=5
            )
        else:
            # Reconnect with specific object list
            self.device = BAC0.device(
                address=self.device_address,
                device_id=self.device_id,
                network=self.bacnet,
                poll=5,
                object_list=object_list
            )
        
        # Update point properties
        self._point_properties_df = self.device.points_properties_df().T

    def set_single_point(self, point_name, value):
        """
        Set a single BACnet point value.
        
        Parameters
        ----------
        point_name
            BACnet point name
        value
            Value to write
        """
        try:
            self.device[point_name] = value
            self.update_point_value(point_name, value)
        except Exception as e:
            print(f"Error setting {point_name}: {e}")

    def set_values(self, point_value_dict):
        """
        Set multiple BACnet point values.
        
        Parameters
        ----------
        point_value_dict
            Dictionary mapping point names to values
        """
        for point_name, value in point_value_dict.items():
            try:
                self.device[point_name] = value
                self.update_point_value(point_name, value)
            except Exception as e:
                print(f"Error setting {point_name}: {e}")

    def get_current_variable_value(self, variable_name):
        """
        Read current value of a BACnet point.
        
        Parameters
        ----------
        variable_name
            BACnet point name
            
        Returns
        -------
        Current value from BACnet device
        """
        try:
            value = self.device[variable_name].value
            self.update_point_value(variable_name, value)
            return value
        except Exception as e:
            print(f"Error reading {variable_name}: {e}")
            return None
    
    def wait(self, duration):
        """
        Wait for specified real-time duration.
        
        Parameters
        ----------
        duration
            Time to wait in seconds (wall clock time)
        """
        time.sleep(duration)
    
    def get_current_time(self):
        """
        Get current wall clock time.
        
        Returns
        -------
        Current time in seconds since epoch
        """
        return time.time()

    def read_all_points(self):
        """
        Read all BACnet point values.
        
        Returns
        -------
        Dictionary mapping point names to current values
        """
        # Update from BAC0 device
        device_points = self.device.points
        
        # Convert to dictionary and update Point objects
        result = {}
        for point_name in self.points:
            if point_name in device_points:
                value = device_points[point_name]
                self.update_point_value(point_name, value)
                result[point_name] = value
        
        return result
