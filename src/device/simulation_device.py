"""
Simulation device implementation using FMU (Functional Mock-up Unit).

This module provides a device implementation for testing CDL (Control Description Language)
models compiled to FMU format using OpenModelica.
"""

from src.device.base_device import BaseDevice, Point
from src.Simcdl import Simcdl
import subprocess
import time
import numpy as np
import pandas as pd


class SimulationDevice(BaseDevice):
    """
    Device implementation for FMU-based simulation testing.
    
    This class wraps an FMU simulation and provides the standardized device interface
    for ASHRAE Guideline 36 conformance testing.
    
    Attributes
    ----------
    model_filepath : str
        Path to the .mo Modelica model file
    model_mopath : str
        Modelica path to the model (e.g., 'Buildings.Controls...')
    fmu_filepath
        Path to the compiled .fmu file
    compile_fmu
        Whether to compile FMU from .mo file
    sim
        Simulation wrapper object
    u
        Input values to be set on simulation
    parameters
        Parameter values for FMU compilation
    """
    
    def __init__(self, device_config):
        """
        Initialize simulation device.
        
        Parameters
        ----------
        device_config
            Configuration dictionary containing:
            - model_filepath: Path to .mo file
            - model_mopath: Modelica model path
            - compile_fmu: Whether to compile FMU
            - fmu_filepath: Path to FMU file
            - point_map: Path to point mapping CSV
        """
        super().__init__(device_config)
        self.init_device(device_config=device_config)

    def init_device(self, device_config):
        """
        Initialize simulation-specific resources.
        
        Loads point mapping, compiles/loads FMU, and prepares simulation.
        
        Parameters
        ----------
        device_config
            Device configuration
        """
        self.model_filepath = device_config["model_filepath"]
        self.model_mopath = device_config["model_mopath"]
        self.compile_fmu = device_config["compile_fmu"]
        self.fmu_filepath = self.model_filepath.replace('.mo', '.fmu')
        
        # Initialize point mapping
        self._load_point_mapping(device_config['point_map'])
        
        # Initialize input and parameter dictionaries
        self.u = {}
        self.parameters = {}
        
        # Initialize the FMU simulation
        self._initialize_sim()

    def _load_point_mapping(self, filepath_pointmap):
        """
        Load point mapping from CSV and populate self.points.
        
        Parameters
        ----------
        filepath_pointmap
            Path to point mapping CSV file
        """
        # Read point map CSV (skip first 3 header rows, use 'Variable Name' as index)
        df_pointmap = pd.read_csv(filepath_pointmap, header=3, index_col='Variable Name')
        
        # CDL Model Class-Instance Map
        class_map = {
            'Buildings.Controls.OBC.ASHRAE.G36.TerminalUnits.Reheat.Controller': 'con',
            'Buildings.Controls.OBC.ASHRAE.G36.ThermalZones.Setpoints': 'set',
            'Buildings.Controls.OBC.ASHRAE.G36.ThermalZones.Alarms': 'zonAla'
        }
        
        # Track output and parameter names for FMU initialization
        self.output_names = []
        self.parameter_names = []
        
        # Process each point and create Point objects
        for test_name in df_pointmap.index:
            if not isinstance(test_name, str):
                continue
                
            row = df_pointmap.loc[test_name]
            causality = row['CDL Causality']
            cdl_block = row['CDL Block']
            cdl_name = row['CDL Name']
            cdl_type = row['CDL Type']
            unit = row['Unit']
            
            # Determine CDL path based on causality
            if causality == 'Input':
                cdl_path = cdl_name
            elif causality == 'Parameter':
                cdl_path = f"{class_map.get(cdl_block, 'unknown')}.{cdl_name}"
                self.parameter_names.append(cdl_path)
            elif causality in ['Output', 'State']:
                cdl_path = f"{class_map.get(cdl_block, 'unknown')}.{cdl_name}"
                self.output_names.append(cdl_path)
            else:
                continue
            
            # Create Point object
            point = Point(
                name=cdl_path,
                name_in_test=test_name,
                unit=unit,
                point_type=cdl_type,
                causality=causality,
                metadata={
                    'cdl_block': cdl_block,
                    'cdl_name': cdl_name
                }
            )
            
            self.points[cdl_path] = point
        
        # Store original dataframe for compatibility
        self._df_pointmap = df_pointmap

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
                'Unit': point.unit,
                'CDL Type': point.point_type,
                'CDL Causality': point.causality,
                'CDL Block': point.metadata.get('cdl_block', ''),
                'CDL Name': point.metadata.get('cdl_name', ''),
                'CDL Path': point_name
            })
        
        df = pd.DataFrame(data)
        # Filter out any points without a name (device name)
        df = df.dropna(subset=['name'])
        df = df.set_index('name')
        
        return df

    def set_single_point(self, point_name, value):
        """
        Set a single point value with unit conversion.
        
        Parameters
        ----------
        point_name
            CDL path of the point
        value
            Value to set (in test units)
        """
        point = self.get_point(point_name)
        if point is None:
            print(f"Warning: Point {point_name} not found")
            return
        
        # Convert from test units to device units
        converted_value = self._unit_conversion(value, point.unit, point.point_type)
        
        # Store in appropriate dictionary
        if point.causality == 'Parameter':
            self.parameters[point_name] = converted_value
        else:
            self.u[point_name] = converted_value
        
        # Update cached value
        self.update_point_value(point_name, converted_value)

    def get_current_variable_value(self, variable_name):
        """
        Get current value of a variable from the simulation.
        
        Parameters
        ----------
        variable_name
            CDL path of the variable
            
        Returns
        -------
        Current value from FMU
        """
        if self.sim is None:
            raise RuntimeError("Simulation not initialized")
        
        _, _, current_time = self.sim.get_current_time()
        _, _, step = self.sim.get_step()
        start_time = current_time - step
        final_time = current_time
        _, _, data = self.sim.get_results([variable_name], start_time, final_time)
        
        value = data[variable_name][-1]
        self.update_point_value(variable_name, value)
        
        return value

    def convert_value_test_unit_to_device_unit(self, point_name, value):
        """
        Convert a value from test units to device (FMU) units.
        
        Parameters
        ----------
        point_name
            CDL path of the point
        value
            Value in test units
            
        Returns
        -------
        Value in device units
        """
        point = self.get_point(point_name)
        if point is None:
            return value
        
        return self._unit_conversion(value, point.unit, point.point_type)

    def get_current_time(self):
        """
        Get current simulation time.
        
        Returns
        -------
        Current FMU simulation time in seconds
        """
        if self.sim is None:
            raise RuntimeError("Simulation not initialized")
        
        _, _, current_time = self.sim.get_current_time()
        return current_time
    
    def wait(self, duration):
        """
        Advance simulation by specified duration.
        
        Steps the simulation forward by calling advance_sim() repeatedly.
        
        Parameters
        ----------
        duration
            Time to advance in seconds (simulation time)
        """
        if self.sim is None:
            raise RuntimeError("Simulation not initialized")
        
        _, _, step_size = self.sim.get_step()
        if step_size == 0:
            step_size = 10  # Default if not set
        
        # Calculate number of steps needed
        num_steps = int(duration / step_size)
        remainder = duration % step_size
        
        # Step through simulation
        for _ in range(num_steps):
            self.advance_sim()
        
        # Handle remainder if needed
        if remainder > 0:
            original_step = step_size
            self.sim.set_step(remainder)
            self.advance_sim()
            self.sim.set_step(original_step)

    def _initialize_sim(self):
        """
        Initialize the FMU simulation (private method).
        
        Compiles FMU if needed, loads it, and performs initial advancement.
        Called automatically during init_device().
        """
        # Save point properties for debugging
        self.get_point_properties().to_csv('point_properties.csv')
        
        # Compile FMU if requested
        if self.device_config["compile_fmu"]:
            self._compile_fmu(self.model_filepath, self.model_mopath, 
                            self.fmu_filepath, self.parameters)
        
        # Initialize simulation wrapper
        self.sim = Simcdl(
            self.device_config["fmu_filepath"],
            output_names=self.output_names,
            parameter_names=self.parameter_names
        )
        
        # Initial simulation setup
        self.sim.set_step(0)
        self.advance_sim()
        self.sim.set_step(10)

    def advance_sim(self):
        """
        Advance the simulation by one timestep with current inputs.
        """
        if self.sim is None:
            raise RuntimeError("Simulation not initialized")
        
        status, message, payload = self.sim.advance(self.u)

    def _compile_fmu(self, model_filepath, model_name, fmu_path, parameters):
        """
        Compile the Modelica model into an FMU using OpenModelica.
        
        Parameters
        ----------
        model_filepath
            Path to .mo model file
        model_name
            Modelica path to model
        fmu_path
            Expected path to output FMU
        parameters
            Parameter values to set during compilation
        """
        # Write .mos script for OpenModelica
        with open('compile_fmu.mos', 'w') as f:
            f.write('installPackage(Modelica, "4.0.0", exactMatch=false);\n')
            f.write('installPackage(Buildings, "11.0.0", exactMatch=true);\n')
            # Uncomment to load Buildings from local:
            # f.write('loadFile("buildings/modelica-buildings/Buildings/package.mo");\n')
            f.write(f'loadFile("{model_filepath}");\n')
            f.write('setCommandLineOptions("--fmiFlags=s:cvode");\n')
            f.write('setCommandLineOptions("--fmiFilter=internal");\n')
            
            # Set parameters
            for par_name, par_value in parameters.items():
                f.write(f'setParameterValue({model_name}, {par_name}, {par_value});\n')
                f.write('getErrorString();\n')
            
            f.write(f'buildModelFMU({model_name}, version = "2.0", fmuType="cs");\n')
            f.write('getErrorString();')
        
        # Execute OpenModelica compilation
        process = subprocess.Popen(['omc', 'compile_fmu.mos'])
        
        # Poll until completion
        while process.poll() is None:
            time.sleep(10)
            print(f'Waiting for OpenModelica to finish compiling {fmu_path}. Checking again in 10 seconds...')
        
        print(f'OpenModelica finished compiling {fmu_path}.')

    #todo: unit conversion to and from device units. do we need both directions during the test. dimensional ratio.

    def _unit_conversion(self, value, unit, par_type=None):
        """
        Convert value from test units to CDL/FMU units.
        
        Parameters
        ----------
        value
            Value to convert
        unit (optional)
            Unit of the value ('F', 'dF', 'cfm', 'percent', etc.)
        par_type (optional)
            Parameter type ('Boolean', 'Real', etc.)
            
        Returns
        -------
        Converted value in CDL units
        """
        # Handle numeric conversions
        if unit == 'cfm' and isinstance(value, (int, float, np.int64)):
            return self._cfm_to_m3_s(value)
        elif unit == 'F' and isinstance(value, (int, float, np.int64)):
            return self._F_to_K(value)
        elif unit == 'dF' and isinstance(value, (int, float, np.int64)):
            return self._dF_to_dK(value)
        elif unit == 'percent' and isinstance(value, (int, float, np.int64)):
            return self._percent_to_one(value)
        
        # Handle string/boolean conversions
        if isinstance(value, str):
            value_to_set = True
            if value.lower() in ['closed', 'present', 'on']:
                value_to_set = True
            elif value.lower() in ['open', 'absent', 'off']:
                value_to_set = False
            
            if value_to_set:
                return 'true' if par_type == 'Boolean' else 1
            else:
                return 'false' if par_type == 'Boolean' else 0
        
        return value

    @staticmethod
    def _cfm_to_m3_s(cfm):
        """Convert cubic feet per minute to cubic meters per second."""
        return cfm * 0.0283168 * (1 / 60)

    @staticmethod
    def _F_to_K(F):
        """Convert degrees Fahrenheit to Kelvin."""
        return (F - 32) * 5 / 9 + 273.15

    @staticmethod
    def _dF_to_dK(dF):
        """
        Convert temperature difference in Fahrenheit to Kelvin.
        
        Uses 70°F as reference point.
        """
        F1 = 70
        F2 = 70 + dF
        K1 = SimulationDevice._F_to_K(F1)
        K2 = SimulationDevice._F_to_K(F2)
        return K2 - K1

    @staticmethod
    def _percent_to_one(percent):
        """Convert percentage (0-100) to fraction (0-1)."""
        return percent / 100
