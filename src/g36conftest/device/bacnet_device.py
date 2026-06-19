"""
BACnet device implementation for hardware-in-the-loop testing.

This module provides a device implementation for testing physical or virtual
BACnet controllers using the BAC0 library.
"""

from .base_device import BaseDevice, Point
import BAC0
import pandas as pd
import time
from pathlib import Path
import asyncio

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

        BAC0.log_level('error')

        self.network_address = config["network_address"]
        self.device_address = config["device_address"]
        self.device_id = config["device_id"]

        # Load point mapping from CSV
        # CSV should have columns: 'Variable Name' and 'BACnet Name' (device name)
        # Can optionally include other metadata columns
        # Resolve paths relative to project root
        project_root = Path(__file__).resolve().parent.parent.parent.parent
        # Read point map CSV (skip first 3 header rows, use 'Variable Name' as index)
        df_pointmap = pd.read_csv(project_root / config["point_map"], header=3, index_col='Variable Name')
        
        # Process each point and create Point objects
        for test_name in df_pointmap.index:
            if not isinstance(test_name, str):
                continue
                
            row = df_pointmap.loc[test_name]
            bacnet_name = row['BACnet Name']
            point = Point(
                name=bacnet_name,
                name_in_test=test_name,
                unit_in_test=row['Unit'],
                unit_in_device=row['BACnet Unit'],
                point_type=row.get('type', None),
                causality=row.get('type', None),
                metadata={
                    'bacnet_address': row.get('BACnet Address', None),
                    'bacnet_object_type': row.get('BACnet Object Type', None),
                    'bacnet_object_id': row.get('BACnet Object ID', ''),
                    'bacnet_description': row.get('BACnet Description', '')
                }
            )
            
            self.points[bacnet_name] = point

    def get_point_properties(self):
        """
        Get point properties as DataFrame for test script compatibility.
        
        Returns
        -------
        DataFrame with device point names as index and test names in 'name_in_test' column
        """
        # Build DataFrame from Point objects
        data = []
        for point_name, point in self.points.items():
            data.append({
                'name': point_name,
                'name_in_test': point.name_in_test,
                'unit_in_test': point.unit_in_test,
                'BACnet Unit': point.unit_in_device,
                'point_type': point.point_type,
                'causality': point.causality,
                'address': point.metadata.get('address'),
                'object_type': point.metadata.get('object_type'),
                'description': point.metadata.get('description'),
                'priority_array': point.metadata.get('priority_array')
            })
        
        df = pd.DataFrame(data)
        # Filter out any points without a name (device name)
        df = df.dropna(subset=['name'])
        df = df.set_index('name')
        
        return df

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

        if value is not None:
            point = self.get_point(point_name)
            write_str = '{0} {1} {2} {3} {4} - {5}'.format(point.metadata['bacnet_address'],
                                                           point.metadata['bacnet_object_type'],
                                                           int(point.metadata['bacnet_object_id']),
                                                           'presentValue',
                                                           value,
                                                           1)
            async def _run():
                async with BAC0.start(ip='127.0.0.1/8') as bacnet:
                    try:
                        await bacnet._write(write_str)
                        self._cache_point_value(point_name, value)
                    except Exception as e:
                        print(f"Error setting {point_name}: {e}")

            asyncio.run(_run())

    def set_multiple_points(self, point_value_dict):
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
                self._cache_point_value(point_name, value)
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
        point = self.get_point(variable_name)
        read_str = '{0} {1}:{2} {3}'.format(point.metadata['bacnet_address'],
                                            point.metadata['bacnet_object_type'],
                                            int(point.metadata['bacnet_object_id']),
                                            'presentValue')
        async def _run():
            async with BAC0.start(ip='127.0.0.1/8') as bacnet:
                try:
                    value = await bacnet.read(read_str)
                    self._cache_point_value(variable_name, value)
                    return value
                except Exception as e:
                    print(f"Error reading {variable_name}: {e}")
                    return None
            
        return asyncio.run(_run())
    
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
                self._cache_point_value(point_name, value)
                result[point_name] = value
        
        return result
