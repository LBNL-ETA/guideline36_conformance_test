import pandas as pd
import re
from pathlib import Path
import math
from .utils.config_loader import load_config
from .conversion.units import convert
from .conversion.state import convert as _
_convert_state = staticmethod(_); del _


class Test:
    def __init__(
        self,
        global_config_path: str = None,
        test_config_path: str = None,
        device_init: bool = True
    ):
        """
        Initialize Test with configuration.
        
        Parameters
        ----------
        global_config_path : str, optional
            Path to global config file. Can be absolute or relative to project root.
            If None, defaults to config/global_config.yaml
        test_config_path : str, optional
            Path to test-specific config file. Can be absolute or relative to project root.
            If None, uses test_type from global config to determine path
        device_init : bool, optional
            Whether to initialize device. Default is True.
        """
        # Set paths relative to this file's location
        self.SRC_FOLDER = Path(__file__).resolve().parent.parent
        self.PROJECT_ROOT = self.SRC_FOLDER.parent
        
        # Convert string paths to Path objects if provided
        global_config_path_obj = Path(global_config_path) if global_config_path else None
        test_config_path_obj = Path(test_config_path) if test_config_path else None
        
        # Load configuration from global and test-specific files
        self.config = load_config(
            self.PROJECT_ROOT,
            global_config_path=global_config_path_obj,
            test_config_path=test_config_path_obj
        )
        
        # Extract config sections
        self.test_type = self.config['test_type']
        self.device_type = self.config['device_type']
        self.test_base_dir = self.PROJECT_ROOT / "conformance_tests" / self.test_type
        self.test_scripts_dir = self.test_base_dir / "test_scripts"
        self.results_dir = self.test_base_dir / "results"

        # Initiate Test Script
        self.test_config = self.config["test"]
        self.test_file = self.test_config["test_script"]
        self.input_points_header = self.test_config.get("input_points_header", "BACnet Inputs")
        self.conditions_header = self.test_config.get("conditions_header", "Conditions for Evaluation of Test Step")
        self.output_points_header = self.test_config.get("output_points_header", "BACnet Expected Outputs")
        # Initiate Device
        self.device_config = self.config["device"]
        device_type = self.device_config['type']
        
        # Import and instantiate appropriate device class
        if device_type == 'simulation':
            from .device.simulation_device import SimulationDevice
            self.controller = SimulationDevice(device_config=self.device_config)
        elif device_type == 'bacnet':
            from .device.bacnet_device import BacnetDevice
            self.controller = BacnetDevice(device_config=self.device_config)
        else:
            raise ValueError(f'In configuration file, device type "{device_type}" is unknown. '
                           f'Valid types: "simulation", "bacnet"')
        # Initiate Test Sequence with Test and Device
        self.point_properties = self.controller.get_point_properties()
        self.init_test_sequence(filename=self.test_file, ip_header=self.input_points_header, cond_header=self.conditions_header, op_header=self.output_points_header, point_prop=self.point_properties)

    def init_test_sequence(self, filename, ip_header, cond_header, op_header, point_prop):
        self.test_df = pd.read_excel(self.test_scripts_dir / filename, index_col=0, header=None)
        self.step_labels = self._extract_step_labels(df = self.test_df)
        self.ip = self.format_excel_df(df=self.test_df.loc[ip_header:cond_header].iloc[1:-1], point_prop=point_prop)
        self.cond = self.format_excel_df(df=self.test_df.loc[cond_header:op_header].iloc[1:-1], is_cond_df=True, point_prop=point_prop)
        self.op = self.format_excel_df(df=self.test_df.loc[op_header:].iloc[1:], point_prop=point_prop)
        self.acceptable_op_bounds = self.op.loc["acceptable_bounds"]

        self.current_step = None
        self.step_outputs = {}
    
    def _extract_step_labels(self, df):
        """Search the DataFrame for 'Test Block' and 'Test Step' cell values,
        then combine them into a list of labels like 'AA3', 'AA4', etc that are indexed by test step column.

        The extraction of a label from the list for a corresponding test step column is done in self._get_step_label().
        
        Parameters
        ----------
        df: DataFrame
            Pandas DataFrame used to create labels.

        Returns
        -------
        labels: list of str
            List of labels as strings.
            If "Test Block" and "Test Step" rows in DataFrame, label strings include block and step as "{block}{step}".
            If only "Test Step" row in DataFrame, level strings include just step as "step{step}".
            Otherwise, an empty list is returned.
            
        """

        test_block_vals = None
        test_step_vals = None

        for idx in df.index:
            row = df.loc[idx]
            # Handle duplicate index returning a DataFrame instead of Series
            if isinstance(row, pd.DataFrame):
                row = row.iloc[0]
            row_list = row.tolist()
            row_str_list = [str(v) for v in row_list if pd.notna(v)]

            if "Test Block" in row_str_list:
                # Everything after "Test Block" in that row are the block names
                pos = next(i for i, v in enumerate(row_list) if str(v) == "Test Block")
                test_block_vals = [v for v in row_list[pos + 1:] if pd.notna(v)]

            if "Test Step" in row_str_list:
                # Everything after "Test Step" in that row are the step names
                pos = next(i for i, v in enumerate(row_list) if str(v) == "Test Step")
                test_step_vals = [v for v in row_list[pos + 1:] if pd.notna(v)]

        # Also check if the index itself contains these labels
        if test_block_vals is None and "Test Block" in df.index:
            test_block_vals = df.loc["Test Block"].dropna().tolist()
        if test_step_vals is None and "Test Step" in df.index:
            test_step_vals = df.loc["Test Step"].dropna().tolist()

        # Combine into labels
        if test_block_vals and test_step_vals:
            labels = []
            for b, s in zip(test_block_vals, test_step_vals):
                s_str = str(int(s)) if isinstance(s, float) else str(s)
                labels.append(f"{b}{s_str}")
            return labels
        elif test_step_vals:
            return [f"step{int(s) if isinstance(s, float) else s}" for s in test_step_vals]
        else:
            return []
    
    def _get_step_label(self, step_num):
        """Helper to convert test step integer to the xlsx label based on Test Block and Test Step.

        The list of labels is created by self._extract_step_labels().

        Parameters
        ----------
        step_num: int
            Test step integer to convert to corresponding label.

        Returns
        -------
        label: str
            Label corresonding to test step integer.
        
        """

        if self.step_labels and (step_num - 1) < len(self.step_labels):
            return self.step_labels[step_num - 1]
        return f"step{step_num}"

    
    def format_excel_df(self, df, is_cond_df=False, point_prop=None):
        df_new = df.reset_index().drop([0], axis=1)
        cols = ['step%d' % i for i in range(len(df_new.columns) - 2)]
        cols = ['variable_name', 'acceptable_bounds'] + cols
        df_new.columns = cols
        if not is_cond_df:
            df_new['variable_name'] = df_new['variable_name'].map(lambda x: point_prop.loc[point_prop['name_in_test'] == x].index.values)
            # Drop any rows that don't have 'variable_name'
            for i in df_new.index.values:
                if not len(df_new.loc[i,'variable_name']):
                    df_new.drop(index=i, inplace=True)
                else:
                    df_new.loc[i,'variable_name'] = df_new.loc[i,'variable_name'][0]
            return df_new.set_index('variable_name').T
        else:
            df_new = df_new.set_index('variable_name').T
            df_new.loc[pd.notna(df_new['VariableName']), 'VariableName'] = df_new.loc[pd.notna(df_new['VariableName']), 'VariableName'].map(lambda x: point_prop.loc[point_prop["name_in_test"] == x].index.values)
            time_vals = df_new.loc[df_new['ClockTime'].notnull()].index
            cond_time = pd.to_datetime(df_new.loc[time_vals, 'ClockTime'], format="%H:%M:%S")
            df_new.loc[time_vals, 'ClockTime'] = cond_time.dt.hour * 3600 + cond_time.dt.minute * 60 + cond_time.dt.second
            # Make 'VariableName' a string instead of list
            for i in df_new.index.values:
                if not isinstance(df_new.loc[i,'VariableName'], float):
                    df_new.loc[i,'VariableName'] = df_new.loc[i,'VariableName'][0]
            return df_new

    def read_points(self):
        points = dict()
        for point in sorted(self.point_properties.index.values):
            var_name_in_test = self.point_properties.loc[point].name_in_test
            # Get current point value and convert to test script units
            value = self.controller.get_current_variable_value(point)
            p = self.controller.get_point(point)
            # If acceptable units assigned, convert from device to test script
            try:
                value = convert(value, p.unit_in_device, p.unit_in_test).magnitude
            # Otherwise, likely a "state" rather than "unit", just print as is for now # TODO
            except:
                pass
            points[var_name_in_test] = value
        return points

    def print_points(self, to_csv=False, name=None):
        points = self.read_points()
        for k in sorted(points):
            print("%s: %s" % (k, str(points[k])))
        print()

        if to_csv:
            # Create output directory if it doesn't exist
            output_dir = self.results_dir / f"run_{name}"
            output_dir.mkdir(parents=True, exist_ok=True)
            
            file = output_dir / f"{name}_values.csv"
            if not file.exists():
                fp = open(file, "w")
                column_names = 'time,' + ','.join(list(points.keys())) + '\n'
                fp.write(column_names)
            else:
                fp = open(file, "a")
            timestamp = str(self.controller.get_current_time())
            values = timestamp+','+','.join([str(value) for value in points.values()])+'\n'
            fp.write(values)

    def save_test_times(self, to_csv=False, name=None, step=None, st=None, et=None, duration=None):
        if to_csv:
            # Create output directory if it doesn't exist
            output_dir = self.results_dir / f"run_{name}"
            output_dir.mkdir(parents=True, exist_ok=True)
            
            file = output_dir / f"{name}_test_times.csv"
            if not file.exists():
                fp = open(file, "w")
                column_names = 'step,start_time,end_time,duration\n'
                fp.write(column_names)
            else:
                fp = open(file, "a")

            values = "%d,%f,%f,%f\n"%(step, st, et, duration)
            fp.write(values)

    def start_test(self, to_csv=False, name=None):
        output_acceptable_bounds = self.acceptable_op_bounds.to_dict()
        start_time = self.controller.get_current_time()
        
        for i in range(1, self.ip.shape[0]):
            self.current_step = i
            print("starting step %d"%i)

            ip = self.ip.iloc[i].to_dict()
            cond = self.cond.iloc[i]
            expected_op = self.op.iloc[i].to_dict()

            self.set_values(variable_value_dict=ip)
            print("Successfully set input values=================================")
            print()

            step_start_time = self.controller.get_current_time()

            self.test_conditions(condition=cond, st=step_start_time, to_csv=to_csv, name=name)
            
            print("Conditions met. Current values = ")
            self.print_points(to_csv=to_csv, name=name)

            actual_outputs = self.get_current_variable_values(variable_list=self.op.columns.values)
            self.step_outputs[self.current_step] = actual_outputs

            if i > 1:
                print("Checking if outputs match the expected values")
                assertion_op = self.assert_output(expected_op_dict = expected_op, actual_output_dict=actual_outputs, acceptable_bounds_dict = output_acceptable_bounds)
                if not assertion_op:
                    end_time = self.controller.get_current_time()
                    time_elapsed = round((end_time - start_time)/60, 2)
                    label = self.step_labels[i-1] if i-1 < len(self.step_labels) else f"step{i}"
                    print("Test failed at test step %s! Total time = %f minutes"%(self._get_step_label(i), round(time_elapsed, 2)))
                    self.save_test_times(to_csv=to_csv, name=name, step=-1, st=start_time, et=end_time,
                                         duration=time_elapsed)
                    Ramp.destroy_all()
                    Periodic.destroy_all()

                    return
                step_end_time = self.controller.get_current_time()
                step_time_elapsed = round((step_end_time - step_start_time)/60, 2)
                print("Passed %s; Time taken for this step = %f minutes"%(self._get_step_label(i), round(step_time_elapsed, 2)))
                Ramp.destroy_all()
                Periodic.destroy_all()
                self.save_test_times(to_csv=to_csv, name=name, step=i, st=step_start_time, et=step_end_time, duration=step_time_elapsed)

            else:
                print("not checking first step values")
                Ramp.destroy_all()
                Periodic.destroy_all()
            print("moving to the next step")
            print()
        end_time = self.controller.get_current_time()
        time_elapsed = round((end_time - start_time) / 60, 2)
        print("Controller passed the test successfully! Total time = %f minutes"%round(time_elapsed, 2))
        
        self.save_test_times(to_csv=to_csv, name=name, step=999, st=start_time, et=end_time,
                             duration=time_elapsed)
        return

    def set_values(self, variable_value_dict):
        # start with assumption that there are no ramping variables in this step
        self.ramp_variables = {}
        self.periodic_variables = {}
        for key in variable_value_dict:
            val = variable_value_dict[key]
            if type(val) == str:
                # remove all whitespaces
                val = val.replace(" ","")

                if "=RAMP(" in val:
                    # import pdb; pdb.set_trace()
                    op = Ramp(raw_string=val, test_obj=self, variable=key)
                    op.get_parameter_dict()                    
                    value_to_set = op.params['ramp_start']
                elif "=PERIODIC(" in val:
                    op = Periodic(raw_string=val, test_obj=self, variable=key)
                    op.get_parameter_dict()                    
                    value_to_set = op.params['periodic_start']
                elif "=INTERPOLATE(" in val:                    
                    op = InterpolateOperation(raw_string=val, test_obj=self)                    
                    op.get_parameter_dict()
                    op.compute_value()
                    value_to_set = op.computed_value
                elif "=ADD(" in val:                    
                    op = Add(raw_string=val, test_obj=self)
                    op.get_parameter_dict()
                    op.compute_value()
                    value_to_set = op.computed_value                
                elif "=SUB(" in val:                    
                    op = Sub(raw_string=val, test_obj=self)
                    op.get_parameter_dict()
                    op.compute_value()
                    value_to_set = op.computed_value
                elif "=MULT(" in val:                    
                    op = Mul(raw_string=val, test_obj=self)
                    op.get_parameter_dict()
                    op.compute_value()
                    value_to_set = op.computed_value  
                elif "=LAST" in val:
                    expression = val[1:]
                    value_to_set = self.evaluate_expression(expression=expression, current_variable = key)
                elif val.startswith("="):
                    expression = val[1:]
                    value_to_set = self.evaluate_expression(expression=expression)
                else:
                    try:
                        # Try correcting if number read in as string
                        value_to_set = float(val)
                    except:
                        # Otherwise, let string go as it should then be a state
                        value_to_set = val
            else:
                # TODO: handle units == 'percent'
                value_to_set = val
            var_name_in_test = self.point_properties.loc[key].name_in_test
            print("Setting input %s to %s"%(var_name_in_test, value_to_set))
            # Convert value to device units and set in device
            # Handle string/boolean conversions # TODO this is hardcoded and needs to be made device-flexible
            if isinstance(value_to_set, str):
                value_to_set = _convert_state(value_to_set)
            else:
            # Handle all other conversions
                point = self.controller.get_point(key)
                value_to_set = convert(value_to_set, point.unit_in_test, point.unit_in_device).magnitude
            self.controller.set_single_point(key, value_to_set)

    def test_conditions(self, condition, st, sleep_interval=None, verbose=False, to_csv=False, name=None):

        print("step = %s " % self._get_step_label(self.current_step))
        device_type = self.controller.get_type()
        current_time = self.controller.get_current_time()
        last_print = None
        condition_met = False
        # Check if time condition is met to end test step
        while current_time - st < condition['ClockTime']:
            seconds_since_start = int(current_time - st)
            # Compute and set new input values for all ramps and periodics at this step
            for obj in Ramp.instances:
                if obj.params['ramp_step']:                        
                    obj.compute_value(seconds_since_start)
                    # Convert value to device units and set in device
                    point = self.controller.get_point(obj.variable)
                    value_to_set = convert(obj.computed_value, point.unit_in_test, point.unit_in_device).magnitude
                    self.controller.set_single_point(obj.variable, value_to_set)
            for obj in Periodic.instances:
                if obj.params['periodic_step']:
                    obj.compute_value(seconds_since_start)
                    # Convert value to device units and set in device
                    point = self.controller.get_point(obj.variable)
                    value_to_set = convert(obj.computed_value, point.unit_in_test, point.unit_in_device).magnitude
                    self.controller.set_single_point(obj.variable, value_to_set)
            # Once new values set, let controller update outputs
            self.controller.wait(duration=0.0000001)
            # Save point values
            self.print_points(to_csv=to_csv, name=name)

            if verbose:
                print("current time = %f, wait until %f" % (current_time - st, condition['ClockTime']))

            # Check if variable condition met to end test step
            if pd.notna(condition['VariableName']):
                output_variable_to_check = condition['VariableName']
                output_value_to_check = condition['VariableValue']
                # Get the output value to check
                # If the value to check is just a number, the check is equality to the number
                try:
                    output_value_to_check = float(output_value_to_check)
                    operator = "="
                # Otherwise the value to check is an expression that needs to be parsed
                except:
                    # Check if the value to check is the form e.g. <=70
                    strings = re.findall(r"\A\D+", output_value_to_check)
                    for string in strings:
                        # If it is, use the operator and the value to be compared
                        if string in ['>', '>=', '<', '<=']:
                            operator = string
                            output_value_to_check = float(output_value_to_check.split(operator)[1])
                            ref_var = False
                            break
                        # Otherwise, the value to check is equality to a referenced variable
                        else:
                            ref_var = True
                    # The value to check is equality to a referenced variable
                    if ref_var:
                        operator = "="
                        point = self.controller.get_point_by_test_name(output_value_to_check)
                        output_value_to_check = self.controller.get_current_variable_value(point.name)
                        output_value_to_check = convert(output_value_to_check, point.unit_in_device, point.unit_in_test).magnitude
                # Get actual point value and convert to test script units
                actual_output_variable_value = self.controller.get_current_variable_value(output_variable_to_check)
                point = self.controller.get_point(output_variable_to_check)
                actual_output_variable_value = convert(actual_output_variable_value, point.unit_in_device, point.unit_in_test).magnitude
                # If condition met, end test step
                if self.evaluate_boolean_expression(operator=operator, actual_value=actual_output_variable_value, expected_value=output_value_to_check):
                    print("condition satisfied, variable %s value %f %s condition value %f"%(output_variable_to_check, actual_output_variable_value, operator, output_value_to_check))
                    print()

                    return

            # If time and variable conditions not met to end test step, wait and advance time
            wait_duration = sleep_interval if sleep_interval else 10
            self.controller.wait(wait_duration) 
            current_time = self.controller.get_current_time()         

            # Save point values (every minute for BACnet, every step for simulation)
            device_type = self.controller.get_type()
            if device_type == 'simulation':
                self.print_points(to_csv=to_csv, name=name)
            else:
                if seconds_since_start%60 == 0:
                    if last_print == None or last_print != seconds_since_start/60:
                        last_print = seconds_since_start/60
                        label = self.step_labels[self.current_step-1] if self.current_step-1 < len(self.step_labels) else f"step{self.current_step}"
                        print("Completed minute %d of %s of the test; Current values="%(int(seconds_since_start/60), self._get_step_label(self.current_step)))
                        self.print_points(to_csv=to_csv, name=name)
        # If time condition met, end test step
        # Update current time
        current_time = self.controller.get_current_time()
        seconds_since_start = int(current_time - st)
        # Compute and set new input values for all ramps and periodics a final time at this step
        for obj in Ramp.instances:
            if obj.params['ramp_step']:                        
                obj.compute_value(seconds_since_start)   
                # Convert value to device units and set in device
                point = self.controller.get_point(obj.variable)
                value_to_set = convert(obj.computed_value, point.unit_in_test, point.unit_in_device).magnitude
                self.controller.set_single_point(obj.variable, value_to_set)      
        for obj in Periodic.instances:
            if obj.params['periodic_step']:
                obj.compute_value(seconds_since_start)
                # Convert value to device units and set in device
                point = self.controller.get_point(obj.variable)
                value_to_set = convert(obj.computed_value, point.unit_in_test, point.unit_in_device).magnitude
                self.controller.set_single_point(obj.variable, value_to_set)
        # Once new values set, let controller update outputs
        self.controller.wait(duration = 0.0000001)
        
        print("test condition finished")

    def evaluate_boolean_expression(self, operator, actual_value, expected_value, error_bound=0):
        '''Checks if a boolean expression is valid, and if so, if it is true or false.
        
        Parameters
        ----------
        operator: str
            Boolean expression operator, one of [>, >=, <, <=, =].
        actual_value: numeric
            The value to check.
        expected_value: numeric
            The value to check against.
        error_bound: numeric, optional
            Tolerance of the actual value to be above or below the expected value.
            Only used if operator is =.
            Default is 0.

        Returns
        -------
        check: bool
            True if <actual_value> <operator> <expected_value>.  Otherwise, False.
        
        '''
        # TODO: Handle initialization step more explicitly in the test loop
        if actual_value is None:  # For simulation device, all varables are None before first wait() call
            check = False
        if operator == ">":
            if actual_value > expected_value:
                check = True
            else:
                check = False
        elif operator == ">=":
            if actual_value >= expected_value:
                check = True
            else:
                check = False
        elif operator == "<":
            if actual_value > expected_value:
                check = True
            else:
                check = False
        elif operator == "<=":
            if actual_value <= expected_value:
                check = True
            else:
                check = False
        elif operator == "=":
            if abs(expected_value - actual_value) > error_bound:
                check = False
            else:
                check = True
        else:
            raise ValueError('The operator {0} is invalid to check for step {1}.'.format(operator, self.current_step))
        
        return check

    def get_current_variable_values(self, variable_list):
        vals = {}
        for var in variable_list:
            # Get current point value and convert to test script units
            value = self.controller.get_current_variable_value(var)
            point = self.controller.get_point(var)
            value = convert(value, point.unit_in_device, point.unit_in_test).magnitude
            vals[var] = value
        return vals

    def assert_output(self, expected_op_dict, actual_output_dict, acceptable_bounds_dict):
        for key in expected_op_dict:
            expected_val = expected_op_dict[key]
            actual_val = actual_output_dict[key]
            error_bound = acceptable_bounds_dict[key]

            if type(actual_val) == str:
                if actual_val == 'inactive':
                    actual_val = 0
                else:
                    actual_val = 1
            
            elif type(expected_val) == str:
                if "ANY" in expected_val:
                    continue
                elif "LAST" in expected_val:
                    operator = expected_val.split('LAST')[0]
                    variable = key
                    expected_val = self.step_outputs[self.current_step - 1][variable]

                    if self.evaluate_boolean_expression(operator=operator, actual_value=actual_val, expected_value=expected_val, error_bound=error_bound):
                        continue
                    else:
                        var_name = self.point_properties.loc[self.point_properties.index == key].name_in_test.values[0]
                        print("For variable %s [or %s], actual value = %f not %s expected value = %f"%(key, var_name, actual_val, operator, expected_val))
                        return False
                elif "INTERPOLATE(" in expected_val:
                    op = InterpolateOperation(raw_string=expected_val, test_obj=self)
                    op.get_parameter_dict()                    
                    op.compute_value()
                    expected_value = op.computed_value                                         
                elif expected_val.startswith("="):
                    expression = expected_val[1:]
                    expected_value = self.evaluate_expression(expression=expression)

                    if abs(expected_value - actual_val) > error_bound:
                        var_name = self.point_properties.loc[self.point_properties.index == key].name_in_test.values[0]
                        print ("outside bounds for %s [or %s], actual value = %f, expected value = %f, bounds = %f" % (
                        key, var_name, actual_val, expected_value, error_bound))
                        return False

            else:
                if abs(expected_val - actual_val) > error_bound:
                    var_name = self.point_properties.loc[self.point_properties.index == key].name_in_test.values[0]
                    print ("outside bounds for %s [or %s], actual value = %f, expected value = %f, bounds = %f"%(key, var_name, actual_val, expected_val, error_bound))
                    return False

        return True

    def evaluate_expression(self, expression, current_variable = None):
        original_expression = expression
        if expression.startswith("="):
            expression = expression[1:]        
            print(f'Expression is {expression}')
        while expression.find(')') != -1:
            e_loc = expression.find(')')
            s_loc = expression[:e_loc].rfind('(')
            
            #detect function name before the '('
            func_start = s_loc
            func_name = None
            for name in ["ADD", "SUB", "MULT"]:
                prefix = name + "("
                if expression[:s_loc + 1].endswith(prefix):
                    func_name = name
                    func_start = s_loc - len(name)   # index where 'A'/'S'/'M' begins
                    break
    
            #substring we evaluate:
            #if inside function: "ADD(10;60)" (full thing)
            #otherwise: whatever was inside parentheses
            if func_name is not None:
                sub_expr = expression[func_start:e_loc + 1]
            else:
                sub_expr = expression[s_loc + 1:e_loc]
    
            op = self.get_value_from_expression(
                expression=sub_expr,
                original_expression=original_expression,
            )

            # replace either "(…)" or "ADD(…)" with result
            expression = expression.replace(expression[func_start if func_name else s_loc : e_loc + 1],
                                            str(op),
                                            1)  # replace only the first occurrence
    
        return self.get_value_from_expression(expression=expression, current_variable = current_variable)

    def get_value_from_expression(self, expression, original_expression = None, current_variable = None):

        operator_found = False
        result = None
    # New: operator tokens for function-style operations
        if original_expression is not None:
            for op_token, op_name in [("ADD(", "ADD"), ("SUB(", "SUB"), ("MULT(", "MULT")]:
                if op_token in original_expression:
                    operator_found = True
    
                    # Extract the argument substring inside the function call:
                    # e.g. from "ADD(a;b)" -> "a;b"
                    inner = original_expression.split(op_token, 1)[1]
                    inner = inner[:-1]  # remove trailing ')'
    
                    # Split arguments on ';'
                    parts = [p.strip() for p in inner.split(";")]
    
                    for part in parts:
                        current_res = self.get_value_from_expression(expression=part)
                        if result is not None:
                            if op_name == "ADD":                                
                                result = result + current_res                                
                            elif op_name == "SUB":
                                result = result - current_res
                            elif op_name == "MULT":
                                result = result * current_res
                        else:
                            result = current_res
                    break
        if operator_found:
            return result
        else:
            if "LAST" in expression:
                # Get last point value from device and convert to test script units
                value = self.controller.get_variable_value_from_prev_time_step(current_variable)
                point = self.controller.get_point(current_variable)
                value = convert(value, point.unit_in_device, point.unit_in_test).magnitude
                return value          
            else:
                names_df = self.point_properties.loc[self.point_properties.name_in_test == expression]
            if not names_df.empty:
                var_to_check = names_df.index.values[0]
                # Get current point value from device and convert to test script units
                value = self.controller.get_current_variable_value(var_to_check)
                point = self.controller.get_point(var_to_check)
                value = convert(value, point.unit_in_device, point.unit_in_test).magnitude
                return value
            else:
                try:
                    print('Currently in the first try block')
                    print(f'The expression is {expression}')
                    float_value = float(expression)
                except Exception as e:
                    print("WARNING: cannot find variable to check %s"%expression)
                return float_value

class StateOperation:
    OP_TOKEN = None 
    def __init__(self, raw_string, test_obj, variable):
        self.raw_string = raw_string
        self.test = test_obj
        self.params = {}
        self.computed_value = None
        self.variable = variable

    def get_parameter_dict(self):
        """Each child overrides this to extract parameters from the raw string."""
        raise NotImplementedError        

    def compute_value(self):
        """Each operation computes a value at time t."""
        raise NotImplementedError

class Ramp(StateOperation):
    OP_TOKEN = "RAMP("
    instances = []
    
    def __init__(self, raw_string, test_obj, variable):
        # import pdb; pdb.set_trace()
        super().__init__(raw_string, test_obj, variable)        
        Ramp.instances.append(self)

    def destroy(self):
        """Call this to allow the object to be garbage collected."""
        if self in Ramp.instances:
            Ramp.instances.remove(self)
    
    @classmethod
    def destroy_all(cls):
        cls.instances.clear()

    def get_parameter_dict(self):
        val = self.raw_string.split(self.OP_TOKEN)[1][:-1]
        string_parameters = [s.replace(" ", "") for s in val.split(";")]
        if len(string_parameters) < 4:
            self.params = {
                "ramp_start": self.test.evaluate_expression(string_parameters[0]),
                "ramp_end": self.test.evaluate_expression(string_parameters[1]),
                "duration": self.test.evaluate_expression(string_parameters[2]),
                "ramp_rate": abs(self.test.evaluate_expression(string_parameters[1]) - self.test.evaluate_expression(string_parameters[0]))/self.test.evaluate_expression(string_parameters[2]), #self.test.evaluate_expression(string_parameters[2])/60,
                "ramp_period":10,
                "ramp_step": self.test.evaluate_expression(string_parameters[0]) != self.test.evaluate_expression(string_parameters[1]),
            }
        else:
            self.params = {
                "ramp_start": self.test.evaluate_expression(string_parameters[0]),
                "ramp_end": self.test.evaluate_expression(string_parameters[1]),
                "duration": self.test.evaluate_expression(string_parameters[2]),
                "ramp_rate": abs(self.test.evaluate_expression(string_parameters[1]) - self.test.evaluate_expression(string_parameters[0]))/self.test.evaluate_expression(string_parameters[2]), #self.test.evaluate_expression(string_parameters[2])/60,
                "ramp_period":self.test.evaluate_expression(string_parameters[3]),
                "ramp_step": self.test.evaluate_expression(string_parameters[0]) != self.test.evaluate_expression(string_parameters[1]),
            }

    def compute_value(self, seconds_since_start):        
        ramp_start = self.params['ramp_start']
        ramp_end = self.params['ramp_end']
        ramp_rate = self.params['ramp_rate']
        ramp_period = self.params['ramp_period']
        ramp_duration = self.params['duration']
        if seconds_since_start % ramp_period == 0:
            # import pdb; pdb.set_trace()
            current_period = (seconds_since_start / ramp_period)
            
            if ramp_start < ramp_end:
                value_to_set = ramp_start + ramp_rate * current_period * ramp_period             
                if value_to_set > ramp_end:
                    value_to_set = ramp_end
            elif ramp_start > ramp_end:
                value_to_set = ramp_start - ramp_rate * current_period * ramp_period
                if value_to_set < ramp_end:
                    value_to_set = ramp_end
            if seconds_since_start <= ramp_duration:
                self.computed_value = value_to_set

class Periodic(StateOperation):
    OP_TOKEN = "PERIODIC("
    instances = []
    
    def __init__(self, raw_string, test_obj, variable):
        super().__init__(raw_string, test_obj, variable)        
        Periodic.instances.append(self)

    def destroy(self):
        """Call this to allow the object to be garbage collected."""
        if self in Periodic.instances:
            Periodic.instances.remove(self)
            
    @classmethod
    def destroy_all(cls):
        cls.instances.clear()
    
    def get_parameter_dict(self):
        val = self.raw_string.split(self.OP_TOKEN)[1][:-1]
        string_parameters = [s.replace(" ", "") for s in val.split(";")]
        if len(string_parameters) < 2:
            self.params = {
                "periodic_start": self.test.evaluate_expression(string_parameters[0]),            
                "periodic_expression": string_parameters[0],
                "period": 10,
                "periodic_step": True,
            }
        else:    
            self.params = {
                "periodic_start": self.test.evaluate_expression(string_parameters[0]),            
                "periodic_expression": string_parameters[0],
                "period": float(string_parameters[1]),
                "periodic_step": True,
            }
        
    def compute_value(self, seconds_since_start):        
        periodic_expression = self.params['periodic_expression']
        period = self.params['period']
        #import pdb; pdb.set_trace()
        if seconds_since_start % period == 0:
            value_to_set = self.test.evaluate_expression(expression=periodic_expression)
            var_name_in_test = self.test.point_properties.loc[self.variable].name_in_test
            print("Periodic: Changing variable %s to %f" % (var_name_in_test, value_to_set))
            self.computed_value = value_to_set

class StateLessOperation:
    OP_TOKEN = None 
    def __init__(self, raw_string, test_obj):
        self.raw_string = raw_string
        self.test = test_obj
        self.params = {}
        self.computed_value = None

    def get_parameter_dict(self):
        """Each child overrides this to extract parameters from the raw string."""
        raise NotImplementedError        

    def compute_value(self):
        """Each operation computes a value at time t."""
        raise NotImplementedError
        
    def split_top_level_semicolons(self, s: str):
        parts = []
        current = []
        depth = 0
        for ch in s:
            if ch == '(':
                depth += 1
                current.append(ch)
            elif ch == ')':
                depth = max(depth - 1, 0)
                current.append(ch)
            elif ch == ';' and depth == 0:
                parts.append(''.join(current))
                current = []
            else:
                current.append(ch)
        if current:
            parts.append(''.join(current))
        return parts
        
class TwoTermOperation(StateLessOperation):
    """
    Handles:
    - parsing OP(arg1 ; arg2)
    - evaluating both arguments
    Child classes only define:
    - OP_TOKEN
    - _apply(a, b)
    """

    def get_parameter_dict(self):
        val = self.raw_string.split(self.OP_TOKEN)[1][:-1]
        string_parameters = [s.replace(" ", "") for s in val.split(";")]

        self.params = {
            "first_term": self.test.evaluate_expression(string_parameters[0]),
            "second_term": self.test.evaluate_expression(string_parameters[1]),
        }

    def compute_value(self):
        self.computed_value = self._apply(self.params["first_term"],
                                          self.params["second_term"])

    def _apply(self, a, b):
        """Child classes must define the actual operation"""
        raise NotImplementedError        

class Add(TwoTermOperation):
    OP_TOKEN = "ADD("

    def _apply(self, a, b):    
        return a + b

class Sub(TwoTermOperation):
    OP_TOKEN = "SUB("
    def _apply(self, a, b):
        return a - b
    
class Mul(TwoTermOperation):
    OP_TOKEN = "MULT("
    def _apply(self, a, b):
        return a * b       

class InterpolateOperation(StateLessOperation):
    OP_TOKEN = "INTERPOLATE("
    def get_parameter_dict(self):
        val = self.raw_string.split(self.OP_TOKEN)[1][:-1]      
        string_parameters = self.split_top_level_semicolons(val)
        string_parameters = [s.replace(' ', '') for s in string_parameters]
        self.params['x'] = self.test.evaluate_expression(expression=string_parameters[0])
        self.params['x0'] = self.test.evaluate_expression(expression=string_parameters[1])        
        self.params['x1'] = self.test.evaluate_expression(expression=string_parameters[2])        
        self.params['y0'] = self.test.evaluate_expression(expression=string_parameters[3])        
        self.params['y1'] = self.test.evaluate_expression(expression=string_parameters[4]) 
        if len(string_parameters) > 5:
            self.params['min_out'] = self.test.evaluate_expression(expression=string_parameters[5]) 
        else:
            self.params['min_out'] = None        
        if len(string_parameters) > 6:
            self.params['max_out'] = self.test.evaluate_expression(expression=string_parameters[6]) 
        else:
            self.params['max_out'] = None
        
    def compute_value(self):
        self.computed_value = self._apply()        
                
    def _apply(self):
        result = self.params['y0'] + (self.params['y1'] - self.params['y0']) * \
        ((self.params['x'] - self.params['x0']) / (self.params['x1'] - self.params['x0']))
        if self.params['min_out'] is None and self.params['max_out'] is None:
            return result
        elif self.params['min_out'] is None:
            return min(result, self.params['max_out'])
        elif self.params['max_out'] is None:
            return max(result, self.params['min_out'])
        else:
            return max(self.params['min_out'], min(result, self.params['max_out'])) 


