import BAC0
import json
import pandas as pd

class DeviceBacnet:
    def __init__(self, device_config):
        self.type = 'bacnet'
        self.device_config = device_config
        self.init_device(config=self.device_config)

    def init_device(self, config):
        self.network_address = config["network_address"]
        self.device_address = config["device_address"]
        self.device_id = config["device_id"]

        self.bacnet = BAC0.connect(ip=self.network_address)
        self.device = BAC0.device(address=self.device_address, device_id=self.device_id, network=self.bacnet, poll=5)
        with open('./files/'+config["point_map"], "r") as fp:
            mapping_dict = json.load(fp)

        self.mapping = pd.DataFrame(data=list(mapping_dict.keys()), index=list(mapping_dict.values()), columns=['name_in_test'])
        self.mapping.index.name = 'bacnet_name'
        self.point_properties = self.device.points_properties_df().T
        self.point_properties = pd.merge(left=self.point_properties, right=self.mapping, how='inner', left_index=True, right_index=True)
        object_list = self.point_properties.apply(lambda x: (x['type'], x['address']), axis=1).values.tolist()
        self.controller.reset_device(object_list = object_list)
        self.points = {}

    def get_point_properties(self):
        return self.point_properties

    def reset_device(self, object_list):
        self.device = BAC0.device(address=self.device_address, device_id=self.device_id, network=self.bacnet, poll=5,
                                  object_list=object_list)
        self.point_properties = self.device.points_properties_df().T

    def read_all_points(self):
        self.points = self.device.points

    def set_values(self, point_value_dict):
        for key in point_value_dict:
            try:
                self.device[key]  =point_value_dict[key]
            except:
                print("error with setting {}".format(key))

    def set_single_point(self, point_name, value):
        self.device[point_name] = value

    def get_type(self):
        return self.type

    def get_current_variable_value(self, var):
        return self.device[var].value