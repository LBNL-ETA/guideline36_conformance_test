from src.Simcdl import Simcdl
import subprocess
import time
import numpy as np
import pandas as pd

class DeviceSimcdl:
    def __init__(self, device_config):
        self.type = 'simcdl'
        self.device_config = device_config
        self.init_device(device_config=self.device_config)

    def init_device(self, device_config):
        self.model_filepath = device_config["model_filepath"]
        self.model_mopath = device_config["model_mopath"]
        self.compile_fmu = device_config["compile_fmu"]
        self.fmu_filepath = self.model_filepath.replace('.mo', '.fmu')
        if self.compile_fmu:
            self.compile = True
        else:
            self.compile = False
        self.points = Points(device_config['point_map'])
        self.u = dict()
        self.parameters = dict()

    def get_point_properties(self):
        df_pointmap = self.points.get_pointmap().reset_index()
        point_properties = df_pointmap.rename(columns={"Variable Name": "name_in_test", "CDL Path": "name"})
        # Drop any points that don't have 'name'
        point_properties = point_properties.dropna(subset=['name'])
        # Make index as name
        point_properties = point_properties.set_index('name')
        return point_properties

    def reset_device(self, object_list):
        pass

    def read_all_points(self):
        self.points = self.device.points

    def set_values(self, point_value_dict):
        pass

    def set_single_point(self, point_name, value):
        point_properties = self.get_point_properties()
        unit = point_properties.loc[point_name,'Unit']
        cdl_type = point_properties.loc[point_name,'CDL Type']
        if point_properties.loc[point_name,'CDL Causality'] == 'Parameter':
            value = self.points.unit_conversion(value, unit, cdl_type)
            self.parameters[point_name] = value
        else:
            value = self.points.unit_conversion(value, unit)
            self.u[point_name] = value

    def get_type(self):
        return self.type

    def get_current_variable_value(self, var):
        _,_,current_time = self.sim.get_current_time()
        _,_,step = self.sim.get_step()
        start_time = current_time - step
        final_time = current_time
        _,_,data = self.sim.get_results([var], start_time, final_time)

        return data[var][-1]
    
    def convert_value_test_unit_to_device_unit(self, point_name, value):
        point_properties = self.get_point_properties()
        unit = point_properties.loc[point_name,'Unit']
        cdl_type = point_properties.loc[point_name,'CDL Type']
        if point_properties.loc[point_name,'CDL Causality'] == 'Parameter':
            value = self.points.unit_conversion(value, unit, cdl_type)
        else:
            value = self.points.unit_conversion(value, unit)

        return value

    def get_current_time(self):
        '''Returns current simulation time of FMU.

        Returns
        -------
        current_time: float
            Current time of FMU simulation.
        
        '''

        _,_,current_time = self.sim.get_current_time()

        return current_time
    
    def initialize_sim(self):
        # Get point properties
        self.get_point_properties().to_csv('point_properties.csv')
        # Compile FMU
        if self.device_config["compile_fmu"]:
            self._compile_fmu(self.model_filepath, self.model_mopath, self.fmu_filepath, self.parameters)
        self.sim = Simcdl(self.device_config["fmu_filepath"], 
                          output_names=self.points.output_names,
                          parameter_names=self.points.parameter_names)
        self.sim.set_step(0)
        self.advance_sim()
        self.sim.set_step(10)

    def _compile_fmu(self, model_filepath, model_name, fmu_path, parameters):
        '''
        Compiles the test model into an FMU using OpenModelica.

        Parameters
        ----------
        model_filepath: str
            Path to .mo model
        model_name: str
            Modelica path to model
        fmu_path: str
            Expected path to FMU. For print/log information only.
        parameters: dict
            Parameter values.
        
        Returns
        -------
        None

        '''
        
        # Write .mos script
        with open('compile_fmu.mos', 'w') as f:
            f.write('installPackage(Modelica, \"4.0.0\", exactMatch=false);\n')
            f.write('installPackage(Buildings, \"11.0.0\", exactMatch=true);\n')
            #f.write('loadFile("buildings/modelica-buildings/Buildings/package.mo");\n') \\ Uncomment to load Buildings from local
            f.write('loadFile("{0}");\n'.format(model_filepath))
            f.write('setCommandLineOptions("--fmiFlags=s:cvode");\n')
            f.write('setCommandLineOptions("--fmiFilter=internal");\n')  
            for par in parameters.keys():
                f.write('setParameterValue({0}, {1}, {2});\n'.format(model_name, par, parameters[par]))  
                f.write('getErrorString();\n')
            f.write('buildModelFMU({0}, version = "2.0", fmuType="cs");\n'.format(model_name))
            f.write('getErrorString();')
        # Call openmodelica to run .mos script
        process = subprocess.Popen(['omc','compile_fmu.mos'])
        # Poll status
        while process.poll() == None:
            time.sleep(10)
            print('Waiting for OpenModelica to finish compiling {0}.  Checking again in 10 seconds...'.format(fmu_path))
        print('OpenModelica finished compiling {0}.'.format(fmu_path))

    def advance_sim(self):
        status, message, payload = self.sim.advance(self.u)

        
class Points(object):
    '''
    '''

    def __init__(self, filepath_pointmap):
        # Initialize point map
        self.df_pointmap = pd.read_csv(filepath_pointmap, header=3, index_col='Variable Name')
        # Set CDL Model Class-Instance Map
        self.class_map = {'Buildings.Controls.OBC.ASHRAE.G36.TerminalUnits.Reheat.Controller': 'con',
                          'Buildings.Controls.OBC.ASHRAE.G36.ThermalZones.Setpoints': 'set',
                          'Buildings.Controls.OBC.ASHRAE.G36.ThermalZones.Alarms': 'zonAla'}
        # Add point paths
        self.output_names = []
        self.parameter_names = []
        for point in self.df_pointmap.index:
            if type(point) == str:
                causality = self.df_pointmap.loc[point]['CDL Causality']
                # Input .mos files
                if causality == 'Input':
                    input_name = self.df_pointmap.loc[point]['CDL Name']
                    self.df_pointmap.loc[point,'CDL Path'] = input_name
                # Parameter dictionary
                elif causality == 'Parameter':
                    par_name = self.class_map[self.df_pointmap.loc[point]['CDL Block']] + '.' + \
                               self.df_pointmap.loc[point]['CDL Name']
                    self.df_pointmap.loc[point,'CDL Path'] = par_name
                    self.parameter_names.append(par_name)
                # Output points
                elif (causality == 'Output') or (causality == 'State'):
                    cdl_block_name = self.df_pointmap.loc[point]['CDL Block']
                    try:
                        if np.isnan(cdl_block_name):
                            output_name = self.df_pointmap.loc[point]['CDL Name']
                        else:
                            output_name = self.class_map[cdl_block_name] + '.' + \
                                        self.df_pointmap.loc[point]['CDL Name']
                    except TypeError:
                        output_name = self.class_map[cdl_block_name] + '.' + \
                                    self.df_pointmap.loc[point]['CDL Name']                        
                    self.df_pointmap.loc[point,'CDL Path'] = output_name
                    self.output_names.append(output_name)

    def get_pointmap(self):
        '''Returns pointmap dataframe.
        
        Returns
        -------
        df_pointmap: pandas df
            Dataframe adjusted with added FMU point paths column

        '''

        return self.df_pointmap

    def cfm_to_m3_s(self, cfm):
        '''Convert cfm to m3/s.
        
        Parameters
        ----------
        cfm : float
            Flow rate in cubic feet per minute.
        
        Returns
        -------
        y : float
            Flow rate in meters cubed per second.
        
        '''

        y = cfm * 0.0283168 * (1 / 60)

        return y

    def F_to_K(self, F):
        '''Convert temperature deg F to K.
        
        Parameters
        ----------
        F : float
            Temperature in deg F.
        
        Returns
        -------
        y : float
            Temperature in K.
        
        '''

        y = (F - 32) * 5 / 9 + 273.15

        return y

    def dF_to_dK(self, dF):
        '''Convert temperature difference in deg F to K with reference as 70 F.
        
        Parameters
        ----------
        dF : float
            Temperature difference in deg F.
        
        Returns
        -------
        y : float
            Temperature difference in K.
        
        '''

        F1 = 70
        F2 = 70 + dF
        K1 = self.F_to_K(F1)
        K2 = self.F_to_K(F2)
        y = K2 - K1

        return y
    
    def percent_to_one(self, percent):
        '''Convert a percentage to a value between 0 and 1.
        
        Parameters
        ----------
        percent : float
            Percent in 0 and 100.
        
        Returns
        -------
        y : float
            Value between 0 and 1.
        
        '''

        y = percent/100

        return y

    def unit_conversion(self, value, unit, par_type=None):
        '''Convert value with unit to corresponding CDL unit.
        
        Parameters
        ----------
        value : float
            Value to convert.
        unit : str
            Unit of value.
        par_type : str, optional
            Type of vparameter ariable (e.g. 'Boolean', or 'Real')
            If None, treat as numeric.
            Default is None.
        Returns
        -------
        y : float
            Value in CDL unit.

        '''

        # Treat units
        if unit == 'cfm' and isinstance(value, (int, float, np.int64)):
            y = self.cfm_to_m3_s(value)
        elif unit == 'F' and isinstance(value, (int, float, np.int64)):
            y = self.F_to_K(value)
        elif unit == 'dF' and isinstance(value, (int, float, np.int64)):
            y = self.dF_to_dK(value)
        elif unit == 'percent' and isinstance(value, (int, float, np.int64)):
            y = self.percent_to_one(value)
        else:            
            y = value

        # Treat booleans and enumerations
        value_to_set = True
        if isinstance(value, str):
            if value.lower() in ['closed', 'present', 'on']:
                value_to_set = True
            elif value.lower() in ['open', 'absent', 'off']:
                value_to_set = False
            if value_to_set == True:
                if par_type=='Boolean':
                    y = 'true'
                else:
                    y = 1
            if value_to_set == False:
                if par_type=='Boolean':
                    y = 'false'
                else:
                    y = 0

        return y