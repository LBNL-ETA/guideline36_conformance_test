import yaml
import json
import pandas as pd
from src.Device import Device
import time
import argparse
import re
import os

class Test:
    def __init__(self, config_file="config.yaml", device_init=True):
        self.FILE_FOLDER = "./files/"
        self.SRC_FOLDER = "./src/"

        with open(self.SRC_FOLDER+config_file, "r") as fp:
            self.config = yaml.safe_load(fp)

        self.test_config = self.config["test"]
        self.test_file = self.test_config["test_script"]
        self.input_points_header = self.test_config.get("input_points_header", "Simulation (controller) Inputs")
        self.conditions_header = self.test_config.get("conditions_header", "Result Time")
        self.output_points_header = self.test_config.get("output_points_header", "Expected Controller BACnet Outputs")

        if device_init:
            self.controller = Device(device_config=self.config["device"])

            self.map_file = self.test_config["point_map"]
            self.init_device(mapping_file=self.map_file)

            self.init_test_sequence(filename=self.test_file, ip_header=self.input_points_header, cond_header=self.conditions_header, op_header=self.output_points_header, point_prop=self.point_properties)

    def init_device(self, mapping_file):
        with open(self.FILE_FOLDER+mapping_file, "r") as fp:
            mapping_dict = json.load(fp)

        self.mapping = pd.DataFrame(data=list(mapping_dict.keys()), index=list(mapping_dict.values()), columns=['name_in_test'])
        self.mapping.index.name = 'bacnet_name'
        self.point_properties = self.controller.get_point_properties()
        self.point_properties = pd.merge(left=self.point_properties, right=self.mapping, how='inner', left_index=True, right_index=True)
        object_list = self.point_properties.apply(lambda x: (x['type'], x['address']), axis=1).values.tolist()
        self.controller.reset_device(object_list = object_list)
        self.points = {}

    def init_test_sequence(self, filename, ip_header, cond_header, op_header, point_prop):
        self.test_df = pd.read_excel(self.FILE_FOLDER+filename, index_col=0, header=None)
        self.ip = self.format_excel_df(df=self.test_df.loc[ip_header:cond_header].iloc[1:-1], point_prop=point_prop)
        self.cond = self.format_excel_df(df=self.test_df.loc[cond_header:op_header].iloc[1:-1], is_cond_df=True, point_prop=point_prop)
        self.op = self.format_excel_df(df=self.test_df.loc[op_header:].iloc[1:], point_prop=point_prop)
        self.acceptable_op_bounds = self.op.loc["acceptable_bounds"]

        self.current_step = None
        self.step_outputs = {}

        self.ramp_step = False
        self.ramp_variables = {}

        self.periodic_step = False
        self.periodic_variables = {}

    def format_excel_df(self, df, is_cond_df=False, point_prop=None):
        df_new = df.reset_index().drop([0, 1], axis=1)
        cols = ['step%d' % i for i in range(len(df_new.columns) - 2)]
        cols = ['variable_name', 'acceptable_bounds'] + cols
        df_new.columns = cols

        if not is_cond_df:
            df_new['variable_name'] = df_new['variable_name'].map(lambda x: point_prop.loc[point_prop['name_in_test'] == x].name[0])
            return df_new.set_index('variable_name').T
        else:
            df_new = df_new.set_index('variable_name').T
            df_new.loc[df_new['or'] == 1, 'VariableName'] = df_new.loc[df_new['or'] == 1, 'VariableName'].map(lambda x: point_prop.loc[point_prop["name_in_test"] == x].name[0])
            time_vals = df_new.loc[df_new['ClkTime'].notnull()].index
            cond_time = pd.to_datetime(df_new.loc[time_vals, 'ClkTime'], format="%H:%M:%S")
            df_new.loc[time_vals, 'ClkTime'] = cond_time.dt.hour * 3600 + cond_time.dt.minute * 60 + cond_time.dt.second
            return df_new

    def read_points(self):
        for point in sorted(self.point_properties.name.values):
            var_name_in_test = self.point_properties.loc[point].name_in_test
            self.points[var_name_in_test] = self.controller.device[point].value
        return self.points

    def print_points(self, to_csv=False, name=None):
        points = self.read_points()
        for k in sorted(points):
            print("%s: %s" % (k, str(points[k])))
        print()

        if to_csv:
            file = self.FILE_FOLDER + name + "_values.csv"
            if not os.path.exists(file):
                fp = open(file, "w")
                column_names = 'time,' + ','.join(list(points.keys())) + '\n'
                fp.write(column_names)
            else:
                fp = open(file, "a")
            values = time.strftime("%Y-%m-%d %H:%M:%S")+','+','.join([str(value) for value in points.values()])+'\n'
            fp.write(values)

    def save_test_times(self, to_csv=False, name=None, step=None, st=None, et=None, duration=None):
        if to_csv:
            file = self.FILE_FOLDER + name + "_test_times.csv"
            if not os.path.exists(file):
                fp = open(file, "w")
                column_names = 'step,start_time,end_time,duration\n'
                fp.write(column_names)
            else:
                fp = open(file, "a")

            values = "%d,%f,%f,%f\n"%(step, st, et, duration)
            fp.write(values)

    def start_test(self, to_csv=False, name=None):
        output_acceptable_bounds = self.acceptable_op_bounds.to_dict()
        start_time = time.time()
        for i in range(1, self.ip.shape[0]):
            self.current_step = i
            print("starting step %d"%i)

            ip = self.ip.iloc[i].to_dict()
            cond = self.cond.iloc[i]
            expected_op = self.op.iloc[i].to_dict()

            # self.controller.set_values(point_value_dict = ip)
            self.set_values(variable_value_dict=ip)
            print("Successfully set input values=================================")
            print()

            step_start_time = time.time()
            self.test_conditions(condition=cond, st=step_start_time, to_csv=to_csv, name=name)
            print("Conditions met. Current values = ")
            self.print_points(to_csv=to_csv, name=name)

            actual_outputs = self.get_current_variable_values(variable_list = self.op.columns.values)
            self.step_outputs[self.current_step] = actual_outputs

            if i > 1:
                print("Checking if outputs match the expected values")
                assertion_op = self.assert_output(expected_op_dict = expected_op, actual_output_dict=actual_outputs, acceptable_bounds_dict = output_acceptable_bounds)
                if not assertion_op:
                    end_time = time.time()
                    time_elapsed = round((end_time - start_time)/60, 2)
                    print("Test failed! Total time = %f minutes"%round(time_elapsed, 2))
                    self.save_test_times(to_csv=to_csv, name=name, step=-1, st=start_time, et=end_time,
                                         duration=time_elapsed)

                    return
                step_end_time = time.time()
                step_time_elapsed = round((step_end_time - step_start_time)/60, 2)
                print("Passed step %d; Time taken for this step = %f minutes"%(i, round(step_time_elapsed, 2)))
                self.save_test_times(to_csv=to_csv, name=name, step=i, st=step_start_time, et=step_end_time, duration=step_time_elapsed)

            else:
                print("not checking first step values")

            print("moving to the next step")
            print()
        end_time = time.time()
        time_elapsed = round((end_time - start_time) / 60, 2)
        print("Controller passed the test successfully! Total time = %f minutes"%round(time_elapsed, 2))
        self.save_test_times(to_csv=to_csv, name=name, step=999, st=start_time, et=end_time,
                             duration=time_elapsed)
        return

    def set_values(self, variable_value_dict):
        # start with assumption that there are no ramping variables in this step
        self.ramp_step = False
        self.ramp_variables = {}

        self.periodic_step = False
        self.periodic_variables = {}

        for key in variable_value_dict:
            val = variable_value_dict[key]
            if type(val) == str:
                # remove all whitespaces
                val = val.replace(" ","")

                if val.startswith("ramp("):
                    ramp_params_dict = self.get_ramp_parameter_dict(val=val)
                    self.ramp_variables[key] = ramp_params_dict
                    value_to_set = ramp_params_dict['ramp_start']
                elif val.startswith("periodic("):
                    periodic_params_dict = self.get_periodic_parameter_dict(val=val)
                    self.periodic_variables[key] = periodic_params_dict
                    value_to_set = periodic_params_dict['periodic_start']
                elif val.startswith("="):
                    expression = val[1:]
                    value_to_set = self.evaluate_expression(expression=expression)
                else:
                    if val.lower() in ['open', 'present', 'on']:
                        value_to_set = 'active'
                    elif val.lower() in ['closed', 'absent', 'off']:
                        value_to_set = 'inactive'
                    else:
                        value_to_set = val
            else:
                # TODO: handle units == 'percent'
                value_to_set = val
            var_name_in_test = self.point_properties.loc[key].name_in_test
            print("Setting input %s to %s"%(var_name_in_test, value_to_set))
            self.controller.device[key] = value_to_set

    def get_ramp_parameter_dict(self, val, default_ramp_period=10):
        val = val.split("ramp(")[1][:-1]
        string_parameters = val.split(';')
        ramp_params = []
        for param in string_parameters:
            if param.startswith("="):
                expression = param[1:]
                val_expression = self.evaluate_expression(expression=expression)
                ramp_params.append(val_expression)
            else:
                ramp_params.append(float(param))

        ramp_params_dict = {}

        # if start == end, no ramping
        if ramp_params[0] != ramp_params[1]:
            self.ramp_step = True

        ramp_params_dict['ramp_start'] = ramp_params[0]
        ramp_params_dict['ramp_end'] = ramp_params[1]

        # convert ramp rate to value per second
        ramp_params_dict['ramp_rate'] = ramp_params[2]/60.0

        if len(ramp_params) == 4:
            ramp_params_dict['ramp_period'] = ramp_params[3]
        else:
            ramp_params_dict['ramp_period'] = default_ramp_period

        return ramp_params_dict

    def get_periodic_parameter_dict(self, val, default_period = 10):
        val = val.split("periodic(")[1][:-1]
        string_parameters = val.split(";")
        periodic_params = []
        for param in string_parameters:
            if param.startswith("="):
                periodic_params.append(param[1:])
            else:
                periodic_params.append(float(param))

        self.periodic_step = True

        periodic_params_dict = {}
        periodic_params_dict['periodic_start'] = self.evaluate_expression(expression=periodic_params[0])
        periodic_params_dict['periodic_expression'] = periodic_params[0]
        if len(periodic_params) == 2:
            periodic_params_dict['period'] = int(periodic_params[1])
        else:
            periodic_params_dict['period'] = default_period

        return periodic_params_dict

    def set_ramp_value(self, variable, params, seconds_since_start):
        ramp_start = params['ramp_start']
        ramp_end = params['ramp_end']
        ramp_rate = params['ramp_rate']
        ramp_period = params['ramp_period']

        if seconds_since_start % ramp_period == 0:
            current_period = seconds_since_start / ramp_period
            if ramp_start < ramp_end:
                value_to_set = ramp_start + ramp_rate * current_period * ramp_period
                if value_to_set > ramp_end:
                    value_to_set = ramp_end
            elif ramp_start > ramp_end:
                value_to_set = ramp_start - ramp_rate * current_period * ramp_period
                if value_to_set < ramp_end:
                    value_to_set = ramp_end

            current_value = self.controller.device[variable].value
            if round(value_to_set, 2) != round(current_value, 2):
                var_name_in_test = self.point_properties.loc[variable].name_in_test
                print("Ramping input %s to %f" % (var_name_in_test, value_to_set))
                print()
                self.controller.device[variable] = value_to_set

    def set_periodic_value(self, variable, params, seconds_since_start):
        periodic_expression = params['periodic_expression']
        period = params['period']

        if seconds_since_start%period == 0:
            value_to_set = self.evaluate_expression(expression=periodic_expression)
            current_value = self.controller.device[variable].value
            if round(value_to_set, 2) != round(current_value, 2):
                var_name_in_test = self.point_properties.loc[variable].name_in_test
                print("Periodic: Changing variable %s to %f" % (var_name_in_test, value_to_set))
                print()
                self.controller.device[variable] = value_to_set

    def test_conditions(self, condition, st, sleep_interval=None, verbose=False, to_csv=False, name=None):

        print("step = %d " % self.current_step)
        current_time = time.time()
        last_print = None

        while current_time - st <= condition['ClkTime']:

            seconds_since_start = int(current_time - st)

            if self.ramp_step:
                for variable in self.ramp_variables:
                    params = self.ramp_variables[variable]
                    self.set_ramp_value(variable=variable, params=params, seconds_since_start=seconds_since_start)

            if self.periodic_step:
                for variable in self.periodic_variables:
                    params = self.periodic_variables[variable]
                    self.set_periodic_value(variable=variable, params=params, seconds_since_start=seconds_since_start)

            if verbose:
                print("current time = %f, wait until %f" % (current_time - st, condition['ClkTime']))

            if condition['or'] == 1:
                output_variable_to_check = condition['VariableName']
                output_value_to_check = condition['VariableValue']

                if type(output_value_to_check) == str:
                    operator = re.findall("\A\D+", output_value_to_check)
                    if len(operator) == 1:
                        operator = operator[0]
                    else:
                        #TODO: handle this better
                        raise Exception("Invalid condition value in step %d for variable %s"%(self.current_step, output_variable_to_check))

                    output_value_to_check = output_value_to_check.split(operator)[1]
                    if output_value_to_check.endswith("%"):
                        output_value_to_check = float(output_value_to_check[:-1])/100
                    else:
                        output_value_to_check = float(output_value_to_check)
                else:
                    operator = ">="

                actual_output_variable_value = self.controller.device[output_variable_to_check].value

                # handle percent values
                if self.point_properties.loc[output_variable_to_check].units_state == 'percent':
                    actual_output_variable_value = actual_output_variable_value/100

                if self.evaluate_boolean_expression(operator=operator, actual_value=actual_output_variable_value, expected_value=output_value_to_check):
                    print("condition satisfied, variable %s value %f %s condition value %f"%(output_variable_to_check, actual_output_variable_value, operator, output_value_to_check))
                    print()
                    return

            if seconds_since_start%60 == 0:
                if last_print == None or last_print != seconds_since_start/60:
                    last_print = seconds_since_start/60
                    print("Completed minute %d of step %d of the test; Current values=" % (int(seconds_since_start/60), self.current_step))
                    self.print_points(to_csv=to_csv, name=name)

            if sleep_interval:
                time.sleep(sleep_interval)

            current_time = time.time()
        print("wait time condition met")

    def evaluate_boolean_expression(self, operator, actual_value, expected_value):
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
            vals[var] = self.controller.device[var].value
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

            if expected_val == "Any":
                continue
            elif type(expected_val) == str:
                if "last" in expected_val:
                    operator = expected_val.split('last')[0]
                    variable = key
                    expected_val = self.step_outputs[self.current_step - 1][variable]

                    if self.evaluate_boolean_expression(operator=operator, actual_value=actual_val, expected_value=expected_val):
                        continue
                    else:
                        var_name = self.point_properties.loc[self.point_properties.name == key].name_in_test.values[0]
                        print("For variable %s [or %s], actual value = %f not %s expected value = %f"%(key, var_name, actual_val, operator, expected_val))
                        return False
                if expected_val.startswith("="):
                    expression = expected_val[1:]
                    expected_value = self.evaluate_expression(expression=expression)

                    if abs(expected_value - actual_val) > error_bound:
                        var_name = self.point_properties.loc[self.point_properties.name == key].name_in_test.values[0]
                        print ("outside bounds for %s [or %s], actual value = %f, expected value = %f, bounds = %f" % (
                        key, var_name, actual_val, expected_val, error_bound))
                        return False

            else:
                if self.point_properties.loc[key].units_state == 'percent':
                    actual_val = actual_val/100

                if abs(expected_val - actual_val) > error_bound:
                    var_name = self.point_properties.loc[self.point_properties.name == key].name_in_test.values[0]
                    print ("outside bounds for %s [or %s], actual value = %f, expected value = %f, bounds = %f"%(key, var_name, actual_val, expected_val, error_bound))
                    return False

        return True

    def evaluate_expression(self, expression):
        if expression.startswith("="):
            expression = expression[1:]

        while expression.find(')') != -1:
            e_loc = expression.find(')')
            s_loc = expression[:e_loc].rfind('(')
            op = self.get_value_from_expression(expression=expression[s_loc + 1:e_loc])
            expression = expression.replace(expression[s_loc:e_loc + 1], str(op))
        return self.get_value_from_expression(expression=expression)

    def get_value_from_expression(self, expression):

        operator_found = False
        result = None
        for operator in ['+', '-', '*', '/']:
            if operator in expression:
                operator_found = True
                parts = expression.split(operator)
                for part in parts:
                    current_res = self.get_value_from_expression(expression=part)
                    if result:
                        if operator == '+':
                            result = result + current_res
                        elif operator == '-':
                            result = result - current_res
                        elif operator == '*':
                            result = result * current_res
                        elif operator == '/':
                            result = result / current_res
                    else:
                        result = current_res
                break
        if operator_found:
            return result
        else:
            names_df = self.point_properties.loc[self.point_properties.name_in_test == expression]
            if not names_df.empty:
                var_name = names_df.name.values[0]
                return self.controller.device[var_name].value
            else:
                try:
                    float_value = float(expression)
                except Exception as e:
                    raise Exception("cannot find variable %s"%expression)
                return float_value


if __name__ == "__main__":
    test = Test()

    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", help="reset point values to first stage", action='store_true')
    parser.add_argument("--output", help="print point values", action='store_true')
    parser.add_argument("--csv", help="save outputs to csv", action='store_true')
    parser.add_argument("--name", help="test name", default=time.strftime("%Y%m%dT%H%M%S"))

    args = parser.parse_args()
    reset = args.reset
    output = args.output
    to_csv = args.csv
    name = args.name

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
        print("starting test; Current values=")
        test.print_points()
        test.start_test(to_csv=to_csv, name=name)

