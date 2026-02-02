"""
Abstract base class for test devices.

This module provides a common interface that all device implementations follow,
ensuring consistent interaction patterns between test scripts and different device types.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class Point:
    """
    Data structure to hold point metadata and current value.
    
    This provides a consistent way to manage point information across different
    device types (simulation and BACnet).
    
    Attributes
    ----------
    name
        Device-specific point name (e.g., CDL path for simulation, BACnet name for hardware)
    name_in_test
        Human-readable name used in test scripts
    value (optional)
        Current value of the point
    unit (optional)
        Engineering unit (e.g., 'F', 'cfm', 'percent')
    point_type (optional)
        Type information (e.g., 'Boolean', 'Real', 'Integer')
    causality (optional)
        For simulation: 'Input', 'Output', 'Parameter', 'State'
        For BACnet: 'analogInput', 'analogOutput', 'binaryInput', etc.
    metadata (optional)
        Additional device-specific metadata
    """
    name: str
    name_in_test: str
    value: any = None
    unit: str = None
    point_type: str = None
    causality: str = None
    metadata: dict = field(default_factory=dict)
    
    def __repr__(self):
        return f"Point(name='{self.name}', name_in_test='{self.name_in_test}', value={self.value})"


class BaseDevice(ABC):
    """
    Abstract base class defining the interface for all device implementations.
    
    This class establishes the contract that both SimulationDevice and BacnetDevice
    must implement, ensuring Test.py can interact with any device type consistently.
    
    Attributes
    ----------
    device_type
        Type identifier ('simulation' or 'bacnet')
    device_config
        Configuration dictionary from config.yaml
    points
        Dictionary mapping device-specific point names to Point objects
    """
    
    def __init__(self, device_config):
        """
        Initialize the device with configuration.
        
        Parameters
        ----------
        device_config
            Device configuration from config.yaml
        """
        self.device_config = device_config
        self.device_type = device_config.get('type', 'unknown')
        self.points = {}
        
    @abstractmethod
    def init_device(self, config):
        """
        Initialize device-specific resources and connections.
        
        This method is called during __init__ and should set up all necessary
        resources (e.g., FMU loading, BACnet connections, point mapping).
        
        Parameters
        ----------
        config
            Device configuration dictionary
        """
        pass
    
    @abstractmethod
    def get_point_properties(self):
        """
        Get point properties as a DataFrame for compatibility with existing test code.
        
        Returns
        -------
        pd.DataFrame
            DataFrame with index as device point names and columns including:
            - 'name_in_test': Test script variable name
            - Additional device-specific columns
        """
        pass
    
    @abstractmethod
    def set_single_point(self, point_name, value):
        """
        Set the value of a single point on the device.
        
        Implementations should:
        1. Convert value to device units if needed
        2. Send the value to the device (FMU/BACnet/etc.)
        3. Call self._cache_point_value() to cache the new value
        
        Parameters
        ----------
        point_name
            Device-specific point name (key in self.points dict)
        value
            Value to set (will be converted to appropriate units/types internally)
        """
        pass
    
    @abstractmethod
    def get_current_variable_value(self, variable_name):
        """
        Read the current value of a variable from the device.
        
        Implementations should:
        1. Query the device for the current value
        2. Call self._cache_point_value() to cache the value
        3. Return the value
        
        Parameters
        ----------
        variable_name
            Device-specific variable name
            
        Returns
        -------
        Current value of the variable in device units
        """
        pass
    
    @abstractmethod
    def wait(self, duration):
        """
        Wait or advance time by specified duration.
        
        For simulation devices: steps simulation forward
        For BACnet devices: sleeps for real time
        
        Parameters
        ----------
        duration
            Time to wait in seconds
        """
        pass
    
    @abstractmethod
    def get_current_time(self):
        """
        Get current time reference.
        
        For simulation devices: returns simulation time
        For BACnet devices: returns wall clock time
        
        Returns
        -------
        Current time in seconds
        """
        pass
    
    def get_type(self):
        """
        Get the device type identifier.
        
        Returns
        -------
        Device type ('simulation' or 'bacnet')
        """
        return self.device_type
    
    def get_point(self, point_name):
        """
        Get Point object by device-specific name.
        
        Parameters
        ----------
        point_name
            Device-specific point name
            
        Returns
        -------
        Point object if found, None otherwise
        """
        return self.points.get(point_name)
    
    def get_point_by_test_name(self, test_name):
        """
        Get Point object by test script name.
        
        Parameters
        ----------
        test_name
            Test script variable name
            
        Returns
        -------
        Point object if found, None otherwise
        """
        for point in self.points.values():
            if point.name_in_test == test_name:
                return point
        return None
    
    def _cache_point_value(self, point_name, value):
        """
        Update the cached value in a Point object
        
        The intent of this internal method is to keep the Point.value attribute
        in sync with the actual device state. It should be called in conjunction with
        the set_single_point() and get_current_variable_value() methods.

        The idea is that the current value of the point is cached to limit device I/O 
        operations and provide quick access to the last known value if being used 
        multiple times in the same test step.
        
        Parameters
        ----------
        point_name
            Device-specific point name
        value
            New value to cache
        """
        if point_name in self.points:
            self.points[point_name].value = value
    
    # Optional methods with default implementations
    
    def reset_device(self, object_list=None):
        """
        Reset device to initial state (optional, device-specific).
        
        Parameters
        ----------
        object_list (optional)
            Device-specific reset parameters
        """
        pass
    
    def read_all_points(self):
        """
        Read all point values and update internal cache.
        
        Returns
        -------
        Dictionary mapping point names to current values
        """
        result = {}
        for point_name in self.points:
            result[point_name] = self.get_current_variable_value(point_name)
        return result
    
    def set_values(self, point_value_dict):
        """
        Set multiple point values.
        
        Default implementation calls set_single_point for each item.
        Can be overridden for batch operations.
        
        Parameters
        ----------
        point_value_dict
            Dictionary mapping point names to values
        """
        for point_name, value in point_value_dict.items():
            try:
                self.set_single_point(point_name, value)
            except Exception as e:
                print(f"Error setting {point_name}: {e}")
