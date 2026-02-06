# -*- coding: utf-8 -*-
"""
This code is a modified version of testcase.py from BOPTEST and is modified according to the license below,
and found at https://github.com/ibpsa/project1-boptest/blob/master/license.md.

----------------------------------------------------------------------------------------------
BOPTEST. Copyright (c) 2018-2024
International Building Performance Simulation Association (IBPSA) and
contributors.
All rights reserved.

Redistribution and use in source and binary forms, with or without modification,
are permitted provided that the following conditions are met:

* Redistributions of source code must retain the above copyright notice,
  this list of conditions and the following disclaimer.
* Redistributions in binary form must reproduce the above copyright notice,a
  this list of conditions and the following disclaimer in the documentation and/or
  other materials provided with the distribution.
* Neither the name of the copyright holder nor the names of its contributors may be used
  to endorse or promote products derived from this software
  without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE,
EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

You are under no obligation whatsoever to provide any bug fixes, patches,
or upgrades to the features, functionality or performance of the source code
("Enhancements") to anyone; however, if you choose to make your Enhancements
available either publicly, or directly to its copyright holders,
without imposing a separate written license agreement for such
Enhancements, then you hereby grant the following license: a non-exclusive,
royalty-free perpetual license to install, use, modify, prepare derivative
works, incorporate into other computer software, distribute, and sublicense
such enhancements or derivative works thereof, in binary and source code form.

Note: The license is a revised 3 clause BSD license with an ADDED paragraph
at the end that makes it easy to accept improvements.
----------------------------------------------------------------------------------------------

"""

from pyfmi import load_fmu
import numpy as np
import copy
import time
import traceback
import logging
import os
import array as a

class Simcdl(object):
    '''Class that implements the test script model.

    '''

    def __init__(self, fmupath, name=None, output_names=None, parameter_names=None, work_dir=None):
        '''Constructor.

        Parameters
        ----------
        fmupath : str
            Path to the test case fmu.
        name : str, optional
            Name of test if want to name it.
            Default is None.
        output_names : list of str, optional
            Names specific outputs of FMU.
            Default is None.
        parameter_names : list of str, optional
            Names specific parameters of FMU.
            Default is None.
        work_dir : str, optional
            Directory for log and result files.
            Default is None (current directory).

        '''

        self.name = name
        self.work_dir = work_dir
        # Set test case fmu path and check if path exists and throw execption
        self.fmupath = fmupath
        if not os.path.exists(fmupath) or not os.path.isfile(fmupath):
            raise Exception("The test case FMU cannot be found. Check TESTCASE name entered correctly.")
        # Load fmu
        self.fmu = load_fmu(self.fmupath)
        self.fmu.set_log_level(7)
        # Configure the log, log file, and console output
        name = 'copper-sv'
        fmt = '%(asctime)s UTC\t%(name)-20s%(levelname)s\t%(message)s'
        datefmt = '%m/%d/%Y %I:%M:%S %p'
        formatter = logging.Formatter(fmt,datefmt)
        
        # Set log file path
        if work_dir:
            log_path = os.path.join(work_dir, '{0}.log'.format(name))
        else:
            log_path = '{0}.log'.format(name)
        
        logging.basicConfig(filename=log_path, filemode='w', level=10, format=fmt, datefmt=datefmt)
        logger = logging.getLogger()
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)
        # Get fmu version and check is 2.0
        self.fmu_version = self.fmu.get_version()
        if self.fmu_version != '2.0':
            raise ValueError('FMU must be version 2.0.')
        # Get available control inputs and outputs
        self.input_names = list(self.fmu.get_model_variables(causality = 2).keys())
        #self.output_names = list(self.fmu.get_model_variables(causality = 3).keys())
        self.output_names = output_names
        #self.parameter_names = list(self.fmu.get_model_variables(causality = 1).keys())
        self.parameter_names = parameter_names
        # Set default communication step
        self.set_step(10)
        # Initialize simulation data arrays
        self.__initilize_data()
        # Set default fmu simulation options
        self.options = self.fmu.simulate_options()
        # Set result file location if work_dir specified
        if self.work_dir:
            # Get the FMU model name from the path
            fmu_name = os.path.splitext(os.path.basename(self.fmupath))[0]
            result_file = os.path.join(self.work_dir, f"{fmu_name}_result.mat")
            self.options['result_file_name'] = result_file
        #self.options['filter'] = self.output_names + self.input_names
        # Initialize test case
        self.initialize(0)

    def __initilize_data(self):
        '''Initializes objects for simulation data storage.

        Uses self.output_names, self.input_names, 
        and self.parameter_names to create
        self.y, self.y_store, self.u, self.u_store,
        self.p, self.p_store
        self.inputs_metadata, self.outputs_metadata, 
        and self.parameters_metadata.

        Parameters
        ----------
        None

        Returns
        -------
        None

        '''

        # Get input and output and forecast meta-data
        #self.inputs_metadata = self._get_var_metadata(self.fmu, self.input_names, inputs=True)
        #self.outputs_metadata = self._get_var_metadata(self.fmu, self.output_names)
        self.inputs_metadata = None
        self.outputs_metadata = None
        self.parameters_metadata = None
        # Outputs data
        self.y = {'time': a.array('d',[])}
        if self.output_names:
            for key in self.output_names:
                self.y[key] = a.array('d',[])
        self.y_store = copy.deepcopy(self.y)
        # Inputs data
        self.u = {'time':a.array('d',[])}
        for key in self.input_names:
            self.u[key] = a.array('d',[])
        self.u_store = copy.deepcopy(self.u)
        # Parameters data
        self.p = {'time': a.array('d',[])}
        if self.parameter_names:
            for key in self.parameter_names:
                self.p[key] = a.array('d',[])
        self.p_store = copy.deepcopy(self.p)

    def __simulation(self,start_time,end_time,input_object=None):
        '''Simulates the FMU using the pyfmi fmu.simulate function.

        Parameters
        ----------
        start_time: int
            Start time of simulation in seconds.
        final_time: int
            Final time of simulation in seconds.
        input_object: pyfmi input_object, optional
            Input object for simulation
            Default is None

        Returns
        -------
        res: pyfmi results object
            Results of the fmu simulation.

        '''

        # Set fmu initialization option
        self.options['initialize'] = self.initialize_fmu
        # Set sample rate
        step = end_time - start_time
        if step >= 30:
            self.options['ncp'] = int((end_time-start_time)/30)
        elif step == 0:
            pass
        elif (step < 30) and (step > 0):
            self.options['ncp'] = int((end_time-start_time)/step)
        # Simulate fmu
        try:
            res = self.fmu.simulate(start_time=start_time,
                                    final_time=end_time,
                                    options=self.options,
                                    input=input_object)
        except:
            return traceback.format_exc()
        # Set internal fmu initialization
        self.initialize_fmu = False

        return res

    def __get_results(self, res, store=True, store_initial=False):
        '''Get results at the end of a simulation and throughout the
        simulation period for storage. This method assigns these results
        to `self.y` and, if `store=True`, also to `self.y_store` and
        to `self.u_store`.
        This method is used by `initialize()` and `advance()` to retrieve
        results. `initialize()` does not store results whereas `advance()`
        does.

        Parameters
        ----------
        res: pyfmi results object
            Results of the fmu simulation.
        store: boolean
            Set to true if desired to store results in `self.y_store` and
            `self.u_store`
        store_initial: boolean
            Set to true if desired to store the initial point.

        '''

        # Determine if store initial point
        if store_initial:
            i = 0
        else:
            i = 1
        # Store measurements
        for key in self.y.keys():
            self.y[key] = res[key][-1]
            if store:
                # Handle initialization of cs fmu generating multiple points for the same time
                if res['time'][0] == res['time'][-1]:
                    self.y_store[key].append(res[key][-1])
                else:
                    for x in res[key][i:]:
                        self.y_store[key].append(x)
        # Store control signals (will be baseline if not activated, test controller input if activated)
        for key in self.u.keys():
            self.u[key] = res[key][-1]
            if store:
                # Handle initialization of cs fmu generating multiple points for the same time
                if res['time'][0] == res['time'][-1]:
                    self.u_store[key].append(res[key][-1])
                else:
                    for x in res[key][i:]:
                        self.u_store[key].append(x)
        # Store parameters
        for key in self.p.keys():
            self.p[key] = res[key][-1]
            if store:
                # Handle initialization of cs fmu generating multiple points for the same time
                if res['time'][0] == res['time'][-1]:
                    self.p_store[key].append(res[key][-1])
                else:
                    for x in res[key][i:]:
                        self.p_store[key].append(x)

    def advance(self, u):
        '''Advances the test case model simulation forward one step.

        Parameters
        ----------
        u : dict
            Defines the control input data to be used for the step.
            {<input_name> : int or float, or str convertable to float}

        Returns
        -------
        status: int
            Indicates whether an advance request has been completed.
            If 200, simulation advance was completed.
            If 400, invalid inputs (non-numeric) were identified.
            If 500, a simulation error occurred.
        message: str
            Includes the debug information
        payload: dict
            Contains the full state of measurement and input data at the end
            of the step.
            {<point_name> : <point_value>}
            If empty, simulation end time has been reached.
            If None, a simulation error has occurred.
        '''

        status = 200

        # Set final time
        self.final_time = self.start_time + self.step
        alert_message = ''
        # Set control inputs if they exist and are written
        # Check if possible to overwrite
        if u.keys():
            # Create input object
            u_list = []
            u_trajectory = self.start_time
            for key in u.keys():
                if (key not in self.input_names):
                    payload = None
                    status = 400
                    message = "Unexpected input variable: {}.".format(key)
                    logging.error(message)
                    return status, message, payload
                if (key != 'time' and (u[key] != None)):
                    try:
                        value = float(u[key])
                    except:
                        payload = None
                        status = 400
                        message = "Invalid value {} for input {}. Value must be a float, integer, or string able to be converted to a float, but is {}.".format(u[key], key, type(u[key]))
                        logging.error(message)
                        return status, message, payload
                    u_list.append(key)
                    u_trajectory = np.vstack((u_trajectory, value))
            input_object = (u_list, np.transpose(u_trajectory))
        # Otherwise, input object is None
        else:
            input_object = None
        # Simulate
        res = self.__simulation(self.start_time, self.final_time, input_object)
        # Process results
        if not isinstance(res, str):
            # Get result and store measurement and control inputs
            self.__get_results(res, store=True, store_initial=self.options['initialize'])
            # Raise the flag to compute time lapse
            self.tic_time = time.time()
            # Get full current state
            payload = self._get_full_current_state()
            # Write any messages
            if alert_message == '':
                message = "Advanced simulation successfully from {0}s to {1}s.".format(self.start_time, self.final_time)
            else:
                message = alert_message
            # Advance start time
            self.start_time = self.final_time
            # Log and return
            logging.info(message)

            return status, message, payload
        
        else:
            # Errors in the simulation
            status = 500
            message = "Failed to advance simulation: {}.".format(res)
            payload = res
            logging.error(message)
            
            return status, message, payload

    def initialize(self, start_time):
        '''Initialize the test simulation.

        Parameters
        ----------
        start_time: int or float
            Start time of simulation to initialize to in seconds.

        Returns
        -------
        status: int
            Indicates whether an initialization request has been completed.
            If 200, initialization was completed successfully.
            If 400, an invalid start time or warmup period (non-numeric) was identified.
            If 500, an error occurred during the initialization simulation.
        message: str
            Includes detailed debugging information.
        payload: dict
            Contains the full state of measurement and input data at the end
            of the initialization period.
            {<point_name> : <point_value>}.
            If None, an error occurred during the initialization simulation.

        '''

        status = 200
        payload = None
        # Reset fmu
        self.fmu.reset()
        # Reset simulation data storage
        self.__initilize_data()
        # Check if the inputs are valid
        try:
            start_time = float(start_time)
        except:
            payload = None
            status = 400
            message = "Invalid value {} for parameter start_time. Value must be a float, integer, or string able to be converted to a float, but is {}.".format(start_time, type(start_time))
            logging.error(message)
            return status, message, payload
        if start_time < 0:
            payload = None
            status = 400
            message = "Invalid value {} for parameter start_time. Value must not be negative.".format(start_time)
            logging.error(message)
            return status, message, payload
        # Record initial testing time
        self.initial_time = start_time
        # Set fmu intitialization
        self.initialize_fmu = True
        self.start_time = start_time
        # # Initialize fmu at start_time
        # res = self.__simulation(start_time, start_time)
        # # Process result
        # if not isinstance(res, str):
        #     # Get result
        #     self.__get_results(res, store=True, store_initial=True)
        #     # Set internal start time to start_time
        #     self.start_time = start_time
        #     # Set scenario end flag to false
        #     self.scenario_end = False
        #     # Get full current state
        #     payload = self._get_full_current_state()
        #     message = "Test simulation initialized successfully to {0}s.".format(self.start_time)
        #     logging.info(message)

        #     return status, message, payload

        # else:
        #     payload = None
        #     status = 500
        #     message = "Failed to initialize test simulation: {}.".format(res)
        #     logging.error(message)

        #     return status, message, payload

        return status, None, payload

    def get_step(self):
        '''Returns the current control step in seconds.

        Parameters
        ----------
        None

        Returns
        -------
        status: int
            Indicates whether a request for querying the control step has been completed.
            If 200, the step was successfully queried.
            If 500, an internal error occurred.
        message: str
            Includes detailed debugging information.
        payload: int
            The current control step.
            None if error during query.

        '''

        status = 200
        message = "Queried the control step successfully."
        payload = None
        try:
            payload = self.step
            logging.info(message)
        except:
            status = 500
            message = "Failed to query the simulation step: {}".format(traceback.format_exc())
            logging.error(message)

        return status, message, payload

    def set_step(self, step):
        '''Sets the control step in seconds.

        Parameters
        ----------
        step: int or float
            Control step in seconds.

        Returns
        -------
        status: int
            Indicates whether a request for setting the control step has been completed.
            If 200, the step was successfully set.
            If 400, an invalid simulation step (non-numeric) was identified.
            If 500, an internal error occurred.
        message: str
            Includes detailed debugging information.
        payload:
            None

        '''

        status = 200
        message = "Control step set successfully."
        payload = None
        try:
            step = float(step)
        except:
            payload = None
            status = 400
            message = "Invalid value {} for parameter step. Value must be a float, integer, or string able to be converted to a float, but is {}.".format(step, type(step))
            logging.error(message)
            return status, message, payload
        if step < 0:
            payload = None
            status = 400
            message = "Invalid value {} for parameter step. Value must not be negative.".format(step)
            logging.error(message)
            return status, message, payload
        try:
            self.step = step
        except:
            payload = None
            status = 500
            message = "Failed to set the control step: {}".format(traceback.format_exc())
            logging.error(message)
            return status, message, payload
        payload={'step':self.step}
        logging.info(message)

        return status, message, payload

    def get_inputs(self):
        '''Returns a dictionary of control inputs and their meta-data.

        Parameters
        ----------
        None

        Returns
        -------
        status: int
            Indicates whether a request for querying the inputs has been completed.
            If 200, the inputs were successfully queried.
            If 500, an internal error occurred.
        message: str
            Includes detailed debugging information.
        payload: dict
            Dictionary of control inputs and their meta-data.
            Returns None if error in getting inputs and meta-data.

        '''

        status = 200
        message = "Queried the inputs successfully."
        payload = None
        try:
            payload = self.inputs_metadata
            logging.info(message)
        except:
            status = 500
            message = "Failed to query the input list: {}".format(traceback.format_exc())
            logging.error(message)

        return status, message, payload

    def get_measurements(self):
        '''Returns a dictionary of measurements and their meta-data.

        Parameters
        ----------
        None

        Returns
        -------
        status: int
            Indicates whether a request for querying the outputs has been completed.
            If 200, the outputs were successfully queried.
            If 500, an internal error occurred.
        message: str
            Includes detailed debugging information.
        payload : dict
            Dictionary of measurements and their meta-data.
            Returns None if error in getting measurements and meta-data.

        '''

        status = 200
        message = "Queried the measurements successfully."
        payload = None
        try:
            payload = self.outputs_metadata
            logging.info(message)
        except:
            status = 500
            message = "Failed to query the measurement list: {}".format(traceback.format_exc())
            logging.error(message)

        return status, message, payload

    def get_results(self, point_names, start_time, final_time):
        '''Returns measurement and control input trajectories.

        Parameters
        ----------
        point_names: list
            Variable names.
        start_time : int or float
            Start time of data to return in seconds.
        final_time : int or float
            Start time of data to return in seconds.

        Returns
        -------
        status: int
            Indicates whether a request for querying the results has been completed.
            If 200, the results were successfully queried.
            If 400, invalid start time and/or invalid final time (non-numeric) were identified.
            If 500, an internal error occured.
        message: str
            Includes detailed debugging information.
        payload : dict
            Dictionary of variable trajectories with time as lists.
            {'time':[<time_data>],
             'var':[<var_data>]
            }
            Returns None if no variable can be found or a simulation error occurs.

        '''

        status = 200
        try:
            start_time = float(start_time)
        except:
            payload = None
            status = 400
            message = "Invalid value {} for parameter start_time. Value must be a float, integer, or string able to be converted to a float, but is {}.".format(start_time, type(start_time))
            logging.error(message)
            return status, message, payload
        try:
            final_time = float(final_time)
        except:
            payload = None
            status = 400
            message = "Invalid value {} for parameter final_time. Value must be a float, integer, or string able to be converted to a float, but is {}.".format(final_time, type(final_time))
            logging.error(message)
            return status, message, payload
        if 'time' in point_names:
            message = 'The point "time" was included in the parameter point_names unnecessarily.'
            logging.warning(message)
            point_names.remove('time')  
        payload = {}
        try:
            for point_name in point_names:
                # Get correct points
                if point_name in self.y_store.keys():
                    payload[point_name] = self.y_store[point_name]
                elif point_name in self.u_store.keys():
                    payload[point_name] = self.u_store[point_name]
                elif point_name in self.p_store.keys():
                    payload[point_name] = self.p_store[point_name]
                else:
                    status = 400
                    message = "Invalid point name {} in parameter point_names.  Check lists of available inputs, measurements, and parameters.".format(point_name)
                    logging.error(message)
                    return status, message, None
            if any(item in point_names for item in self.y_store.keys()):
                payload['time'] = self.y_store['time']
            elif any(item in point_names for item in self.u_store.keys()):
                payload['time'] = self.u_store['time']
            elif any(item in point_names for item in self.p_store.keys()):
                payload['time'] = self.p_store['time']
            # Get correct time
            if payload and 'time' in payload:
                # Find min and max time
                min_t = min(payload['time'])
                max_t = max(payload['time'])
                # If min time is before start time
                if min_t < start_time:
                    # Check if start time in time array
                    if start_time in payload['time']:
                        t1 = start_time
                    # Otherwise, find first time in time array after start time
                    else:
                        np_t = np.array(payload['time'])
                        t1 = np_t[np_t>=start_time][0]
                # Otherwise, first time is min time
                else:
                    t1 = min_t
                # If max time is after final time
                if max_t > final_time:
                    # Check if final time in time array
                    if final_time in payload['time']:
                        t2 = final_time
                    # Otherwise, find last time in time array before final time
                    else:
                        np_t = np.array(payload['time'])
                        t2 = np_t[np_t<=final_time][-1]
                # Otherwise, last time is max time
                else:
                    t2 = max_t
                # Use found first and last time to find corresponding indecies
                i1 = payload['time'].index(t1)
                i2 = payload['time'].index(t2)+1
                for key in (point_names +['time']):
                    payload[key] = payload[key][i1:i2]
        except:
            status = 500
            message = "Failed to query simulation results: {}".format(traceback.format_exc())
            logging.error(message)
            return status, message, None

        if not isinstance(payload, (list, type(None))):
            for key in payload:
                payload[key] = payload[key].tolist()

        message = "Queried results data successfully for point names {}.".format(point_names)
        logging.info(message)
        return status, message, payload
    
    def save_fmu_state(self, filepath='fmu_state.bin'):
        '''Saves the state of the FMU to a file.
        
        Parameters
        ----------
        filepath: str, optional
            Filepath to save state to (must end in .bin).
            Default is "fmu_state.bin".

        Returns
        -------
        status: int
            Indicate whether a request to save fmu state has been successfully completed.
            If 200, the state was successfully saved.
            If 500, an internal error occurred.
        message: str
            Includes detailed debugging information.
        payload : str
            Filepath of saved state.

        '''

        status = 200
        try:
            state = self.fmu.get_fmu_state()
            with open(filepath, "wb") as f:
                f.write(state)
            message = None
            payload = filepath
        except Exception as e:
            status = 500
            message = 'An internal error occured. Could not save state. Error message is: {0}'.format(e)
            payload = None

        return status, message, payload
    
    def load_fmu_state(self, filepath='fmu_state.bin'):
        '''Sets the state of the FMU from a file saved within the class.
        
        Parameters
        ----------
        filepath : str, optional
            Filepath to load state from (must end in .bin).
            Default is "fmu_state.bin".

        Returns
        -------
        status: int
            Indicate whether a request to save fmu state has been successfully completed.
            If 200, the state was successfully saved.
            If 500, an internal error occurred.
        message: str
            Includes detailed debugging information
        payload : str
            True if successful. False otherwise.

        '''

        status = 200
        try:
            with open(filepath, "rb") as f:
                state = f.read()
            self.fmu.set_fmu_state(state)
            message = None
            payload = True
        except Exception as e:
            status = 500
            message = 'An internal error occured. Could not set state. Error message is: {0}'.format(e)
            payload = None

        return status, message, payload

    def get_name(self):
        '''Returns the name of the test case fmu.

        Parameters
        ----------
        None

        Returns
        -------
        status: int
            Indicate whether a request for querying the name of the test case has been successfully completed.
            If 200, the name was successfully queried.
            If 500, an internal error occurred.
        message: str
            Includes detailed debugging information
        payload :  dict
            Name of test case as {'name': <str>}

        '''

        status = 200
        message = "Queried the name of the test case successfully."
        payload = {'name': self.name}
        logging.info(message)

        return status, message, payload

    def _get_var_metadata(self, fmu, var_list, inputs=False):
        '''Build a dictionary of variables and their metadata.

        Parameters
        ----------
        fmu : pyfmi fmu object
            FMU from which to get variable metadata
        var_list : list of str
            List of variable names

        Returns
        -------
        var_metadata : dict
            Dictionary of variable names as keys and metadata as fields.
            {<var_name_str> :
                "Unit" : str,
                "Description" : str,
                "Minimum" : float,
                "Maximum" : float
            }

        '''

        # Inititalize
        var_metadata = dict()
        # Get metadata
        for var in var_list:
            # Units
            if var == 'time':
                unit = 's'
                description = 'Time of simulation'
                mini = None
                maxi = None
            else:
                unit = fmu.get_variable_unit(var)
                description = fmu.get_variable_description(var)
                if inputs:
                    try:
                        mini = fmu.get_variable_min(var)
                        maxi = fmu.get_variable_max(var)
                    except:
                        mini = None
                        maxi = None
                else:
                    mini = None
                    maxi = None
            var_metadata[var] = {'Unit':unit,
                                 'Description':description,
                                 'Minimum':mini,
                                 'Maximum':maxi}

        return var_metadata

    def _get_full_current_state(self):
        '''Combines the self.y and self.u dictionaries into one.

        Returns
        -------
        z: dict
            Combination of self.y and self.u dictionaries.

        '''

        z = self.y.copy()
        z.update(self.u)

        return z
    
    def get_current_time(self):
        '''Returns current simulation time of FMU.

        Returns
        -------
        current_time: float
            Current time of FMU simulation.

        Returns
        -------
        status: int
            Indicates whether a request for querying the control step has been completed.
            If 200, the step was successfully queried.
            If 500, an internal error occurred.
        message: str
            Includes detailed debugging information.
        payload: int
            The current time of the FMU simulation.
            None if error during query.
        
        '''

        status = 200
        payload = self.start_time
        message = "Queried the current simulation time successfully."
        logging.info(message)

        return status, message, payload