import pandas as pd
import time
import argparse
import re
import os
import math
from pathlib import Path
from loguru import logger
from src.utils.config_loader import load_config


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
        self.SRC_FOLDER = Path(__file__).resolve().parent
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
            from src.device.simulation_device import SimulationDevice
            self.controller = SimulationDevice(device_config=self.device_config)
        elif device_type == 'bacnet':
            from src.device.bacnet_device import BacnetDevice
            self.controller = BacnetDevice(device_config=self.device_config)
        else:
            raise ValueError(f'In configuration file, device type "{device_type}" is unknown. '
                           f'Valid types: "simulation", "bacnet"')
        # Initiate Test Sequence with Test and Device
        self.point_properties = self.controller.get_point_properties()
        self.init_test_sequence(filename=self.test_file, ip_header=self.input_points_header, cond_header=self.conditions_header, op_header=self.output_points_header, point_prop=self.point_properties)

    def init_test_sequence(self, filename, ip_header, cond_header, op_header, point_prop):
        self.test_df = pd.read_excel(self.test_scripts_dir / filename, index_col=0, header=None)
        self.ip = self.format_excel_df(df=self.test_df.loc[ip_header:cond_header].iloc[1:-1], point_prop=point_prop)
        self.cond = self.format_excel_df(df=self.test_df.loc[cond_header:op_header].iloc[1:-1], is_cond_df=True, point_prop=point_prop)
        self.op = self.format_excel_df(df=self.test_df.loc[op_header:].iloc[1:], point_prop=point_prop)
        self.acceptable_op_bounds = self.op.loc["acceptable_bounds"]

        self.current_step = None
        self.step_outputs = {}

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
            points[var_name_in_test] = self.controller.get_current_variable_value(point)
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
            for k, v in actual_outputs.items():
                print(f"  [comparison] {k} = {v}")
            self.step_outputs[self.current_step] = actual_outputs

            if i > 1:
                print("Checking if outputs match the expected values")
                assertion_op = self.assert_output(expected_op_dict = expected_op, actual_output_dict=actual_outputs, acceptable_bounds_dict = output_acceptable_bounds)
                if not assertion_op:
                    end_time = self.controller.get_current_time()
                    time_elapsed = round((end_time - start_time)/60, 2)
                    print("Test failed at test step %d! Total time = %f minutes"%(i, round(time_elapsed, 2)))
                    self.save_test_times(to_csv=to_csv, name=name, step=-1, st=start_time, et=end_time,
                                         duration=time_elapsed)
                    Ramp.destroy_all()
                    Periodic.destroy_all()

                    return
                step_end_time = self.controller.get_current_time()
                step_time_elapsed = round((step_end_time - step_start_time)/60, 2)
                print("Passed step %d; Time taken for this step = %f minutes"%(i, round(step_time_elapsed, 2)))
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
                    value_to_set = val
            else:
                # TODO: handle units == 'percent'
                value_to_set = val
            var_name_in_test = self.point_properties.loc[key].name_in_test
            print("Setting input %s to %s"%(var_name_in_test, value_to_set))
            self.controller.set_single_point(key, value_to_set)

    def test_conditions(self, condition, st, sleep_interval=None, verbose=False, to_csv=False, name=None):

        print("step = %d " % self.current_step)
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
                    self.controller.set_single_point(obj.variable, obj.computed_value)
            for obj in Periodic.instances:
                if obj.params['periodic_step']:
                    obj.compute_value(seconds_since_start)
                    self.controller.set_single_point(obj.variable, obj.computed_value)
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
                if type(output_value_to_check) == str:
                    operator = re.findall(r"\A\D+", output_value_to_check)
                    if len(operator) == 1:
                        operator = operator[0]
                    else:
                        #TODO: handle this better
                        raise Exception("Invalid condition value in step %d for variable %s"%(self.current_step, output_variable_to_check))
                    output_value_to_check = float(output_value_to_check.split(operator)[1])
                    output_value_to_check = self.controller.convert_value_test_unit_to_device_unit(output_variable_to_check, output_value_to_check)
                else:
                    operator = ">="
                actual_output_variable_value = self.controller.get_current_variable_value(output_variable_to_check)
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
                        print("Completed minute %d of step %d of the test; Current values=" % (int(seconds_since_start/60), self.current_step))
                        self.print_points(to_csv=to_csv, name=name)
        # If time condition met, end test step
        # Update current time
        current_time = self.controller.get_current_time()
        seconds_since_start = int(current_time - st)
        # Compute and set new input values for all ramps and periodics a final time at this step
        for obj in Ramp.instances:
            if obj.params['ramp_step']:                        
                obj.compute_value(seconds_since_start)   
                self.controller.set_single_point(obj.variable, obj.computed_value)        
        for obj in Periodic.instances:
            if obj.params['periodic_step']:
                obj.compute_value(seconds_since_start)
                self.controller.set_single_point(obj.variable, obj.computed_value)
        # Once new values set, let controller update outputs
        self.controller.wait(duration = 0.0000001)
        
        print("test condition finished")

    def evaluate_boolean_expression(self, operator, actual_value, expected_value):
        # TODO: Handle initialization step more explicitly in the test loop
        if actual_value is None:  # For simulation device, all varables are None before first wait() call
            return False
        if operator == ">" and actual_value > expected_value:
            return True
        elif operator == ">=" and actual_value >= expected_value:
            return True
        elif operator == "<" and actual_value < expected_value:
            return True
        elif operator == "<=" and actual_value <= expected_value:
            return True
        elif operator == "==" and actual_value == expected_value:
            return True
        else:
            return False

    def get_current_variable_values(self, variable_list):
        vals = {}
        for var in variable_list:
            vals[var] = self.controller.get_current_variable_value(var)
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

                    if self.evaluate_boolean_expression(operator=operator, actual_value=actual_val, expected_value=expected_val):
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
                        key, var_name, actual_val, expected_val, error_bound))
                        return False

            else:
                expected_val = self.controller.convert_value_test_unit_to_device_unit(key, expected_val)
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
                return self.controller.get_variable_value_from_prev_time_step(current_variable)                
            else:
                names_df = self.point_properties.loc[self.point_properties.name_in_test == expression]
            if not names_df.empty:
                var_name = names_df.name_in_test.values[0]
                var_to_check = names_df.index.values[0]
                return self.controller.get_current_variable_value(var_to_check)
                #return self.controller.get_current_variable_value(var_name)
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
                print(f'RAMP_START is {ramp_rate}, RAMP_RATE is {ramp_rate}, SECONDS_SINCE_START is {seconds_since_start}')
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

if __name__ == "__main__":

    # Parse command-line arguments first
    parser = argparse.ArgumentParser(
        description="Run ASHRAE Guideline 36 conformance tests"
    )
    parser.add_argument(
        "--global-config",
        help="path to global config file (default: config/global_config.yaml)",
        default=None
    )
    parser.add_argument(
        "--test-config",
        help="path to test-specific config file (default: determined from test_type)",
        default=None
    )
    parser.add_argument("--reset", help="reset point values to first stage (overrides config)", action='store_true')
    parser.add_argument("--output", help="print point values without running test (overrides config)", action='store_true')
    parser.add_argument("--csv", help="save outputs to csv (overrides config)", action='store_true')
    parser.add_argument("--name", help="test run name (overrides config)", default=None)

    args = parser.parse_args()
    
    # Initialize test with config files
    test = Test(
        global_config_path=args.global_config,
        test_config_path=args.test_config
    )
    
    # Get test_runner config with defaults
    test_runner_config = test.config.get('test_runner', {})
    
    # Extract CLI arguments with fallback to config values
    # All boolean flags use: CLI flag OR config value OR False
    reset = args.reset or test_runner_config.get('reset_points', False)
    output = args.output or test_runner_config.get('print_output', False)
    to_csv = args.csv or test_runner_config.get('save_csv', False)
    
    # Name uses: CLI value OR config value OR timestamp
    name = args.name or test_runner_config.get('name') or time.strftime("%Y%m%dT%H%M%S")

    print(to_csv)
    print(name)

    if reset:
        print("resetting points")
        test.set_values(variable_value_dict=test.ip.iloc[1].to_dict())
        points = test.read_points()
        cool_loop_output = points['CoolLoopOut']

        while cool_loop_output != 0:
            print("waiting for cooling loop output to drop to 0, current value = %f"%cool_loop_output)
            time.sleep(3)
            points = test.read_points()
            cool_loop_output = points['CoolLoopOut']

        print()
        test.print_points()
    elif output:
        print("printing values")
        test.print_points()
    else:
        # print("starting test; Current values=")
        # test.print_points()
        test.start_test(to_csv=to_csv, name=name)

